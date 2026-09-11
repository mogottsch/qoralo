#!/usr/bin/env python3
"""Validate coupled FP16 head reassembly and return to quantized O-projection."""
from __future__ import annotations


def exit_gate(graph, previous, plan):
    def indexes(g):
        names, consumers = {}, {}
        for op in g['operators']:
            names[op['name']] = op
            for t in op['inputs']:
                consumers.setdefault(t['name'], []).append(op)
        return names, consumers
    current, consumers = indexes(graph)
    old, old_consumers = indexes(previous)
    found, issues = {}, []
    for layer in plan:
        for name in layer['consumer_nodes']:
            mm = current.get(name)
            try:
                assert mm and len(mm['outputs']) == 1, 'missing MatMul output'
                targets = consumers.get(mm['outputs'][0]['name'], [])
                assert len(targets) == 1 and targets[0]['type'] == 'Concat', 'unexpected post-MatMul arithmetic or consumer'
                cat = targets[0]
                if cat['name'] in found:
                    continue
                before = old[cat['name']]
                assert before['type'] == 'Concat'
                assert [t['name'] for t in cat['inputs']] == [t['name'] for t in before['inputs']], 'head order changed'
                assert [t['dimensions'] for t in cat['inputs']] == [t['dimensions'] for t in before['inputs']], 'head dimensions changed'
                assert all(t['datatype'] == 'Float_16' for t in cat['inputs'] + cat['outputs']), 'head Concat not Float16'
                assert len(cat['outputs']) == len(before['outputs']) == 1
                joined, original = cat['outputs'][0], before['outputs'][0]
                assert joined['name'] == original['name'] and joined['dimensions'] == original['dimensions']
                after_cat = consumers.get(joined['name'], [])
                assert len(after_cat) == 1 and after_cat[0]['type'] == 'Convert', 'no scoped conversion back to quantized boundary'
                conversion = after_cat[0]
                assert len(conversion['inputs']) == len(conversion['outputs']) == 1
                quantized = conversion['outputs'][0]
                assert quantized['datatype'] == original['datatype'] == 'uFxp_16'
                assert quantized['dimensions'] == original['dimensions']
                def enc(op, tensor_name):
                    return [p.split(' encoding : ', 1)[1] for p in op.get('parameters', [])
                            if p.startswith(tensor_name + ' encoding : ')]
                before_enc, after_enc = enc(before, original['name']), enc(conversion, quantized['name'])
                assert len(before_enc) == 1 and before_enc == after_enc, 'output-projection input grid changed'
                downstream = consumers.get(quantized['name'], [])
                previous_downstream = old_consumers.get(original['name'], [])
                assert len(downstream) == len(previous_downstream) == 1
                projection, previous_projection = downstream[0], previous_downstream[0]
                assert projection['name'] == previous_projection['name'] and projection['type'] == previous_projection['type'] == 'Conv2d'
                assert projection['outputs'] == previous_projection['outputs'], 'output-projection output signature changed'
                assert projection['inputs'][1:] == previous_projection['inputs'][1:], 'projection parameter tensor signatures changed'
                assert [p for p in projection.get('parameters', []) if ' encoding ' in p] == [p for p in previous_projection.get('parameters', []) if ' encoding ' in p], 'projection encoding metadata changed'
                found[cat['name']] = {'head_concat': cat, 'exit_convert': conversion,
                                      'unchanged_projection': projection,
                                      'before_input_encoding': before_enc, 'after_input_encoding': after_enc}
            except (AssertionError, KeyError, IndexError) as error:
                issues.append({'value_matmul': name, 'issue': str(error) or 'coupled exit mismatch'})
    if not found:
        issues.append({'value_matmul': None, 'issue': 'no head-reassembly groups observed'})
    return {'passed': not issues, 'issues': issues, 'head_group_count': len(found),
            'groups': list(found.values()),
            'scope': 'FP16 head Concat is a required coupled consumer; original fixed-point grid resumes before unchanged output-projection signatures',
            'numerical_equivalence_proven': False, 'physical_execution': False}
