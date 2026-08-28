#!/usr/bin/env python3
"""Compare one chunked-prefill CPU call with N sequential accepted AR1 CPU calls."""
import argparse,hashlib,json,struct,time
from pathlib import Path
import numpy as np,onnxruntime as ort
ATTN={2,5,9,13,17,21,24,27};H=2048;CAP=4096;VOCAB=128000;EMBED='/model/embed_tokens/GatherBlockQuantized/output_0'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def metric(a,b):
 d=np.abs(a.astype(np.float32)-b.astype(np.float32));return {'elements':int(d.size),'max_abs':float(d.max()),'mean_abs':float(d.mean()),'allclose_rtol_0_02_atol_0_02':bool(np.allclose(a,b,rtol=.02,atol=.02)),'finite':bool(np.isfinite(a).all() and np.isfinite(b).all())}
def embed(ids,q,s,z):
 o=np.empty((1,len(ids),H),np.float32)
 for r,t in enumerate(ids):
  for b in range(64):
   zp=float((z[t,b//2]>>(4 if b&1 else 0))&15)
   for i in range(32):
    j=b*32+i;o[0,r,j]=(float((q[t,j//2]>>(4 if j&1 else 0))&15)-zp)*s[t,b]
 return o
ap=argparse.ArgumentParser();ap.add_argument('--ar1-model',type=Path,required=True);ap.add_argument('--chunk-model',type=Path,required=True);ap.add_argument('--token-file',type=Path,required=True);ap.add_argument('--embedding-dir',type=Path,required=True);ap.add_argument('--sequence-length',type=int,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();N=a.sequence_length;ids=np.asarray(struct.unpack('<%di'%(a.token_file.stat().st_size//4),a.token_file.read_bytes())[:N],np.int32);q=np.memmap(a.embedding_dir/'embedding-quant.u8',np.uint8,'r',shape=(VOCAB,1024));s=np.memmap(a.embedding_dir/'embedding-scales.f32le',np.float32,'r',shape=(VOCAB,64));z=np.memmap(a.embedding_dir/'embedding-zp.u8',np.uint8,'r',shape=(VOCAB,32));op=ort.SessionOptions();op.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;t=time.time();ar=ort.InferenceSession(str(a.ar1_model),op,providers=['CPUExecutionProvider']);ch=ort.InferenceSession(str(a.chunk_model),op,providers=['CPUExecutionProvider']);create=time.time()-t;states=[]
for i in range(30):states += [f'present.{i}.key',f'present.{i}.value'] if i in ATTN else [f'present_conv.{i}']
arlog=[x.name for x in ar.get_outputs() if x.name.startswith('logits_vocab_')];chlog=[x.name for x in ch.get_outputs() if x.name.startswith('logits_vocab_')];conv={i:np.zeros((1,H,3),np.float32) for i in range(30) if i not in ATTN};key={i:np.zeros((1,8,64,CAP-1),np.float32) for i in ATTN};val={i:np.zeros((1,8,CAP-1,64),np.float32) for i in ATTN};t=time.time();last=None
for p,tok in enumerate(ids):
 f={EMBED:embed([tok],q,s,z),'position_ids':np.asarray([[p]],np.int64)};mask=np.full((1,1,1,CAP),-65504,np.float32);mask[0,0,0,:p]=0;mask[0,0,0,-1]=0;f['attention_mask']=mask
 for i in range(30):
  if i in ATTN:f[f'past_key_values.{i}.key']=key[i];f[f'past_key_values.{i}.value']=val[i]
  else:f[f'past_conv.{i}']=conv[i]
 req=states+(arlog if p==N-1 else []);out=ar.run(req,f);d=dict(zip(req,out));
 for i in range(30):
  if i in ATTN:key[i][:,:,:,p:p+1]=d[f'present.{i}.key'];val[i][:,:,p:p+1,:]=d[f'present.{i}.value']
  else:conv[i]=d[f'present_conv.{i}']
 last=d
ar_seconds=time.time()-t;past=CAP-N;cf={EMBED:embed(ids,q,s,z),'position_ids':np.arange(N,dtype=np.int64)[None,:]};mask=np.full((1,1,N,CAP),-65504,np.float32)
for r in range(N):mask[0,0,r,past:past+r+1]=0
cf['attention_mask']=mask
for i in range(30):
 if i in ATTN:cf[f'past_key_values.{i}.key']=np.zeros((1,8,64,past),np.float32);cf[f'past_key_values.{i}.value']=np.zeros((1,8,past,64),np.float32)
 else:cf[f'past_conv.{i}']=np.zeros((1,H,3),np.float32)
t=time.time();co=ch.run(states+chlog,cf);chunk_seconds=time.time()-t;cd=dict(zip(states+chlog,co));ms=[]
for i in range(30):
 if i in ATTN:ms += [{'name':f'present.{i}.key',**metric(key[i][:,:,:,:N],cd[f'present.{i}.key'])},{'name':f'present.{i}.value',**metric(val[i][:,:,:N,:],cd[f'present.{i}.value'])}]
 else:ms.append({'name':f'present_conv.{i}',**metric(conv[i],cd[f'present_conv.{i}'])})
al=np.concatenate([last[x] for x in arlog],axis=-1);cl=np.concatenate([cd[x] for x in chlog],axis=-1);lm=metric(al,cl);aa=int(np.argmax(al));ca=int(np.argmax(cl));res={'schema_version':1,'classification':'cpu_chunk_prefill_vs_sequential_ar1_fidelity','sequence_length':N,'tokens':ids.tolist(),'ar1_model_sha256':sha(a.ar1_model),'chunk_model_sha256':sha(a.chunk_model),'session_create_seconds':create,'sequential_ar1_seconds':ar_seconds,'chunk_seconds':chunk_seconds,'speedup_cpu_diagnostic':ar_seconds/chunk_seconds,'state_tensor_count':len(ms),'state_allclose_count':sum(x['allclose_rtol_0_02_atol_0_02'] for x in ms),'state_max_abs':max(x['max_abs'] for x in ms),'state_mean_abs_max':max(x['mean_abs'] for x in ms),'state_details':ms,'logits':lm,'sequential_ar1_argmax':aa,'chunk_argmax':ca,'argmax_equal':aa==ca,'state_semantics':'Sequential AR1 writes each returned K/V slice at its token position. Chunk prefill returns the same N positions in one slice; all convolution final states and attention slices are compared.','claim_boundary':'CPU fidelity and timing diagnostic only; no HTP compilation/execution or physical performance claim.'};a.output.write_text(json.dumps(res,indent=2,sort_keys=True)+'\n');print(json.dumps({k:res[k] for k in ('sequence_length','sequential_ar1_seconds','chunk_seconds','speedup_cpu_diagnostic','state_allclose_count','state_tensor_count','state_max_abs','state_mean_abs_max','sequential_ar1_argmax','chunk_argmax','argmax_equal','logits')},indent=2))
