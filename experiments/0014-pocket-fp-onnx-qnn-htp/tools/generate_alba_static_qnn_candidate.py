#!/usr/bin/env python3
"""Generate host CPU audio for the fixed-cache QNN-compatible route with Alba state."""
from __future__ import annotations
import hashlib,json,subprocess,sys,wave
from pathlib import Path
import numpy as np,onnxruntime as ort
TEXT="Pocket TTS runs entirely on this Android phone using the original floating point model."
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def session(p):
 o=ort.SessionOptions();o.intra_op_num_threads=o.inter_op_num_threads=1;o.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;return ort.InferenceSession(str(p),o,providers=['CPUExecutionProvider'])
def init_decoder(manifest):
 ty={'float32':np.float32,'int64':np.int64,'bool':np.bool_};s={}
 for e in manifest:
  if e['fill']=='nan':x=np.full(e['shape'],np.nan,ty[e['dtype']])
  elif e['fill']=='ones':x=np.ones(e['shape'],ty[e['dtype']])
  else:x=np.zeros(e['shape'],ty[e['dtype']])
  s[e['input_name']]=x
 return s
def write_wav(p,x):
 x=np.asarray(x,np.float32).reshape(-1);pcm=np.clip(np.rint(x*32767),-32768,32767).astype('<i2')
 with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(pcm.tobytes())
 return {'path':str(p),'sha256':sha(p),'samples':x.size,'seconds':x.size/24000,'peak_float':float(np.max(np.abs(x))),'rms_float':float(np.sqrt(np.mean(x*x))),'finite':bool(np.isfinite(x).all()),'clipped_before_conversion':int(np.count_nonzero(np.abs(x)>1))}
def main():
 root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip());e12=root/'experiments/0012-pocket-onnx-vs-executorch-android';e14=root/'experiments/0014-pocket-fp-onnx-qnn-htp';static=e14/'.local/static-optimized';flowdir=e14/'.local/qnn-flow';mimidir=e14/'.local/qnn-v2';bundle=e12/'.local/onnx-controlled';assets=e14/'work/quality-recovery/alba-assets';out=e14/'work/quality-recovery/static-alba';out.mkdir(parents=True,exist_ok=True);meta=json.loads((bundle/'bundle.json').read_text());cache=np.fromfile(assets/'alba-flow-cache-v1.f32',dtype='<f4').reshape(6,2,1,126,16,64)
 tc=session(static/'text_conditioner-text26.onnx');pref=session(flowdir/'flow_lm_prefill_text26.onnx');bos=session(flowdir/'flow_lm_ar_bos1.onnx');ar=session(flowdir/'flow_lm_ar_latent1.onnx');flow=session(static/'flow_lm_flow-flow1.onnx');dec={12:session(mimidir/'mimi_decoder-decoder12.onnx'),6:session(mimidir/'mimi_decoder-decoder6.onnx'),1:session(mimidir/'mimi_decoder-decoder1.onnx')};ids=np.array([1456,603,597,602,854,640,791,261,260,1332,323,288,285,287,489,594,1355,1049,265,311,2081,3697,273,519,1836,263],np.int64).reshape(1,26);text=tc.run(None,{'token_ids':ids})[0];rows=[]
 for temp in (.3,.7):
  state=[]
  for i in range(6):
   for kv in range(2):
    x=np.zeros((1,16,256,64),np.float32);x[:,:,-126:]=cache[i,kv].transpose(0,2,1,3);state.append(x)
  mask=np.full((1,1,1,256),-10000,np.float32);mask[:,:,:,-126:]=0;names=[z for i in range(6) for z in (f'k_cache_{i}',f'v_cache_{i}')];feed={'embeddings':text,'positions':np.arange(126,152,dtype=np.int64),'valid_mask':mask,**dict(zip(names,state))};r=pref.run(None,feed);state=list(r[:12]);mask=r[12];noise=np.fromfile(assets/f'numpy-randomstate-seed0-temp{str(temp).replace(".","p")}-134x32.f32',dtype='<f4').reshape(134,32);lat=[];logits=[];cur=None;eos=None
  for step in range(134):
   feed={'positions':np.array([152+step],np.int64),'valid_mask':mask,**dict(zip(names,state))}
   if step:r=ar.run(None,{'sequence':cur.reshape(1,1,32),**feed})
   else:r=bos.run(None,feed)
   state=list(r[2:14]);mask=r[14];logit=float(r[1][0,0]);logits.append(logit)
   if eos is None and logit>-4:eos=step
   if eos is not None and step>=eos+3:break
   n=noise[step:step+1];d=flow.run(None,{'c':r[0],'s':np.array([[0]],np.float32),'t':np.array([[1]],np.float32),'x':n})[0];cur=n+d;lat.append(cur.reshape(1,1,32))
  lat=np.concatenate(lat,axis=1);ds=init_decoder(meta['mimi_state_manifest']);audio=[];start=0
  while start<lat.shape[1]:
   remaining=lat.shape[1]-start;n=12 if remaining>=12 else (6 if remaining==6 else 1);r=dec[n].run(None,{'latent':lat[:,start:start+n],**ds});audio.append(r[0].reshape(-1));ds={e['input_name']:r[1+e['index']] for e in meta['mimi_state_manifest']};start+=n
  audio=np.concatenate(audio);tag=str(temp).replace('.','p');row=write_wav(out/f'fixed-cache-fp-alba-temp{tag}-seed0.wav',audio);row.update({'temperature':temp,'seed':0,'eos_step':eos,'latent_frames':int(lat.shape[1]),'eos_logits':logits});rows.append(row)
 graphs=[static/'text_conditioner-text26.onnx',flowdir/'flow_lm_prefill_text26.onnx',flowdir/'flow_lm_ar_bos1.onnx',flowdir/'flow_lm_ar_latent1.onnx',static/'flow_lm_flow-flow1.onnx',mimidir/'mimi_decoder-decoder12.onnx',mimidir/'mimi_decoder-decoder6.onnx',mimidir/'mimi_decoder-decoder1.onnx'];report={'schema_version':1,'status':'awaiting_human_listening_verdict','route':'QNN-compatible fixed-cache FP-source derivative on host CPU, initialized from pinned Alba state','graphs':{p.name:sha(p) for p in graphs},'contract':{'text':TEXT,'voice':'official pinned Alba state','voice_state_sha256':'e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c','temperatures':[.3,.7],'seed':0,'noise':'same NumPy fixtures as accepted controlled ONNX host route','max_frames':134},'outputs':rows,'claim_boundary':'This tests perceptual recovery of the QNN-compatible derivative on CPU; it is not HTP evidence and remains unaccepted until Moritz listens.'};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
