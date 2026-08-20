#!/usr/bin/env python3
"""QNN-oriented static FlowLM export with a fixed rolling cache ABI.

This keeps the exact learned modules/weights but replaces dynamic scatter/slice state
with right-aligned K/V caches plus a finite additive validity mask. Target-bound
graphs cover configured voice/text prefill lengths, the first/BOS AR step, and
subsequent latent AR steps. Defaults reproduce the historical 126/26/256 route;
canonical benchmark variants use separate outputs and explicit arguments.
"""
from __future__ import annotations
import argparse,hashlib,json,math,subprocess
from pathlib import Path
import numpy as np,torch
from torch import nn
from torch.nn import functional as F
class ExactGelu(torch.autograd.Function):
 @staticmethod
 def forward(ctx,x):return F.gelu(x,approximate='none')
 @staticmethod
 def symbolic(g,x):return g.op('com.microsoft::Gelu',x)
class StaticFlowCore(nn.Module):
 def __init__(self,flow,steps:int,capacity:int):
  super().__init__();self.steps=steps;self.capacity=capacity;self.input_linear=flow.input_linear;self.layers=flow.transformer.layers;self.out_norm=flow.out_norm;self.out_eos=flow.out_eos;self.bos_emb=flow.bos_emb
  d=64;freqs=torch.exp(torch.arange(d//2,dtype=torch.float32)*(-math.log(10000.0)*2/d));self.register_buffer('rope_freqs',freqs.reshape(1,1,1,d//2))
  future=torch.zeros((1,1,steps,capacity),dtype=torch.float32)
  for i in range(steps):
   if i+1<steps:future[0,0,i,capacity-steps+i+1:]=-10000.0
  self.register_buffer('future_mask',future)
 def rope(self,q,k,positions):
  b,t,h,d=q.shape;angles=positions.to(torch.float32).reshape(1,t,1,1)*self.rope_freqs;co=torch.cos(angles);si=torch.sin(angles)
  qp=q.reshape(b,t,h,d//2,2);kp=k.reshape(b,t,h,d//2,2);qr,qi=qp[...,0],qp[...,1];kr,ki=kp[...,0],kp[...,1]
  qo=torch.stack((qr*co-qi*si,qr*si+qi*co),dim=-1).reshape(b,t,h,d);ko=torch.stack((kr*co-ki*si,kr*si+ki*co),dim=-1).reshape(b,t,h,d);return qo,ko
 def run_core(self,x,positions,valid_mask,flat_cache):
  t=self.steps;new_mask=torch.cat((valid_mask[:,:,:,t:],torch.zeros((1,1,1,t),dtype=valid_mask.dtype,device=valid_mask.device)),dim=3);next_cache=[]
  for index,layer in enumerate(self.layers):
   residual=x;n=layer.norm1(x);p=layer.self_attn.in_proj(n).reshape(1,t,3,16,64);q,k,v=p[:,:,0],p[:,:,1],p[:,:,2];q,k=self.rope(q,k,positions);q=q.transpose(1,2);k=k.transpose(1,2);v=v.transpose(1,2)
   old_k,old_v=flat_cache[index*2],flat_cache[index*2+1];new_k=torch.cat((old_k[:,:,t:,:],k),dim=2);new_v=torch.cat((old_v[:,:,t:,:],v),dim=2);next_cache.extend((new_k,new_v))
   scores=torch.matmul(q,new_k.transpose(-2,-1))*0.125;scores=scores+new_mask+self.future_mask;probs=torch.softmax(scores,dim=-1);a=torch.matmul(probs,new_v).transpose(1,2).reshape(1,t,1024);x=residual+layer.self_attn.out_proj(a)
   residual=x;x=layer.norm2(x);x=residual+layer.linear2(ExactGelu.apply(layer.linear1(x)))
  return x,next_cache,new_mask
class Prefill(StaticFlowCore):
 def forward(self,embeddings,positions,valid_mask,*cache):
  _,new_cache,new_mask=self.run_core(embeddings,positions,valid_mask,cache);return (*new_cache,new_mask)
class ArLatent(StaticFlowCore):
 def forward(self,sequence,positions,valid_mask,*cache):
  x=self.input_linear(sequence);x,new_cache,new_mask=self.run_core(x,positions,valid_mask,cache);c=self.out_norm(x)[:,-1];return (c,self.out_eos(c),*new_cache,new_mask)
class ArBos(StaticFlowCore):
 def forward(self,positions,valid_mask,*cache):
  seq=self.bos_emb.reshape(1,1,32);x=self.input_linear(seq);x,new_cache,new_mask=self.run_core(x,positions,valid_mask,cache);c=self.out_norm(x)[:,-1];return (c,self.out_eos(c),*new_cache,new_mask)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def export_one(module,args,path,input_names,output_names):
 module.eval();torch.onnx.export(module,args,str(path),input_names=input_names,output_names=output_names,opset_version=17,dynamo=False,do_constant_folding=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--capacity',type=int,default=256);p.add_argument('--voice-steps',type=int,default=126);p.add_argument('--text-steps',type=int,default=26);p.add_argument('--skip-voice',action='store_true');p.add_argument('--exporter-root',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 from pocket_tts.models.tts_model import TTSModel
 torch.manual_seed(0);model=TTSModel.load_model(config=str(a.config)).cpu().eval();flow=model.flow_lm;c=a.capacity
 cache=tuple(torch.zeros((1,16,c,64),dtype=torch.float32) for _ in range(12));mask=torch.full((1,1,1,c),-10000.0);names_cache=[z for i in range(6) for z in (f'k_cache_{i}',f'v_cache_{i}')];out_cache=[z for i in range(6) for z in (f'new_k_cache_{i}',f'new_v_cache_{i}')]
 specs=[];prefills=[]
 if not a.skip_voice:prefills.append((f'voice{a.voice_steps}',a.voice_steps))
 prefills.append((f'text{a.text_steps}',a.text_steps))
 for label,t in prefills:
  mod=Prefill(flow,t,c);args=(torch.randn(1,t,1024),torch.arange(t,dtype=torch.int64),mask,*cache);path=a.output/f'flow_lm_prefill_{label}.onnx';export_one(mod,args,path,['embeddings','positions','valid_mask',*names_cache],[*out_cache,'new_valid_mask']);specs.append((label,path,t,'prefill'))
 bos_position=a.voice_steps+a.text_steps
 mod=ArBos(flow,1,c);args=(torch.tensor([bos_position],dtype=torch.int64),mask,*cache);path=a.output/'flow_lm_ar_bos1.onnx';export_one(mod,args,path,['positions','valid_mask',*names_cache],['conditioning','eos_logit',*out_cache,'new_valid_mask']);specs.append(('ar_bos1',path,1,'ar_bos'))
 mod=ArLatent(flow,1,c);args=(torch.randn(1,1,32),torch.tensor([bos_position+1],dtype=torch.int64),mask,*cache);path=a.output/'flow_lm_ar_latent1.onnx';export_one(mod,args,path,['sequence','positions','valid_mask',*names_cache],['conditioning','eos_logit',*out_cache,'new_valid_mask']);specs.append(('ar_latent1',path,1,'ar_latent'))
 import onnx
 report={'schema_version':1,'derivative':'fixed-right-aligned-kv-cache-flowlm','source':{'config':str(a.config.resolve()),'weights':str(Path(model.config.weights_path).resolve()) if hasattr(model,'config') else None,'weights_sha256':sha(Path(a.config.parent/'source-assets/languages/english/model.safetensors')) if (a.config.parent/'source-assets/languages/english/model.safetensors').exists() else None,'exporter_root':str(a.exporter_root.resolve()),'exporter_commit':subprocess.check_output(['git','-C',str(a.exporter_root),'rev-parse','HEAD'],text=True).strip()},'cache_abi':{'capacity':c,'voice_steps':a.voice_steps,'text_steps':a.text_steps,'bos_absolute_position':a.voice_steps+a.text_steps,'layout':'12 tensors [1,16,capacity,64], right-aligned; one additive valid mask [1,1,1,capacity]','invalid_mask_value':-10000.0,'position_input':'absolute int64 positions; RoPE Cos/Sin remain inside QNN graph'},'graphs':[]}
 for label,path,t,kind in specs:
  m=onnx.load(str(path));onnx.checker.check_model(m,full_check=True);report['graphs'].append({'variant':label,'kind':kind,'steps':t,'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'nodes':len(m.graph.node),'operators':sorted(set(x.op_type for x in m.graph.node))})
 (a.output/'export-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
