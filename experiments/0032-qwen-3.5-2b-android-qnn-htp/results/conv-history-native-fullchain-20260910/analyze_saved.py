#!/usr/bin/env python3
"""Saved JSON/log/raw-FP32 analysis only. No Torch, SDK or model/runtime imports."""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys

ROOT=Path(__file__).resolve().parent
DOMAINS={'history':(0.0007933978922665119,37640),'projection':(0.0008176580304279923,36523),
         'concat':(0.0009200899512507021,32457),'output':(0.0008176580304279923,36523)}
BASE={'history':'history','projection':'projection','concat':'aten_cat_default','output':'aten_slice_copy_tensor'}
SELECTED=6053*4+2


def read_json(path):return json.loads(path.read_text())
def sha(data):return hashlib.sha256(data).hexdigest()
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def qdq(value,domain):
    scale,zero=DOMAINS[domain]
    code=min(65535,max(0,round(f32(value*f32(1.0/scale)))+zero))
    return f32(f32(code-zero)*scale)


def output_analysis(root):
    raw=root/'raw';folder=raw/'case/runtime/data';data=(folder/'output-0.raw').read_bytes()
    if len(data)!=98304:raise ValueError('Not the fixed output geometry')
    values=struct.unpack('<24576f',data);all_finite=all(map(math.isfinite,values))
    history=(folder/'history.f32le').read_bytes();projection=(folder/'projection.f32le').read_bytes()
    req=read_json(raw/'request.json')
    if [sha(history),sha(projection)]!=req['input_hashes']:raise ValueError('Not released input bytes')
    h=struct.unpack('<24576f',history);p=struct.unpack('<6144f',projection)
    reconstructed=[]
    for channel in range(6144):
        for slot in range(4):
            value=h[channel*4+slot+1] if slot<3 else p[channel]
            value=qdq(value,'history' if slot<3 else 'projection')
            reconstructed.append(qdq(qdq(value,'concat'),'output'))
    oracle=struct.pack('<24576f',*reconstructed)
    if oracle!=(raw/'reference/scalar-oracle.f32le').read_bytes():raise ValueError('Independent scalar reconstruction failed')
    comparisons={}
    for case,oracle_name,cpu_name in [('fullchain','scalar-oracle.f32le','cpu-output.f32le'),
                                     ('outputonly','outputonly-oracle.f32le','outputonly-cpu.f32le'),
                                     ('aligned','aligned-oracle.f32le','aligned-cpu.f32le')]:
        expected=(raw/'reference'/oracle_name).read_bytes();cpu=(raw/'reference'/cpu_name).read_bytes()
        if expected!=cpu:raise ValueError('Accepted CPU/oracle bytes disagree')
        ref=struct.unpack('<24576f',expected);errs=[abs(a-b) for a,b in zip(values,ref)] if all_finite else None
        # Values in this fixed fixture are finite with matched signs for ULP comparisons.
        bits=struct.unpack('<24576I',data);rbits=struct.unpack('<24576I',expected)
        same_sign=all((x>>31)==(y>>31) for x,y in zip(bits,rbits))
        ulps=[abs(x-y) for x,y in zip(bits,rbits)] if all_finite and same_sign else None
        comparisons[case]={'oracle_sha256':sha(expected),'cpu_bytes_equal_oracle':True,
            'all_bytes_equal':data==expected,'bit_mismatch_values':sum(a!=b for a,b in zip(bits,rbits)),
            'selected_actual':values[SELECTED] if math.isfinite(values[SELECTED]) else None,'selected_expected':ref[SELECTED],
            'selected_abs_error':errs[SELECTED] if errs else None,'max_abs_error':max(errs) if errs else None,
            'mean_abs_error_fp64':math.fsum(errs)/len(errs) if errs else None,
            'excluding_selected_max_abs':max(e for i,e in enumerate(errs) if i!=SELECTED) if errs else None,
            'max_ulp_if_finite_same_sign':max(ulps) if ulps else None,
            'excluding_selected_max_ulp':max(e for i,e in enumerate(ulps) if i!=SELECTED) if ulps else None,
            'excluding_selected_values_above_one_ulp':sum(e>1 for i,e in enumerate(ulps) if i!=SELECTED) if ulps else None,
            'per_output_slot':[{'slot':slot,'values':6144,'first_channel_actual':values[slot] if all_finite else None,
                                'first_channel_expected':ref[slot],
                                'max_abs':max(errs[slot::4]) if errs else None,
                                'values_above_one_ulp':sum(e>1 for e in ulps[slot::4]) if ulps else None} for slot in range(4)]}
    return {'output_bytes':len(data),'output_sha256':sha(data),'value_count':len(values),
            'finite_count':sum(map(math.isfinite,values)),'all_finite':all_finite,
            'numerical_status':'finite_mismatch' if all_finite and data!=oracle else ('exact' if all_finite else 'nonfinite'),
            'independent_fullchain_scalar_reconstruction_matches_retained_oracle':True,
            'comparisons_to_existing_saved_cpu_oracles':comparisons,
            'other_native_cases_executed':False,'calculation':'stdlib FP32 decode and FP64 subtraction/aggregation; no backend calls'}


def encoding_record(args):
    return {'scale':args[1],'zero_point':args[2],'quant_min':args[3],'quant_max':args[4],'dtype':args[5]}


def metadata_analysis(root):
    folder=root/'raw/case/compile/data/taps';snapshots=[];selected=[];mismatches=[]
    for path in sorted(folder.glob('*.json')):
        d=read_json(path)
        if 'nodes' in d:
            nodes=d['nodes'];by_name={n['name']:n for n in nodes};boundaries={}
            for label,name in BASE.items():
                node=by_name[name];records=[]
                attrs=node['metadata'].get('quant_attrs')
                if attrs:records.append({'source':'base_node.quant_attrs',**{k:attrs[k] for k in ('scale','zero_point','quant_min','quant_max','dtype')}})
                for candidate in nodes:
                    if '.quantize_per_tensor.' in candidate['target'] and candidate['args'][0]=={'node':name}:
                        records.append({'source':candidate['name']+'.args',**encoding_record(candidate['args'])})
                scale,zero=DOMAINS[label]
                match=bool(records) and all((x['scale'],x['zero_point'],x['quant_min'],x['quant_max'],x['dtype'])==
                         (scale,zero,0,65535,{'type':'dtype','text':'torch.int32'}) for x in records)
                boundaries[label]={'exact_domain_preserved':match,'records':records,'base_value_metadata':node['value_metadata']}
                if not match:mismatches.append({'file':path.name,'boundary':label})
            snapshots.append({'file':path.name,'sha256':sha(path.read_bytes()),'pass_type':d.get('pass_type'),
                              'node_count':d['node_count'],'boundaries':boundaries})
        if 'encoding_config_before_get_data_type' in d:
            selected.append({'file':path.name,'node':d['node'],'consumer':d['consumer'],
                             'configuration':d['encoding_config_before_get_data_type']})
    wrappers=read_json(folder/'0063-native-wrapper-encodings.json')
    checks=[]
    for op,label in zip(wrappers['operators'][:4],('history','projection','concat','output')):
        tensor=op['outputs'][0];scale,zero=DOMAINS[label]
        valid=tensor['dtype']['code']==1046 and tensor['encodings']==[
                {'scale':scale,'scale_float32_le_hex':struct.pack('<f',scale).hex(),'qnn_offset':-zero}]
        checks.append({'boundary':label,'operator':op['type'],'tensor_name':tensor['name'],'native_dtype':tensor['dtype'],
                       'native_encodings':tensor['encodings'],'exact_scale_offset_preserved':valid,
                       'encoding_kind':tensor['encoding_kind'],'bitwidth':tensor['bitwidth']})
    io=read_json(folder/'0064-native-manager-io.json')
    return {'tap_files':len(list(folder.glob('*.json'))),'graph_snapshots':snapshots,'selected_configurations':selected,
            'first_observed_domain_mismatch':mismatches[0] if mismatches else None,
            'all_four_boundaries_preserved_in_every_captured_graph':not mismatches,
            'native_boundary_checks':checks,'all_native_scale_offsets_preserved':all(x['exact_scale_offset_preserved'] for x in checks),
            'input_quantize_wrappers_present':[x['type'] for x in wrappers['operators'][:2]]==['Quantize','Quantize'],
            'representation_boundaries':[
                {'file':'0024-after-pass.json','change':'AnnotateQuantAttrs copies unchanged QDQ args to producer quant_attrs.'},
                {'file':'0026-after-pass.json','change':'FoldQDQ removes explicit Q/DQ nodes; four domain attributes remain.'},
                {'file':'0046-after-pass.json','change':'InsertRequantize leaves this five-node graph and four domain encodings unchanged.'},
                {'file':'0048-after-pass.json','change':'InsertIOQDQ moves input attributes to two explicit Quantize nodes and inserts output Dequantize; domains unchanged.'},
                {'file':'0063-native-wrapper-encodings.json','change':'Native fixed-point tensors use UFIXED16 code1046, not the graph INT32 carrier; exact FP32 scales and negated zero points remain.'}],
            'manager_io_raw':io['graphs'],'postcompile_io_encoding_metadata':None,
            'postcompile_io_reason':'Manager getter arrays were empty at this tap; do not infer missing graph IO or finalized encodings.',
            'first_observed_semantic_scale_change':None if not mismatches and all(x['exact_scale_offset_preserved'] for x in checks) else 'see checks',
            'complete_native_encoding_kind_bitwidth_known':False,'internal_finalized_graph_known':False,
            'conclusion':'No semantic domain change observed through captured pre-Compile wrappers. Frontend omission is not supported; the internal execution path remains unknown.'}


def log_counts(root):
    result={}
    needles=['QnnBackend_create started','QnnBackend_create done successfully','QnnContext_create started',
             'QnnContext_createFromBinary started','QnnGraph_finalize started','QnnGraph_finalize done',
             'QnnGraph_execute started','QnnGraph_execute done']
    for phase in ('compile','runtime'):
        path=root/f'raw/case/{phase}/guard/stderr.log';text=path.read_text()
        result[phase]={'log_sha256':sha(path.read_bytes()),'exact_substring_counts':{n:text.count(n) for n in needles},
                       'execute_completion_statuses':re.findall(r'QnnGraph_execute done\. status (\S+)',text)}
    return result


def analyze(root=ROOT):
    return {'evidence_class':'saved_firstcase_bytes_and_precompile_metadata_analysis','no_backend_calls':True,
            'output':output_analysis(root),'metadata':metadata_analysis(root),'native_log_observations':log_counts(root),
            'causal_or_full_model_verdict':False}


if __name__=='__main__':
    print(json.dumps(analyze(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT),indent=2,allow_nan=False))
