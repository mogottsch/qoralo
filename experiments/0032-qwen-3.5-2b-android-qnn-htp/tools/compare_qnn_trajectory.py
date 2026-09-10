#!/usr/bin/env python3
"""Bounded host QNN-x86 own-state trajectory comparison (source-only readiness).

73 outputs = logits + 48 state outputs + 24 hidden diagnostics. Only QNN's own
48 state outputs feed the next call; saved QDQ tensors are comparison targets,
never state inputs. Each invocation needs reviewed position/time limits and a
fresh disk-backed output directory. Explicit checkpoint continuation is a new
host diagnostic segment, NOT loaded-route benchmark reuse or an automatic retry.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import traceback

from replay_saved_qdq import (
    EXPERIMENT, ReplayInterrupted, _atomic_write, advance_state, artifact,
    interruption_signals, read_short_ids, summarize_logits,
)

DEFAULT_MANIFEST = EXPERIMENT / 'results/host-histogram-precision-20260910/artifact-manifest.json'
DEFAULT_REFERENCE = EXPERIMENT / 'results/host-histogram-full-short-20260910'


class BudgetExpired(Exception):
    pass


def budget_plan(max_positions, timeout):
    if not 1 <= max_positions <= 174 or not math.isfinite(timeout) or not 0 < timeout <= 7200:
        raise ValueError('Require 1..174 positions and an explicit finite host timeout in (0,7200] seconds')
    estimated = 60 + 120 * max_positions
    return {'max_positions_this_segment': max_positions, 'timeout_seconds': timeout,
            'estimated_seconds': estimated, 'estimate_exceeds_budget': estimated > timeout,
            'estimate_basis': 'Roughly one hour per30 QNN-x86 inputs previously observed, plus60s preparation allowance; estimate only, not a validity gate.'}


class Store:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=False)
        (directory / 'raw').mkdir()
        (directory / 'checkpoints').mkdir()
        self.result_path = directory / 'result.json'
        self.progress = directory / 'progress.jsonl'
        self.result_path.touch(exist_ok=False)
        self.progress.touch(exist_ok=False)

    def result(self, result):
        content = (json.dumps(result, indent=2, allow_nan=False) + '\n').encode()
        _atomic_write(self.result_path, lambda f: f.write(content))

    def tensor(self, relative, value):
        import torch
        path = self.directory / relative
        with path.open('xb'):
            pass
        _atomic_write(path, lambda f: torch.save(value, f))
        return artifact(path)

    def json_file(self, relative, value):
        path = self.directory / relative
        with path.open('xb'):
            pass
        content = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
        _atomic_write(path, lambda f: f.write(content))
        return artifact(path)

    def append(self, record):
        with self.progress.open('a') as f:
            f.write(json.dumps(record, allow_nan=False) + '\n'); f.flush(); os.fsync(f.fileno())


def checked_artifact(path, expected):
    actual = artifact(path)
    if (actual['bytes'], actual['sha256']) != (expected['bytes'], expected['sha256']):
        raise ValueError(f'Artifact bytes/hash mismatch: {path}')
    return actual


def load_bound_tensor(path, expected):
    import torch
    data = path.read_bytes()
    if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
        raise ValueError(f'Tensor changed after preflight: {path}')
    return torch.load(io.BytesIO(data), map_location='cpu', weights_only=True)


def prefix_hash(ids, next_position):
    return hashlib.sha256(struct.pack(f'<{next_position}i', *ids[:next_position])).hexdigest()


def load_runtime(pte, params, context):
    # No imports/loads on --help or during injected synthetic tests.
    from executorch.extension.llm.custom_ops import custom_ops  # noqa: F401
    from executorch.extension.pybindings.portable_lib import _load_for_executorch
    from executorch.examples.models.llama.model_args import ModelArgs
    from diagnose_quantized_output import make_state_templates
    config = ModelArgs(max_seq_len=context, max_context_len=context, max_batch_size=1,
                       use_kv_cache=True, **json.loads(params.read_text()))
    if config.n_layers != 24:
        raise ValueError('Expected exact24-layer Qwen geometry')
    module = _load_for_executorch(str(pte))
    meta = module.method_meta('forward')
    if meta.num_inputs() != 51 or meta.num_outputs() != 73:
        raise ValueError('Expected51 inputs/73 diagnostic outputs')
    shapes = [(1, 1), (1, 1, 1, context), (1, 1)] + [tuple(x.shape) for x in make_state_templates(config, context)]
    for i, shape in enumerate(shapes):
        info = meta.input_tensor_meta(i)
        if tuple(info.sizes()) != shape or info.dtype() != (3 if i in (0, 2) else 6):
            raise ValueError(f'Input ABI mismatch at {i}')
    return module, config


def load_reference(args, ids, manifest):
    report = json.loads((args.reference_directory / 'raw/result.json').read_text())
    if report['status'] != 'completed' or report['evaluated_tokens'] != 174 or report['state_updates_completed'] != 174:
        raise ValueError('Reference must be completed174-position QDQ replay')
    for name, key in [('qdq_file', 'histogram_qdq'), ('params', 'params'), ('token_ids', 'input_ids')]:
        if report['input_artifacts'][name]['sha256'] != manifest[key]['sha256']:
            raise ValueError('QDQ reference is from a different artifact/input route')
    journal = args.reference_directory / 'raw/progress.jsonl'
    checked_artifact(journal, report['progress_artifact'])
    rows = [json.loads(s) for s in journal.read_text().splitlines()]
    if len(rows) != 174 or any(row['position'] != i or row['input_token'] != ids[i] for i, row in enumerate(rows)):
        raise ValueError('Reference position/token sequence mismatch')
    ref_manifest = args.reference_directory / 'compression-manifest.json'
    entries = [e for e in json.loads(ref_manifest.read_text())['files'] if 'position' in e]
    if len(entries) != 174 or {e['position'] for e in entries} != set(range(174)):
        raise ValueError('Reference tensor manifest must cover all174 distinct positions')
    entries = {e['position']: e for e in entries}
    for i, row in enumerate(rows):
        if (row['artifact']['sha256'], row['artifact']['bytes']) != (entries[i]['raw_sha256'], entries[i]['raw_bytes']):
            raise ValueError('Reference journal/tensor binding mismatch')
    return rows, entries, artifact(ref_manifest)


def reference_path(args, entry):
    path = (args.reference_root / entry['raw_path']).resolve()
    if not path.is_relative_to(args.reference_root.resolve()):
        raise ValueError('Reference tensor path escapes the configured local retrieval root')
    return path


def comparison(reference, actual):
    import torch
    if reference.shape != actual.shape:
        raise ValueError('Reference/QNN logit geometry mismatch')
    a, b = reference.float().reshape(-1), actual.float().reshape(-1)
    if not bool(torch.isfinite(a).all()) or not bool(torch.isfinite(b).all()):
        raise ValueError('Nonfinite comparison input; raw QNN outputs retained')
    return {'cosine': float(torch.nn.functional.cosine_similarity(a, b, dim=0)),
            'max_abs': float((a - b).abs().max()), 'mean_abs': float((a - b).abs().mean()),
            'qdq_argmax': int(a.argmax()), 'qnn_argmax': int(b.argmax())}


def resume_header(args, binding, ids):
    if args.resume_checkpoint is None:
        if args.resume_sha256 is not None:
            raise ValueError('Resume digest without a checkpoint')
        return None, 0
    if not args.resume_sha256 or artifact(args.resume_checkpoint)['sha256'] != args.resume_sha256:
        raise ValueError('Checkpoint metadata SHA-256 mismatch or missing digest')
    header = json.loads(args.resume_checkpoint.read_text())
    if header['binding'] != binding or header['backend_state'] != 'qnn_x86_own_propagated_state':
        raise ValueError('Checkpoint route/state-origin binding mismatch')
    next_pos = header['next_position']
    if not isinstance(next_pos, int) or not 0 <= next_pos < 174 or header['consumed_prefix_sha256'] != prefix_hash(ids, next_pos):
        raise ValueError('Checkpoint consumed-prefix/position mismatch')
    checked_artifact(Path(header['state_artifact']['path']), header['state_artifact'])
    return header, next_pos


def run_trajectory(args, runtime_loader=None, clock=time.monotonic):
    plan = budget_plan(args.max_positions, args.timeout_seconds)
    store = Store(args.output_dir)
    start_time = clock()
    result = {'schema_version': 1, 'evidence_class': 'host_qnn_x86_own_state_teacher_forced_trajectory',
              'status': 'started_not_complete', 'phase': 'preflight', 'budget': plan,
              'graph_calls_returned': 0, 'state_updates_completed': 0, 'comparisons_completed': 0,
              'latest_checkpoint': None, 'latest_raw_outputs': None, 'physical_execution': False,
              'full174_in_this_process': False,
              'loaded_route_benchmark_reuse_claimed': False, 'automatic_retry': False,
              'comparison_boundary': 'Same input prefix and initially zero state; each backend carries its OWN evolved state. Accumulated trajectory drift, NOT same-state operator comparison.',
              'claim_limits': ['Host simulation only; no physical QNN/HTP or generated-text/campaign claim.',
                               'Explicit checkpoint continuation reloads the runtime in a new diagnostic segment, not a loaded-route benchmark.',
                               'Worker checks time cooperatively; the CLI supervisor enforces an independent wall deadline through TERM/bounded grace/KILL/reap.']}

    def check_budget():
        if clock() - start_time >= args.timeout_seconds:
            raise BudgetExpired('Explicit host runtime budget exhausted')

    try:
        store.result(result)
        ids = read_short_ids(args.token_ids, args.context)
        manifest = json.loads(args.artifact_manifest.read_text())['files']
        result['artifact_manifest'] = artifact(args.artifact_manifest)
        result['input_artifacts'] = {name: checked_artifact(getattr(args, name), manifest[key])
                                     for name, key in [('pte', 'histogram_pte'), ('params', 'params'), ('token_ids', 'input_ids')]}
        rows, entries, reference_manifest = load_reference(args, ids, manifest)
        binding = {'pte_sha256': manifest['histogram_pte']['sha256'], 'params_sha256': manifest['params']['sha256'],
                   'token_ids_sha256': manifest['input_ids']['sha256'], 'reference_manifest_sha256': reference_manifest['sha256'],
                   'qdq_sha256': manifest['histogram_qdq']['sha256'], 'context': args.context, 'state_abi': 1,
                   'driver_sha256': artifact(Path(__file__))['sha256'],
                   'state_transport_sha256': artifact(EXPERIMENT / 'tools/replay_saved_qdq.py')['sha256']}
        result['binding'] = binding
        header, begin = resume_header(args, binding, ids)
        end = begin + args.max_positions
        if end > 174:
            raise ValueError('Requested segment exceeds the174-token reference; no silent truncation')
        result.update(start_position=begin, end_position_exclusive=end,
                      state_origin='zero_initialization' if header is None else 'explicit_qnn_checkpoint',
                      resumed_from=None if header is None else artifact(args.resume_checkpoint))
        # Missing/corrupt LOCAL-ONLY target bytes are detected BEFORE loading QNN.
        for position in range(begin, end):
            check_budget()
            entry = entries[position]
            checked_artifact(reference_path(args, entry), {'sha256': entry['raw_sha256'], 'bytes': entry['raw_bytes']})
        check_budget()
        result['phase'] = 'load'
        store.result(result)
        runtime, config = (runtime_loader or load_runtime)(args.pte, args.params, args.context)
        import torch
        from diagnose_quantized_output import make_state_templates
        if config.n_layers != 24 or len(config.layer_types) != 24:
            raise ValueError('Expected24 layers and48 state tensors')
        states = make_state_templates(config, args.context)
        if header is not None:
            restored = load_bound_tensor(Path(header['state_artifact']['path']), header['state_artifact'])
            if len(restored) != len(states) or any(x.shape != y.shape or x.dtype != y.dtype for x, y in zip(restored, states)):
                raise ValueError('Checkpoint tensor count/shape/dtype mismatch')
            states = [x.detach().clone() for x in restored]
        result['phase'] = 'trajectory'
        store.result(result)
        with torch.no_grad():
            for position in range(begin, end):
                check_budget()
                result['current_position'] = position
                mask = torch.full((1, 1, 1, args.context), -65504.0)
                mask[..., :position] = 0; mask[..., -1] = 0
                outputs = runtime.forward([torch.tensor([[ids[position]]], dtype=torch.int32), mask,
                                           torch.tensor([[position]], dtype=torch.int32), *states])
                outputs = [x.detach().cpu().clone() for x in outputs]
                result['latest_raw_outputs'] = store.tensor(f'raw/position-{position:03d}.pt', outputs)
                result['graph_calls_returned'] += 1
                store.result(result)
                if len(outputs) != 73:
                    raise ValueError('Expected73 outputs: logits +48 state +24 hidden diagnostics')
                if tuple(outputs[0].shape) != (1, 1, config.vocab_size):
                    raise ValueError('QNN output logit geometry mismatch')
                summary = summarize_logits(outputs[0])
                if not summary['finite']:
                    raise ValueError('Nonfinite QNN logits; raw outputs retained')
                # No silent dtype conversion at a quantized/float state boundary.
                for i, current in enumerate(states):
                    if outputs[1 + i].dtype != current.dtype:
                        raise ValueError('State output dtype mismatch')
                advance_state(config, states, outputs, position)
                state_artifact = store.tensor(f'checkpoints/position-{position:03d}.states.pt', [x.clone() for x in states])
                checkpoint = {'schema_version': 1, 'binding': binding,
                              'backend_state': 'qnn_x86_own_propagated_state', 'next_position': position + 1,
                              'consumed_prefix_sha256': prefix_hash(ids, position + 1),
                              'state_artifact': state_artifact, 'prior_segment_checkpoint': result['resumed_from']}
                result['latest_checkpoint'] = store.json_file(f'checkpoints/position-{position:03d}.json', checkpoint)
                result['state_updates_completed'] += 1
                record = {'position': position, 'input_token': ids[position], 'qnn_logits': summary,
                          'raw_outputs': result['latest_raw_outputs'], 'checkpoint': result['latest_checkpoint'],
                          'comparison': None}
                # A pending journal row keeps model work even if comparison fails.
                store.append({'event': 'state_committed', **record})
                store.result(result)
                check_budget()
                result['phase'] = 'compare'
                reference = load_bound_tensor(reference_path(args, entries[position]),
                                              {'bytes': entries[position]['raw_bytes'], 'sha256': entries[position]['raw_sha256']})
                record['comparison'] = comparison(reference, outputs[0])
                if record['comparison']['qdq_argmax'] != rows[position]['logits']['argmax']:
                    raise ValueError('Reference tensor/summary mismatch')
                store.append({'event': 'compared', **record})
                result['comparisons_completed'] += 1
                result['phase'] = 'trajectory'
                store.result(result)
                print(json.dumps({'position': position, **record['comparison']}), flush=True)
        check_budget()
        result['status'] = 'bounded_segment_completed'
        result['full174_in_this_process'] = begin == 0 and end == 174
    except BaseException as error:
        result['status'] = ('timeout' if isinstance(error, BudgetExpired) else
                            'interrupted' if isinstance(error, (ReplayInterrupted, KeyboardInterrupt)) else 'error')
        result['error'] = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
        result['elapsed_seconds'] = clock() - start_time
        result['progress_artifact'] = artifact(store.progress)
        store.result(result)
        raise
    result['elapsed_seconds'] = clock() - start_time
    result['progress_artifact'] = artifact(store.progress)
    store.result(result)
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('pte', 'params', 'token-ids', 'output-dir'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--artifact-manifest', type=Path, default=DEFAULT_MANIFEST)
    p.add_argument('--reference-directory', type=Path, default=DEFAULT_REFERENCE)
    p.add_argument('--reference-root', type=Path, default=EXPERIMENT)
    p.add_argument('--context', type=int, default=4096)
    p.add_argument('--max-positions', type=int, required=True)
    p.add_argument('--timeout-seconds', type=float, required=True)
    p.add_argument('--resume-checkpoint', type=Path)
    p.add_argument('--resume-sha256')
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    return p


def main():
    args = parser().parse_args()
    budget_plan(args.max_positions, args.timeout_seconds)
    if args.worker:
        if os.environ.get('QWEN_TRAJECTORY_SUPERVISED') != 'yes':
            raise RuntimeError('Worker requires the independent CLI supervisor')
        with interruption_signals():
            run_trajectory(args)
        return
    from qwen_host_guard import supervise
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    scratch = root / 'scratch'; scratch.mkdir()
    fs_type = subprocess.check_output(['stat', '-f', '-c', '%T', str(scratch)], text=True).strip()
    if fs_type in ('tmpfs', 'ramfs'):
        raise ValueError('Use disk-backed owned output/scratch, not tmpfs/ramfs')
    worker = [sys.executable, str(Path(__file__).resolve()), '--worker']
    args.output_dir = root / 'trajectory'
    for name, value in vars(args).items():
        if name != 'worker' and value is not None:
            worker.extend(['--' + name.replace('_', '-'), str(value)])
    command = ['nice', '-n', '15', 'ionice', '-c', '2', '-n', '7', *worker]
    env = dict(os.environ, TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch),
               OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4',
               QWEN_TRAJECTORY_SUPERVISED='yes', PYTHONUNBUFFERED='1')
    (root / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    result = supervise(command, root, args.timeout_seconds, env=env)
    print(json.dumps(result), flush=True)
    raise SystemExit(0 if result['exit_code'] == 0 and result['reason'] == 'process_exit' else 1)


if __name__ == '__main__':
    main()
