#!/usr/bin/env python3
"""Generate and compare canonical-v2 one-shot original/static fixed-Alba host routes."""
from __future__ import annotations
import argparse,hashlib,json,subprocess,wave
from pathlib import Path
import numpy as np,onnxruntime as ort
from safetensors import safe_open
TEXT_SHA="424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def sess(p):
 o=ort.SessionOptions();o.intra_op_num_threads=o.inter_op_num_threads=1;o.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;return ort.InferenceSession(str(p),o,providers=['CPUExecutionProvider'])
def init_state(manifest):
 types={'float32':np.float32,'int64':np.int64,'bool':np.bool_};out={}
 for e in manifest:
  if e['fill']=='nan':x=np.full(e['shape'],np.nan,types[e['dtype']])
  elif e['fill']=='ones':x=np.ones(e['shape'],types[e['dtype']])
  else:x=np.zeros(e['shape'],types[e['dtype']])
  out[e['input_name']]=x
 return out
def update(state,result,manifest,offset):
 for e in manifest:state[e['input_name']]=result[offset+e['index']]
def write_wav(path,audio):
 x=np.asarray(audio,np.float32).reshape(-1);assert x.size and np.isfinite(x).all() and np.any(x) and np.max(np.abs(x))<1;pcm=np.clip(np.rint(x*32767),-32768,32767).astype('<i2')
 with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(pcm.tobytes())
 return {'path':str(path),'sha256':sha(path),'samples':x.size,'seconds':x.size/24000,'peak_float':float(np.max(np.abs(x))),'rms_float':float(np.sqrt(np.mean(x*x))),'finite':True,'non_silent':True,'unclipped':True}
def decode(latents,sessions,manifest):
 state=init_state(manifest);audio=[];start=0
 while start<latents.shape[1]:
  rem=latents.shape[1]-start;n=12 if rem>=12 else (6 if rem==6 else 1);session=sessions[n];r=session.run(None,{'latent':latents[:,start:start+n],**state});audio.append(r[0].reshape(-1));update(state,r,manifest,1);start+=n
 return np.concatenate(audio)
def original_state(alba,manifest):
 modules={}
 with safe_open(str(alba),framework='np') as f:
  for key in f.keys():module,tensor=key.split('/',1);modules.setdefault(module,{})[tensor]=f.get_tensor(key)
 state=init_state(manifest)
 for e in manifest:
  module=modules.get(e['module'],{});source=module.get(e['key'])
  if source is None and e['key']=='step':source=module.get('offset')
  if source is None:continue
  source=np.asarray(source,dtype=state[e['input_name']].dtype);target=state[e['input_name']];slices=tuple(slice(0,min(a,b)) for a,b in zip(source.shape,target.shape));target[slices]=source[slices];state[e['input_name']]=target
 return state
def main():
 p=argparse.ArgumentParser();p.add_argument('--canonical-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip());e12=root/'experiments/0012-pocket-onnx-vs-executorch-android';e14=root/'experiments/0014-pocket-fp-onnx-qnn-htp';bundle=e12/'.local/onnx-controlled';flow_static=a.canonical_dir/'qnn-flow';text_static=a.canonical_dir/'text';mimi=e14/'.local/qnn-v2';assets=e14/'work/canonical-benchmark/assets';alba=e12/'.local/source-assets/languages/english/embeddings/alba.safetensors';meta=json.loads((bundle/'bundle.json').read_text());a.output.mkdir(parents=True,exist_ok=True);ids=np.fromfile(assets/'canonical-token-ids-64.i64',dtype='<i8').reshape(1,64);noise=np.fromfile(assets/'numpy-randomstate-seed0-temp0p3-292x32.f32',dtype='<f4').reshape(292,32);assert sha(assets/'canonical-token-ids-64.i64')=='56d50c958627be19a7f2c86dde68a537a80f3f6d9087c16f55fde58c4d117c82';assert sha(assets/'numpy-randomstate-seed0-temp0p3-292x32.f32')=='c70130d0d42d7a281bad2258b7820fab85d5cd0c6b869b463a1a3281869ddbb1'
 # Shared/reused sessions.
 flow=sess(e14/'.local/static-optimized/flow_lm_flow-flow1.onnx');orig_dec=sess(bundle/'mimi_decoder.onnx');static_dec={12:sess(mimi/'mimi_decoder-decoder12.onnx'),6:sess(mimi/'mimi_decoder-decoder6.onnx'),1:sess(mimi/'mimi_decoder-decoder1.onnx')}
 # Original dynamic one-shot reference (no sentence splitting).
 tc=sess(bundle/'text_conditioner.onnx');main=sess(bundle/'flow_lm_main.onnx');text=tc.run(None,{'token_ids':ids})[0];state=original_state(alba,meta['flow_lm_state_manifest']);r=main.run(None,{'sequence':np.zeros((1,0,32),np.float32),'text_embeddings':text,**state});update(state,r,meta['flow_lm_state_manifest'],2);cur=np.full((1,1,32),np.nan,np.float32);empty=np.zeros((1,0,1024),np.float32);orig_lat=[];orig_logits=[];orig_eos=None
 for step in range(292):
  r=main.run(None,{'sequence':cur,'text_embeddings':empty,**state});update(state,r,meta['flow_lm_state_manifest'],2);logit=float(r[1][0,0]);orig_logits.append(logit)
  if orig_eos is None and logit>-4:orig_eos=step
  if orig_eos is not None and step>=orig_eos+3:break
  n=noise[step:step+1];d=flow.run(None,{'c':r[0],'s':np.array([[0]],np.float32),'t':np.array([[1]],np.float32),'x':n})[0];cur=(n+d).reshape(1,1,32);orig_lat.append(cur)
 orig_lat=np.concatenate(orig_lat,axis=1);orig_audio=decode(orig_lat,{12:orig_dec,6:orig_dec,1:orig_dec},meta['mimi_state_manifest'])
 # New text64/cache512 derivative.
 tc2=sess(text_static/'text_conditioner-text64.onnx');pref=sess(flow_static/'flow_lm_prefill_text64.onnx');bos=sess(flow_static/'flow_lm_ar_bos1.onnx');ar=sess(flow_static/'flow_lm_ar_latent1.onnx');text2=tc2.run(None,{'token_ids':ids})[0];packed=np.fromfile(e14/'work/quality-recovery/alba-assets/alba-flow-cache-v1.f32',dtype='<f4').reshape(6,2,1,126,16,64);cache=[]
 for layer in range(6):
  for kv in range(2):x=np.zeros((1,16,512,64),np.float32);x[:,:,-126:]=packed[layer,kv].transpose(0,2,1,3);cache.append(x)
 mask=np.full((1,1,1,512),-10000,np.float32);mask[:,:,:,-126:]=0;names=[z for i in range(6) for z in (f'k_cache_{i}',f'v_cache_{i}')];r=pref.run(None,{'embeddings':text2,'positions':np.arange(126,190,dtype=np.int64),'valid_mask':mask,**dict(zip(names,cache))});cache=list(r[:12]);mask=r[12];static_lat=[];static_logits=[];static_eos=None;cur=None
 for step in range(292):
  feed={'positions':np.array([190+step],np.int64),'valid_mask':mask,**dict(zip(names,cache))};r=bos.run(None,feed) if step==0 else ar.run(None,{'sequence':cur,**feed});cache=list(r[2:14]);mask=r[14];logit=float(r[1][0,0]);static_logits.append(logit)
  if static_eos is None and logit>-4:static_eos=step
  if static_eos is not None and step>=static_eos+3:break
  n=noise[step:step+1];d=flow.run(None,{'c':r[0],'s':np.array([[0]],np.float32),'t':np.array([[1]],np.float32),'x':n})[0];cur=(n+d).reshape(1,1,32);static_lat.append(cur)
 static_lat=np.concatenate(static_lat,axis=1);static_audio=decode(static_lat,static_dec,meta['mimi_state_manifest']);orig_info=write_wav(a.output/'original-dynamic-one-shot.wav',orig_audio);static_info=write_wav(a.output/'fixed-cache512-text64.wav',static_audio);comparison={'equal_frames':orig_lat.shape[1]==static_lat.shape[1],'original_frames':int(orig_lat.shape[1]),'static_frames':int(static_lat.shape[1]),'original_eos_step':orig_eos,'static_eos_step':static_eos}
 if orig_audio.shape==static_audio.shape:
  x=orig_audio.astype(np.float64);y=static_audio.astype(np.float64);d=x-y;comparison.update({'equal_samples':True,'correlation':float(np.corrcoef(x,y)[0,1]),'snr_db':float(10*np.log10(np.mean(x*x)/np.mean(d*d))) if np.any(d) else None,'max_abs':float(np.max(np.abs(d))),'mae':float(np.mean(np.abs(d)))})
 else:comparison['equal_samples']=False
 report={'schema_version':1,'status':'awaiting_fresh_moritz_listening_verdict','route':'canonical-v2 Pocket fixed Alba, one-shot text64/cache512 host CPU gate','canonical_transcript':{'version':2,'bytes':226,'sha256':TEXT_SHA},'frontend':{'token_count':64,'token_fixture_sha256':'56d50c958627be19a7f2c86dde68a537a80f3f6d9087c16f55fde58c4d117c82'},'original_one_shot':orig_info,'static_candidate':static_info,'comparison':comparison,'graphs':{'text64':sha(text_static/'text_conditioner-text64.onnx'),'prefill64':sha(flow_static/'flow_lm_prefill_text64.onnx'),'ar_bos_cache512':sha(flow_static/'flow_lm_ar_bos1.onnx'),'ar_latent_cache512':sha(flow_static/'flow_lm_ar_latent1.onnx'),'flow':sha(e14/'.local/static-optimized/flow_lm_flow-flow1.onnx'),'decoder12':sha(mimi/'mimi_decoder-decoder12.onnx'),'decoder6':sha(mimi/'mimi_decoder-decoder6.onnx'),'decoder1':sha(mimi/'mimi_decoder-decoder1.onnx')},'claim_boundary':'Fresh canonical text requires fresh listening. Numerical comparison does not transfer the text26 verdict.'};(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
