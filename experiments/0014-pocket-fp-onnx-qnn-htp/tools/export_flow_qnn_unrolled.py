#!/usr/bin/env python3
"""Export Pocket FlowLM conditioning + autoregression as one static QNN graph.

The graph begins with the exact 126-frame voice and 26-token text prefills, then
unrolls N autoregressive and flow calls. K/V tensors grow to their exact logical
length at every call; there is no padding mask, zero-length tensor, scatter,
runtime shape construction, or host recurrent state round-trip. CPU supplies
only the deterministic noise tensor and selects the EOS-delimited output prefix.
"""
from __future__ import annotations
import argparse,hashlib,json,math,subprocess
from pathlib import Path
import torch
from torch import nn
from torch.nn import functional as F
class ExactGelu(torch.autograd.Function):
 @staticmethod
 def forward(ctx,x):return F.gelu(x,approximate='none')
 @staticmethod
 def symbolic(g,x):return g.op('com.microsoft::Gelu',x)
class UnrolledFlow(nn.Module):
 def __init__(self,flow,steps):
  super().__init__();self.flow=flow;self.steps=steps;d=64;self.register_buffer('freqs',torch.exp(torch.arange(d//2,dtype=torch.float32)*(-math.log(10000.0)*2/d)).reshape(1,1,1,d//2))
 def rope(self,q,k,start):
  b,t,h,d=q.shape;pos=torch.arange(start,start+t,dtype=torch.float32,device=q.device).reshape(1,t,1,1);co=torch.cos(pos*self.freqs);si=torch.sin(pos*self.freqs);qp=q.reshape(b,t,h,d//2,2);kp=k.reshape(b,t,h,d//2,2);qr,qi=qp[...,0],qp[...,1];kr,ki=kp[...,0],kp[...,1];return torch.stack((qr*co-qi*si,qr*si+qi*co),-1).reshape(b,t,h,d),torch.stack((kr*co-ki*si,kr*si+ki*co),-1).reshape(b,t,h,d)
 def block(self,x,start,caches):
  t=x.shape[1];new=[]
  for i,layer in enumerate(self.flow.transformer.layers):
   residual=x;n=layer.norm1(x);p=layer.self_attn.in_proj(n).reshape(1,t,3,16,64);q,k,v=p[:,:,0],p[:,:,1],p[:,:,2];q,k=self.rope(q,k,start);q=q.transpose(1,2);k=k.transpose(1,2);v=v.transpose(1,2);old=caches[i]
   if old is None:nk,nv=k,v
   else:nk,nv=torch.cat((old[0],k),2),torch.cat((old[1],v),2)
   scores=torch.matmul(q,nk.transpose(-2,-1))*0.125
   if t>1:
    rows=torch.arange(t,device=scores.device,dtype=torch.int64).reshape(t,1);cols=torch.arange(start+t,device=scores.device,dtype=torch.int64).reshape(1,start+t);allowed=cols<=(start+rows);mask=torch.where(allowed,torch.zeros((),dtype=scores.dtype,device=scores.device),torch.full((),-10000.0,dtype=scores.dtype,device=scores.device)).reshape(1,1,t,start+t);scores=scores+mask
   probs=torch.softmax(scores,-1);a=torch.matmul(probs,nv).transpose(1,2).reshape(1,t,1024);x=residual+layer.self_attn.out_proj(a);residual=x;x=layer.norm2(x);x=residual+layer.linear2(ExactGelu.apply(layer.linear1(x)));new.append((nk,nv))
  return x,new
 def forward(self,voice_embeddings,text_embeddings,noise):
  caches=[None]*6;x,caches=self.block(voice_embeddings,0,caches);x,caches=self.block(text_embeddings,126,caches);lat=[];logits=[];cur=None
  for step in range(self.steps):
   if step==0:seq=self.flow.bos_emb.reshape(1,1,32)
   else:seq=cur.reshape(1,1,32)
   x=self.flow.input_linear(seq);x,caches=self.block(x,152+step,caches);c=self.flow.out_norm(x)[:,-1];logits.append(self.flow.out_eos(c));n=noise[:,step];cur=n+self.flow.flow_net(c,torch.zeros_like(n[:,:1]),torch.ones_like(n[:,:1]),n);lat.append(cur)
  return torch.stack(lat,1),torch.stack(logits,1)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--exporter-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--steps',type=int,default=100);a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
 from pocket_tts.models.tts_model import TTSModel
 torch.manual_seed(0);tts=TTSModel.load_model(config=str(a.config)).cpu().eval();m=UnrolledFlow(tts.flow_lm,a.steps).eval();voice=torch.randn(1,126,1024);text=torch.randn(1,26,1024);noise=torch.randn(1,a.steps,32)
 with torch.no_grad():pt=m(voice,text,noise)
 torch.onnx.export(m,(voice,text,noise),str(a.output),input_names=['voice_embeddings','text_embeddings','noise'],output_names=['latents','eos_logits'],opset_version=17,dynamo=False,do_constant_folding=True)
 import onnx,onnxruntime as ort,numpy as np
 q=onnx.load(str(a.output));aliases={};removed=set()
 for node in q.graph.node:
  if node.op_type=='Identity' and len(node.input)==len(node.output)==1:aliases[node.output[0]]=node.input[0];removed.add(node.name)
 def resolve(name):
  while name in aliases:name=aliases[name]
  return name
 for node in q.graph.node:
  for i,name in enumerate(node.input):node.input[i]=resolve(name)
 for out in q.graph.output:out.name=resolve(out.name)
 nodes=[node for node in q.graph.node if node.name not in removed];del q.graph.node[:];q.graph.node.extend(nodes);onnx.checker.check_model(q,full_check=True);onnx.save(q,str(a.output));o=ort.SessionOptions();o.intra_op_num_threads=1;o.inter_op_num_threads=1;s=ort.InferenceSession(str(a.output),o,providers=['CPUExecutionProvider']);got=s.run(None,{'voice_embeddings':voice.numpy(),'text_embeddings':text.numpy(),'noise':noise.numpy()});checks=[]
 for x,y in zip(pt,got):d=np.abs(x.numpy().astype(np.float64)-y.astype(np.float64));checks.append({'max_abs':float(d.max()),'mean_abs':float(d.mean())})
 report={'schema_version':1,'derivative':'static-unrolled-exact-length-flowlm','steps':a.steps,'source':{'config':str(a.config.resolve()),'weights_sha256':sha(a.config.parent/'source-assets/languages/english/model.safetensors'),'exporter_commit':subprocess.check_output(['git','-C',str(a.exporter_root),'rev-parse','HEAD'],text=True).strip()},'output':{'path':str(a.output),'bytes':a.output.stat().st_size,'sha256':sha(a.output),'nodes':len(q.graph.node),'initializers':len(q.graph.initializer),'operator_types':sorted(set(x.op_type for x in q.graph.node))},'torch_vs_onnx':checks,'abi':{'voice':[1,126,1024],'text':[1,26,1024],'noise':[1,a.steps,32],'latents':[1,a.steps,32],'eos_logits':[1,a.steps,1]},'host_orchestration':'CPU creates noise and scans EOS logits; all learned FlowLM, cache updates, autoregression, and flow computation are inside this neural graph.'};Path(str(a.output)+'.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
