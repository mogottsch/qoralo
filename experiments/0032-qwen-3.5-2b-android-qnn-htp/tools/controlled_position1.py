#!/usr/bin/env python3
"""Prepare QDQ-origin position1 inputs, or run ONE separately approved control.

prepare reads saved output tensors only. call --backend qdq and call --backend
qnn are separate supervised invocations, never an automatic two-model sequence.
The optional one-call QDQ validation establishes a reference on the SAME pack;
historical full-replay logits alone retain the deterministic-lineage assumption.
This is not own-QNN resume, autoregressive generation, or a campaign.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace

from compare_qnn_trajectory import Store, BudgetExpired, checked_artifact, load_bound_tensor, load_reference, prefix_hash
from replay_saved_qdq import EXPERIMENT, ReplayInterrupted, advance_state, artifact, interruption_signals, read_short_ids, summarize_logits

KIND = 'controlled_qdq_origin_position1_input_pack_v1'
DEFAULT_SOURCE = EXPERIMENT / 'results/host-histogram-precision-20260910'
DEFAULT_REFERENCE = EXPERIMENT / 'results/host-histogram-full-short-20260910'
DEFAULT_PREFIX = EXPERIMENT / 'results/host-qnn-trajectory-prefix-000-003-20260910'


def values_digest(tensors):
    """Hash logical tensor values, dtype and shape independently of serialization."""
    h = hashlib.sha256()
    for x in tensors:
        x = x.detach().cpu().contiguous()
        h.update(json.dumps([str(x.dtype), list(x.shape)], separators=(',', ':')).encode() + b'\n')
        h.update(x.numpy().tobytes())
    return h.hexdigest()


def input_specs(config, context):
    a, b = [], []
    for kind in config.layer_types:
        if kind == 'linear_attention':
            a.append((1, config.linear_num_value_heads, config.linear_key_head_dim, config.linear_value_head_dim))
            b.append((1, 2 * config.linear_num_key_heads * config.linear_key_head_dim + config.linear_num_value_heads * config.linear_value_head_dim, 1, config.linear_conv_kernel_dim))
        elif kind == 'full_attention':
            a.append((1, config.n_kv_heads, config.head_dim, context - 1))
            b.append((1, config.n_kv_heads, context - 1, config.head_dim))
        else:
            raise ValueError('Unknown layer kind')
    return [(1, 1), (1, 1, 1, context), (1, 1), *a, *b]


def validate_inputs(inputs, config, ids, context):
    import torch
    if config.n_layers != 24 or len(config.layer_types) != 24 or len(inputs) != 51:
        raise ValueError('Expected24-layer/51-input controlled pack')
    for i, (tensor, shape) in enumerate(zip(inputs, input_specs(config, context))):
        if tuple(tensor.shape) != shape or tensor.dtype != (torch.int32 if i in (0, 2) else torch.float32):
            raise ValueError(f'Controlled input geometry/dtype mismatch at {i}')
        if not bool(torch.isfinite(tensor).all()):
            raise ValueError('Nonfinite controlled inputs')
    if int(inputs[0].item()) != ids[1] or int(inputs[2].item()) != 1:
        raise ValueError('Control is only canonical input position1')
    mask = torch.full_like(inputs[1], -65504.0); mask[..., 0] = 0; mask[..., -1] = 0
    if not torch.equal(inputs[1], mask):
        raise ValueError('Controlled mask does not expose only prior slot0/current slot')
    for layer, kind in enumerate(config.layer_types):
        if kind == 'full_attention':
            if bool(inputs[3 + layer][..., 1:].count_nonzero()) or bool(inputs[27 + layer][:, :, 1:, :].count_nonzero()):
                raise ValueError('Unexpected occupied future KV slot')


def prepare(args):
    import torch
    from diagnose_quantized_output import make_state_templates
    store = Store(args.output_dir)
    result = {'status': 'started_not_complete', 'operation': 'saved_output_data_materialization',
              'model_or_qnn_execution_performed': False, 'state_origin': 'qdq_after_position0_not_qnn_resume'}
    try:
        store.result(result)
        source = args.source_evidence / 'artifact-manifest.json'
        manifest = json.loads(source.read_text())['files']
        params = args.artifact_root / manifest['params']['path']
        tokens = args.artifact_root / manifest['input_ids']['path']
        checked_artifact(params, manifest['params']); checked_artifact(tokens, manifest['input_ids'])
        ids = read_short_ids(tokens, 4096)
        config = SimpleNamespace(**json.loads(params.read_text()))
        command_path = args.source_evidence / 'current/02-qdq/command.json'
        command = json.loads(command_path.read_text())
        if command[command.index('--phase') + 1] != 'qdq' or '--diagnostic-hidden-states' not in command:
            raise ValueError('Source is not the retained position0 QDQ diagnostic')
        for flag, key in [('--qdq-file', 'histogram_qdq'), ('--params', 'params'), ('--token-ids', 'input_ids')]:
            # Original absolute path recorded in source command, not a new model read.
            if not command[command.index(flag) + 1].endswith(manifest[key]['path']):
                raise ValueError('Source command/artifact lineage mismatch')
        outputs = load_bound_tensor(args.artifact_root / manifest['histogram_qdq_outputs']['path'], manifest['histogram_qdq_outputs'])
        if len(outputs) != 73:
            raise ValueError('Expected73 saved QDQ outputs')
        _, refs, reference_manifest = load_reference(args, ids, manifest)
        historical = []
        for p in (0, 1):
            e = refs[p]
            historical.append(load_bound_tensor(args.artifact_root / e['raw_path'], {'bytes': e['raw_bytes'], 'sha256': e['raw_sha256']}))
        match = bool(torch.equal(outputs[0], historical[0]))
        states = make_state_templates(config, 4096)
        advance_state(config, states, outputs, 0)
        mask = torch.full((1, 1, 1, 4096), -65504.0); mask[..., 0] = 0; mask[..., -1] = 0
        inputs = [torch.tensor([[ids[1]]], dtype=torch.int32), mask, torch.tensor([[1]], dtype=torch.int32),
                  *[x.detach().cpu().contiguous().clone() for x in states]]
        validate_inputs(inputs, config, ids, 4096)
        pack = store.tensor('raw/input-pack.pt', inputs)
        old_p1 = store.tensor('raw/historical-qdq-position1.pt', historical[1])
        header = {'schema_version': 1, 'kind': KIND, 'state_origin': 'qdq_after_position0_not_qnn_resume',
                  'target_position': 1, 'target_token': ids[1], 'context': 4096,
                  'consumed_prefix_sha256': prefix_hash(ids, 1), 'input_pack': pack,
                  'input_values_sha256': values_digest(inputs),
                  'tensor_specs': [{'shape': list(x.shape), 'dtype': str(x.dtype)} for x in inputs],
                  'source_qdq_outputs': manifest['histogram_qdq_outputs'],
                  'source_evidence_manifest': artifact(source), 'origin_command': artifact(command_path),
                  'models': {k: manifest[k] for k in ('histogram_pte', 'histogram_qdq', 'params', 'input_ids')},
                  'historical_qdq_position1': old_p1, 'historical_reference_manifest': reference_manifest,
                  'lineage': {'source_position': 0, 'source_token': ids[0], 'initial_state': 'all zero',
                              'source_mask': 'only current-token final slot visible',
                              'position0_logits_bit_identical_to_full_replay': match,
                              'full_replay_state_bytes_retained': False,
                              'assumption': 'Same artifact/input/reset lineage and deterministic source are assumed; matching logits do not prove missing full-replay state bytes equal.'},
                  'exact_attribution_gate': 'For an exact paired comparison, first run optionalONE QDQposition1 call on THIS pack and use its bound result for a separately released QNNposition1 call.'}
        result.update(status='materialized_data_only', header=store.json_file('pack-header.json', header),
                      input_pack=pack, input_values_sha256=header['input_values_sha256'], lineage=header['lineage'])
        store.result(result)
        return result
    except BaseException as e:
        result.update(status='error', error={'type': type(e).__name__, 'message': str(e)})
        store.result(result); raise


def verify_materialization(header_path, header_sha256, artifact_root):
    """Check copied state values directly against saved outputs, without a model."""
    import torch
    if artifact(header_path)['sha256'] != header_sha256:
        raise ValueError('Pack header digest mismatch')
    h = json.loads(header_path.read_text())
    if h['kind'] != KIND or h['state_origin'] != 'qdq_after_position0_not_qnn_resume':
        raise ValueError('Not a QDQ-origin control pack')
    params = artifact_root / h['models']['params']['path']
    tokens = artifact_root / h['models']['input_ids']['path']
    checked_artifact(params,h['models']['params']); checked_artifact(tokens,h['models']['input_ids'])
    ids = read_short_ids(tokens,h['context'])
    config = SimpleNamespace(**json.loads(params.read_text()))
    inputs = load_bound_tensor(Path(h['input_pack']['path']),h['input_pack'])
    source = load_bound_tensor(artifact_root / h['source_qdq_outputs']['path'],h['source_qdq_outputs'])
    validate_inputs(inputs,config,ids,h['context'])
    if values_digest(inputs) != h['input_values_sha256']:
        raise ValueError('Input logical-value digest mismatch')
    for layer,kind in enumerate(config.layer_types):
        a,b = inputs[3+layer],inputs[27+layer]
        expected_a,expected_b = source[1+layer],source[25+layer]
        if kind == 'linear_attention':
            if not torch.equal(a,expected_a) or not torch.equal(b,expected_b):
                raise ValueError('Copied recurrent/convolution state differs from source')
        else:
            if not torch.equal(a[...,0],expected_a[...,0]) or not torch.equal(b[:,:,0,:],expected_b[:,:,0,:]):
                raise ValueError('Inserted KV slot0 differs from source')
    return {'state_tensors_checked':48,'input_tensors_checked':51,'state_materialization_matches_saved_outputs':True,
            'input_values_sha256':h['input_values_sha256'],'model_or_qnn_execution_performed':False,
            'full_replay_state_byte_equality_proved':False}


def metrics(reference, actual):
    import torch
    if reference.shape != actual.shape or not bool(torch.isfinite(reference).all() and torch.isfinite(actual).all()):
        raise ValueError('Invalid reference/actual logits')
    a, b = reference.float().reshape(-1), actual.float().reshape(-1)
    return {'cosine': float(torch.nn.functional.cosine_similarity(a, b, dim=0)),
            'max_abs': float((a-b).abs().max()), 'mean_abs': float((a-b).abs().mean()),
            'reference_argmax': int(a.argmax()), 'actual_argmax': int(b.argmax())}


def difference_vectors(own_qnn, controlled_qnn, paired_qdq, historical_qdq):
    """Vector identity only. Cosines/error norms are NOT added."""
    current = controlled_qnn - paired_qdq
    feedback = own_qnn - controlled_qnn
    reference_shift = paired_qdq - historical_qdq
    observed = own_qnn - historical_qdq
    return {'current_call': current, 'qnn_state_effect': feedback,
            'historical_reference_shift': reference_shift, 'observed_own_trajectory_difference': observed,
            'rounding_residual': current + feedback + reference_shift - observed}


def load_backend(backend, path, params, context):
    if backend == 'qdq':
        from replay_saved_qdq import load_runtime
        return load_runtime(params, path, context)
    from compare_qnn_trajectory import load_runtime
    return load_runtime(path, params, context)


def read_paired_reference(args, header, inputs_hash):
    if args.qdq_control_result is None:
        if args.qdq_control_sha256 is not None:
            raise ValueError('Paired digest without a QDQ control result')
        return None, None
    if args.backend != 'qnn' or artifact(args.qdq_control_result)['sha256'] != args.qdq_control_sha256:
        raise ValueError('Paired control result digest/backend mismatch')
    r = json.loads(args.qdq_control_result.read_text())
    if (r['status'] != 'completed_single_call' or r['backend'] != 'qdq'
            or r['graph_calls_returned'] != 1 or r['target_position'] != 1
            or r['pack_header']['sha256'] != args.pack_header_sha256
            or r['submitted_input_values_sha256'] != inputs_hash
            or r['input_mutation_observed']
            or r['model_artifact']['sha256'] != header['models']['histogram_qdq']['sha256']):
        raise ValueError('QDQ control is not a completed call on the identical pack')
    outputs = load_bound_tensor(Path(r['raw_outputs']['path']), r['raw_outputs'])
    if len(outputs) != 73:
        raise ValueError('Wrong paired QDQ output ABI')
    return outputs[0], artifact(args.qdq_control_result)


def run_control(args, runtime_loader=None, clock=time.monotonic):
    if args.backend not in ('qdq', 'qnn') or not math.isfinite(args.timeout_seconds) or not 0 < args.timeout_seconds <= 7200:
        raise ValueError('Explicit backend and finite (0,7200] timeout required')
    store = Store(args.output_dir)
    started = clock()
    result = {'schema_version': 1, 'evidence_class': 'host_controlled_qdq_origin_position1_single_call',
              'status': 'started_not_complete', 'phase': 'preflight', 'backend': args.backend,
              'target_position': 1, 'graph_calls_returned': 0, 'maximum_forward_calls': 1,
              'state_origin': 'qdq_after_position0_not_qnn_resume', 'resume': False,
              'automatic_follow_on': False, 'physical_execution': False,
              'exact_same_pack_qdq_reference_used': False, 'input_mutation_observed': None,
              'timeout_seconds': args.timeout_seconds}
    def budget():
        if clock() - started >= args.timeout_seconds:
            raise BudgetExpired('Single-call host budget exhausted')
    try:
        store.result(result)
        if artifact(args.pack_header)['sha256'] != args.pack_header_sha256:
            raise ValueError('Reviewed pack-header digest mismatch')
        header = json.loads(args.pack_header.read_text())
        if header['kind'] != KIND or header['state_origin'] != 'qdq_after_position0_not_qnn_resume' or header['target_position'] != 1:
            raise ValueError('Not a QDQ-origin position1 input pack; own-state resume is forbidden')
        params = args.artifact_root / header['models']['params']['path']
        tokens = args.artifact_root / header['models']['input_ids']['path']
        checked_artifact(params, header['models']['params']); checked_artifact(tokens, header['models']['input_ids'])
        ids = read_short_ids(tokens, header['context'])
        if header['target_token'] != ids[1] or header['consumed_prefix_sha256'] != prefix_hash(ids,1):
            raise ValueError('Target token/prefix mismatch')
        inputs = load_bound_tensor(Path(header['input_pack']['path']), header['input_pack'])
        config = SimpleNamespace(**json.loads(params.read_text()))
        validate_inputs(inputs, config, ids, header['context'])
        digest = values_digest(inputs)
        if digest != header['input_values_sha256']:
            raise ValueError('Input values do not match the reviewed materialization')
        result.update(pack_header=artifact(args.pack_header), input_pack=header['input_pack'],
                      submitted_input_values_sha256=digest, lineage=header['lineage'])
        historical = load_bound_tensor(Path(header['historical_qdq_position1']['path']), header['historical_qdq_position1'])
        paired, paired_record = read_paired_reference(args, header, digest)
        result['paired_qdq_control'] = paired_record
        result['exact_same_pack_qdq_reference_used'] = paired_record is not None
        key = 'histogram_qdq' if args.backend == 'qdq' else 'histogram_pte'
        model_path = args.artifact_root / header['models'][key]['path']
        result['model_artifact'] = checked_artifact(model_path, header['models'][key])
        budget(); result['phase'] = 'load'; store.result(result)
        runtime, loaded_config = (runtime_loader or load_backend)(args.backend, model_path, params, header['context'])
        budget(); result['phase'] = 'call'; store.result(result)
        import torch
        before = values_digest(inputs)
        if before != digest:
            raise ValueError('Input changed before the controlled call')
        with torch.no_grad():
            outputs = runtime(*inputs) if args.backend == 'qdq' else runtime.forward(inputs)
        outputs = [x.detach().cpu().clone() for x in outputs]
        result['raw_outputs'] = store.tensor('raw/position-001.outputs.pt', outputs)
        result['graph_calls_returned'] = 1
        result['input_mutation_observed'] = values_digest(inputs) != before
        store.result(result)
        if len(outputs) != 73 or tuple(outputs[0].shape) != (1,1,loaded_config.vocab_size):
            raise ValueError('Controlled output ABI mismatch; raw outputs retained')
        if result['input_mutation_observed']:
            raise ValueError('Backend mutated controlled inputs; raw outputs retained')
        result['logits'] = summarize_logits(outputs[0])
        if not result['logits']['finite']:
            raise ValueError('Nonfinite controlled output; raw outputs retained')
        budget(); result['phase'] = 'compare'
        result['historical_qdq_comparison'] = metrics(historical, outputs[0])
        result['historical_qdq_logits_bit_identical'] = bool(torch.equal(historical, outputs[0]))
        if paired is not None:
            result['same_pack_qdq_comparison'] = metrics(paired, outputs[0])
        result['interpretation'] = ('Same input-values digest for separately evaluated QDQ and QNN calls.' if paired is not None else
                                    'Historical comparison retains lineage assumption; exact same-state attribution is not established.')
        result['status'] = 'completed_single_call'
    except BaseException as e:
        result['status'] = 'timeout' if isinstance(e,BudgetExpired) else 'interrupted' if isinstance(e,(ReplayInterrupted,KeyboardInterrupt)) else 'error'
        result['error'] = {'type':type(e).__name__, 'message':str(e), 'traceback':traceback.format_exc()}
        result['elapsed_seconds'] = clock()-started; store.result(result); raise
    result['elapsed_seconds'] = clock()-started
    result['claim_limits'] = ['ExactlyONE position1 host call on explicit QDQ-origin inputs; not resume or generation.',
                              'No full-trajectory/accuracy/physical/campaign claim. Difference-vector interpretation is conditional on fixed artifact/runtime identities; scalar cosines are not additive.']
    store.result(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='operation', required=True)
    prep = modes.add_parser('prepare', help='Saved-tensor data materialization only; no model call')
    prep.add_argument('--source-evidence', type=Path, default=DEFAULT_SOURCE)
    prep.add_argument('--reference-directory', type=Path, default=DEFAULT_REFERENCE)
    prep.add_argument('--artifact-root', type=Path, default=EXPERIMENT)
    prep.add_argument('--output-dir', type=Path, required=True)
    verify = modes.add_parser('verify', help='Verify saved tensor materialization only; no model')
    verify.add_argument('--pack-header',type=Path,required=True)
    verify.add_argument('--pack-header-sha256',required=True)
    verify.add_argument('--artifact-root',type=Path,default=EXPERIMENT)
    call = modes.add_parser('call', help='ONE separately authorized supervised backend call')
    call.add_argument('--backend', choices=('qdq','qnn'), required=True)
    call.add_argument('--pack-header', type=Path, required=True)
    call.add_argument('--pack-header-sha256', required=True)
    call.add_argument('--artifact-root', type=Path, default=EXPERIMENT)
    call.add_argument('--output-dir', type=Path, required=True)
    call.add_argument('--timeout-seconds', type=float, required=True)
    call.add_argument('--qdq-control-result', type=Path)
    call.add_argument('--qdq-control-sha256')
    call.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.operation == 'prepare':
        print(json.dumps(prepare(args), indent=2)); return
    if args.operation == 'verify':
        print(json.dumps(verify_materialization(args.pack_header,args.pack_header_sha256,args.artifact_root),indent=2)); return
    if not math.isfinite(args.timeout_seconds) or not 0 < args.timeout_seconds <= 7200:
        raise ValueError('Finite (0,7200] timeout required')
    if args.worker:
        if os.environ.get('QWEN_CONTROL_SUPERVISED') != 'yes': raise RuntimeError('Internal worker requires supervisor')
        with interruption_signals(): run_control(args)
        return
    from qwen_host_guard import supervise
    root = args.output_dir.resolve(); root.mkdir(parents=True, exist_ok=False)
    scratch = root/'scratch'; scratch.mkdir()
    if subprocess.check_output(['stat','-f','-c','%T',str(scratch)],text=True).strip() in ('tmpfs','ramfs'):
        raise ValueError('Disk-backed owned scratch required')
    args.output_dir = root/'control'
    command = ['nice','-n','15','ionice','-c','2','-n','7',sys.executable,str(Path(__file__).resolve()),'call','--worker']
    for name,value in vars(args).items():
        if name not in ('operation','worker') and value is not None: command.extend(['--'+name.replace('_','-'),str(value)])
    env=dict(os.environ,TMPDIR=str(scratch),TMP=str(scratch),TEMP=str(scratch),OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',QWEN_CONTROL_SUPERVISED='yes',PYTHONUNBUFFERED='1')
    (root/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    result=supervise(command,root,args.timeout_seconds,env=env)
    print(json.dumps(result)); raise SystemExit(0 if result['exit_code']==0 and result['reason']=='process_exit' else 1)


if __name__ == '__main__': main()
