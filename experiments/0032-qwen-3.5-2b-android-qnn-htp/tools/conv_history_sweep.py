#!/usr/bin/env python3
"""Source/CPU-only range sweep preparation; no compiler/runtime execution CLI."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct
import sys

import conv_history_probe as probe
from audit_conv_history_metadata import fp32, scalar_qdq

EXP = Path(__file__).resolve().parents[1]
FIRST = EXP / 'results/conv-history-native-fullchain-20260910'
FIRST_MANIFEST_SHA = '2ba77a5c20d6f75806c7904cb951b4767b9bb405281d309e2f40a1d2aa3d8222'
PTE_SHA = '0170b6a2ae96759b36722f05daf8d0925f14b4da57968806b6602008c05d69c3'
PTE_BYTES = 232144
REQUEST_SHA = 'f9ef7075427df9a4cf8c4e565f9c261c4065380384ec35a7a1dbba9865b8548e'


def identity(path):
    path = Path(path)
    return {'path': str(path.absolute()), 'bytes': path.stat().st_size,
            'sha256': probe.digest(path.read_bytes())}


def adjacent(value, direction):
    """One finite binary32 neighbor, not Python's binary64 nextafter."""
    value = fp32(value)
    if not math.isfinite(value) or direction not in (-1, 1):
        raise ValueError('Need a finite FP32 value and signed direction')
    if value == 0:
        return struct.unpack('<f', struct.pack('<I', 1 if direction > 0 else 0x80000001))[0]
    bits = struct.unpack('<I', struct.pack('<f', value))[0]
    bits += 1 if (value > 0) == (direction > 0) else -1
    result = struct.unpack('<f', struct.pack('<I', bits))[0]
    if not math.isfinite(result):
        raise ValueError('Neighbor would be nonfinite')
    return result


def clipping_onset(nominal, direction, encoding):
    """Find the first actually clipped FP32 value around a half-step estimate."""
    value = fp32(nominal)
    for _ in range(1024):
        inward = adjacent(value, -direction)
        clipped = scalar_qdq(value, encoding)['clipped']
        if clipped and not scalar_qdq(inward, encoding)['clipped']:
            return value
        value = inward if clipped else adjacent(value, direction)
    raise ValueError('Could not bracket the scalar clipping onset')


def sample_values():
    stages = probe.case_spec('fullchain')['stages']
    h, out = stages['history'], stages['output']
    bounds = scalar_qdq(0, h)
    low, high = bounds['representable_min_fp32'], bounds['representable_max_fp32']
    final = scalar_qdq(0, out)
    rows = []
    def add(label, value, family):
        value = fp32(value)
        rows.append({'label': label, 'family': family, 'value': value,
                     'f32le_hex': struct.pack('<f', value).hex()})
    def triplet(label, value, family):
        for suffix, v in [('below', adjacent(value, -1)), ('at', value), ('above', adjacent(value, 1))]:
            add(label + '_' + suffix, v, family)
    for label, value in [('zero', 0), ('negative_zero', -0.0), ('half', .5), ('negative_three_quarters', -.75),
                         ('one', 1), ('interior_upper', 20)]:
        add(label, value, 'in_range_anchor')
    for index in (-100, 100):
        triplet(f'ordinary_half_step_{index}', fp32((index + .5) * h['scale']), 'ordinary_rounding')
    triplet('history_upper_endpoint', high, 'decoded_endpoint')
    upper_half = fp32(high + .5 * h['scale'])
    triplet('upper_nominal_half_step', upper_half, 'nominal_clipping_boundary')
    triplet('upper_actual_clipping_onset', clipping_onset(upper_half, 1, h), 'scalar_clipping_boundary')
    for label, value in [('upper_plus_one_step', high + h['scale']),
                         ('upper_plus_two_steps', high + 2*h['scale']),
                         ('upper_gap_midpoint', (high + final['representable_max_fp32']) / 2),
                         ('final_upper_below', adjacent(final['representable_max_fp32'], -1)),
                         ('final_upper_at', final['representable_max_fp32'])]:
        add(label, value, 'above_history_within_final_range')
    triplet('history_lower_endpoint', low, 'decoded_endpoint')
    lower_half = fp32(low - .5 * h['scale'])
    triplet('lower_nominal_half_step', lower_half, 'nominal_clipping_boundary')
    triplet('lower_actual_clipping_onset', clipping_onset(lower_half, -1, h), 'scalar_clipping_boundary')
    for label, value in [('lower_minus_one_step', low - h['scale']),
                         ('lower_minus_two_steps', low - 2*h['scale']),
                         ('final_lower_at', final['representable_min_fp32']),
                         ('final_lower_above', adjacent(final['representable_min_fp32'], 1))]:
        add(label, value, 'lower_control_final_clipping_confounded')
    if len(rows) > 128 or len({r['label'] for r in rows}) != len(rows):
        raise ValueError('Unexpected sweep geometry/labels')
    return rows


def frozen_route():
    """Hash/read receipts and the tiny PTE only; no deserialization or SDK import."""
    manifest = (FIRST / 'SHA256SUMS').read_bytes()
    if probe.digest(manifest) != FIRST_MANIFEST_SHA:
        raise ValueError('Reviewed firstcase manifest changed')
    entries = {name: digest for digest, name in (s.split('  ', 1) for s in manifest.decode().splitlines())}
    def receipt(name):
        raw = (FIRST / name).read_bytes()
        if probe.digest(raw) != entries[name]:
            raise ValueError('Reviewed receipt changed: ' + name)
        return json.loads(raw)
    request = receipt('raw/request.json')
    if probe.digest((FIRST / 'raw/request.json').read_bytes()) != REQUEST_SHA:
        raise ValueError('Not the reviewed firstcase request')
    artifact = receipt('raw/case/compile/data/artifact.json')
    final = receipt('raw/case/compile/data/final-program.json')
    delegation = receipt('raw/case/compile/data/delegation.json')
    if not delegation['all_tensor_compute_delegated'] or not final['zero_kernel_calls_all_delegates_qnn']:
        raise ValueError('Missing reviewed zero tensor-fallback gate')
    if any(p['called_kernels'] or p['delegate_calls'] != ['QnnBackend'] for p in final['plans']):
        raise ValueError('Unexpected emitted plan')
    pte = artifact['pte']
    if pte['bytes'] != PTE_BYTES or pte['sha256'] != PTE_SHA or Path(pte['path']).stat().st_size != PTE_BYTES:
        raise ValueError('Not the frozen tiny PTE')
    if identity(pte['path']) != pte:
        raise ValueError('Frozen PTE bytes changed')
    native_artifacts = receipt('local-native-artifacts.json')
    context = {key: native_artifacts[0][key] for key in ('path', 'bytes', 'sha256')}
    if context['bytes'] != 230736 or context['sha256'] != '33ba1075e4b4a31db22d47f6cf9b7d7d645975d8bab11907e0ada01244a2cf1f':
        raise ValueError('Not the frozen context')
    if Path(context['path']).stat().st_size != 230736 or identity(context['path']) != context:
        raise ValueError('Frozen context changed')
    for source in request['sources'] + [request['binding_identity']]:
        if identity(source['path']) != source:
            raise ValueError('Reviewed source/binding changed: ' + source['path'])
    return {'pte': pte, 'context': context, 'firstcase_manifest_sha256': FIRST_MANIFEST_SHA,
            'firstcase_request_sha256': REQUEST_SHA, 'source_stack': request['sources'],
            'binding_identity': request['binding_identity'], 'compile_options': request['compile_options'],
            'sdk_root': request['sdk_root'], 'firstcase_receipts': {n: entries[n] for n in
            ('raw/case/compile/data/artifact.json', 'raw/case/compile/data/final-program.json',
             'raw/case/compile/data/delegation.json', 'raw/case/runtime/data/abi.json')},
            'zero_executorch_tensor_fallback_receipt': True,
            'same_pte_is_a_fresh_runtime_load_not_loaded_route_isolation_proof': True}


def build_pack():
    """New inputs; preserve original arrays, slots, projection and outlier anchor."""
    history = bytearray((FIRST / 'raw/case/runtime/data/history.f32le').read_bytes())
    projection = (FIRST / 'raw/case/runtime/data/projection.f32le').read_bytes()
    manifest = (FIRST / 'SHA256SUMS').read_bytes()
    if probe.digest(manifest) != FIRST_MANIFEST_SHA:
        raise ValueError('Reviewed firstcase manifest changed')
    entries = {n: d for d, n in (line.split('  ', 1) for line in manifest.decode().splitlines())}
    for name, data in [('history', history), ('projection', projection)]:
        if probe.digest(data) != entries[f'raw/case/runtime/data/{name}.f32le']:
            raise ValueError('Baseline input changed')
    rows = sample_values()
    for index, row in enumerate(rows):
        row['channels'] = [index, 3072 + index]
        for channel in row['channels']:
            struct.pack_into('<f', history, (channel*4+3)*4, row['value'])
    rows.append({'label': 'retained_original_outlier', 'family': 'original_anchor',
                 'value': probe.COMMON_VALUE, 'f32le_hex': struct.pack('<f', probe.COMMON_VALUE).hex(),
                 'channels': [6053]})
    for row in rows:
        current = row['value']; trace = []
        for stage in ('history', 'concat', 'output'):
            record = scalar_qdq(current, probe.case_spec('fullchain')['stages'][stage])
            trace.append({'stage': stage, **record}); current = record['output_fp32']
        row.update(history_slot=3, output_slot=2, fullchain_stages=trace,
                   expected_output_fp32=current,
                   direct_output_only=scalar_qdq(row['value'], probe.case_spec('fullchain')['stages']['output']))
    return (bytes(history), projection), rows


def prepare(directory):
    store = probe.Evidence(directory)
    status = {'scope': 'source_and_one_weight_free_cpu_forward_only', 'status': 'started',
              'compile_calls': 0, 'native_loads': 0, 'native_forwards': 0, 'cpu_forwards': 0,
              'execution_authorized': False, 'full_model_loads': 0, 'phone_access': False}
    try:
        route = frozen_route(); store.json('frozen-route.json', route)
        inputs_raw, rows = build_pack()
        for name, raw in zip(('history', 'projection'), inputs_raw):
            store.raw(name + '.f32le', raw)
        store.json('scalar-stages.json', rows)
        store.json('spec.json', probe.case_spec('fullchain'))
        for case in probe.CASES:
            store.raw(case + '-oracle.f32le', probe.oracle(case, *inputs_raw))
        torch = probe.cpu_torch(); torch.set_num_threads(4)
        model = probe.make_module('fullchain')
        if list(model.parameters()) or list(model.buffers()):
            raise ValueError('Unexpected model weights/buffers')
        inputs = tuple(torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(shape)
                       for raw, shape in zip(inputs_raw, (probe.HISTORY_SHAPE, probe.PROJECTION_SHAPE)))
        status['cpu_forwards'] = 1
        with torch.no_grad():
            output = model(*inputs)
        store.raw('cpu-output.f32le', probe.tensor_bytes(output))  # raw before validation
        comparison = probe.validate_output('fullchain', output, inputs_raw)
        comparison['inputs_unchanged'] = tuple(probe.tensor_bytes(t) for t in inputs) == inputs_raw
        store.json('cpu-comparison.json', comparison)
        if not (comparison['finite'] and comparison['all_output_bytes_match_scalar_oracle'] and comparison['inputs_unchanged']):
            raise ValueError('CPU reference failed; retain outputs and stop')
        status.update(status='complete', sample_rows=len(rows), sweep_values=len(rows)-1,
                      unique_value_bits=len({r['f32le_hex'] for r in rows}),
                      sweep_channels=sum(len(r['channels']) for r in rows[:-1]),
                      torch_version=torch.__version__, python_version=sys.version,
                      preparation_source=identity(__file__), math_threads=torch.get_num_threads(),
                      source_stack=route['source_stack'])
    except BaseException as error:
        status.update(status='error', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        status['files'] = dict(store.records)
        store.json('result.json', status)
    return status


def verify(directory):
    directory = Path(directory); status = json.loads((directory / 'result.json').read_text())
    if status['status'] != 'complete' or status['execution_authorized'] or status['cpu_forwards'] != 1:
        raise ValueError('Not a completed, unapproved CPU-only pack')
    if any(status[key] != 0 for key in ('compile_calls', 'native_loads', 'native_forwards', 'full_model_loads', 'phone_access')):
        raise ValueError('Not a source/CPU-only result')
    if status['preparation_source'] != identity(__file__):
        raise ValueError('Preparation source changed')
    if set(status['files']) | {'result.json'} != {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file()}:
        raise ValueError('Immutable pack file set changed')
    for name, record in status['files'].items():
        data = (directory / name).read_bytes()
        if len(data) != record['bytes'] or probe.digest(data) != record['sha256']:
            raise ValueError('Pack bytes changed: ' + name)
    raw, rows = build_pack()
    if rows != json.loads((directory / 'scalar-stages.json').read_text()):
        raise ValueError('Scalar stages differ from source reconstruction')
    for name, data in zip(('history', 'projection'), raw):
        if data != (directory / (name + '.f32le')).read_bytes():
            raise ValueError('Input sweep differs from source reconstruction')
    for case in probe.CASES:
        if probe.oracle(case, *raw) != (directory / (case + '-oracle.f32le')).read_bytes():
            raise ValueError('Scalar oracle mismatch')
    if (directory / 'cpu-output.f32le').read_bytes() != (directory / 'fullchain-oracle.f32le').read_bytes():
        raise ValueError('CPU reference bytes do not match scalar oracle')
    return {'status': 'verified_saved_bytes_only', 'rows': len(rows), 'runtime_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare-cpu', 'verify'))
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps((prepare if args.mode == 'prepare-cpu' else verify)(args.output_dir), indent=2))


if __name__ == '__main__':
    main()
