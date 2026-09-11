#!/usr/bin/env python3
"""Bounded, CPU-only AR171 query-prescale validation; immutable baseline/raw outputs."""
import argparse
import copy
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time

import numpy as np
import onnx
from onnx import TensorProto, helper

from prescale_ar171_queries import EMBED, external_paths, sha, stage

EXP = Path(__file__).resolve().parents[1]
MAX_DISK = 6 << 30
LIMIT = 131072


def write_json(path, obj):
    with Path(path).open('x') as stream:
        json.dump(obj, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def file_record(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def stats(array):
    flat = np.asarray(array).reshape(-1)
    finite = nan = positive_inf = negative_inf = zero = subnormal16 = 0
    maximum = None
    for start in range(0, flat.size, LIMIT):
        values = flat[start:start + LIMIT]
        valid = np.isfinite(values)
        finite += int(valid.sum())
        nan += int(np.isnan(values).sum())
        positive_inf += int(np.isposinf(values).sum())
        negative_inf += int(np.isneginf(values).sum())
        absolute = np.abs(values[valid].astype(np.float64))
        zero += int((absolute == 0).sum())
        subnormal16 += int(((absolute > 0) & (absolute < np.finfo(np.float16).tiny)).sum())
        if absolute.size:
            largest = float(absolute.max())
            maximum = largest if maximum is None else max(maximum, largest)
    return {'elements': int(flat.size), 'finite': finite, 'nan': nan,
            'positive_inf': positive_inf, 'negative_inf': negative_inf, 'zero': zero,
            'nonzero_below_fp16_min_normal': subnormal16, 'max_abs_finite': maximum}


def round16(values):
    """IEEE FP16 boundary rounding only, not a hardware-accumulation emulator."""
    with np.errstate(over='ignore', invalid='ignore', under='ignore'):
        rounded = np.asarray(values).astype(np.float16)
    raw = np.asarray(values).reshape(-1)
    half = rounded.reshape(-1)
    underflow = overflow = subnormal = 0
    for start in range(0, raw.size, LIMIT):
        a, b = raw[start:start + LIMIT], half[start:start + LIMIT]
        finite = np.isfinite(a)
        underflow += int((finite & (a != 0) & (b == 0)).sum())
        overflow += int((finite & np.isinf(b)).sum())
        absolute = np.abs(b.astype(np.float32))
        subnormal += int(((absolute > 0) & (absolute < np.finfo(np.float16).tiny)).sum())
    return rounded, {'input': stats(values), 'rounded': stats(rounded),
                     'finite_nonzero_rounded_to_zero': underflow,
                     'finite_rounded_to_infinity': overflow,
                     'rounded_subnormal_count': subnormal}


def compare(reference, candidate):
    if reference.shape != candidate.shape or reference.dtype != candidate.dtype:
        raise ValueError('Tensor shape/dtype mismatch')
    a, b = reference.reshape(-1), candidate.reshape(-1)
    maximum = relative_maximum = total = 0.0
    finite_pairs = unequal = tight_bad = historical_bad = bitwise_bad = 0
    for start in range(0, a.size, LIMIT):
        x, y = a[start:start + LIMIT], b[start:start + LIMIT]
        bitwise_bad += int(np.count_nonzero(x.view(np.uint8) != y.view(np.uint8)))
        unequal += int(np.count_nonzero(x != y))
        valid = np.isfinite(x) & np.isfinite(y)
        finite_pairs += int(valid.sum())
        xv, yv = x[valid].astype(np.float64), y[valid].astype(np.float64)
        delta = np.abs(yv - xv)
        if delta.size:
            maximum = max(maximum, float(delta.max()))
            total += float(delta.sum(dtype=np.float64))
            relative_maximum = max(relative_maximum, float((delta / np.maximum(np.abs(xv), 1e-12)).max()))
        tight_bad += int((delta > 1e-6 + 1e-5 * np.abs(xv)).sum()) + int((~valid).sum())
        historical_bad += int((delta > 0.02 + 0.02 * np.abs(xv)).sum()) + int((~valid).sum())
    return {'shape': list(reference.shape), 'dtype': str(reference.dtype), 'element_count': int(a.size),
            'reference': stats(reference), 'candidate': stats(candidate),
            'bitwise_equal': bitwise_bad == 0, 'unequal_elements': unequal,
            'finite_pair_count': finite_pairs, 'finite_pair_max_abs_delta': maximum if finite_pairs else None,
            'finite_pair_mean_abs_delta': total / finite_pairs if finite_pairs else None,
            'max_relative_delta_denominator_floor_1e_12': relative_maximum if finite_pairs else None,
            'tight_allclose': tight_bad == 0, 'tight_outside_count': tight_bad,
            'historical_allclose': historical_bad == 0, 'historical_outside_count': historical_bad}


def probe(query, key):
    q16, qstats = round16(query)
    k16, kstats = round16(key)
    # These are explicitly FP32 BLAS accumulations on FP16-rounded operands.
    post_acc = q16.astype(np.float32) @ k16.astype(np.float32)
    post_mm, post_mm_stats = round16(post_acc)
    post, post_stats = round16(post_mm.astype(np.float32) * np.float32(0.125))
    del post_acc, post_mm
    qscaled, qscaled_stats = round16(q16.astype(np.float32) * np.float32(0.125))
    pre_acc = qscaled.astype(np.float32) @ k16.astype(np.float32)
    pre, pre_stats = round16(pre_acc)
    return post, pre, {'casts': {'query_ingress': qstats, 'key_ingress': kstats,
                                'post_unscaled_matmul': post_mm_stats, 'post_score_scale': post_stats,
                                'pre_query_scale': qscaled_stats, 'pre_scaled_matmul': pre_stats},
                       'scores': compare(post, pre)}


def campaign_bytes(root):
    directories = [root]
    prior = os.environ.get('LFM_PRIOR_RUN')
    if prior:
        directories += [Path(prior), EXP / 'results/query-prescale-cpu-attempt-1-external-path-failure']
    used = sum(p.stat().st_size for directory in directories for p in directory.rglob('*')
               if p.is_file() and not p.is_symlink())
    # Launcher sidecars are outside the exclusive run directories.
    for directory in ([root, Path(prior)] if prior else [root]):
        used += sum(p.stat().st_size for p in directory.parent.glob(directory.name + '.*') if p.is_file())
    return used


def dump_arrays(directory, arrays):
    root = directory.parent
    used = campaign_bytes(root)
    predicted = sum(v.nbytes + 512 for v in arrays.values())
    if used + predicted + (64 << 20) > MAX_DISK:
        raise RuntimeError('Array write would exceed6GiB scratch budget including metadata reserve')
    directory.mkdir(exist_ok=False)
    entries = []
    for index, (name, array) in enumerate(arrays.items()):
        path = directory / f'{index:03d}.npy'
        with path.open('xb') as stream:
            np.save(stream, array, allow_pickle=False)
            stream.flush()
            os.fsync(stream.fileno())
        entries.append({'name': name, 'file': path.name, 'shape': list(array.shape),
                        'dtype': str(array.dtype), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    write_json(directory / 'manifest.json', entries)
    return entries


def load_arrays(directory):
    entries = json.loads((directory / 'manifest.json').read_text())
    arrays = {}
    for e in entries:
        path = directory / e['file']
        if sha(path) != e['sha256']:
            raise ValueError(f'Array hash mismatch {path}')
        arrays[e['name']] = np.load(path, mmap_mode='r', allow_pickle=False)
    return arrays


def guard(root):
    if shutil.disk_usage(root).free < 8 << 30:
        raise RuntimeError('Less than8GiB disk headroom')
    used = campaign_bytes(root)
    if used > MAX_DISK:
        raise RuntimeError('Exceeded6GiB scratch bound')
    group = next(line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    cgroup = Path('/sys/fs/cgroup') / group.lstrip('/')
    actual = {name: (cgroup / name).read_text().strip() for name in ('memory.max', 'memory.swap.max', 'cpu.max')}
    if actual['memory.max'] == 'max' or int(actual['memory.max']) > 12 << 30 or actual['memory.swap.max'] != '0':
        raise RuntimeError(f'Memory bounds not enforced: {actual}')
    quota, period = actual['cpu.max'].split()
    if quota == 'max' or int(quota) > 2 * int(period):
        raise RuntimeError(f'CPU bound not enforced: {actual}')
    if os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise RuntimeError('Expected nice>=10')
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        if os.environ.get(name) != '2':
            raise RuntimeError(f'Thread bound missing: {name}')
    return {'cgroup': group, 'limits': actual, 'new_disk_bytes': used,
            'nice': os.getpriority(os.PRIO_PROCESS, 0)}


def prepare(root, baseline, embedding_dir, token_file, criteria, reuse_baseline):
    original = onnx.load(baseline, load_external_data=False)
    frozen = json.loads(criteria.read_text())
    if sha(baseline) != frozen['baseline_onnx_sha256'] or sha(token_file) != frozen['token_ids_sha256']:
        raise ValueError('Baseline or canonical token identity mismatch')
    derivative = root / 'models' / 'query-prescale.onnx'
    rewrite_result = stage(baseline, derivative, copy_budget_bytes=MAX_DISK - campaign_bytes(root) - (512 << 20))
    debug = copy.deepcopy(original)
    for site in rewrite_result['changes']:
        debug.graph.output.extend([
            helper.make_tensor_value_info(site['query'], TensorProto.FLOAT, [1, 32, 171, 64]),
            helper.make_tensor_value_info(site['key'], TensorProto.FLOAT, [1, 32, 64, 4096]),
        ])
    # Adding outputs only. No baseline node/initializer mutation or graph rewriting.
    debug_path = root / 'models' / 'baseline-debug.onnx'
    onnx.save(debug, debug_path)
    onnx.checker.check_model(str(debug_path), full_check=False)
    assert [x.SerializeToString() for x in debug.graph.node] == [x.SerializeToString() for x in original.graph.node]
    ids = np.fromfile(token_file, dtype='<i4')
    if ids.shape != (171,) or (ids < 0).any() or (ids >= 128000).any():
        raise ValueError('Expected171 exact canonical IDs')
    quant = np.memmap(embedding_dir / 'embedding-quant.u8', dtype=np.uint8, mode='r', shape=(128000, 1024))[ids]
    scales = np.memmap(embedding_dir / 'embedding-scales.f32le', dtype='<f4', mode='r', shape=(128000, 64))[ids]
    zp = np.memmap(embedding_dir / 'embedding-zp.u8', dtype=np.uint8, mode='r', shape=(128000, 32))[ids]
    unpacked = np.empty((171, 2048), np.float32)
    unpacked[:, 0::2], unpacked[:, 1::2] = quant & 15, quant >> 4
    zeros = np.empty((171, 64), np.float32)
    zeros[:, 0::2], zeros[:, 1::2] = zp & 15, zp >> 4
    embeddings = ((unpacked - zeros.repeat(32, axis=1)) * scales.repeat(32, axis=1))[None, :, :]
    mask = np.full((1, 1, 171, 4096), -65504, np.float32)
    for row in range(171):
        mask[0, 0, row, 3925:3925 + row + 1] = 0
    arrays = {}
    for value in original.graph.input:
        name = value.name
        if name == EMBED:
            arrays[name] = embeddings
        elif name == 'position_ids':
            arrays[name] = np.arange(171, dtype=np.int64)[None, :]
        elif name == 'attention_mask':
            arrays[name] = mask
        elif name.startswith(('past_conv.', 'past_key_values.')):
            arrays[name] = np.zeros([d.dim_value for d in value.type.tensor_type.shape.dim], np.float32)
        else:
            raise ValueError(f'Unexpected model input {name}')
    if len(arrays) != 41 or len(original.graph.output) != 60:
        raise ValueError('Expected41 inputs/60 outputs')
    dump_arrays(root / 'inputs', arrays)
    immutable = [baseline, token_file, criteria, *external_paths(original, baseline).values()]
    immutable += [embedding_dir / name for name in ('embedding-quant.u8', 'embedding-scales.f32le', 'embedding-zp.u8')]
    immutable += [Path(__file__).resolve(), Path(__file__).with_name('prescale_ar171_queries.py').resolve()]
    amendment = EXP / 'protocol/query-prescale-storage-amendment.json'
    immutable += [amendment, *(Path(x['copy']) for x in rewrite_result['external_copies'])]
    reuse = bind_reused_baseline(root, baseline, reuse_baseline, rewrite_result)
    prepared = {'baseline': str(baseline), 'derivative': str(derivative), 'debug': str(debug_path),
                'original_outputs': [v.name for v in original.graph.output], 'rewrite': rewrite_result,
                'immutable_artifacts': [file_record(p) for p in immutable],
                'debug_artifact': file_record(debug_path), 'frozen_criteria': frozen,
                'inputs': json.loads((root / 'inputs' / 'manifest.json').read_text()),
                'resource_guard': guard(root), 'baseline_reuse': reuse,
                'storage_amendment': json.loads(amendment.read_text())}
    write_json(root / 'prepared.json', prepared)


def bind_reused_baseline(root, baseline, prior, rewrite_result):
    """Reuse only exact original graph/data/inputs/runtime/options/output bindings."""
    import onnxruntime as ort
    previous = json.loads((prior / 'prepared.json').read_text())
    amendment = json.loads((EXP / 'protocol/query-prescale-storage-amendment.json').read_text())
    for file, field in (('baseline/manifest.json', 'prior_baseline_output_manifest_sha256'),
                        ('inputs/manifest.json', 'prior_input_manifest_sha256'),
                        ('baseline-runtime.json', 'prior_baseline_runtime_sha256')):
        if sha(prior / file) != amendment[field]:
            raise ValueError(f'Frozen prior-artifact binding mismatch: {file}')
    if sha(EXP / 'protocol/query-prescale-numerical-check.json') != amendment['original_criteria_sha256']:
        raise ValueError('Original numerical criteria changed')
    if sha(root / 'models/baseline-debug.onnx') != previous['debug_artifact']['sha256']:
        raise ValueError('Storage-only amendment changed debug protobuf bytes')
    if sha(baseline) != previous['rewrite']['source_sha256'] or rewrite_result['derivative_sha256'] != previous['rewrite']['derivative_sha256']:
        raise ValueError('Storage amendment changed baseline/derivative protobuf bytes')
    if json.loads((root / 'inputs/manifest.json').read_text()) != previous['inputs']:
        raise ValueError('Freshly serialized inputs do not exactly match baseline inputs')
    load_arrays(prior / 'inputs')
    outputs = load_arrays(prior / 'baseline')
    if set(outputs) != set(previous['original_outputs']) or len(outputs) != 60:
        raise ValueError('Missing exact baseline60 output coverage')
    bindings = []
    for original in previous['immutable_artifacts']:
        if original['path'].endswith(('prescale_ar171_queries.py', 'verify_query_prescale_cpu.py')):
            continue  # The separately frozen storage-only source amendment.
        current = file_record(Path(original['path']))
        if current != original:
            raise ValueError(f'Original baseline input/data/criteria binding changed: {original["path"]}')
        bindings.append(current)
    runtime = json.loads((prior / 'baseline-runtime.json').read_text())
    expected = {'onnxruntime_version': ort.__version__, 'numpy_version': np.__version__, 'onnx_version': onnx.__version__,
                'python': sys.version, 'platform': platform.platform(), 'providers': ['CPUExecutionProvider'],
                'optimization': 'ORT_DISABLE_ALL', 'execution_mode': 'ORT_SEQUENTIAL', 'intra_op_threads': 2,
                'inter_op_threads': 1, 'cpu_arena': False, 'memory_pattern': False,
                'runtime_libraries': [file_record(p) for p in sorted((Path(ort.__file__).parent / 'capi').glob('*.so*'))]}
    for name, value in expected.items():
        if runtime[name] != value:
            raise ValueError(f'Reused baseline runtime/options mismatch: {name}')
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        if runtime['environment'][name] != os.environ[name]:
            raise ValueError(f'Reused baseline thread mismatch: {name}')
    shutil.copytree(prior / 'baseline', root / 'baseline', copy_function=shutil.copyfile)
    shutil.copyfile(prior / 'baseline-runtime.json', root / 'baseline-runtime.json')
    load_arrays(root / 'baseline')
    for name in ('prepared.json', 'baseline-runtime.json', 'baseline/manifest.json', 'inputs/manifest.json'):
        bindings.append(file_record(prior / name))
    return {'prior_run': str(prior), 'new_baseline_execution': False,
            'exact_graph_data_input_runtime_options_output_binding_passed': True,
            'bindings': bindings, 'expected_runtime_options': expected,
            'source_amendment_only': 'External-data independent copies, aggregate disk accounting, exact retained baseline reuse; worker runtime settings and numerical criteria unchanged.'}


def worker(root, variant):
    import onnxruntime as ort
    prepared = json.loads((root / 'prepared.json').read_text())
    settings = ort.SessionOptions()
    settings.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    settings.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    settings.intra_op_num_threads = 2
    settings.inter_op_num_threads = 1
    settings.enable_cpu_mem_arena = False
    settings.enable_mem_pattern = False
    settings.add_session_config_entry('session.intra_op.allow_spinning', '0')
    settings.add_session_config_entry('session.inter_op.allow_spinning', '0')
    guard(root)
    inputs = load_arrays(root / 'inputs')
    session = ort.InferenceSession(prepared[variant], settings, providers=['CPUExecutionProvider'])
    if session.get_providers() != ['CPUExecutionProvider']:
        raise RuntimeError('Not an exclusive CPU session')
    names = [v.name for v in session.get_outputs()]
    values = session.run(names, inputs)
    dump_arrays(root / variant, dict(zip(names, values)))
    write_json(root / f'{variant}-runtime.json', {
        'onnxruntime_version': ort.__version__, 'numpy_version': np.__version__, 'onnx_version': onnx.__version__,
        'python': sys.version, 'platform': platform.platform(), 'providers': session.get_providers(),
        'optimization': 'ORT_DISABLE_ALL', 'execution_mode': 'ORT_SEQUENTIAL',
        'intra_op_threads': 2, 'inter_op_threads': 1, 'cpu_arena': False, 'memory_pattern': False,
        'ru_maxrss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'runtime_libraries': [file_record(p) for p in sorted((Path(ort.__file__).parent / 'capi').glob('*.so*'))],
        'environment': {k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'TMPDIR')},
        'resource_guard': guard(root),
    })


def rankings(reference, candidate):
    names = sorted((n for n in reference if n.startswith('logits_vocab_')), key=lambda n: int(n.split('_')[2]))
    a, b = [np.concatenate([v[n].reshape(-1) for n in names]) for v in (reference, candidate)]
    if a.size != 128000:
        raise ValueError('Missing vocabulary coverage')
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        return {'available': False, 'reason': 'Nonfinite logits; raw outputs retained'}
    order_a, order_b = np.argsort(-a, kind='stable'), np.argsort(-b, kind='stable')
    rank_a, rank_b = np.empty(a.size, np.int32), np.empty(b.size, np.int32)
    rank_a[order_a], rank_b[order_b] = np.arange(a.size), np.arange(b.size)
    return {'available': True, 'reference_argmax': int(order_a[0]), 'candidate_argmax': int(order_b[0]),
            'reference_top20_ids': order_a[:20].tolist(), 'candidate_top20_ids': order_b[:20].tolist(),
            'reference_top20_scores': a[order_a[:20]].tolist(), 'candidate_top20_scores': b[order_b[:20]].tolist(),
            'top20_intersection': len(set(order_a[:20]) & set(order_b[:20])),
            'entire_vocab_rank_changed_count': int(np.count_nonzero(rank_a != rank_b)),
            'maximum_rank_displacement': int(np.abs(rank_a - rank_b).max()),
            'tie_policy': 'stable ascending vocabulary ID for equal score'}


def analyze(root):
    prepared = json.loads((root / 'prepared.json').read_text())
    baseline, candidate, debug = [load_arrays(root / v) for v in ('baseline', 'derivative', 'debug')]
    details = []
    instrument = []
    for name in prepared['original_outputs']:
        instrument.append({'name': name, **compare(baseline[name], debug[name])})
        detail = {'name': name, **compare(baseline[name], candidate[name])}
        _, detail['reference_fp16_cast'] = round16(baseline[name])
        _, detail['candidate_fp16_cast'] = round16(candidate[name])
        details.append(detail)
    write_json(root / 'instrumentation-comparison.json', instrument)
    write_json(root / 'all60-comparison.json', details)
    rank = rankings(baseline, candidate)
    write_json(root / 'logit-rankings.json', rank)
    if not all(d['bitwise_equal'] for d in instrument):
        raise RuntimeError('Debug instrumentation changed baseline outputs: no operand-equivalence inference/probes')
    proxy = []
    for index, site in enumerate(prepared['rewrite']['changes']):
        guard(root)
        post, pre, metrics = probe(debug[site['query']], debug[site['key']])
        # The initial-zero cache is masked out; report causal unmasked scores separately.
        # Full causal metrics, not a mean of per-row means.
        valid_post = np.concatenate([post[:, :, r, 3925:3926 + r].reshape(-1) for r in range(171)])
        valid_pre = np.concatenate([pre[:, :, r, 3925:3926 + r].reshape(-1) for r in range(171)])
        metrics['causal_unmasked_scores'] = compare(valid_post, valid_pre)
        metrics['site'] = site
        dump_arrays(root / f'fp16-proxy-{index:02d}', {'postscale_scores': post, 'prescale_scores': pre})
        proxy.append(metrics)
        write_json(root / f'fp16-proxy-{index:02d}.json', metrics)
        del post, pre, valid_post, valid_pre
    unchanged = []
    for before in prepared['immutable_artifacts'] + prepared['baseline_reuse']['bindings']:
        after = file_record(Path(before['path']))
        unchanged.append({'path': before['path'], 'before_sha256': before['sha256'], 'after_sha256': after['sha256'],
                          'unchanged': before == after})
    write_json(root / 'immutable-after.json', unchanged)
    if not all(x['unchanged'] for x in unchanged):
        raise RuntimeError('Immutable artifact changed during validation')
    result = {'schema_version': 1, 'classification': 'ar171_query_prescale_bounded_cpu_numerical_observation',
              'phone_access': False, 'accelerator_aot': False, 'qnn_runtime': False,
              'speedup_claim': False, 'quality_equivalence_claim': False, 'aot_authorized_by_result': False,
              'baseline_reused_without_execution': True,
              'prepared': prepared, 'commands': json.loads((root / 'commands.json').read_text()),
              'runtime': {v: json.loads((root / f'{v}-runtime.json').read_text()) for v in ('baseline', 'derivative', 'debug')},
              'tensor_count': len(details), 'state_count': sum(x['name'].startswith('present') for x in details),
              'logit_chunk_count': sum(x['name'].startswith('logits_vocab_') for x in details),
              'all60_bitwise_equal': all(x['bitwise_equal'] for x in details),
              'all60_finite': all(x['reference']['finite'] == x['element_count'] and x['candidate']['finite'] == x['element_count'] for x in details),
              'debug_all60_bitwise_equal': True, 'all60': details, 'logit_rankings': rank,
              'fp16_same_operand_proxies': proxy, 'immutable_after': unchanged, 'resource_guard': guard(root),
              'limitations': [
                  'Single canonical171-token zero-initial-state case; no carried/nonzero initial-state coverage or AR1 decode.',
                  'CPU-only Q4/FP32 ONNX runtime with optimizations disabled; no representation of actual HTP mixed precision/fusion/rounding.',
                  'FLOAT16 score probes use rounded ingress and boundary tensors but FLOAT32 NumPy/BLAS accumulation with gradual underflow; not HTP execution or an all-layer FP16 rollout.',
                  'Rounded subnormals may be flushed by some hardware; FTZ and actual HTP accumulator behavior were not measured.',
                  'No speed measurement/comparison, quality/equivalence acceptance, campaign or registry claim. New accelerator work requires review and separate authorization.',
              ]}
    write_json(root / 'result.json', result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--worker', choices=['baseline', 'derivative', 'debug', 'analyze'])
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--reuse-baseline', type=Path)
    parser.add_argument('--embedding-dir', type=Path)
    parser.add_argument('--token-file', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.worker:
        guard(root)
        analyze(root) if args.worker == 'analyze' else worker(root, args.worker)
        return
    if args.reuse_baseline is None:
        raise ValueError('Storage-only continuation requires exact retained baseline reuse, no rerun')
    prior = args.reuse_baseline.resolve(strict=True)
    if prior == root or not prior.is_relative_to(EXP / '.local'):
        raise ValueError('Expected distinct retained experiment-local prior run')
    os.environ['LFM_PRIOR_RUN'] = str(prior)
    root.mkdir(exist_ok=False)
    (root / 'tmp').mkdir()
    criteria = EXP / 'protocol/query-prescale-numerical-check.json'
    write_json(root / 'launch.json', {'argv': sys.argv, 'unit': os.environ.get('LFM_SYSTEMD_UNIT'), 'start_unix': time.time(), 'resource_guard': guard(root)})
    commands = []
    try:
        prepare(root, args.baseline.resolve(), args.embedding_dir.resolve(), args.token_file.resolve(), criteria, prior)
        # Each child has its own300s timeout. The surrounding cgroup also has1200s total.
        for variant in ('derivative', 'debug', 'analyze'):
            command = ['timeout', '--signal=TERM', '--kill-after=5s', '300s', sys.executable,
                       str(Path(__file__).resolve()), '--root', str(root), '--worker', variant]
            commands.append(command)
        write_json(root / 'commands.json', commands)
        for variant, command in zip(('derivative', 'debug', 'analyze'), commands):
            guard(root)
            with (root / f'{variant}.stdout').open('xb') as out, (root / f'{variant}.stderr').open('xb') as err:
                completed = subprocess.run(command, stdout=out, stderr=err, check=False)
            write_json(root / f'{variant}-exit.json', {'returncode': completed.returncode})
            if completed.returncode:
                raise RuntimeError(f'{variant} first outcome exit{completed.returncode}; preserved, no retry')
        # Hash every newly retained non-symlink file, including all raw arrays; never weights.
        records = [file_record(p) for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()]
        write_json(root / 'retained-files.json', records)
        print(json.dumps({'result': str(root / 'result.json'), 'resource_guard': guard(root)}))
    except Exception as error:
        write_json(root / 'failure.json', {'type': type(error).__name__, 'error': str(error), 'no_retry': True})
        raise


if __name__ == '__main__':
    main()
