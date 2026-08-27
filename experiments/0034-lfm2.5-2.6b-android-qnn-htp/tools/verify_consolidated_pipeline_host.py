#!/usr/bin/env python3
"""Compare 37-graph consolidated route with the proven 263-part CPU route."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np,onnxruntime as ort
from verify_htp_pipeline_host import Pipeline,ATTENTION_LAYERS
class Consolidated:
 def __init__(self,models:Path,embedding:Pipeline):
  self.embedding=embedding.embedding;self.sessions={p.stem:ort.InferenceSession(str(p),providers=['CPUExecutionProvider']) for p in models.glob('*.onnx')};self.state={}
  for l in range(30):
   if l in ATTENTION_LAYERS:self.state[f'past_key_values.{l}.key']=np.zeros((1,8,64,4095),np.float32);self.state[f'past_key_values.{l}.value']=np.zeros((1,8,4095,64),np.float32)
   else:self.state[f'past_conv.{l}']=np.zeros((1,2048,3),np.float32)
 def run(self,token,pos):
  h=self.embedding(token);hname='/model/embed_tokens/GatherBlockQuantized/output_0';mask=np.full((1,1,1,4096),-65504,np.float32);mask[...,:pos]=0;mask[...,-1]=0;pid=np.array([[pos]],np.int64)
  for l in range(30):
   s=self.sessions[f'layer-{l:02d}'];feed={hname:h}
   if l in ATTENTION_LAYERS:feed.update({'position_ids':pid,'attention_mask':mask,f'past_key_values.{l}.key':self.state[f'past_key_values.{l}.key'],f'past_key_values.{l}.value':self.state[f'past_key_values.{l}.value']})
   else:feed[f'past_conv.{l}']=self.state[f'past_conv.{l}']
   vals=dict(zip((x.name for x in s.get_outputs()),s.run(None,feed),strict=True));hname=f'/model/layers.{l}/Add_2/output_0';h=vals[hname]
   if l in ATTENTION_LAYERS:self.state[f'past_key_values.{l}.key'][:,:,:,pos:pos+1]=vals[f'present.{l}.key'];self.state[f'past_key_values.{l}.value'][:,:,pos:pos+1,:]=vals[f'present.{l}.value']
   else:self.state[f'past_conv.{l}']=vals[f'present_conv.{l}']
  s=self.sessions['final-norm'];n=s.run(None,{s.get_inputs()[0].name:h})[0];logits=[]
  for g in range(6):
   s=self.sessions[f'heads-{g:02d}'];logits.extend(s.run(None,{s.get_inputs()[0].name:n}))
  return np.concatenate(logits,-1)[0,-1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--parts-dir',type=Path,required=True);ap.add_argument('--models-dir',type=Path,required=True);ap.add_argument('--source-model',type=Path,required=True);ap.add_argument('--tokens',type=Path,required=True);ap.add_argument('--count',type=int,default=5);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();tokens=np.fromfile(a.tokens,np.int32)[:a.count];split=Pipeline(a.parts_dir,a.source_model);merged=Consolidated(a.models_dir,split);rows=[];start=time.time_ns()
 for pos,t in enumerate(tokens):
  x=split.run(int(t),pos);y=merged.run(int(t),pos);delta=np.abs(x-y);state_delta=max(float(np.max(np.abs(split.states[k]-merged.state[k]))) for k in split.states);rows.append({'position':pos,'token':int(t),'split_argmax':int(x.argmax()),'consolidated_argmax':int(y.argmax()),'max_abs':float(delta.max()),'mean_abs':float(delta.mean()),'state_max_abs':state_delta,'allclose':bool(np.allclose(x,y,rtol=1e-4,atol=1e-4))})
 r={'schema_version':1,'classification':'host_cpu_bounded_graph_consolidation_equivalence','tokens':rows,'all_argmax_equal':all(x['split_argmax']==x['consolidated_argmax'] for x in rows),'allclose':all(x['allclose'] for x in rows),'state_boundary':'Both routes independently update and compare all 22 convolution and 8 attention K/V states for every token. Differences reflect changed graph optimization boundaries and are reported, not hidden.','started_ns':start,'stopped_ns':time.time_ns(),'claim_boundary':'CPU semantic/greedy-decision equivalence only; not HTP execution.'};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
