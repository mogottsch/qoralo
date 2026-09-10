#!/usr/bin/env python3
"""Independent saved-byte analysis only: stdlib, no Torch/SDK/backend imports."""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parent
DOMAINS = {'history': (0.0007933978922665119, 37640),
           'projection': (0.0008176580304279923, 36523),
           'concat': (0.0009200899512507021, 32457),
           'output': (0.0008176580304279923, 36523)}
REQUEST_SHA = 'dd7e107a6ee22c8793fc43bb76eed6430bd9b5d0b1fdae39b6b0218ce2df1cc1'
PACK_SHA = '422726849aabe269ee6c18c06f16eee7ca5dca2815600ca2f3bc0a44314e4225'
PTE_SHA = '0170b6a2ae96759b36722f05daf8d0925f14b4da57968806b6602008c05d69c3'


def read(path): return json.loads(path.read_text())
def sha(data): return hashlib.sha256(data).hexdigest()
def f32(value): return struct.unpack('<f', struct.pack('<f', value))[0]
def bits(value): return struct.pack('<f', value).hex()
def values(data): return struct.unpack('<' + str(len(data)//4) + 'f', data)


def trace(value, domain):
    scale, zero = DOMAINS[domain]
    scaled = f32(value * f32(1.0 / scale))
    code = round(scaled) + zero
    clipped = min(65535, max(0, code))
    return {'input_fp32': value, 'scaled_fp32': scaled, 'unclamped_code': code,
            'clamped_code': clipped, 'clipped': code != clipped,
            'output_fp32': f32(f32(clipped-zero) * scale),
            'representable_min_fp32': f32(-zero * scale),
            'representable_max_fp32': f32((65535-zero) * scale)}


def qdq(value, domain): return trace(value, domain)['output_fp32']


def full_oracle(history, projection, case):
    result = []
    cache = {}
    for channel in range(6144):
        for slot in range(4):
            value = history[channel*4+slot+1] if slot < 3 else projection[channel]
            domain = 'history' if slot < 3 else 'projection'
            key = (bits(value), domain, case)
            if key not in cache:
                if case != 'outputonly':
                    value = qdq(value, 'output' if case == 'aligned' else domain)
                    value = qdq(value, 'output' if case == 'aligned' else 'concat')
                cache[key] = qdq(value, 'output')
            result.append(cache[key])
    return struct.pack('<24576f', *result)


def distance(actual, expected):
    finite = math.isfinite(actual) and math.isfinite(expected)
    ai, ei = struct.unpack('<II', struct.pack('<ff', actual, expected))
    # Monotone ordering across signs, with -0/+0 adjacent. Keep exact bits too.
    def ordered(x): return (~x & 0xffffffff) if x & 0x80000000 else x | 0x80000000
    return {'actual': actual if math.isfinite(actual) else None, 'actual_f32le_hex': bits(actual),
            'expected': expected, 'expected_f32le_hex': bits(expected),
            'bit_equal': ai == ei, 'abs_error_fp64': abs(actual-expected) if finite else None,
            'ordered_float32_ulp_distance': abs(ordered(ai)-ordered(ei)) if finite else None,
            'error_in_final_scale_steps': abs(actual-expected)/DOMAINS['output'][0] if finite else None}


def aggregate(actual, expected, indices):
    indices = list(indices)
    rows = [distance(actual[i], expected[i]) for i in indices]
    finite = all(r['abs_error_fp64'] is not None for r in rows)
    return {'values': len(rows), 'all_finite': finite,
            'bit_mismatches': sum(not r['bit_equal'] for r in rows),
            'max_abs_error_fp64': max(r['abs_error_fp64'] for r in rows) if finite else None,
            'max_ulp_distance': max(r['ordered_float32_ulp_distance'] for r in rows) if finite else None,
            'values_above_one_ulp': sum(r['ordered_float32_ulp_distance'] > 1 for r in rows) if finite else None}


def analyze(root=ROOT):
    raw = root/'raw'; pack = raw/'pack'; folder = raw/'case/runtime/data'
    req_bytes = (raw/'request.json').read_bytes(); req = json.loads(req_bytes)
    assert sha(req_bytes) == REQUEST_SHA
    manifest = read(pack/'result.json'); assert sha((pack/'result.json').read_bytes()) == PACK_SHA
    assert set(manifest['files']) | {'result.json'} == {str(p.relative_to(pack)) for p in pack.rglob('*') if p.is_file()}
    for name, record in manifest['files'].items():
        data = (pack/name).read_bytes(); assert len(data) == record['bytes'] and sha(data) == record['sha256']
    assert req['frozen_route'] == read(pack/'frozen-route.json')
    assert req['frozen_route']['pte']['sha256'] == PTE_SHA
    release = read(raw/'control/release.json')
    assert release['status'] == 'approved' and release['request_sha256'] == REQUEST_SHA
    assert release['scope'] == req['scope'] and release['approval_reference']
    command = read(raw/'control/command.json')
    assert command[command.index('--output-dir')+1] == release['output_directory']
    assert not (raw/'case/compile').exists()
    cpu = (pack/'cpu-output.f32le').read_bytes()
    history_raw, projection_raw = ((pack/(name+'.f32le')).read_bytes() for name in ('history','projection'))
    assert len(history_raw) == 98304 and len(projection_raw) == 24576
    for name, expected in [('history',history_raw),('projection',projection_raw)]:
        assert (folder/(name+'.f32le')).read_bytes() == expected
        assert (folder/(name+'-after.f32le')).read_bytes() == expected
    history, projection = values(history_raw), values(projection_raw)
    refs = {}
    for case in ('fullchain','outputonly','aligned'):
        oracle = full_oracle(history, projection, case)
        assert oracle == (pack/(case+'-oracle.f32le')).read_bytes()
        refs[case] = values(oracle)
    assert cpu == (pack/'fullchain-oracle.f32le').read_bytes()
    output = (folder/'output-0.raw').read_bytes(); assert len(output) == 98304
    actual = values(output); all_finite = all(map(math.isfinite, actual))
    descriptors = read(folder/'raw-output-descriptors.json')
    assert len(descriptors) == 1 and descriptors[0]['sha256'] == sha(output)
    rows = read(pack/'scalar-stages.json'); assert len(rows) == 40
    label_results = []; repeated = {}; paired_equal = 0
    for index, row in enumerate(rows):
        expected_channels = [index, 3072+index] if index < 39 else [6053]
        assert row['channels'] == expected_channels and row['history_slot'] == 3 and row['output_slot'] == 2
        assert bits(row['value']) == row['f32le_hex']
        current = row['value']; stages = []
        for domain in ('history','concat','output'):
            record = {'stage': domain, **trace(current,domain)}
            stages.append(record); current = record['output_fp32']
        assert stages == row['fullchain_stages'] and current == row['expected_output_fp32']
        assert trace(row['value'],'output') == row['direct_output_only']
        channels = row['channels']; indices = [c*4+2 for c in channels]
        for c in channels:
            assert bits(history[c*4+3]) == row['f32le_hex']
            repeated.setdefault(row['f32le_hex'], []).append((c, bits(actual[c*4+2])))
        pair = len(channels) == 2 and bits(actual[indices[0]]) == bits(actual[indices[1]])
        paired_equal += int(pair)
        label_results.append({**row, 'native_output_values': [actual[i] if math.isfinite(actual[i]) else None for i in indices],
            'native_output_f32le_hex': [bits(actual[i]) for i in indices],
            'paired_bits_equal': pair if len(channels) == 2 else None,
            'paired_reason': None if len(channels) == 2 else 'Original single-channel anchor.',
            'comparisons': {case: [distance(actual[i],ref[i]) for i in indices] for case,ref in refs.items()},
            'final_native_vs_scalar_intermediate_values': [
                {'stage': s['stage'], 'comparison': distance(actual[indices[0]],s['output_fp32'])} for s in stages],
            'intermediate_comparison_caveat': 'Arithmetic difference only; no native intermediate tensor was observed.',
            'direct_input_below_final_decoded_minimum': row['value'] < trace(0,'output')['representable_min_fp32']})
    sweep_indices = {c*4+2 for r in rows[:-1] for c in r['channels']}
    labelled_indices = sweep_indices | {6053*4+2}
    baseline = values((raw/'baseline/output-0.raw').read_bytes())
    baseline_history = (raw/'baseline/history.f32le').read_bytes()
    assert (raw/'baseline/projection.f32le').read_bytes() == projection_raw
    assert all(history_raw[i*4:i*4+4] == baseline_history[i*4:i*4+4]
               for i in range(24576) if i not in {c*4+3 for r in rows[:-1] for c in r['channels']})
    assert all(bits(actual[i]) == bits(baseline[i]) for i in range(24576) if i not in sweep_indices)
    controller = read(raw/'case/result.json'); worker = read(folder/'result.json')
    assert controller['status'] == worker['status'] == 'complete'
    assert worker['load_calls'] == worker['forward_calls'] == 1 and worker['compile_calls'] == 0
    assert worker['evidence_kind'] == 'native_binding'
    assert worker['comparison']['output_sha256'] == sha(output)
    log_raw = (raw/'case/runtime/guard/stderr.log').read_bytes(); log = log_raw.decode()
    needles = ['QnnBackend_create started','QnnBackend_create done successfully',
               'QnnContext_create started','QnnContext_createFromBinary started',
               'QnnGraph_finalize started','QnnGraph_finalize done','QnnGraph_execute started','QnnGraph_execute done']
    return {'evidence_class': 'saved_frozen_pte_sweep_bytes_only', 'no_backend_calls': True,
        'request_sha256': REQUEST_SHA, 'pack_manifest_sha256': PACK_SHA, 'pte_sha256': PTE_SHA,
        'output_sha256': sha(output), 'output_values': 24576, 'finite_values': sum(map(math.isfinite,actual)),
        'all_finite': all_finite, 'inputs_before_after_match_released_pack': True,
        'all_three_independent_scalar_oracles_match_saved_arrays': True,
        'cpu_fullchain_bytes_equal_scalar': True,
        'numerical_status': 'finite_mismatch' if all_finite and output != cpu else ('byte_equal' if all_finite else 'nonfinite'),
        'paired_rows': 39, 'paired_rows_bit_equal': paired_equal,
        'unique_input_bitpatterns': len(repeated),
        'all_repeated_input_bits_produce_identical_output_bits': all(len({b for _,b in group}) == 1 for group in repeated.values()),
        'signed_zero_rows': [r for r in label_results if r['label'] in ('zero','negative_zero')],
        'comparisons': {case: aggregate(actual,ref,range(24576)) for case,ref in refs.items()},
        'unlabelled_outputs_vs_fullchain': aggregate(actual,refs['fullchain'],(i for i in range(24576) if i not in labelled_indices)),
        'unchanged_outputs_vs_original_native_case': aggregate(actual,baseline,(i for i in range(24576) if i not in sweep_indices)),
        'per_slot_vs_fullchain': [aggregate(actual,refs['fullchain'],range(slot,24576,4)) for slot in range(4)],
        'labelled_results': label_results,
        'logical_counts': {'compiles': 0,'loads': 1,'forwards': 1},
        'native_log_observations': {'log_sha256': sha(log_raw), 'exact_substring_counts': {n:log.count(n) for n in needles},
            'execute_completion_statuses': re.findall(r'QnnGraph_execute done\. status (\S+)',log)},
        'interpretation': 'Empirical final-output regions only. No native intermediate taps, internal SDK path/cause, full-model or physical inference.',
        'ulp_note': 'Ordered binary32 bit distance; -0/+0 adjacent. Bit patterns remain separately retained; one-ULP grouping is descriptive, not an acceptance tolerance.'}


if __name__ == '__main__':
    print(json.dumps(analyze(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT),indent=2,allow_nan=False))
