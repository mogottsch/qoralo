#!/usr/bin/env python3
"""Compare the static unrolled FlowLM derivative with the frozen 0012 CPU graph."""
import argparse,json,wave
from pathlib import Path
import numpy as np,onnxruntime as ort,sentencepiece as spm
def S(p):
 o=ort.SessionOptions();o.intra_op_num_threads=1;o.inter_op_num_threads=1;return ort.InferenceSession(str(p),o,providers=['CPUExecutionProvider'])
def init(meta):
 out={};ty={'float32':np.float32,'int64':np.int64,'bool':np.bool_}
 for e in meta:out[e['input_name']]=np.full(e['shape'],np.nan,ty[e['dtype']]) if e['fill']=='nan' else np.zeros(e['shape'],ty[e['dtype']])
 return out
def update(st,r,m):
 for e in m:st[e['input_name']]=r[2+e['index']]
def met(a,b):
 d=np.abs(a.astype(np.float64)-b.astype(np.float64));return {'max_abs':float(d.max()),'mean_abs':float(d.mean()),'rmse':float(np.sqrt(np.mean(d*d))),'correlation':float(np.corrcoef(a.reshape(-1),b.reshape(-1))[0,1])}
p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--model',type=Path,required=True);p.add_argument('--voice',type=Path,required=True);p.add_argument('--temperature',type=float,default=.7);p.add_argument('--output',type=Path,required=True);a=p.parse_args();meta=json.loads((a.bundle/'bundle.json').read_text());
with wave.open(str(a.voice),'rb') as w:audio=np.frombuffer(w.readframes(w.getnframes()),'<i2').astype(np.float32).reshape(1,1,-1)/32768
enc=S(a.bundle/'mimi_encoder.onnx');voice=np.concatenate((np.load(a.bundle/'bos_before_voice.npy').astype(np.float32),enc.run(None,{'audio':audio})[0]),1);tok=spm.SentencePieceProcessor();tok.Load(str(a.bundle/'tokenizer.model'));ids=np.asarray(tok.Encode('Pocket TTS runs entirely on this Android phone using the original floating point model.'),np.int64).reshape(1,-1);tc=S(a.bundle/'text_conditioner.onnx');text=tc.run(None,{'token_ids':ids})[0];steps=S(a.model).get_inputs()[2].shape[1];rng=np.random.RandomState(0);noise=rng.normal(0,np.sqrt(a.temperature),(1,steps,32)).astype(np.float32);u=S(a.model).run(None,{'voice_embeddings':voice,'text_embeddings':text,'noise':noise});main=S(a.bundle/'flow_lm_main.onnx');flow=S(a.bundle/'flow_lm_flow.onnx');st=init(meta['flow_lm_state_manifest']);empty=np.zeros((1,0,32),np.float32);et=np.zeros((1,0,1024),np.float32)
for emb in (voice,text):r=main.run(None,{'sequence':empty,'text_embeddings':emb,**st});update(st,r,meta['flow_lm_state_manifest'])
cur=np.full((1,1,32),np.nan,np.float32);lat=[];log=[]
for i in range(steps):
 r=main.run(None,{'sequence':cur,'text_embeddings':et,**st});update(st,r,meta['flow_lm_state_manifest']);x=noise[:,i];x=x+flow.run(None,{'c':r[0],'s':np.zeros((1,1),np.float32),'t':np.ones((1,1),np.float32),'x':x})[0];cur=x.reshape(1,1,32);lat.append(x);log.append(r[1])
lat=np.stack(lat,1);log=np.stack(log,1);oe=next((i for i,x in enumerate(log[:, :, 0].reshape(-1)) if x>-4),None);ue=next((i for i,x in enumerate(u[1][:,:,0].reshape(-1)) if x>-4),None);out={'schema_version':1,'steps':steps,'temperature':a.temperature,'latents':met(lat,u[0]),'eos_logits':met(log,u[1]),'oracle_eos':oe,'unrolled_eos':ue,'per_step':[{'step':i,'latent_max_abs':float(np.max(np.abs(lat[:,i]-u[0][:,i]))),'eos_oracle':float(log[0,i,0]),'eos_unrolled':float(u[1][0,i,0])} for i in range(steps)]};a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='per_step'},indent=2))
