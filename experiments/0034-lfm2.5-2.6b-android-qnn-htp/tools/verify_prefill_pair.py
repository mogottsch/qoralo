#!/usr/bin/env python3
"""Offline-only comparison of the saved native AR171 prefill pair; no model calls."""
import argparse
import json
from pathlib import Path
import re

import numpy as np

from verify_query_prescale_cpu import compare, load_arrays, rankings, sha, stats, write_json


def snapshot(directory):
    rows = [json.loads(line) for line in (directory / 'tensors.jsonl').read_text().splitlines()]
    arrays, records = {}, []
    for row in rows:
        if row['name'] in arrays or not re.fullmatch(r'[0-9]+\.raw', row['file']):
            raise ValueError('Duplicate tensor or unsafe filename')
        if row['byte_order'] != 'little' or row['dtype'] not in ('float32', 'int64'):
            raise ValueError('Native byte-order/dtype mismatch')
        dtype = np.dtype('<f4' if row['dtype'] == 'float32' else '<i8')
        count = int(np.prod(row['shape'], dtype=np.int64))
        path = directory / row['file']
        if count <= 0 or row['bytes'] != count * dtype.itemsize or path.stat().st_size != row['bytes']:
            raise ValueError(f'Native tensor size/shape mismatch: {row["name"]}')
        arrays[row['name']] = np.memmap(path, mode='r', dtype=dtype, shape=tuple(row['shape']))
        records.append({**row, 'sha256': sha(path), 'statistics': stats(arrays[row['name']])})
    return arrays, records


def profile(path):
    pattern = re.compile(r'qnn_profile phase=prefill depth=(\d+) type=(\d+) value=(\d+) unit=(\d+) identifier=(.*)')
    top, nodes = [], []
    for line in path.read_text(errors='replace').splitlines():
        match = pattern.fullmatch(line)
        if not match:
            continue
        depth, kind, value, unit, name = match.groups()
        event = {'type': int(kind), 'value': int(value), 'unit': int(unit), 'identifier': name}
        if int(depth) == 0:
            top.append(event)
        elif int(depth) == 1 and int(kind) == 404 and int(unit) == 3:
            nodes.append(event)
    def unique(name, unit):
        values = [e['value'] for e in top if e['identifier'] == name and e['unit'] == unit]
        return values[0] if len(values) == 1 else None
    cycles = unique('Accelerator (execute) time (cycles)', 3)
    node_sum = sum(x['value'] for x in nodes) if nodes else None
    return {'source_sha256': sha(path), 'top_level_events': top, 'node_events': nodes,
            'accelerator_cycles': cycles, 'per_node_cycle_sum': node_sum,
            'per_node_sum_equals_top': node_sum == cycles if cycles is not None and node_sum is not None else None,
            'scale_named_nodes': [x for x in nodes if '/htp_chunk/scaled_query' in x['identifier'] or '/htp_chunk/scaled_scores' in x['identifier']],
            'missing_or_ambiguous_profile': not top or cycles is None,
            'scope': 'One prefill call per fresh process. Names do not establish tensor dimensions; nullable missing/ambiguous telemetry is not a model-output failure.'}


def stdout_json(path):
    text = path.read_text(errors='replace')
    marker = text.find('{\n  "route":"single_ar171_prefill_native_snapshot"')
    if marker < 0:
        raise ValueError('Native runner result missing')
    return json.JSONDecoder().raw_decode(text[marker:])[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phone-run', type=Path, required=True)
    parser.add_argument('--host-inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference_inputs = load_arrays(args.host_inputs)
    saved = {}
    for phase in ('baseline', 'candidate'):
        base = args.phone_run / phase
        inputs, input_records = snapshot(base / 'native/inputs')
        outputs, output_records = snapshot(base / 'native/outputs')
        if set(inputs) != set(reference_inputs) or len(inputs) != 41 or len(outputs) != 60:
            raise ValueError('Expected all41 exact inputs and60 outputs')
        runner = stdout_json(base / 'runner.stdout')
        endpoint_file = base / 'native/endpoint.int32le'
        endpoint_bytes = endpoint_file.read_bytes()
        endpoint = int(np.frombuffer(endpoint_bytes, dtype='<i4')[0]) if len(endpoint_bytes) == 4 else None
        log_names = sorted((name for name in outputs if name.startswith('logits_vocab_')), key=lambda name: int(name.split('_')[2]))
        flat_logits = np.concatenate([outputs[name].reshape(-1) for name in log_names])
        output_argmax = int(np.argmax(flat_logits)) if flat_logits.size == 128000 and np.isfinite(flat_logits).all() else None
        endpoint_binding = {'bytes': len(endpoint_bytes), 'sha256': sha(endpoint_file), 'token': endpoint,
                            'output_argmax': output_argmax,
                            'valid': bool(runner.get('endpoint_emitted') and endpoint is not None and endpoint == runner.get('endpoint_token') == output_argmax)}
        saved[phase] = {'inputs': inputs, 'outputs': outputs, 'input_manifest': input_records,
                        'output_manifest': output_records, 'runner': runner, 'endpoint_binding': endpoint_binding,
                        'profile': profile(base / 'runner.stderr'),
                        'inputs_vs_host': [{'name': name, **compare(reference_inputs[name], inputs[name])} for name in reference_inputs]}
    a, b = saved['baseline'], saved['candidate']
    if set(a['outputs']) != set(b['outputs']):
        raise ValueError('Output interface name mismatch')
    input_deltas = [{'name': name, **compare(a['inputs'][name], b['inputs'][name])} for name in reference_inputs]
    deltas = [{'name': name, **compare(a['outputs'][name], b['outputs'][name])} for name in a['outputs']]
    same_expected_inputs = all(x['bitwise_equal'] for x in input_deltas) and all(x['bitwise_equal'] for phase in saved.values() for x in phase['inputs_vs_host'])
    all_finite = all(x['reference']['finite'] == x['element_count'] and x['candidate']['finite'] == x['element_count'] for x in deltas)
    valid_calls = all(x['runner']['graph_success'] and x['runner']['prefill_completed'] and x['runner']['snapshot_complete'] and x['endpoint_binding']['valid'] for x in saved.values())
    valid = same_expected_inputs and all_finite and valid_calls
    times = [x['runner'].get('qnn_graph_api_seconds') for x in (a, b)]
    ratio = times[0] / times[1] if valid and all(isinstance(x, (int, float)) and x > 0 for x in times) else None
    result = {'schema_version': 1, 'classification': 'single_ordered_physical_ar171_prefill_pair_offline_analysis',
              'same_expected_inputs_bitwise': same_expected_inputs, 'all60_outputs_finite': all_finite,
              'both_calls_and_snapshots_complete': valid_calls, 'pair_valid_for_descriptive_observation': valid,
              'input_deltas': input_deltas, 'all60_output_deltas': deltas,
              'logit_rankings': rankings(a['outputs'], b['outputs']),
              'phases': {name: {k: value for k, value in phase.items() if k not in ('inputs', 'outputs')} for name, phase in saved.items()},
              'descriptive_baseline_over_candidate_api_time_ratio': ratio,
              'ratio_missing_reason': None if ratio is not None else 'Input/output/call validity or positive API timing not established',
              'new_model_execution_for_analysis': False, 'ar1_executions': 0, 'campaign': False,
              'statistical_speedup_claim': False, 'quality_equivalence_claim': False,
              'limitations': ['One baseline-first/candidate-second fresh-process pair; order, thermal, driver and filesystem cache effects are not controlled by repetitions.',
                              'API timing excludes input/output persistence, host copies/scan/argmax/bridge, context/backend setup and profile extraction; detailed backend instrumentation remains inside graph execution.',
                              'All finite outputs and one endpoint argmax do not establish full-answer quality, numerical equivalence or AR1 continuation.',
                              'Profile counters are exact retained event-set observations when present, not measured host/RPC/DDR traffic or a warm distribution.',
                              'Original CPU/proxy rounding caveats and baseline grammatical/truncated-output limitations remain.']}
    write_json(args.output, result)
    print(json.dumps({key: result[key] for key in ('same_expected_inputs_bitwise', 'all60_outputs_finite', 'both_calls_and_snapshots_complete', 'descriptive_baseline_over_candidate_api_time_ratio')}, indent=2))


if __name__ == '__main__':
    main()
