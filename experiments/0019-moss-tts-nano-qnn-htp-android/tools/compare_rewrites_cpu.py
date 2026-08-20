#!/usr/bin/env python3
import gc,hashlib,json,math
from pathlib import Path
import numpy as np,onnxruntime as ort
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'.local/specialized';TTS=ROOT.parent/'0018-moss-tts-nano-onnx-android/.local/tts';CODEC=ROOT.parent/'0018-moss-tts-nano-onnx-android/.local/codec'
POL=json.load(open(ROOT/'protocol/rewrite-equivalence-policy.json'))['criteria'];rng=np.random.default_rng(20260818)
def session(path):
 o=ort.SessionOptions();o.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;o.intra_op_num_threads=4;o.inter_op_num_threads=1
 return ort.InferenceSession(str(path),sess_options=o,providers=['CPUExecutionProvider'])
def run(path,feeds):
 s=session(path);names=[x.name for x in s.get_outputs()];values=s.run(names,feeds);shapes=[list(x.shape) for x in values];del s;gc.collect();return names,values,shapes
def compare(label,original,rewrite,feeds):
 n0,a,s0=run(original,feeds);n1,b,s1=run(rewrite,feeds);assert n0==n1 and s0==s1
 max_abs=0.;sq=0.;count=0;dot=0.;na=0.;nb=0.;finite=True;int_exact=True;per=[]
 for name,x,y in zip(n0,a,b):
  if x.dtype.kind in 'biu':
   exact=bool(np.array_equal(x,y));int_exact &= exact;per.append({'name':name,'shape':list(x.shape),'dtype':str(x.dtype),'exact':exact});continue
  xf=x.astype(np.float64,copy=False);yf=y.astype(np.float64,copy=False);d=xf-yf
  ma=float(np.max(np.abs(d))) if d.size else 0.;rm=float(np.sqrt(np.mean(d*d))) if d.size else 0.;co=float(np.dot(xf.ravel(),yf.ravel())/(np.linalg.norm(xf.ravel())*np.linalg.norm(yf.ravel()))) if np.any(xf) and np.any(yf) else 1.
  finite &= bool(np.isfinite(xf).all() and np.isfinite(yf).all());max_abs=max(max_abs,ma);sq+=float(np.sum(d*d));count+=d.size;dot+=float(np.sum(xf*yf));na+=float(np.sum(xf*xf));nb+=float(np.sum(yf*yf));per.append({'name':name,'shape':list(x.shape),'dtype':str(x.dtype),'max_abs':ma,'rmse':rm,'cosine':co})
 rmse=math.sqrt(sq/count) if count else 0.;cos=dot/math.sqrt(na*nb) if na and nb else 1.
 passed=int_exact and finite and max_abs<=POL['float_max_abs_error_lte'] and rmse<=POL['float_rmse_lte'] and cos>=POL['float_cosine_gte']
 return {'label':label,'original':str(original),'rewrite':str(rewrite),'output_count':len(n0),'integer_boolean_exact':int_exact,'float_finite':finite,'float_elements':count,'max_abs':max_abs,'rmse':rmse,'cosine':cos,'passed':passed,'outputs':per}
# Exact prefill rows.
man=json.load(open(TTS/'browser_poc_manifest.json'));tok=json.load(open(ROOT/'protocol/tokenization.json'))['token_ids'];cfg=man['tts_config'];voice=next(x for x in man['builtin_voices'] if x['voice']=='Junhao');width=17
prefix=man['prompt_templates']['user_prompt_prefix_token_ids']+[cfg['audio_start_token_id']];suffix=[cfg['audio_end_token_id']]+man['prompt_templates']['user_prompt_after_reference_token_ids']+tok+man['prompt_templates']['assistant_prompt_prefix_token_ids']+[cfg['audio_start_token_id']]
rows=[]
for t in prefix:rows.append([t]+[cfg['audio_pad_token_id']]*16)
for codes in voice['prompt_audio_codes']:rows.append([cfg['audio_user_slot_token_id']]+codes[:16])
for t in suffix:rows.append([t]+[cfg['audio_pad_token_id']]*16)
assert len(rows)==226
results=[]
results.append(compare('prefill-s226',S/'prefill-s226.onnx',S/'prefill-s226-qnn.onnx',{'input_ids':np.asarray([rows],np.int32),'attention_mask':np.ones((1,226),np.int32)}))
for step,past in [(0,226),(104,330),(208,434)]:
 feeds={'input_ids':np.asarray([[[9]+rng.integers(0,1024,16,dtype=np.int32).tolist()]],np.int32),'past_valid_lengths':np.asarray([past],np.int32)}
 for i in range(12):
  feeds[f'past_key_{i}']=rng.normal(0,.1,(1,past,12,64)).astype(np.float32);feeds[f'past_value_{i}']=rng.normal(0,.1,(1,past,12,64)).astype(np.float32)
 name=f'decode-step-{step:03d}-past-{past}';results.append(compare(name,S/(name+'.onnx'),S/(name+'-qnn.onnx'),feeds));del feeds;gc.collect()
feeds={'global_hidden':rng.normal(0,.1,(1,768)).astype(np.float32),'repetition_seen_mask':np.zeros((1,16,1024),np.int32),'assistant_random_u':np.asarray([.4],np.float32),'audio_random_u':np.linspace(.1,.9,16,dtype=np.float32).reshape(1,16)}
results.append(compare('local-fixed-b1-shape-specialization',TTS/'moss_tts_local_fixed_sampled_frame.onnx',S/'local-fixed-b1.onnx',feeds))
feeds={'audio_codes':rng.integers(0,1024,(1,209,16),dtype=np.int32),'audio_code_lengths':np.asarray([209],np.int32)}
results.append(compare('codec-full-f209',S/'codec-full-f209.onnx',S/'codec-full-f209-qnn.onnx',feeds))
out={'schema_version':1,'policy':'protocol/rewrite-equivalence-policy.json','runtime':{'onnxruntime':ort.__version__,'providers':ort.get_available_providers(),'used':'CPUExecutionProvider'},'results':results,'passed':all(x['passed'] for x in results)}
(ROOT/'results/rewrite-cpu-equivalence.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'passed':out['passed'],'results':[{k:x[k] for k in ['label','passed','max_abs','rmse','cosine']} for x in results]},indent=2))
if not out['passed']:raise SystemExit(1)
