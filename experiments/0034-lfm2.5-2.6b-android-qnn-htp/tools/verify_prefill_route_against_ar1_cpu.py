#!/usr/bin/env python3
"""Compare several carried chunk calls against sequential accepted AR1 at each boundary."""
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
def embeds(ids,q,s,z):
 o=np.empty((1,len(ids),H),np.float32)
 for r,t in enumerate(ids):
  for b in range(64):
   zp=float((z[t,b//2]>>(4 if b&1 else 0))&15)
   for i in range(32):
    j=b*32+i;o[0,r,j]=(float((q[t,j//2]>>(4 if j&1 else 0))&15)-zp)*s[t,b]
 return o
ap=argparse.ArgumentParser();ap.add_argument('--ar1-model',type=Path,required=True);ap.add_argument('--chunk-model',type=Path,required=True);ap.add_argument('--token-file',type=Path,required=True);ap.add_argument('--embedding-dir',type=Path,required=True);ap.add_argument('--sequence-length',type=int,required=True);ap.add_argument('--steps',type=int,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();N=a.sequence_length;total=N*a.steps;allids=struct.unpack('<%di'%(a.token_file.stat().st_size//4),a.token_file.read_bytes());ids=np.asarray(allids[:total],np.int32)
if total>CAP-N:raise SystemExit('span exceeds chunk cache')
q=np.memmap(a.embedding_dir/'embedding-quant.u8',np.uint8,'r',shape=(VOCAB,1024));s=np.memmap(a.embedding_dir/'embedding-scales.f32le',np.float32,'r',shape=(VOCAB,64));z=np.memmap(a.embedding_dir/'embedding-zp.u8',np.uint8,'r',shape=(VOCAB,32));op=ort.SessionOptions();op.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;t=time.time();ar=ort.InferenceSession(str(a.ar1_model),op,providers=['CPUExecutionProvider']);ch=ort.InferenceSession(str(a.chunk_model),op,providers=['CPUExecutionProvider']);create=time.time()-t;states=[]
for i in range(30):states += [f'present.{i}.key',f'present.{i}.value'] if i in ATTN else [f'present_conv.{i}']
arlog=[x.name for x in ar.get_outputs() if x.name.startswith('logits_vocab_')];chlog=[x.name for x in ch.get_outputs() if x.name.startswith('logits_vocab_')];ac={i:np.zeros((1,H,3),np.float32) for i in range(30) if i not in ATTN};ak={i:np.zeros((1,8,64,CAP-1),np.float32) for i in ATTN};av={i:np.zeros((1,8,CAP-1,64),np.float32) for i in ATTN};past=CAP-N;cc={i:np.zeros((1,H,3),np.float32) for i in range(30) if i not in ATTN};ck={i:np.zeros((1,8,64,past),np.float32) for i in ATTN};cv={i:np.zeros((1,8,past,64),np.float32) for i in ATTN};bounds=[]
for step in range(a.steps):
 base=step*N;chunk_ids=ids[base:base+N];t=time.time();last=None
 for off,tok in enumerate(chunk_ids):
  p=base+off;f={EMBED:embeds([tok],q,s,z),'position_ids':np.asarray([[p]],np.int64)};mask=np.full((1,1,1,CAP),-65504,np.float32);mask[0,0,0,:p]=0;mask[0,0,0,-1]=0;f['attention_mask']=mask
  for i in range(30):
   if i in ATTN:f[f'past_key_values.{i}.key']=ak[i];f[f'past_key_values.{i}.value']=av[i]
   else:f[f'past_conv.{i}']=ac[i]
  req=states+(arlog if off==N-1 else []);vals=ar.run(req,f);last=dict(zip(req,vals))
  for i in range(30):
   if i in ATTN:ak[i][:,:,:,p:p+1]=last[f'present.{i}.key'];av[i][:,:,p:p+1,:]=last[f'present.{i}.value']
   else:ac[i]=last[f'present_conv.{i}']
 arsec=time.time()-t;cf={EMBED:embeds(chunk_ids,q,s,z),'position_ids':np.arange(base,base+N,dtype=np.int64)[None,:]};mask=np.full((1,1,N,CAP),-65504,np.float32)
 for r in range(N):mask[0,0,r,:base]=0;mask[0,0,r,past:past+r+1]=0
 cf['attention_mask']=mask
 for i in range(30):
  if i in ATTN:cf[f'past_key_values.{i}.key']=ck[i];cf[f'past_key_values.{i}.value']=cv[i]
  else:cf[f'past_conv.{i}']=cc[i]
 t=time.time();vals=ch.run(states+chlog,cf);chsec=time.time()-t;cd=dict(zip(states+chlog,vals));valid=base+N;ms=[]
 for i in range(30):
  if i in ATTN:ck[i][:,:,:,base:valid]=cd[f'present.{i}.key'];cv[i][:,:,base:valid,:]=cd[f'present.{i}.value'];ms += [{'name':f'present.{i}.key','scope':f'valid_prefix_0_{valid}',**metric(ak[i][:,:,:,:valid],ck[i][:,:,:,:valid])},{'name':f'present.{i}.value','scope':f'valid_prefix_0_{valid}',**metric(av[i][:,:,:valid,:],cv[i][:,:,:valid,:])}]
  else:cc[i]=cd[f'present_conv.{i}'];ms.append({'name':f'present_conv.{i}','scope':'final_state',**metric(ac[i],cc[i])})
 al=np.concatenate([last[x] for x in arlog],axis=-1);cl=np.concatenate([cd[x] for x in chlog],axis=-1);lm=metric(al,cl);aa=int(np.argmax(al));ca=int(np.argmax(cl));bounds.append({'step':step,'boundary_position':valid,'sequential_ar1_seconds':arsec,'chunk_seconds':chsec,'state_tensor_count':len(ms),'state_allclose_count':sum(x['allclose_rtol_0_02_atol_0_02'] for x in ms),'state_max_abs':max(x['max_abs'] for x in ms),'state_mean_abs_max':max(x['mean_abs'] for x in ms),'state_details':ms,'logits':lm,'sequential_ar1_argmax':aa,'chunk_argmax':ca,'argmax_equal':aa==ca})
r={'schema_version':1,'classification':'cpu_carried_chunk_route_vs_sequential_ar1_at_each_boundary','sequence_length':N,'steps':a.steps,'total_tokens':total,'tokens':ids.tolist(),'ar1_model_sha256':sha(a.ar1_model),'chunk_model_sha256':sha(a.chunk_model),'session_create_seconds':create,'all_boundary_argmax_equal':all(x['argmax_equal'] for x in bounds),'boundaries':bounds,'state_semantics':'Both routes carry all 38 states. Every boundary compares the full valid attention-cache prefix plus each final convolution state.','claim_boundary':'CPU carried-state fidelity and timing diagnostics only; no HTP execution or physical performance claim.'};a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({'ar':N,'steps':a.steps,'all_argmax':r['all_boundary_argmax_equal'],'boundaries':[{k:x[k] for k in ('boundary_position','state_allclose_count','state_tensor_count','state_max_abs','state_mean_abs_max','sequential_ar1_argmax','chunk_argmax','argmax_equal','logits')} for x in bounds]},indent=2))
