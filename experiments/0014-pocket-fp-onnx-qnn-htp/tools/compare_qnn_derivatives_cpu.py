#!/usr/bin/env python3
"""Compare every 0014 QNN derivative against the frozen 0012 FP ONNX oracle on CPU."""
from __future__ import annotations
import argparse,hashlib,json,sys,wave
from pathlib import Path
import numpy as np,onnxruntime as ort
def metrics(a,b):
 a=np.asarray(a);b=np.asarray(b);d=np.abs(a.astype(np.float64)-b.astype(np.float64));return {'shape':list(a.shape),'max_abs':float(d.max(initial=0)),'mean_abs':float(d.mean()) if d.size else 0.0,'rmse':float(np.sqrt(np.mean(d*d))) if d.size else 0.0,'finite':bool(np.isfinite(b).all())}
def sess(path):
 o=ort.SessionOptions();o.intra_op_num_threads=1;o.inter_op_num_threads=1;o.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;return ort.InferenceSession(str(path),o,providers=['CPUExecutionProvider'])
def init_state(manifest):
 ty={'float32':np.float32,'int64':np.int64,'bool':np.bool_};out={}
 for e in manifest:
  if e['fill']=='nan':x=np.full(e['shape'],np.nan,dtype=ty[e['dtype']])
  elif e['fill']=='ones':x=np.ones(e['shape'],dtype=ty[e['dtype']])
  else:x=np.zeros(e['shape'],dtype=ty[e['dtype']])
  out[e['input_name']]=x
 return out
def update(state,result,manifest,offset=2):
 for e in manifest:state[e['input_name']]=result[offset+e['index']]
def load_wav(path):
 with wave.open(str(path),'rb') as w:
  if w.getframerate()!=24000 or w.getnchannels()!=1 or w.getsampwidth()!=2:raise ValueError('unexpected wav')
  return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32).reshape(1,1,-1)/32768
def max_records(records,key):return max((x[key] for x in records),default=0.0)
def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--static',type=Path,required=True);p.add_argument('--flow',type=Path,required=True);p.add_argument('--flow-step',type=Path);p.add_argument('--mimi',type=Path,required=True);p.add_argument('--voice',type=Path,required=True);p.add_argument('--text',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();meta=json.loads((a.bundle/'bundle.json').read_text());report={'schema_version':1,'oracle':'0012 FP ONNX CPU','temperature':0.3,'seed':0,'text':a.text,'components':{}}
 # Encoder on exact 10-second Bria fixture.
 audio=load_wav(a.voice);assert audio.shape==(1,1,240000)
 oe=sess(a.bundle/'mimi_encoder.onnx');ce=sess(a.mimi/'mimi_encoder-encoder240000.onnx');orig_voice=oe.run(None,{'audio':audio})[0];cand_voice=ce.run(None,{'audio':audio})[0];report['components']['mimi_encoder']=metrics(orig_voice,cand_voice);del oe,ce
 # Tokenizer/text conditioner.
 sys.path.insert(0,str(a.bundle.parent));import sentencepiece as spm
 tok=spm.SentencePieceProcessor();tok.Load(str(a.bundle/meta['tokenizer_file']));text=a.text.strip();text=text if not text[-1].isalnum() else text+'.';ids=np.asarray(tok.Encode(text),dtype=np.int64).reshape(1,-1);assert ids.shape==(1,26),ids.shape
 tc=sess(a.static/'text_conditioner-text26.onnx');text_emb=tc.run(None,{'token_ids':ids})[0];bos=np.load(a.bundle/meta['bos_before_voice_file']).astype(np.float32);voice_emb=np.concatenate((bos,orig_voice),axis=1);assert voice_emb.shape==(1,126,1024)
 # Original explicit state and derivative rolling state.
 om=sess(a.bundle/'flow_lm_main.onnx');flow=sess(a.flow_step or a.static/'flow_lm_flow-flow1.onnx');ostate=init_state(meta['flow_lm_state_manifest']);cache=[np.zeros((1,16,256,64),np.float32) for _ in range(12)];mask=np.full((1,1,1,256),-10000,np.float32);cache_names=[z for i in range(6) for z in (f'k_cache_{i}',f'v_cache_{i}')]
 state_records=[];pos=0;candidate_sessions={p.name:sess(p) for p in a.flow.glob('*.onnx')}
 def candidate_call(path,inputs):
  nonlocal cache,mask
  s=candidate_sessions[path.name];feed=dict(inputs,positions=np.arange(pos,pos+(inputs.get('embeddings',inputs.get('sequence',np.empty((1,1,1))))).shape[1],dtype=np.int64),valid_mask=mask,**dict(zip(cache_names,cache)));r=s.run(None,feed)
  off=0 if 'prefill' in path.name else 2;cache=list(r[off:off+12]);mask=r[off+12];return r
 def compare_cache(stage,valid):
  vals=[]
  for layer in range(6):
   oc=ostate[f'state_{layer*3}'];ok=oc[0,:,:valid].transpose(0,2,1,3);ov=oc[1,:,:valid].transpose(0,2,1,3);ck=cache[layer*2][:,:,-valid:];cv=cache[layer*2+1][:,:,-valid:];vals.extend((metrics(ok,ck),metrics(ov,cv)))
  state_records.append({'stage':stage,'valid':valid,'max_abs':max(x['max_abs'] for x in vals),'mean_abs_max':max(x['mean_abs'] for x in vals),'mask_valid_zeros':bool(np.all(mask[:,:,:,-valid:]==0)),'mask_invalid_value':float(mask[0,0,0,0]) if valid<256 else 0})
 empty_seq=np.zeros((1,0,32),np.float32);empty_text=np.zeros((1,0,1024),np.float32)
 r=om.run(None,{'sequence':empty_seq,'text_embeddings':voice_emb,**ostate});update(ostate,r,meta['flow_lm_state_manifest']);candidate_call(a.flow/'flow_lm_prefill_voice126.onnx',{'embeddings':voice_emb});pos+=126;compare_cache('voice_prefill',126)
 r=om.run(None,{'sequence':empty_seq,'text_embeddings':text_emb,**ostate});update(ostate,r,meta['flow_lm_state_manifest']);candidate_call(a.flow/'flow_lm_prefill_text26.onnx',{'embeddings':text_emb});pos+=26;compare_cache('text_prefill',152)
 rng=np.random.RandomState(0);orig_cur=np.full((1,1,32),np.nan,np.float32);cand_cur=None;steps=[];orig_eos=None;cand_eos=None;orig_latents=[];cand_latents=[]
 for step in range(100):
  ro=om.run(None,{'sequence':orig_cur,'text_embeddings':empty_text,**ostate});update(ostate,ro,meta['flow_lm_state_manifest']);path=a.flow/('flow_lm_ar_bos1.onnx' if step==0 else 'flow_lm_ar_latent1.onnx');inp={} if step==0 else {'sequence':cand_cur};rc=candidate_call(path,inp);pos+=1
  noise=rng.normal(0,np.sqrt(0.3),(1,32)).astype(np.float32);s0=np.array([[0]],np.float32);t1=np.array([[1]],np.float32);lo=noise+flow.run(None,{'c':ro[0],'s':s0,'t':t1,'x':noise})[0];lc=noise+flow.run(None,{'c':rc[0],'s':s0,'t':t1,'x':noise})[0];orig_cur=lo.reshape(1,1,32);cand_cur=lc.reshape(1,1,32);orig_latents.append(orig_cur);cand_latents.append(cand_cur)
  if orig_eos is None and float(ro[1][0,0])>-4:orig_eos=step
  if cand_eos is None and float(rc[1][0,0])>-4:cand_eos=step
  steps.append({'step':step,'conditioning_max_abs':metrics(ro[0],rc[0])['max_abs'],'eos_logit_orig':float(ro[1][0,0]),'eos_logit_candidate':float(rc[1][0,0]),'eos_logit_abs':abs(float(ro[1][0,0])-float(rc[1][0,0])),'latent_max_abs':metrics(orig_cur,cand_cur)['max_abs']})
 report['components']['flow_lm']={'cache_checkpoints':state_records,'steps':100,'original_eos_step':orig_eos,'candidate_eos_step':cand_eos,'conditioning_max_abs_over_steps':max_records(steps,'conditioning_max_abs'),'eos_logit_max_abs_over_steps':max_records(steps,'eos_logit_abs'),'latent_max_abs_over_steps':max_records(steps,'latent_max_abs'),'step_records':steps}
 # Decode the first 78 oracle-count frames through six 12-frame calls and a 6-frame tail.
 lat=np.concatenate(orig_latents[:78],axis=1);os=init_state(meta['mimi_state_manifest']);cs=init_state(meta['mimi_state_manifest']);audio_o=[];audio_c=[];dec=[];decoder_sessions={tag:(sess(a.static/f'mimi_decoder-{tag}.onnx'),sess(a.mimi/f'mimi_decoder-{tag}.onnx')) for tag in ('decoder12','decoder6')}
 for start in range(0,78,12):
  chunk=lat[:,start:min(start+12,78)];tag='decoder12' if chunk.shape[1]==12 else 'decoder6';so,sc=decoder_sessions[tag];ro=so.run(None,{'latent':chunk,**os});rc=sc.run(None,{'latent':chunk,**cs})
  audio_o.append(ro[0]);audio_c.append(rc[0]);dec.append({'start_frame':start,'frames':chunk.shape[1],**metrics(ro[0],rc[0])});update(os,ro,meta['mimi_state_manifest'],1);update(cs,rc,meta['mimi_state_manifest'],1)
 ao=np.concatenate(audio_o,axis=-1);ac=np.concatenate(audio_c,axis=-1);report['components']['mimi_decoder']={'calls':dec,'audio':metrics(ao,ac),'samples':int(ao.size)}
 report['summary']={'encoder_max_abs':report['components']['mimi_encoder']['max_abs'],'flow_cache_max_abs':max(x['max_abs'] for x in state_records),'flow_conditioning_max_abs':report['components']['flow_lm']['conditioning_max_abs_over_steps'],'flow_eos_same_step':orig_eos==cand_eos,'decoder_audio_max_abs':report['components']['mimi_decoder']['audio']['max_abs'],'all_candidate_finite':all([report['components']['mimi_encoder']['finite'],report['components']['mimi_decoder']['audio']['finite']])}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['summary'],indent=2))
if __name__=='__main__':main()
