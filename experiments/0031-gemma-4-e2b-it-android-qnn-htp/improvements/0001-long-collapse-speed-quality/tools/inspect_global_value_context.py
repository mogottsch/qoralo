#!/usr/bin/env python3
"""Validate official AOT context metadata, never treating compilation as execution."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

FLOAT16 = 'QNN_DATATYPE_FLOAT_16'
FLAT = 'QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER'
NAMES = {'ar1_cl4096_1_of_1', 'ar128_cl4096_1_of_1'}
SELECTED = {f'past_value_{layer}_h0_{suffix}' for layer in (4, 9, 14) for suffix in ('in', 'out')}


def cache_signature(tensor):
    # QnnUtils assigns (0,0) to every nonquantized tensor regardless of inactive
    # QNN quantization union fields. Preserve raw metadata, compare active semantics.
    return (tensor['dataType'], None if tensor['dataType'] == FLOAT16 else tensor['quantizeParams'])


def compare_context(candidate, baseline):
    info, old = candidate['info'], baseline['info']
    issues = []
    if info['backendId'] != 6 or info['socModel'] != 43 or info['numGraphs'] != 2:
        issues.append('expected two-graph HTP backend6 SM8550 soc43 context')
    if info['buildId'] != old['buildId']:
        issues.append('compiler build differs from accepted baseline')
    graphs = {g['info']['graphName']: g['info'] for g in info['graphs']}
    old_graphs = {g['info']['graphName']: g['info'] for g in old['graphs']}
    if set(graphs) != NAMES or len(info['graphs']) != 2:
        issues.append('graph aliases/count changed')
    maps = {}
    summaries = {}
    for name in sorted(set(graphs) & NAMES):
        sides = {}
        for side in ('graphInputs', 'graphOutputs'):
            before = {t['info']['name']: t['info'] for t in old_graphs[name][side]}
            after = {t['info']['name']: t['info'] for t in graphs[name][side]}
            if set(after) != set(before) or len(after) != len(graphs[name][side]):
                issues.append(f'{name} {side}: tensor names/count changed')
            for tensor_name in sorted(set(before) & set(after)):
                a, b = after[tensor_name], before[tensor_name]
                fields = ['dimensions', 'rank', 'dataFormat', 'type']
                if tensor_name in SELECTED:
                    if a['dataType'] != FLOAT16:
                        issues.append(f'{name} {tensor_name}: selected cache not FP16')
                else:
                    fields += ['dataType', 'quantizeParams']
                for field in fields:
                    if a[field] != b[field]:
                        issues.append(f'{name} {tensor_name}: {field} changed')
                if ('_key_' in tensor_name or '_value_' in tensor_name) and a['dataFormat'] != FLAT:
                    issues.append(f'{name} {tensor_name}: NativeKV/non-flat cache forbidden')
            sides[side] = after
        maps[name] = sides
        summaries[name] = {side: {'count': len(entries),
                                  'datatypes': dict(Counter(t['dataType'] for t in entries.values()))}
                           for side, entries in sides.items()}
    cache_count = 0
    if set(maps) == NAMES:
        a, b = maps['ar1_cl4096_1_of_1'], maps['ar128_cl4096_1_of_1']
        names = [n for n in a['graphOutputs'] if '_key_' in n or '_value_' in n]
        for output in names:
            inp = output.removesuffix('_out') + '_in'
            try:
                tensors = [a['graphInputs'][inp], a['graphOutputs'][output],
                           b['graphInputs'][inp], b['graphOutputs'][output]]
            except KeyError:
                issues.append(f'cache input/output missing: {output}')
                continue
            signatures = [cache_signature(t) for t in tensors]
            if any(sig != signatures[0] for sig in signatures):
                issues.append(f'four-way active cache signature mismatch: {output}')
            cache_count += 1
        if cache_count != 30:
            issues.append('expected30 cache pairs')
    cache_formats = Counter(t['dataFormat'] for sides in maps.values() for tensors in sides.values()
                            for name, t in tensors.items() if '_key_' in name or '_value_' in name)
    positional_inputs = {name: sorted(t for t in sides['graphInputs'] if 'position_ids' in t)
                         for name, sides in maps.items()}
    return {'metadata_gate_passed': not issues, 'issues': issues,
            'backend_id': info['backendId'], 'soc_model': info['socModel'],
            'build_id': info['buildId'], 'graphs': summaries, 'cache_count': cache_count,
            'cache_data_format_counts': dict(cache_formats), 'positional_inputs': positional_inputs,
            'flat_buffer_required': True, 'native_kv_supported_claim': False,
            'float_quantization_semantics': 'Genie QnnUtils nonquantized placeholder (0,0); inactive union ignored',
            'physical_execution_proven': False, 'full_cpu_free_execution_proven': False,
            'fidelity_proven': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--metadata', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = compare_context(json.loads(args.metadata.read_text()), json.loads(args.baseline.read_text()))
    result['metadata_sha256'] = hashlib.sha256(args.metadata.read_bytes()).hexdigest()
    result['baseline_sha256'] = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['metadata_gate_passed'] else 1)
