#!/usr/bin/env python3
"""Compare chunk-lowered prefill state/logits against the trusted GQA CPU graph."""
import argparse,hashlib,json,struct,time
from pathlib import Path
import numpy as np,onnxruntime as ort
ATTN={2,5,9,13,17,21,24,27};H=2048;CAP=4096;VOCAB=128000
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def metrics(a,b):
 d=np.abs(a.astype(np.float32)-b.astype(np.float32));return {'elements':int(d.size),'max_abs':float(d.max()),'mean_abs':float(d.mean()),'allclose_rtol_0_02_atol_0_02':bool(np.allclose(a,b,rtol=.02,atol=.02)),'finite':bool(np.isfinite(a).all() and np.isfinite(b).all())}
def embeddings(ids,quant,scales,zps):
 out=np.empty((1,len(ids),H),np.float32)
 for row,t in enumerate(ids):
  q=quant[t];s=scales[t];zp=zps[t]
  for block in range(64):
   z=float((zp[block//2] >> (4 if block&1 else 0))&15)
   for i in range(32):
    j=block*32+i;out[0,row,j]=(float((q[j//2] >> (4 if j&1 else 0))&15)-z)*s[block]
 return out
ap=argparse.ArgumentParser();ap.add_argument('--reference-model',type=Path,required=True);ap.add_argument('--candidate-model',type=Path,required=True);ap.add_argument('--token-file',type=Path,required=True);ap.add_argument('--embedding-dir',type=Path,required=True);ap.add_argument('--sequence-length',type=int,required=True);ap.add_argument('--steps',type=int,default=1);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();N=a.sequence_length;past=CAP-N;raw=a.token_file.read_bytes();tokens=list(struct.unpack('<%di'%(len(raw)//4),raw));need=N*a.steps
if len(tokens)<need or need>past:raise SystemExit('invalid token/step span')
q=np.memmap(a.embedding_dir/'embedding-quant.u8',np.uint8,'r',shape=(VOCAB,1024));s=np.memmap(a.embedding_dir/'embedding-scales.f32le',np.float32,'r',shape=(VOCAB,64));z=np.memmap(a.embedding_dir/'embedding-zp.u8',np.uint8,'r',shape=(VOCAB,32));opt=ort.SessionOptions();opt.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;t=time.time();ref=ort.InferenceSession(str(a.reference_model),opt,providers=['CPUExecutionProvider']);cand=ort.InferenceSession(str(a.candidate_model),opt,providers=['CPUExecutionProvider']);create=time.time()-t
conv={i:np.zeros((1,H,3),np.float32) for i in range(30) if i not in ATTN};key={i:np.zeros((1,8,64,past),np.float32) for i in ATTN};value={i:np.zeros((1,8,past,64),np.float32) for i in ATTN};steps=[]
state_names=[]
for i in range(30):state_names += [f'present.{i}.key',f'present.{i}.value'] if i in ATTN else [f'present_conv.{i}']
logits_names=[x.name for x in cand.get_outputs() if x.name.startswith('logits_vocab_')];ref_logits_names=[x.name for x in ref.get_outputs() if x.name.startswith('logits_vocab_')];ref_uses_cpu_embedding=any(x.name=='/model/embed_tokens/GatherBlockQuantized/output_0' for x in ref.get_inputs())
for step in range(a.steps):
 base=step*N;ids=np.asarray(tokens[base:base+N],np.int32);pos=np.arange(base,base+N,dtype=np.int64)[None,:];embed=embeddings(ids,q,s,z);rf={'position_ids':pos,'seqlens_k':np.asarray([base+N-1],np.int32)};rf['/model/embed_tokens/GatherBlockQuantized/output_0' if ref_uses_cpu_embedding else 'input_ids']=embed if ref_uses_cpu_embedding else ids[None,:];cf={'/model/embed_tokens/GatherBlockQuantized/output_0':embed,'position_ids':pos};mask=np.full((1,1,N,CAP),-65504,np.float32)
 for r in range(N):mask[0,0,r,:base]=0;mask[0,0,r,past:past+r+1]=0
 cf['attention_mask']=mask
 for i in range(30):
  if i in ATTN:rf[f'past_key_values.{i}.key']=key[i].transpose(0,1,3,2);rf[f'past_key_values.{i}.value']=value[i];cf[f'past_key_values.{i}.key']=key[i];cf[f'past_key_values.{i}.value']=value[i]
  else:rf[f'past_conv.{i}']=conv[i];cf[f'past_conv.{i}']=conv[i]
 ref_requested=(ref_logits_names if ref_logits_names else ['logits'])+state_names;t=time.time();rr=ref.run(ref_requested,rf);rt=time.time()-t;t=time.time();cr=cand.run(state_names+logits_names,cf);ct=time.time()-t;ref_logit_count=len(ref_logits_names) or 1;rd={'logits':np.concatenate(rr[:ref_logit_count],axis=-1) if ref_logits_names else rr[0],**dict(zip(state_names,rr[ref_logit_count:]))};cd=dict(zip(state_names+logits_names,cr));state=[]
 for i in range(30):
  if i in ATTN:
   # GQA writes the newly valid positions into the left-aligned logical
   # cache, while the standard-op candidate returns only this chunk's slices.
   rk=rd[f'present.{i}.key'][:,:,base:base+N,:].transpose(0,1,3,2);rv=rd[f'present.{i}.value'][:,:,base:base+N,:];ck=cd[f'present.{i}.key'];cv=cd[f'present.{i}.value'];state += [metrics(rk,ck),metrics(rv,cv)];key[i][:,:,:,base:base+N]=ck;value[i][:,:,base:base+N,:]=cv
  else:
   state.append(metrics(rd[f'present_conv.{i}'],cd[f'present_conv.{i}']));conv[i]=cd[f'present_conv.{i}']
 cl=np.concatenate([cd[x] for x in logits_names],axis=-1);rl=rd['logits'][:,-1:,:];ra=int(np.argmax(rl));ca=int(np.argmax(cl));ld=metrics(rl,cl);steps.append({'step':step,'base_position':base,'tokens':ids.tolist(),'reference_seconds':rt,'candidate_seconds':ct,'state_allclose_count':sum(x['allclose_rtol_0_02_atol_0_02'] for x in state),'state_tensor_count':len(state),'state_max_abs':max(x['max_abs'] for x in state),'state_mean_abs_max':max(x['mean_abs'] for x in state),'reference_argmax':ra,'candidate_argmax':ca,'argmax_equal':ra==ca,'logits':ld})
r={'schema_version':1,'classification':'cpu_chunk_prefill_semantic_comparison','sequence_length':N,'steps':a.steps,'positions_covered':need,'reference_model_sha256':sha(a.reference_model),'candidate_model_sha256':sha(a.candidate_model),'token_file_sha256':sha(a.token_file),'session_create_seconds':create,'all_step_argmax_equal':all(x['argmax_equal'] for x in steps),'all_state_tensors_close':all(x['state_allclose_count']==x['state_tensor_count'] for x in steps),'steps_detail':steps,'state_semantics':f'Each candidate returns {N} new K/V positions; caller writes them left-aligned at base:base+N and carries all 38 states to the next chunk.','claim_boundary':'CPU semantic/fidelity comparison only; no QNN compilation, HTP execution, or performance claim.'};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({'ar':N,'steps':a.steps,'argmax':r['all_step_argmax_equal'],'states_close':r['all_state_tensors_close'],'details':steps},indent=2))
