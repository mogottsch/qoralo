#!/usr/bin/env python3
"""Metadata/scalar audit only: no torch import, model load, weights or execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def fp32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def scalar_qdq(value, encoding):
    """Mirror round(input * inv_scale)+zp, clamp, then FP32 dequantization."""
    s, z = encoding['scale'], encoding['zero_point']
    low, high = encoding['quant_min'], encoding['quant_max']
    scaled = fp32(fp32(value) * fp32(1.0 / s))
    rounded = round(scaled)  # nearest, ties to even as torch.round
    unclamped = int(fp32(fp32(rounded) + fp32(z)))
    code = min(high, max(low, unclamped))
    out = fp32(fp32(fp32(code) - fp32(z)) * fp32(s))
    return {'input_fp32': fp32(value), 'scaled_fp32': scaled, 'unclamped_code': unclamped,
            'clamped_code': code, 'clipped': code != unclamped, 'output_fp32': out,
            'representable_min_fp32': fp32((low-z)*s), 'representable_max_fp32': fp32((high-z)*s)}


def scalar_inputs(node):
    result = {}
    for item in node['inputs']:
        a = item['arg']
        for tag in ('as_float', 'as_int', 'as_scalar_type'):
            if tag in a: result[item['name']] = a[tag]
    return result


def inspect_program(program, value):
    gm = program['graph_module']; graph = gm['graph']
    nodes = {o['as_tensor']['name']: n for n in graph['nodes'] for o in n['outputs'] if 'as_tensor' in o}
    users = [s['user_input']['arg']['as_tensor']['name'] for s in gm['signature']['input_specs'] if 'user_input' in s]
    if users[27] != 'states_24' or graph['outputs'][25]['as_tensor']['name'] != 'dequantize_per_tensor_221':
        raise ValueError('Not the pinned diagnostic ABI/conv-history output')
    names = ['quantize_per_tensor_25', 'dequantize_per_tensor_148', 'cat',
             'quantize_per_tensor_67', 'dequantize_per_tensor_220', 'slice_1',
             'quantize_per_tensor_68', 'dequantize_per_tensor_221',
             'quantize_per_tensor_66', 'dequantize_per_tensor_218']
    selected = {name: {k: nodes[name][k] for k in ('name','target','inputs','outputs')} for name in names}
    expected_links = {'quantize_per_tensor_25':'states_24', 'dequantize_per_tensor_148':'quantize_per_tensor_25',
                      'quantize_per_tensor_67':'cat', 'dequantize_per_tensor_220':'quantize_per_tensor_67',
                      'slice_1':'dequantize_per_tensor_220', 'quantize_per_tensor_68':'slice_1',
                      'dequantize_per_tensor_221':'quantize_per_tensor_68',
                      'dequantize_per_tensor_218':'quantize_per_tensor_66'}
    for name, expected in expected_links.items():
        first = nodes[name]['inputs'][0]['arg'].get('as_tensor',{}).get('name')
        if first != expected: raise ValueError(f'Unexpected lineage at {name}')
    cat_args = nodes['cat']['inputs'][0]['arg']['as_tensors']
    if [x['name'] for x in cat_args] != ['dequantize_per_tensor_148','dequantize_per_tensor_218']:
        raise ValueError('Unexpected concat branches')
    if scalar_inputs(nodes['cat'])['dim'] != -1 or scalar_inputs(nodes['slice_1'])['dim'] != 3 or scalar_inputs(nodes['slice_1'])['start'] != -4:
        raise ValueError('Unexpected history concatenation/slice geometry')
    encodings = []
    trace = []
    current = value
    for stage, q_name, dq_name in [('state_input','quantize_per_tensor_25','dequantize_per_tensor_148'),
                                   ('concat','quantize_per_tensor_67','dequantize_per_tensor_220'),
                                   ('slice_output','quantize_per_tensor_68','dequantize_per_tensor_221')]:
        q = scalar_inputs(nodes[q_name]); dq = scalar_inputs(nodes[dq_name])
        if q != dq or q['quant_min'] != 0 or q['quant_max'] != 65535 or q['dtype'] != 4:
            raise ValueError('Unexpected paired encoding/range/container')
        encoded = {'stage':stage,'quantize_node':q_name,'dequantize_node':dq_name,**q}
        row = {'stage':stage,**scalar_qdq(current,q)}
        encodings.append(encoded);trace.append(row);current=row['output_fp32']
    output_only = scalar_qdq(value, encodings[-1])
    return {'graph_nodes':len(graph['nodes']), 'user_inputs':len(users), 'outputs':len(graph['outputs']),
            'input_index':27,'input_name':'states_24','output_index':25,'output_name':'dequantize_per_tensor_221',
            'input_tensor_metadata':graph['tensor_values']['states_24'],
            'output_tensor_metadata':graph['tensor_values']['dequantize_per_tensor_221'],
            'selected_nodes':selected,'encodings':encodings,'scalar_trace':trace,
            'scalar_result_fp32':current,'output_only_hypothesis':output_only,
            'qdq_integer_container':'serialized ScalarType.INT=4 (INT32), with activation codes0..65535',
            'claim_limits':['Exact retained QDQ path and scalar arithmetic only; no model/weights were loaded or executed.',
                            'Input clipping followed by concat/output requantization explains this QDQ endpoint, not the final-output ceiling alone.',
                            'Output-only arithmetic near QNN does not prove the actual lowered/fused QNN path, a backend bug, logit causality or FP32 accuracy.']}


def audit(archive, output_dir, common_value):
    output_dir.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        names = [n for n in z.namelist() if n.endswith('/models/model.json')]
        if len(names) != 1: raise ValueError('Expected one model graph metadata member')
        info = z.getinfo(names[0])
        if info.file_size > 64*1024*1024: raise ValueError('Metadata member exceeds the bounded audit size')
        data = z.read(names[0])  # ONLY this member; never weights/constants/sample inputs.
    program = json.loads(data)
    result = inspect_program(program,common_value)
    result['archive_metadata'] = {'archive_path':str(archive),'archive_bytes':archive.stat().st_size,
                                  'member':names[0],'member_bytes':len(data),'member_sha256':hashlib.sha256(data).hexdigest(),
                                  'member_crc32':info.CRC,'torch_version':program['torch_version'],
                                  'archive_sha256_recomputed':False,'members_read':[names[0]],
                                  'weight_constant_or_sample_input_members_read':0}
    (output_dir/'graph-model.json').write_bytes(data)
    (output_dir/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--common-value',type=float,default=23.721895217895508)
    a=p.parse_args();r=audit(a.archive,a.output_dir,a.common_value)
    print(json.dumps({'metadata':r['archive_metadata'],'encodings':r['encodings'],'trace':r['scalar_trace']},indent=2))


if __name__=='__main__':main()
