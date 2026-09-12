#!/usr/bin/env python3
"""Static full-output-head source fidelity audit; NO model forward or ADB.

The exported config says tied embeddings whereas the pinned QAT config says
untied. Check actual exported head values, not just that metadata discrepancy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time
import numpy as np
import onnx

TRACK=Path(__file__).resolve().parents[1]
EXP=TRACK.parents[1]
CHECKPOINT=EXP/'.local/hf-checkpoint/model.safetensors'
EXPECTED_CHECKPOINT='efab429012b97ab986c4d4838a46ff3ad95d618b42ce514771ca40fadc76a9a4'
ARCHIVE=EXP/'.local/checkpoint/extracted/gemma_4_e2b_it_w4a16'
SOURCE=TRACK/'.local/same-source-reference-readiness/source-20260912-01'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(4*1024*1024),b''):h.update(data)
    return h.hexdigest()


def unpack2(packed):
    return np.stack([((packed>>s)&3).astype(np.int8)-2 for s in (0,2,4,6)],axis=-1).reshape(packed.shape[0],-1)


def bf16_round(x):
    x=np.asarray(x,dtype=np.float32)
    if not np.isfinite(x).all():raise ValueError('nonfinite values outside this finite-weight audit')
    u=x.view(np.uint32);v=(u+np.uint32(0x7fff)+((u>>16)&1))&np.uint32(0xffff0000)
    return v.view(np.float32)


def candidates(q,scale):
    integers=unpack2(q).astype(np.float32)
    return {'f32':integers*scale,'bf16_forward':bf16_round(integers*bf16_round(scale))}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to((TRACK/'.local/same-source-reference-readiness').resolve()):ap.error('owned fresh private output required')
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    if sha(CHECKPOINT)!=EXPECTED_CHECKPOINT:raise ValueError('source checkpoint changed')
    with CHECKPOINT.open('rb') as f:
        header_len=struct.unpack('<Q',f.read(8))[0]
        if header_len>8*1024*1024:raise ValueError('unbounded checkpoint header')
        header=json.loads(f.read(header_len))
    origin=8+header_len
    def tensor(name):
        row=header[name];dt={'U8':'u1','F32':'<f4'}[row['dtype']]
        return np.memmap(CHECKPOINT,dtype=dt,mode='r',offset=origin+row['data_offsets'][0],shape=tuple(row['shape']))
    q=tensor('lm_head.weight');scale=tensor('lm_head.weight_scale')
    emb=tensor('model.language_model.embed_tokens.embedding_quantized');embscale=tensor('model.language_model.embed_tokens.embedding_scale')
    if q.shape!=(262144,384) or emb.shape!=q.shape or scale.shape!=(262144,1) or embscale.shape!=scale.shape:raise ValueError('unexpected source shapes')
    graph_path=ARCHIVE/'model_dynamic.onnx';model=onnx.load(str(graph_path),load_external_data=False)
    found=[t for t in model.graph.initializer if t.name=='model.lm_head.weight']
    if len(found)!=1:raise ValueError('output head initializer ambiguous')
    t=found[0];ext={v.key:v.value for v in t.external_data}
    if list(t.dims)!=[262144,1536,1,1] or t.data_type!=onnx.TensorProto.FLOAT or ext.get('location')!='model.data' or int(ext['length'])!=262144*1536*4:raise ValueError('head external-data layout changed')
    exported=np.memmap(ARCHIVE/'model.data',dtype='<f4',mode='r',offset=int(ext['offset']),shape=(262144,1536))
    metrics={k:{'mismatching_values':0,'max_abs_error':0.0} for k in ('head_f32','head_bf16_forward','embedding_f32','embedding_bf16_forward')}
    dig=hashlib.sha256();source_dig={k:hashlib.sha256() for k in metrics}
    for begin in range(0,262144,256):
        end=begin+256;actual=np.asarray(exported[begin:end]);dig.update(actual.tobytes())
        expected={'head_'+k:v for k,v in candidates(q[begin:end],scale[begin:end]).items()}
        expected.update({'embedding_'+k:v for k,v in candidates(emb[begin:end],embscale[begin:end]).items()})
        for k,value in expected.items():
            source_dig[k].update(value.tobytes());metrics[k]['mismatching_values']+=int(np.count_nonzero(actual!=value));metrics[k]['max_abs_error']=max(metrics[k]['max_abs_error'],float(np.max(np.abs(actual-value))))
        if begin%16384==0:
            (out/'progress.json').write_text(json.dumps({'rows_checked':end,'elapsed_seconds':time.monotonic()-started})+'\n')
        if time.monotonic()-started>160:raise TimeoutError('static audit wall budget')
    for k in metrics:metrics[k]['dequantized_f32_bytes_sha256']=source_dig[k].hexdigest();metrics[k]['exact_equal']=metrics[k]['mismatching_values']==0
    scales=[]
    with CHECKPOINT.open('rb') as f:
        for name,row in header.items():
            if (name.startswith('model.language_model.') or name.startswith('lm_head.')) and name.endswith(('input_activation_scale','output_activation_scale')):
                if row['dtype']!='F32' or row['shape']!=[]:raise ValueError('unexpected SRQ scale shape')
                f.seek(origin+row['data_offsets'][0]);scales.append(struct.unpack('<f',f.read(4))[0])
    official=json.loads((SOURCE/'config.json').read_text());export_config=json.loads((ARCHIVE/'config.json').read_text())
    result={'classification':'static_same_source_head_fidelity_audit','model_forward_or_inference':False,'adb_calls':0,'rows':262144,'values':262144*1536,'source_checkpoint_sha256':EXPECTED_CHECKPOINT,'checkpoint_bytes':CHECKPOINT.stat().st_size,'checkpoint_header_bytes':header_len,'checkpoint_tensor_count':len(header)-('__metadata__' in header),'source_config_sha256':sha(SOURCE/'config.json'),'source_quant_code_sha256':sha(SOURCE/'gemma_quant.py'),'export_graph_sha256':sha(graph_path),'export_head_region':ext,'export_head_region_sha256':dig.hexdigest(),'export_config_tie_word_embeddings':export_config['tie_word_embeddings'],'source_config_tie_word_embeddings':official['tie_word_embeddings'],'source_lm_head_bits':official['quantization_config']['module_quant_configs']['^lm_head$']['num_bits'],'comparisons':metrics,'text_and_head_SRQ_scale_count':len(scales),'nonzero_SRQ_scales':sum(x!=0 for x in scales),'seconds':time.monotonic()-started,'limits':'Original float ONNX head only, not DLC quantized arithmetic/HTP kernels, whole-model fidelity or a causal explanation of repetition. BF16-forward candidate rounds scale first, then product as the pinned source does.'}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
