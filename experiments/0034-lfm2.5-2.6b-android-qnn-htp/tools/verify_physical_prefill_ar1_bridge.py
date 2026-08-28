#!/usr/bin/env python3
"""Bridge retained physical AR171 state into AR1 and compare CPU continuations."""
import argparse,hashlib,json,struct,time
from pathlib import Path
import numpy as np,onnxruntime as ort
ATTN={2,5,9,13,17,21,24,27};H=2048;CAP=4096;VOCAB=128000;EMBED='/model/embed_tokens/GatherBlockQuantized/output_0';N=171
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def metric(a,b):
 d=np.abs(a.astype(np.float32)-b.astype(np.float32));return {'elements':int(d.size),'max_abs':float(d.max()),'mean_abs':float(d.mean()),'allclose_rtol_0_02_atol_0_02':bool(np.allclose(a,b,rtol=.02,atol=.02)),'finite':bool(np.isfinite(a).all() and np.isfinite(b).all())}
def emb(ids,q,s,z):
 o=np.empty((1,len(ids),H),np.float32)
 for r,t in enumerate(ids):
  u=np.empty(H,np.float32);u[::2]=q[t]&15;u[1::2]=q[t]>>4;zp=np.empty(64,np.float32);zp[::2]=z[t]&15;zp[1::2]=z[t]>>4;o[0,r]=(u-np.repeat(zp,32))*np.repeat(s[t],32)
 return o
def names():
 x=[]
 for i in range(30):x += [f'present.{i}.key',f'present.{i}.value'] if i in ATTN else [f'present_conv.{i}']
 return x
def physical_file(root,name):return root/(name.replace('.','_').replace('/','_')+'.raw')
def zero_ar1():return ({i:np.zeros((1,H,3),np.float32) for i in range(30) if i not in ATTN},{i:np.zeros((1,8,64,CAP-1),np.float32) for i in ATTN},{i:np.zeros((1,8,CAP-1,64),np.float32) for i in ATTN})
def ar1_step(sess,token,pos,conv,key,val,q,s,z,state_names,log_names):
 f={EMBED:emb([token],q,s,z),'position_ids':np.asarray([[pos]],np.int64)};mask=np.full((1,1,1,CAP),-65504,np.float32);mask[0,0,0,:pos]=0;mask[0,0,0,-1]=0;f['attention_mask']=mask
 for i in range(30):
  if i in ATTN:f[f'past_key_values.{i}.key']=key[i];f[f'past_key_values.{i}.value']=val[i]
  else:f[f'past_conv.{i}']=conv[i]
 vals=sess.run(state_names+log_names,f);d=dict(zip(state_names+log_names,vals));
 for i in range(30):
  if i in ATTN:key[i][:,:,:,pos:pos+1]=d[f'present.{i}.key'];val[i][:,:,pos:pos+1,:]=d[f'present.{i}.value']
  else:conv[i]=d[f'present_conv.{i}']
 return d,np.concatenate([d[x] for x in log_names],axis=-1)
def compare_states(a,b):
 out=[]
 for n in names():out.append({'name':n,**metric(a[n],b[n])})
 return {'tensor_count':len(out),'allclose_count':sum(x['allclose_rtol_0_02_atol_0_02'] for x in out),'max_abs':max(x['max_abs'] for x in out),'mean_abs_max':max(x['mean_abs'] for x in out),'details':out}
ap=argparse.ArgumentParser();ap.add_argument('--physical-output-dir',type=Path,required=True);ap.add_argument('--ar171-model',type=Path,required=True);ap.add_argument('--ar1-model',type=Path,required=True);ap.add_argument('--token-file',type=Path,required=True);ap.add_argument('--embedding-dir',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();ids=np.asarray(struct.unpack('<%di'%(a.token_file.stat().st_size//4),a.token_file.read_bytes())[:N],np.int32);q=np.memmap(a.embedding_dir/'embedding-quant.u8',np.uint8,'r',shape=(VOCAB,1024));s=np.memmap(a.embedding_dir/'embedding-scales.f32le',np.float32,'r',shape=(VOCAB,64));z=np.memmap(a.embedding_dir/'embedding-zp.u8',np.uint8,'r',shape=(VOCAB,32));state_names=names();op=ort.SessionOptions();op.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;t=time.time();chunk=ort.InferenceSession(str(a.ar171_model),op,providers=['CPUExecutionProvider']);ar1=ort.InferenceSession(str(a.ar1_model),op,providers=['CPUExecutionProvider']);create=time.time()-t;chunk_logs=[x.name for x in chunk.get_outputs() if x.name.startswith('logits_vocab_')];ar1_logs=[x.name for x in ar1.get_outputs() if x.name.startswith('logits_vocab_')]
# CPU AR171 state and endpoint logits.
past=CAP-N;cf={EMBED:emb(ids,q,s,z),'position_ids':np.arange(N,dtype=np.int64)[None,:]};mask=np.full((1,1,N,CAP),-65504,np.float32)
for r in range(N):mask[0,0,r,past:past+r+1]=0
cf['attention_mask']=mask
for i in range(30):
 if i in ATTN:cf[f'past_key_values.{i}.key']=np.zeros((1,8,64,past),np.float32);cf[f'past_key_values.{i}.value']=np.zeros((1,8,past,64),np.float32)
 else:cf[f'past_conv.{i}']=np.zeros((1,H,3),np.float32)
t=time.time();vals=chunk.run(state_names+chunk_logs,cf);chunk_s=time.time()-t;cpu_chunk=dict(zip(state_names+chunk_logs,vals));cpu_chunk_logits=np.concatenate([cpu_chunk[x] for x in chunk_logs],axis=-1)
# Retained physical AR171 state.
physical={n:np.fromfile(physical_file(a.physical_output_dir,n),np.float32).reshape(cpu_chunk[n].shape) for n in state_names};phys_logs=[]
for n in chunk_logs:phys_logs.append(np.fromfile(physical_file(a.physical_output_dir,n),np.float32).reshape(cpu_chunk[n].shape))
physical_logits=np.concatenate(phys_logs,axis=-1)
# Sequential accepted AR1 state through the same prompt.
sc,sk,sv=zero_ar1();t=time.time();seq_last=None
for p,tok in enumerate(ids):seq_last,seq_logits=ar1_step(ar1,int(tok),p,sc,sk,sv,q,s,z,state_names,ar1_logs)
seq_s=time.time()-t
# Materialize each bridge source in the accepted AR1 cache contract.
def bridge_state(source):
 c,k,v=zero_ar1()
 for i in range(30):
  if i in ATTN:k[i][:,:,:,:N]=source[f'present.{i}.key'];v[i][:,:,:N,:]=source[f'present.{i}.value']
  else:c[i]=source[f'present_conv.{i}'].copy()
 return c,k,v
pc,pk,pv=bridge_state(physical);cc,ck,cv=bridge_state(cpu_chunk);sources={}
for label,c,k,v in [('physical_ar171',pc,pk,pv),('cpu_ar171',cc,ck,cv),('sequential_ar1',sc,sk,sv)]:
 t=time.time();out,logits=ar1_step(ar1,597,N,c,k,v,q,s,z,state_names,ar1_logs);sources[label]={'seconds':time.time()-t,'state':out,'logits':logits,'argmax':int(np.argmax(logits))}
# Pre-bridge physical fidelity and continuation pairwise comparisons.
pre=compare_states(physical,cpu_chunk);pre_logits_cpu_chunk=metric(physical_logits,cpu_chunk_logits);pre_logits_seq_ar1=metric(physical_logits,seq_logits)
key2_physical=physical['present.2.key'];key2_cpu=cpu_chunk['present.2.key'];key2_diff=np.abs(key2_physical-key2_cpu);flat_order=np.argsort(key2_diff.reshape(-1))[-16:][::-1]
key2_outliers={'physical_range':[float(key2_physical.min()),float(key2_physical.max())],'cpu_range':[float(key2_cpu.min()),float(key2_cpu.max())],'physical_quantiles':{str(qv):float(np.quantile(key2_physical,qv)) for qv in (0,.001,.01,.5,.99,.999,1)},'cpu_quantiles':{str(qv):float(np.quantile(key2_cpu,qv)) for qv in (0,.001,.01,.5,.99,.999,1)},'abs_diff_quantiles':{str(qv):float(np.quantile(key2_diff,qv)) for qv in (0,.5,.9,.99,.999,1)},'physical_abs_threshold_counts':{str(v):int((np.abs(key2_physical)>v).sum()) for v in (10,20,100,1000)},'abs_diff_threshold_counts':{str(v):int((key2_diff>v).sum()) for v in (.02,.1,1,10,100,1000)},'top_abs_diff_indices':[{'flat_index':int(i),'index':[int(v) for v in np.unravel_index(int(i),key2_diff.shape)],'physical':float(key2_physical.reshape(-1)[i]),'cpu':float(key2_cpu.reshape(-1)[i]),'abs_diff':float(key2_diff.reshape(-1)[i])} for i in flat_order]}
pairs={}
for left,right in [('physical_ar171','cpu_ar171'),('physical_ar171','sequential_ar1'),('cpu_ar171','sequential_ar1')]:
 sm=compare_states(sources[left]['state'],sources[right]['state']);lm=metric(sources[left]['logits'],sources[right]['logits']);pairs[f'{left}_vs_{right}']={'state':sm,'logits':lm,'argmax_left':sources[left]['argmax'],'argmax_right':sources[right]['argmax'],'argmax_equal':sources[left]['argmax']==sources[right]['argmax']}
r={'schema_version':1,'classification':'host_cpu_ar171_physical_state_to_ar1_bridge_validation','physical_output_binding':{'directory':str(a.physical_output_dir),'state_files':38,'logit_files':22,'all_finite':bool(all(np.isfinite(x).all() for x in physical.values()) and np.isfinite(physical_logits).all()),'endpoint_argmax':int(np.argmax(physical_logits))},'models':{'ar171_sha256':sha(a.ar171_model),'ar1_sha256':sha(a.ar1_model),'token_file_sha256':sha(a.token_file)},'session_create_seconds':create,'cpu_ar171_seconds':chunk_s,'sequential_ar1_171_seconds':seq_s,'bridge':{'token':597,'position':171,'mask':'zeros for valid cache positions 0:171 and current final slot; finite-negative elsewhere','kv_placement':'AR171 171-position slices copied into AR1 left-aligned cache 0:171; remaining 3924 positions zero','conv_placement':'all 22 physical/CPU convolution states carried directly','all_sources_argmax':{k:v['argmax'] for k,v in sources.items()},'all_argmax_equal':len({v['argmax'] for v in sources.values()})==1,'source_seconds':{k:v['seconds'] for k,v in sources.items()}},'pre_bridge_physical_vs_cpu_ar171_state':pre,'pre_bridge_endpoint_logits':{'physical_vs_cpu_ar171':pre_logits_cpu_chunk,'physical_vs_sequential_ar1':pre_logits_seq_ar1,'physical_argmax':int(np.argmax(physical_logits)),'cpu_ar171_argmax':int(np.argmax(cpu_chunk_logits)),'sequential_ar1_argmax':int(np.argmax(seq_logits))},'present_2_key_outliers':key2_outliers,'retained_sequential_physical_ar1_state':{'available':False,'reason':'Accepted physical AR1 runners retained state only in process memory and preserved generated token output, not raw 38-state tensors; cleanup ended the process.'},'continuation_comparisons':pairs,'fidelity_boundary':'All numeric state/logit deltas are retained. Endpoint greedy equality is not numerical equivalence or broad output fidelity.','claim_boundary':'Host CPU bridge validation using retained physical prefill state. No new phone/HTP execution or performance campaign.'};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({'physical_endpoint':r['physical_output_binding']['endpoint_argmax'],'bridge_argmax':r['bridge']['all_sources_argmax'],'bridge_all_equal':r['bridge']['all_argmax_equal'],'pre_state':{k:pre[k] for k in ('allclose_count','tensor_count','max_abs','mean_abs_max')},'pre_logits':{'physical_vs_cpu_max':pre_logits_cpu_chunk['max_abs'],'physical_vs_seq_max':pre_logits_seq_ar1['max_abs']},'present2_outliers':key2_outliers['abs_diff_threshold_counts'],'pairs':{k:{'argmax':v['argmax_left'],'state_max':v['state']['max_abs'],'logit_max':v['logits']['max_abs']} for k,v in pairs.items()}},indent=2))
