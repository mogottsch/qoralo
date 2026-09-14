#!/usr/bin/env python3
"""Bounded SAVED/STATIC audit. No neural graph, operator replay, phone or repair."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import onnx

TRACK=Path(__file__).resolve().parents[1]
EXP=TRACK.parents[1]
POLICY=TRACK/'.local/matched-prefill-reference/policy-01/policy.json'
POLICY_SHA='7fffebe9208bc5e2b92d80ed6ed01b7b57263e8f23d188188588682754c18b59'
FLOAT_GRAPH=EXP/'.local/checkpoint/extracted/gemma_4_e2b_it_w4a16/model_dynamic.onnx'
GRAPH_SHA='51d4e8183a6734a8c7bbd24ebc072768f080e54b011725ae645dfa32498bf0d0'
FLOAT_DATA=FLOAT_GRAPH.parent/'model.data'
DATA_SHA='e156c33d176273555003039959ecb0ae0ddc8a328eceeec1e8f4a6255840e072'
HEAD_REGION_SHA='eb7ac2b168bd4446daba2aabf0df0d3a0f7b25dfea5afbcffad375e61e4146fc'
HEADER=Path('/home/moritz/opt/qairt/2.49.40.260810/include/QNN/QnnTypes.h')
WEIGHTS=['model.lm_head.weight','model.model.layers.0.self_attn.q_proj_sha.0.weight','val_42']


def sha(path,offset=0,length=None):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        f.seek(offset)
        while length is None or length>0:
            block=f.read(4*1024*1024 if length is None else min(length,4*1024*1024))
            if not block:break
            h.update(block)
            if length is not None:length-=len(block)
    if length not in (None,0):raise ValueError('short region read')
    return h.hexdigest()


def signed_low_bits(values,bits):
    q=np.asarray(values,dtype=np.int32)&((1<<bits)-1)
    return np.where(q>=(1<<(bits-1)),q-(1<<bits),q)


def metrics(candidate,source,scales):
    delta=candidate.astype(np.float64)-source.astype(np.float64);a=np.abs(delta)
    steps=a/scales.astype(np.float64);norm=float(np.linalg.norm(candidate.astype(np.float64))*np.linalg.norm(source.astype(np.float64)))
    return {'values':int(source.size),'mean_absolute_error':float(a.mean()),'max_absolute_error':float(a.max()),'RMSE':float(np.sqrt(np.mean(delta**2))),'cosine_to_known_float_weights':float(np.sum(candidate.astype(np.float64)*source.astype(np.float64))/norm) if norm else None,'within_half_scale_fraction':float(np.mean(steps<=.5001)),'max_error_scale_units':float(steps.max()),'nonzero_sign_disagreements':int(np.count_nonzero((source!=0)&(candidate!=0)&(np.signbit(source)!=np.signbit(candidate)))),'known_zero_values':int(np.count_nonzero(source==0)),'known_zero_nonzero_decodes':int(np.count_nonzero((source==0)&(candidate!=0)))}


def audit(out):
    started=time.monotonic();out.mkdir(parents=True,exist_ok=False)
    if sha(POLICY)!=POLICY_SHA or sha(FLOAT_GRAPH)!=GRAPH_SHA or sha(FLOAT_DATA)!=DATA_SHA:raise ValueError('frozen policy or known float export changed')
    (out/'source-verification.json').write_text(json.dumps({'policy_sha256':POLICY_SHA,'float_graph_sha256':GRAPH_SHA,'float_data_sha256':DATA_SHA,'seconds':time.monotonic()-started,'model_or_operator_forward_calls':0},indent=2)+'\n')
    policy=json.loads(POLICY.read_text());graph=onnx.load(str(FLOAT_GRAPH),load_external_data=False);initializers={t.name:t for t in graph.graph.initializer}
    header=HEADER.read_text();required=["all bits above the specified bitwidth will be ignored","signed bit is the most","0b00001101"]
    if not all(text in header for text in required):raise ValueError('expected documented BW storage contract missing')
    groups=Counter()
    for tensor in policy['tensors'].values():
        if tensor['datatype']=='sFxp_8' and 'static' in tensor:
            g=tensor['grid'];groups[(tensor['encoding_kind'],tuple(sorted(set(g['bitwidths']))),tuple(sorted(set(g['offset']))))]+=1
    result={'classification':'saved_static_reference_contract_audit','model_or_operator_forward_calls':0,'phone_calls':0,'reference_implementation_changed':False,'policy_sha256':POLICY_SHA,'known_float_graph_sha256':GRAPH_SHA,'known_float_data_sha256':DATA_SHA,'storage_contract':{'header_path':str(HEADER),'header_sha256':sha(HEADER),'line_ranges':[[529,563],[593,631]],'documented_rule':'For BW scale-offset and BW per-axis encodings, use low specified bits; ignore upper container bits; signed bit is the most significant effective bit (example0x0d and0xfd bothmean-3 atBW4).','actual_signed_static_encoding_groups':[{'encoding':k[0],'bits':list(k[1]),'offsets':list(k[2]),'tensors':n} for k,n in groups.items()]},'weights':[]}
    for name in WEIGHTS:
        t=policy['tensors'][name];g=t['grid'];init=initializers[name];ext={v.key:v.value for v in init.external_data};dims=list(init.dims);offset=int(ext['offset']);length=int(ext['length'])
        if ext['location']!='model.data' or init.data_type!=onnx.TensorProto.FLOAT or length!=int(np.prod(dims))*4:raise ValueError('known external float weight contract mismatch')
        known=np.memmap(FLOAT_DATA,dtype='<f4',mode='r',offset=offset,shape=tuple(dims));raw_path=POLICY.parent/t['static']['file']
        if sha(raw_path)!=t['static']['npy_sha256']:raise ValueError('actual DLC static codes changed')
        raw=np.load(raw_path,mmap_mode='r',allow_pickle=False)
        if len(dims)==4 and dims[2:]==[1,1]:
            known_matrix=known[:,:,0,0];code_matrix=raw[0,0].T;expected_axis=3;layout='OIHW float -> HWIO DLC; canonical comparison rows=output channels'
        elif name=='val_42':
            known_matrix=known.T;code_matrix=raw;expected_axis=0;layout='known val_42 transpose -> FullyConnected OI rows'
        else:raise ValueError('unreviewed static layout')
        if list(raw.shape)!=t['dimensions'] or code_matrix.shape!=known_matrix.shape or g['axis']!=expected_axis or set(g['bitwidths'])!={4} or set(g['offset'])!={0}:raise ValueError('static shape/axis/BW/offset mismatch')
        rows=np.unique(np.linspace(0,known_matrix.shape[0]-1,min(1024,known_matrix.shape[0]),dtype=np.int64))
        source=np.asarray(known_matrix[rows],dtype=np.float32);codes=np.asarray(code_matrix[rows],dtype=np.int8)
        scales=np.asarray(g['scale'],dtype=np.float32)[rows,None];offsets=np.asarray(g['offset'],dtype=np.float32)[rows,None]
        interpretations={'documented_signed_BW4':signed_low_bits(codes,4),'signed_int8_container_without_BW_interpretation':codes.astype(np.int32),'diagnostic_unsigned_nibble_minus8':(codes.astype(np.int32)&15)-8}
        candidates={key:metrics((q.astype(np.float32)+offsets)*scales,source,scales) for key,q in interpretations.items()}
        predicted=np.clip(np.rint(source/scales-offsets),-8,7).astype(np.int32);doc=interpretations['documented_signed_BW4']
        region_sha=sha(FLOAT_DATA,offset,length)
        if name=='model.lm_head.weight' and region_sha!=HEAD_REGION_SHA:raise ValueError('previously proven float head region changed')
        result['weights'].append({'name':name,'encoding':t['encoding_kind'],'IR_datatype':t['datatype'],'container_dtype':str(raw.dtype),'IR_dimensions':t['dimensions'],'known_float_dimensions':dims,'channel_axis':g['axis'],'bitwidth':4,'offsets':[0],'layout':layout,'sampled_output_channels':len(rows),'sampled_values':int(source.size),'code_histogram':[int(np.count_nonzero(codes==v)) for v in range(16)],'raw_npy_sha256':sha(raw_path),'float_region':{'offset':offset,'bytes':length,'sha256':region_sha},'min_scale_units':float(g['min'][0]/g['scale'][0]),'max_scale_units':float(g['max'][0]/g['scale'][0]),'source_values_outside_signed_grid':int(np.count_nonzero((source/scales-offsets < -8)|(source/scales-offsets > 7))),'documented_codes_matching_requantized_known_float':int(np.count_nonzero(doc==predicted)),'candidates':candidates})
        (out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
        del source,codes,known,raw,known_matrix,code_matrix
        if time.monotonic()-started>270:raise TimeoutError('static audit work budget')
    result['seconds']=time.monotonic()-started;result['finding_scope']='Storage interpretation checked against the documented ACTUAL BW encoding and known float weights, not fitted to QNN logits. This does not validate all graph operator/cache semantics.'
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/declared-reference-static-audit'):p.error('owned fresh static-audit output required')
    audit(out)
