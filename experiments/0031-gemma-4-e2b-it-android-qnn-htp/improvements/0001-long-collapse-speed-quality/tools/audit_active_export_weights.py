#!/usr/bin/env python3
"""Stream active exported weights against native checkpoint data; no model execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import time

TRACK=Path(__file__).resolve().parents[1]
EXP=TRACK.parents[1]
ARCHIVE=EXP/'.local/checkpoint/extracted/gemma_4_e2b_it_w4a16'
CHECKPOINT=EXP/'.local/hf-checkpoint/model.safetensors'
EXPECTED='efab429012b97ab986c4d4838a46ff3ad95d618b42ce514771ca40fadc76a9a4'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def source_mapping(name,dims):
    if name=='val_42':return {'source':'model.language_model.per_layer_model_projection.weight','transpose':True,'start_row':0}
    if name=='model.lm_head.weight':return {'source':'lm_head.weight','start_row':0}
    q=re.fullmatch(r'model\.model\.layers\.(\d+)\.self_attn\.([qkv])_proj_sha\.(\d+)\.weight',name)
    if q:
        layer,proj,head=q.groups()
        return {'source':f'model.language_model.layers.{layer}.self_attn.{proj}_proj.weight','start_row':int(head)*dims[0]}
    n=re.fullmatch(r'model\.model\.layers\.(\d+)\.self_attn\.([qkv])_norm_sha\.\d+\.weight',name)
    if n:return {'source':f'model.language_model.layers.{n[1]}.self_attn.{n[2]}_norm.weight','start_row':0}
    if name.startswith('model.model.'):
        return {'source':name.replace('model.model.','model.language_model.',1).replace('.o_proj_conv.','.o_proj.'),'start_row':0}
    return None


def active_initializer_names(graph):
    producers={out:node for node in graph.node for out in node.output};seen=set();pending=[v.name for v in graph.output]
    while pending:
        name=pending.pop()
        if name in seen:continue
        seen.add(name)
        if name in producers:pending.extend(producers[name].input)
    return {t.name for t in graph.initializer if t.name in seen}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    root=TRACK/'.local/matched-prefill-reference'
    if not out.is_relative_to(root):p.error('owned fresh disk-backed output required')
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();issues=[];rows=[]
    import numpy as np
    import onnx
    if sha(CHECKPOINT)!=EXPECTED:raise ValueError('checkpoint identity changed')
    with CHECKPOINT.open('rb') as f:
        length=struct.unpack('<Q',f.read(8))[0]
        if length>4*1024*1024:raise ValueError('unbounded header')
        header=json.loads(f.read(length))
    origin=length+8
    inventory=json.loads((TRACK/'.local/native-qat-reference/full-prefill-1800-01/load-validation.json').read_text())['native_quant_modules']
    def native_tensor(name):
        h=header[name];dt={'F32':'<f4','BF16':'<u2','U8':'u1','I8':'i1'}[h['dtype']]
        return np.memmap(CHECKPOINT,dtype=dt,mode='r',offset=origin+h['data_offsets'][0],shape=tuple(h['shape']))
    def as_float(data,dtype):
        if dtype=='BF16':return (np.asarray(data,dtype=np.uint32)<<16).view(np.float32)
        return np.asarray(data,dtype=np.float32)
    model=onnx.load(ARCHIVE/'model_dynamic.onnx',load_external_data=False);active=active_initializer_names(model.graph)
    for t in model.graph.initializer:
        if t.name not in active:continue
        dims=list(t.dims);mapping=source_mapping(t.name,dims);ext={v.key:v.value for v in t.external_data}
        item={'name':t.name,'shape':dims,'onnx_dtype':t.data_type,'mapping':mapping}
        rows.append(item)
        if mapping is None:
            if ext:item['issue']='unmapped external initializer';issues.append(item['name'])
            else:item.update(classification='inline structural constant',serialized_sha256=hashlib.sha256(t.SerializeToString()).hexdigest())
            continue
        key=mapping['source']
        if key not in header:item['issue']='native key missing';issues.append(item['name']);continue
        if ext:
            if ext['location']!='model.data' or t.data_type!=onnx.TensorProto.FLOAT:raise ValueError('unexpected external format')
            exported=np.memmap(ARCHIVE/'model.data',dtype='<f4',mode='r',offset=int(ext['offset']),shape=tuple(dims))
        else:exported=onnx.numpy_helper.to_array(t)
        source=native_tensor(key);source_dtype=header[key]['dtype'];scale_key=key+'_scale';scale=None;bits=None
        if scale_key in header:
            scale=native_tensor(scale_key);bits=inventory[key.removesuffix('.weight')]['num_bits']
        mismatch=0;count=0;maximum=0.;eh=hashlib.sha256();sh=hashlib.sha256()
        # The unquantized model-projection initializer is transposed, only55MB.
        # Compare native output rows in blocks while reading corresponding ONNX columns.
        row_count=source.shape[0] if mapping.get('transpose') else (dims[0] if dims else 1)
        for start in range(0,row_count,128):
            stop=min(start+128,row_count);first=mapping['start_row']+start;last=mapping['start_row']+stop
            if not dims:
                wanted=as_float(source,source_dtype).reshape(1);actual=np.asarray(exported).reshape(1)
            else:
                raw=source[first:last]
                if bits:
                    if bits==8:q=np.asarray(raw,dtype=np.int8)
                    else:q=np.stack([((raw>>shift)&((1<<bits)-1)).astype(np.int8)-(1<<(bits-1)) for shift in range(0,8,bits)],axis=-1).reshape(raw.shape[0],-1)
                    wanted=q.astype(np.float32)*np.asarray(scale[first:last],dtype=np.float32)
                else:wanted=as_float(raw,source_dtype)
                actual=np.asarray(exported[:,start:stop]).T if mapping.get('transpose') else np.asarray(exported[start:stop]).reshape(wanted.shape)
            if actual.shape!=wanted.shape:raise ValueError('shape mismatch '+t.name)
            bad=int(np.count_nonzero(actual!=wanted));mismatch+=bad;count+=actual.size
            if bad:maximum=max(maximum,float(np.max(np.abs(actual-wanted))))
            eh.update(np.ascontiguousarray(actual).tobytes());sh.update(np.ascontiguousarray(wanted).tobytes())
            if time.monotonic()-started>260:raise TimeoutError('static weight budget')
        item.update(classification='mapped native F32 dequant/cast',source_dtype=source_dtype,native_bits=bits,values_checked=count,mismatching_values=mismatch,max_abs_error=maximum,export_comparison_order_sha256=eh.hexdigest(),native_comparison_order_sha256=sh.hexdigest(),equal=mismatch==0)
        if mismatch:issues.append(item['name'])
        (out/'progress.json').write_text(json.dumps({'initializers_processed':len(rows),'seconds':time.monotonic()-started})+'\n')
    result={'classification':'active_export_weight_static_mapping','neural_forward_calls':0,'adb_calls':0,'checkpoint_sha256':EXPECTED,'export_graph_sha256':sha(ARCHIVE/'model_dynamic.onnx'),'export_data_sha256':sha(ARCHIVE/'model.data'),'passed':not issues,'issues':issues,'active_initializer_count':len(active),'mapped_count':sum(x.get('classification')=='mapped native F32 dequant/cast' for x in rows),'structural_constant_count':sum(x.get('classification')=='inline structural constant' for x in rows),'mapped_values':sum(x.get('values_checked',0) for x in rows),'entries':rows,'seconds':time.monotonic()-started,'boundary':'F32 dequant/cast and structural mapping, not BF16/SRQ8 execution equivalence, quantized-DLC weights, producer provenance, or DSP-kernel proof.'}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='entries'},indent=2))


if __name__=='__main__':main()
