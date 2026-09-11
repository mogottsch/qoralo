#!/usr/bin/env python3
"""One bounded AR171 prepare-only QNN compilation, with no graph execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time

import onnx
import onnxruntime as ort
import onnxruntime_qnn as qnn

EXP = Path(__file__).resolve().parents[1]
MODEL_SHA = 'b93c65c9c419f915bad81046f34c91c632ce6dd1bed4137751f36204d64492a0'
MEMORY_LIMIT_GIB = 12
PRIOR = [EXP / '.local/query-prescale-20260911T093452Z-73227', EXP / '.local/query-prescale-20260911T094138Z-78096',
         EXP / 'results/query-prescale-cpu-attempt-1-external-path-failure', EXP / 'results/query-prescale-cpu-attempt-2-numerical-check',
         EXP / '.local/query-prescale-aot-20260911T101011Z-109277', EXP / 'results/query-prescale-aot-attempt-1-memory-limit']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def artifact(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def byte_count(root):
    return sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink())


def bounds(root):
    current = byte_count(root)
    retained = current + sum(byte_count(p) for p in PRIOR)
    if current > (3584 << 20) or retained + (256 << 20) > 8 << 30:
        raise RuntimeError('Disk stop threshold (3.5GiB job / 8GiB aggregate with256MiB margin) reached')
    group = next(x.split(':', 2)[2] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    path = Path('/sys/fs/cgroup') / group.lstrip('/')
    limits = {x: (path / x).read_text().strip() for x in ('memory.max', 'memory.swap.max', 'cpu.max')}
    if limits != {'memory.max': str(MEMORY_LIMIT_GIB << 30), 'memory.swap.max': '0', 'cpu.max': '200000 100000'}:
        raise RuntimeError(f'Unexpected cgroup bounds: {limits}')
    if os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise RuntimeError('Expected nice10 or lower priority')
    peak = (path / 'memory.peak').read_text().strip() if (path / 'memory.peak').exists() else None
    return {'cgroup': group, 'limits': limits, 'job_bytes': current, 'aggregate_bytes': retained,
            'metadata_reserve_bytes': 256 << 20, 'memory_peak_bytes': int(peak) if peak is not None else None}


def execute(root, label, command, timeout):
    save(root / f'{label}-command.json', {'argv': command, 'timeout_seconds': timeout})
    with (root / f'{label}.stdout').open('xb') as out, (root / f'{label}.stderr').open('xb') as err:
        process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)
        start = time.monotonic()
        try:
            while process.poll() is None:
                bounds(root)
                if time.monotonic() - start > timeout:
                    raise TimeoutError(f'{label} exceeded{timeout}s')
                time.sleep(0.5)
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait()
            raise
    save(root / f'{label}-exit.json', {'returncode': process.returncode})
    if process.returncode:
        raise RuntimeError(f'{label} exited{process.returncode}; first outcome retained, no blind retry')


def abi(context):
    info = context['info']
    if info['numGraphs'] != 1:
        raise ValueError('Expected single ordinary graph')
    graph = info['graphs'][0]['info']
    result = {}
    for name in ('graphInputs', 'graphOutputs'):
        result[name] = [{k: value['info'][k] for k in ('name', 'dataType', 'dimensions', 'type', 'dataFormat')}
                        for value in graph[name]]
    return result


def inspect(root, baseline_info):
    compiled = json.loads((root / 'compiled/result.json').read_text())
    trace = json.loads((root / 'compiled/trace/qnn_op_trace.json').read_text())
    context = json.loads((root / 'context-info.json').read_text())
    original_context = json.loads(baseline_info.read_text())
    mapping = [x for graph in trace['subgraph_traces'] for x in graph['op_mappings']]
    sites = []
    for layer in (2, 5, 9, 13, 17, 21, 24, 27):
        prefix = f'/model/layers.{layer}/attn/GroupQueryAttention/htp_chunk/'
        sites.append({'layer': layer,
                      'scaled_query_mappings': [x for x in mapping if x['dst_name'].startswith(prefix + 'scaled_query') or any(s['name'] == prefix + 'scaled_query' for s in x.get('sources', []))],
                      'scaled_scores_mappings': [x for x in mapping if x['dst_name'] == prefix + 'scaled_scores' or any(s['name'] == prefix + 'scaled_scores' for s in x.get('sources', []))],
                      'score_matmul_mappings': [x for x in mapping if any(s['name'] == prefix + 'scores' for s in x.get('sources', []))]})
    current_abi, old_abi = abi(context), abi(original_context)
    summary = trace['summary']
    report = {'classification': 'ar171_query_prescale_prepare_only_aot_no_inference',
              'compiled': compiled, 'trace_summary': summary, 'target': trace['compilation_target'],
              'unsupported_nodes': trace['unsupported_nodes'], 'backend_type': trace['backend_type'],
              'context_build_id': context['info']['buildId'], 'num_graphs': context['info']['numGraphs'],
              'input_count': len(current_abi['graphInputs']), 'output_count': len(current_abi['graphOutputs']),
              'ordered_abi_identical_to_baseline': current_abi == old_abi,
              'abi': current_abi, 'scale_sites': sites,
              'source_query_shape': [1, 32, 171, 64], 'source_score_shape': [1, 32, 171, 4096],
              'trace_shape_limitation': 'Framework op mappings identify names/types, not finalized kernel tensor dimensions or cycle cost. Source shapes and mapping names do not by themselves establish final hardware schedule.',
              'graph_execution_requested': False, 'phone_access': False,
              'speedup_claim': False, 'htp_numerical_safety_claim': False,
              'metadata': artifact(root / 'context-info.json'), 'resource_final': bounds(root)}
    save(root / 'inspection.json', report)
    if not compiled.get('success') or not compiled.get('session_disable_cpu_ep_fallback') or not compiled.get('prepare_only'):
        raise ValueError('Prepare-only fallback-disabled compile not established')
    if trace['backend_type'] != 'htp' or trace['compilation_target'] != {'device_id': 0, 'htp_arch': 'V73', 'soc_model': 43}:
        raise ValueError('Wrong compilation target')
    if trace['unsupported_nodes'] or summary['unsupported_nodes'] or summary['supported_nodes'] != summary['total_onnx_nodes']:
        raise ValueError('Incomplete optimized-source delegation')
    if context['info']['buildId'] != 'v2.49.40.260810104044' or current_abi != old_abi or len(current_abi['graphInputs']) != 41 or len(current_abi['graphOutputs']) != 60:
        raise ValueError('Context build or ordered ABI changed')
    return report


def main():
    global MEMORY_LIMIT_GIB
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--qairt', type=Path, required=True)
    parser.add_argument('--memory-gib', type=int, choices=(12, 16), default=12)
    args = parser.parse_args()
    MEMORY_LIMIT_GIB = args.memory_gib
    root, model = args.root.resolve(), args.model.resolve(strict=True)
    root.mkdir(exist_ok=False); (root / 'tmp').mkdir()
    # Each generated file is additionally capped at2GiB; context is expected near1.60GB.
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 << 30, 2 << 30))
    try:
        before_bounds = bounds(root)
        mem = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
        minimum_available_gib = 22 if MEMORY_LIMIT_GIB == 16 else 16
        if mem['MemAvailable'] < minimum_available_gib * 1024 * 1024 or shutil.disk_usage(root).free < 12 << 30:
            raise RuntimeError('Unsafe host preflight memory/disk headroom')
        if os.environ.get('TMPDIR') != str(root / 'tmp'):
            raise RuntimeError('TMPDIR must be fresh disk-backed run directory')
        fs = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(root)], text=True).strip()
        if fs in ('tmpfs', 'ramfs'):
            raise RuntimeError('Scratch must not use tmpfs/ramfs')
        if sha(model) != MODEL_SHA or ort.__version__ != '1.26.0' or qnn.__version__ != '2.5.0':
            raise ValueError('Reviewed model/runtime identity mismatch')
        protobuf = onnx.load(model, load_external_data=False)
        locations = sorted({dict((e.key, e.value) for e in t.external_data)['location'] for t in protobuf.graph.initializer if t.external_data})
        data = [model.parent / location for location in locations]
        if any(p.is_symlink() or p.stat().st_nlink != 1 or p.resolve().parent != model.parent for p in data):
            raise ValueError('Input data must remain independent in-directory regular copies')
        numerical_path = EXP / 'results/query-prescale-cpu-attempt-2-numerical-check/result.json'
        if sha(numerical_path) != 'dcb851892064154930d4de48472b15811353e341f8602deebc80a450b4fa192f':
            raise ValueError('Reviewed numerical report hash changed')
        numerical = json.loads(numerical_path.read_text())
        expected_copies = {Path(x['copy']).name: x for x in numerical['prepared']['rewrite']['external_copies']}
        if numerical['prepared']['rewrite']['derivative_sha256'] != MODEL_SHA:
            raise ValueError('Saved numerical derivative binding mismatch')
        for path in data:
            expected = expected_copies[path.name]
            if path.stat().st_size != expected['bytes'] or sha(path) != expected['copy_sha256']:
                raise ValueError(f'Reviewed external data binding mismatch: {path}')
        baseline_info = EXP / '.local/qnn-prefill/ar171/compiled/context-info.json'
        utility = args.qairt.resolve() / 'bin/x86_64-linux-clang/qnn-context-binary-utility'
        sources = [model, *data, Path(__file__).resolve(), EXP / 'tools/compile_qnn_part.py', baseline_info,
                   EXP / 'protocol/query-prescale-aot-check.json',
                   EXP / 'results/query-prescale-cpu-attempt-2-numerical-check/result.json', utility]
        if MEMORY_LIMIT_GIB == 16:
            sources.append(EXP / 'protocol/query-prescale-aot-memory-amendment.json')
        libraries = sorted(Path(qnn.get_library_path()).parent.glob('*.so'))
        libraries += sorted((args.qairt.resolve() / 'lib/x86_64-linux-clang').glob('libQnnSystem.so'))
        libraries += sorted((Path(ort.__file__).parent / 'capi').glob('*.so*'))
        before = [artifact(p) for p in sources + libraries]
        save(root / 'preflight.json', {'argv': sys.argv, 'artifacts_before': before, 'bounds': before_bounds,
                                      'filesystem': fs, 'memory_available_kib': mem['MemAvailable'],
                                      'memory_limit_gib': MEMORY_LIMIT_GIB, 'minimum_available_gib': minimum_available_gib,
                                      'onnxruntime': ort.__version__, 'qnn_ep': qnn.__version__,
                                      'input_model_sha256': MODEL_SHA, 'source_nodes': len(protobuf.graph.node)})
        execute(root, 'compile', [sys.executable, str(EXP / 'tools/compile_qnn_part.py'), '--model', str(model),
                                 '--output-dir', str(root / 'compiled'), '--threads', '2'], 840)
        execute(root, 'metadata', [str(utility), '--context_binary=' + str(root / 'compiled/context_qnn.bin'),
                                  '--json_file=' + str(root / 'context-info.json')], 30)
        inspect(root, baseline_info)
        after = [artifact(Path(x['path'])) for x in before]
        save(root / 'immutable-after.json', {'all_unchanged': before == after, 'artifacts_after': after})
        if before != after:
            raise ValueError('Immutable model/data/source/library changed during AOT')
        save(root / 'outcome.json', {'outcome': 'prepare_only_aot_and_metadata_complete', 'no_graph_execution': True,
                                     'resource_final': bounds(root)})
        print(json.dumps({'outcome': 'complete', 'root': str(root), 'resource_final': bounds(root)}))
    except Exception as error:
        save(root / 'failure.json', {'type': type(error).__name__, 'error': str(error), 'no_blind_retry': True})
        raise


if __name__ == '__main__':
    main()
