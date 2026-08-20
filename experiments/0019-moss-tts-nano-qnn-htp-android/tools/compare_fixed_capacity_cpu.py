#!/usr/bin/env python3
import gc,json,math,time
from pathlib import Path
import numpy as np,onnxruntime as ort
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.local/specialized';E18=ROOT.parent/'0018-moss-tts-nano-onnx-android/.local';TTS=E18/'tts';CODEC=E18/'codec'
policy=json.load(open(ROOT/'protocol/fixed-capacity-equivalence-policy.json'));crit=policy['criteria'];rng=np.random.default_rng(20260818)
class JavaRandom:
 def __init__(self,seed):self.seed=(seed^0x5DEECE66D)&((1<<48)-1)
 def next(self,bits):self.seed=(self.seed*0x5DEECE66D+0xB)&((1<<48)-1);return self.seed>>(48-bits)
 def next_double(self):return ((self.next(26)<<27)+self.next(27))/float(1<<53)
def sess(path):
 o=ort.SessionOptions();o.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;o.intra_op_num_threads=4;o.inter_op_num_threads=1
 return ort.InferenceSession(str(path),o,providers=['CPUExecutionProvider'])
class Stats:
 def __init__(self):self.count=0;self.sq=0.;self.dot=0.;self.aa=0.;self.bb=0.;self.max=0.;self.finite=True
 def add(self,a,b):
  x=np.asarray(a,dtype=np.float64);y=np.asarray(b,dtype=np.float64);assert x.shape==y.shape;d=x-y;self.count+=d.size;self.sq+=float(np.sum(d*d));self.dot+=float(np.sum(x*y));self.aa+=float(np.sum(x*x));self.bb+=float(np.sum(y*y));self.max=max(self.max,float(np.max(np.abs(d))) if d.size else 0.);self.finite &= bool(np.isfinite(x).all() and np.isfinite(y).all())
 def result(self):return {'elements':self.count,'max_abs':self.max,'rmse':math.sqrt(self.sq/self.count) if self.count else 0.,'cosine':self.dot/math.sqrt(self.aa*self.bb) if self.aa and self.bb else 1.,'finite':self.finite}
def passed(x):return x['finite'] and x['max_abs']<=crit['float_max_abs_error_lte'] and x['rmse']<=crit['float_rmse_lte'] and x['cosine']>=crit['float_cosine_gte']
# Exact prompt rows.
man=json.load(open(TTS/'browser_poc_manifest.json'));cfg=man['tts_config'];tok=json.load(open(ROOT/'protocol/canonical-v2-tokenization.json'))['token_ids'];voice=next(x for x in man['builtin_voices'] if x['voice']=='Junhao');rows=[]
prefix=man['prompt_templates']['user_prompt_prefix_token_ids']+[cfg['audio_start_token_id']];suffix=[cfg['audio_end_token_id']]+man['prompt_templates']['user_prompt_after_reference_token_ids']+tok+man['prompt_templates']['assistant_prompt_prefix_token_ids']+[cfg['audio_start_token_id']]
for t in prefix:rows.append([t]+[cfg['audio_pad_token_id']]*16)
for codes in voice['prompt_audio_codes']:rows.append([cfg['audio_user_slot_token_id']]+codes[:16])
for t in suffix:rows.append([t]+[cfg['audio_pad_token_id']]*16)
assert len(rows)==226
# Prefill once, retaining initial dynamic K/V.
t0=time.monotonic();pre=sess(S/'prefill-s226-qnn.onnx');pnames=[x.name for x in pre.get_outputs()];pout=pre.run(pnames,{'input_ids':np.asarray([rows],np.int32),'attention_mask':np.ones((1,226),np.int32)});del pre;gc.collect();pm=dict(zip(pnames,pout));global_hidden=pm['global_hidden'][:,-1,:].copy();dyn=[];fixed=[]
for i in range(12):
 for kind in ['key','value']:
  a=pm[f'present_{kind}_{i}'];dyn.append(a);state=np.zeros((1,601,12,64),np.float32);state[:,:226]=a;fixed.append(state)
del pm,pout;gc.collect()
dynamic=sess(TTS/'moss_tts_decode_step.onnx');fixed_s=sess(S/'decode-fixed-cap600-attention-qnn.onnx');local=sess(S/'local-fixed-b1.onnx');dout=[x.name for x in dynamic.get_outputs()];fout=[x.name for x in fixed_s.get_outputs()];lin=[x.name for x in local.get_inputs()];lout=[x.name for x in local.get_outputs()]
din=[x.name for x in dynamic.get_inputs()][2:];fin=[x.name for x in fixed_s.get_inputs()][2:];assert din==fin and len(din)==24
java=JavaRandom(20260818);seen=[set() for _ in range(16)];tokens=[];hidden_stats=Stats();kv_new_stats=Stats();markers={};observed_stop=None
for step in range(375):
 valid=226+step;assert valid<=600
 if observed_stop is None:
  mask=np.zeros((1,16,1024),np.int32)
  for q,s in enumerate(seen):
   if s:mask[0,q,list(s)]=1
  au=np.asarray([min(max(java.next_double(),1e-6),1-1e-6)],np.float32);ru=np.asarray([[min(max(java.next_double(),1e-6),1-1e-6) for _ in range(16)]],np.float32)
  lo=dict(zip(lout,local.run(lout,{'global_hidden':global_hidden,'repetition_seen_mask':mask,'assistant_random_u':au,'audio_random_u':ru})))
  cont=int(np.asarray(lo['should_continue']).ravel()[0])>0;frame=np.asarray(lo['frame_token_ids'],np.int32).reshape(-1)[:16]
  if not cont:observed_stop=step
 if observed_stop is None:
  frame=frame.copy();tokens.append(frame.tolist());[seen[q].add(int(frame[q])) for q in range(16)]
 else:
  # Exercise every remaining ABI state transition even though the reference CPU sampler stopped.
  frame=rng.integers(0,1024,16,dtype=np.int32)
 row=np.concatenate([np.asarray([cfg['audio_assistant_slot_token_id']],np.int32),frame]).reshape(1,1,17);length=np.asarray([valid],np.int32)
 feeds={'input_ids':row,'past_valid_lengths':length};feeds.update(zip(din,dyn));do=dict(zip(dout,dynamic.run(dout,feeds)))
 ffeeds={'input_ids':row,'past_valid_lengths':length};ffeeds.update((name,state[:,:600]) for name,state in zip(fin,fixed));fo=dict(zip(fout,fixed_s.run(fout,ffeeds)))
 dh=do['global_hidden'][:,-1,:];fh=fo['global_hidden'][:,-1,:];local_h=Stats();local_h.add(dh,fh);hidden_stats.add(dh,fh);local_k=Stats()
 nd=[]
 for i in range(12):
  for kind in ['key','value']:
   name=f'present_{kind}_{i}';da=do[name];fa=fo[name];local_k.add(da[:,-1,:,:],fa[:,600,:,:]);kv_new_stats.add(da[:,-1,:,:],fa[:,600,:,:]);fixed[len(nd)][:,valid,:,:]=fa[:,600,:,:];nd.append(da)
 dyn=nd;global_hidden=dh.copy()
 if step in {0,104,208,209,373,374}:markers[str(step)]={'pre_step_valid_length':valid,'state_slot_written':valid,'hidden':local_h.result(),'new_kv':local_k.result(),'dynamic_output_positions':valid+1,'fixed_output_positions':601}
 del do,fo,feeds,ffeeds
assert observed_stop is not None and 0<observed_stop<375,observed_stop
# Final full state includes slot 600 from final decode and must equal dynamic positions 0..600.
final_state=Stats()
for a,b in zip(dyn,fixed):final_state.add(a,b)
# Release decoder sessions before codec sessions.
del dynamic,fixed_s,local,dyn;gc.collect()
# Codec compares the canonical-v2 observed stop length and full capacity 375.
source_codec=sess(CODEC/'moss_audio_tokenizer_decode_full.onnx');fixed_codec=sess(S/'codec-full-cap375-qnn.onnx');cn=[x.name for x in source_codec.get_outputs()];fn=[x.name for x in fixed_codec.get_outputs()]
def codec_compare(codes,length):
 src=dict(zip(cn,source_codec.run(cn,{'audio_codes':codes[:,:length,:].copy(),'audio_code_lengths':np.asarray([length],np.int32)})))
 fixed_codes=np.zeros((1,375,16),np.int32);fixed_codes[:,:length,:]=codes[:,:length,:]
 fx=dict(zip(fn,fixed_codec.run(fn,{'audio_codes':fixed_codes,'audio_code_lengths':np.asarray([length],np.int32)})))
 sl=int(np.asarray(src['audio_lengths']).ravel()[0]);fl=int(np.asarray(fx['audio_lengths']).ravel()[0]);st=Stats();st.add(src['audio'][...,:sl],fx['audio'][...,:sl]);return {'frames':length,'source_reported_samples':sl,'fixed_reported_samples':fl,'fixed_tensor_samples':int(fx['audio'].shape[-1]),'metrics':st.result(),'length_exact':sl==fl}
observed=np.asarray([tokens],np.int32);assert observed.shape==(1,observed_stop,16);codec_observed=codec_compare(observed,observed_stop)
full=rng.integers(0,1024,(1,375,16),dtype=np.int32);codec_full=codec_compare(full,375)
del source_codec,fixed_codec;gc.collect()
h=hidden_stats.result();k=kv_new_stats.result();fs=final_state.result();all_metrics=[h,k,fs,codec_observed['metrics'],codec_full['metrics']]
out={'schema_version':1,'policy':'protocol/fixed-capacity-equivalence-policy.json','runtime':{'onnxruntime':ort.__version__,'provider':'CPUExecutionProvider'},'abi':policy['abi'],'observed_generation':{'frames':len(tokens),'stop_step':observed_stop,'audio_token_ids':tokens},'decode':{'calls':375,'hidden':h,'new_kv':k,'markers':markers,'final_state':fs,'final_state_slot_600_written':bool(any(np.any(x[:,600]) for x in fixed))},'codec':{'observed':codec_observed,'full_375':codec_full},'elapsed_seconds':time.monotonic()-t0}
out['passed']=all(passed(x) for x in all_metrics) and codec_observed['length_exact'] and codec_full['length_exact'] and out['decode']['calls']==375 and out['decode']['final_state_slot_600_written']
(ROOT/'results/fixed-capacity-cpu-equivalence.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({k:out[k] for k in ['passed','elapsed_seconds']},indent=2));print('hidden',h);print('kv',k);print('state',fs);print('codec209',codec_observed);print('codec375',codec_full)
if not out['passed']:raise SystemExit(1)
