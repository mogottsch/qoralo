#!/usr/bin/env python3
"""Prepare, host-run, and compare the real one-chunk Android generation chain."""
from __future__ import annotations
import argparse, hashlib, json, resource, time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'experiments/0002-vibevoice-1.5b-executorch-android'
ART=ROOT/'artifacts/0002'
F32=np.dtype('<f4'); I64=np.dtype('<i8')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):
 a=v.detach().cpu().contiguous().numpy() if hasattr(v,'detach') else np.asarray(v)
 p.write_bytes(a.astype(F32,copy=False).tobytes())
def read(p,shape):
 a=np.fromfile(p,dtype=F32)
 if a.size!=int(np.prod(shape)): raise ValueError(f'{p}: expected {np.prod(shape)}, got {a.size}')
 return a.reshape(shape)
def meta(p,shape):
 a=read(p,shape); return {'file':p.name,'shape':list(shape),'dtype':'float32','bytes':p.stat().st_size,'sha256':sha(p),'finite':bool(np.isfinite(a).all())}

def prepare(a):
 import torch
 a.output.mkdir(parents=True,exist_ok=True)
 q=ART/'lane-c/qwen2-fixtures'; pre=torch.load(q/'prefill.pt',map_location='cpu',weights_only=True); dec=torch.load(q/'decode.pt',map_location='cpu',weights_only=True)
 loop=torch.load(ART/'lane-b/diffusion-android/diffusion-loop.reference.pt',map_location='cpu',weights_only=True)
 files={'prompt-embeddings.f32le':pre['inputs_embeds'],'speech-start-embedding.f32le':dec['inputs_embeds'],'initial-noise.f32le':loop['initial_latent'],'negative-condition.f32le':loop['negative_condition'],'timesteps.f32le':loop['timesteps'],'sigmas.f32le':loop['sigmas']}
 for n,v in files.items(): put(a.output/n,v)
 text=(ROOT/'artifacts/0001/reference.txt').read_text().strip(); (a.output/'prompt.txt').write_text(text+'\n')
 manifest={'schema_version':1,'input_kind':'smallest pinned real text fixture accepted by the fixed S=503 Qwen2 export','text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'prefill_tokens':503,'seed':42,'cfg':1.3,'inputs':{n:{'bytes':(a.output/n).stat().st_size,'sha256':sha(a.output/n)} for n in files},'boundary':'Only text-derived embeddings, speaker negative condition, schedule, and seeded initial noise are initial inputs. No generated intermediate is serialized back into the chain.'}
 (a.output/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n'); print(json.dumps(manifest,indent=2))

def load_method(runtime,path): return runtime.load_program(str(path)).load_method('forward')
def execute(runtime,path,inputs): return tuple(x.clone() for x in load_method(runtime,path).execute(tuple(inputs)))
def qwen(runtime,root,embed,length,caches=None,position=0):
 import torch
 pre=length==503; cap=1024; mask=torch.zeros((1,cap),dtype=torch.int64); mask[:,:503 if pre else position+1]=1
 pos=torch.arange(503,dtype=torch.int64).reshape(1,-1) if pre else torch.tensor([[position]],dtype=torch.int64); cp=pos.reshape(-1)
 stem='' if pre else 'decode-'; hidden,causal,cos,sin=execute(runtime,root/f'{stem}prepare.pte',(embed,mask,pos,cp)); zero=torch.zeros((1,2,cap,128)); nxt=[]
 for i in range(28):
  kv=(zero,zero) if pre else (caches[2*i],caches[2*i+1]); out=execute(runtime,root/f'{stem}layer-{i:02d}.pte',(hidden,causal,cp,cos,sin,*kv)); hidden=out[0]; nxt.extend(out[1:])
 hidden,logits=execute(runtime,root/f'{stem}final.pte',(hidden,)); return hidden,logits,nxt

def host(a):
 import torch
 from executorch.runtime import Runtime
 from diffusion_scheduler import DpmSolverState
 runtime=Runtime.get(); inp=a.inputs; out=a.output; out.mkdir(parents=True,exist_ok=True); times={}; qroot=ART/'lane-c/qwen2-int8-package'
 prompt=torch.from_numpy(read(inp/'prompt-embeddings.f32le',(1,503,1536)).copy()); speech=torch.from_numpy(read(inp/'speech-start-embedding.f32le',(1,1,1536)).copy())
 t=time.perf_counter(); h0,l0,c0=qwen(runtime,qroot,prompt,503); times['qwen_prefill']=time.perf_counter()-t
 allowed=[151643,151652,151653,151654]; tok0=max(allowed,key=lambda x:(float(l0[0,x]),-x)); assert tok0==151654
 noise=torch.from_numpy(read(inp/'initial-noise.f32le',(1,64)).copy());neg=torch.from_numpy(read(inp/'negative-condition.f32le',(1,1536)).copy());ts=torch.from_numpy(read(inp/'timesteps.f32le',(10,)).copy());sig=torch.from_numpy(read(inp/'sigmas.f32le',(11,)).copy()); sched=DpmSolverState(sig); diff=load_method(runtime,ART/'lane-b/diffusion-head/diffusion-step-xnnpack.pte')
 t=time.perf_counter();latent=noise
 for step in ts: latent=sched.step(diff.execute((latent,step.reshape(1),h0.reshape(1,1536),neg))[0].clone(),latent)
 times['diffusion']=time.perf_counter()-t; put(out/'diffusion.f32le',latent)
 x=latent.reshape(1,64,1);t=time.perf_counter()
 for i in range(8): x=execute(runtime,ART/f'acoustic-decoder-streaming-first-segments-1.2/segment-{i}.pte',(x,))[0]
 times['decoder']=time.perf_counter()-t;put(out/'decoder_pcm.f32le',x)
 t=time.perf_counter(); sem=execute(runtime,ART/'lane-b/semantic-encoder/semantic-encoder-first-xnnpack.pte',(x,))[0];times['semantic']=time.perf_counter()-t;put(out/'semantic_features.f32le',sem)
 t=time.perf_counter();conn=execute(runtime,ART/'lane-b/connectors/connectors-xnnpack.pte',(latent.reshape(1,1,64),sem))[0];times['connector']=time.perf_counter()-t;put(out/'connector_embedding.f32le',conn)
 t=time.perf_counter();h1,l1,_=qwen(runtime,qroot,conn,1,c0,503);times['qwen_decode_503']=time.perf_counter()-t
 put(out/'qwen_prefill_hidden.f32le',h0);put(out/'qwen_prefill_logits.f32le',l0);put(out/'qwen_decode_503_hidden.f32le',h1);put(out/'qwen_decode_503_logits.f32le',l1)
 pcm=np.clip(x.detach().numpy().reshape(-1),-1,1); pcm16=np.round(pcm*np.where(pcm<0,32768,32767)).astype('<i2');(out/'generation.pcm').write_bytes(pcm16.tobytes())
 result={'schema_version':1,'status':'passed','tokens':[tok0],'timings_seconds':times,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'intermediates':{p.stem:{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.glob('*.f32le')},'pcm':{'sha256':sha(out/'generation.pcm'),'samples':pcm16.size,'finite':bool(np.isfinite(pcm).all())}}
 (out/'host-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

def compare(a):
 device=json.loads(a.device_result.read_text()); host=json.loads((a.host/'host-result.json').read_text()); shapes={'qwen_prefill_hidden':(1536,),'qwen_prefill_logits':(151936,),'qwen_decode_503_hidden':(1536,),'qwen_decode_503_logits':(151936,),'diffusion':(64,),'decoder_pcm':(3200,),'semantic_features':(128,),'connector_embedding':(1536,)}
 runs=[];accepted=device.get('status')=='passed' and host.get('status')=='passed'
 for r in range(2):
  records={}
  for name,shape in shapes.items():
   hp=a.host/f'{name}.f32le';dp=a.artifacts/f'generation-run-{r}-{name}.f32le';e=read(hp,shape);v=read(dp,shape);d=np.abs(e-v);atol=1e-3 if name.startswith('qwen') else (1e-4 if name in ('diffusion','semantic_features','connector_embedding') else 2e-5); close=np.isclose(e,v,atol=atol,rtol=1e-4);cos=float(np.dot(e.reshape(-1).astype('float64'),v.reshape(-1).astype('float64'))/(np.linalg.norm(e)*np.linalg.norm(v)));nrmse=float(np.linalg.norm(e-v)/max(np.linalg.norm(e),1e-12));criterion=(bool(close.all()) if name=='decoder_pcm' else (cos>=0.99 if name.startswith('qwen_prefill') else (cos>=0.98 if name.startswith('qwen_decode') else (cos>=0.999 if name=='semantic_features' else (cos>=0.97 if name=='connector_embedding' else True)))));records[name]={'host_sha256':sha(hp),'android_sha256':sha(dp),'finite':bool(np.isfinite(v).all()),'max_abs_error':float(d.max(initial=0)),'mean_abs_error':float(d.mean()),'mismatch_count':int((~close).sum()),'atol':atol,'rtol':1e-4,'strict_allclose':bool(close.all()),'cosine_similarity':cos,'nrmse':nrmse,'integration_criterion':criterion};accepted &= records[name]['finite'] and criterion
  runs.append(records)
 pcm0=a.artifacts/'generation-run-0.pcm';pcm1=a.artifacts/'generation-run-1.pcm';det=sha(pcm0)==sha(pcm1); raw=np.fromfile(pcm0,dtype='<i2');accepted &= det and raw.size==3200
 result={'schema_version':1,'status':'passed' if accepted else 'rejected','scope':'one real text prompt through actual chained Android component outputs to one PCM chunk','provenance':{'source_revision':'6dd49cb7200c0367205a5f1e650244259e9e423d','model_revision':'c00898d257e6b46004e3e2866a47534085fb685a','seed':42,'cfg':1.3},'actual_output_chaining':True,'fixture_intermediate_substitution':False,'comparison_policy':{'qwen_prefill_cosine_min':0.99,'qwen_decode_cosine_min':0.98,'semantic_cosine_min':0.999,'connector_cosine_min':0.97,'decoder_pcm_atol':2e-5,'diffusion':'finite and reported; downstream PCM must pass','rationale':'The accepted INT8/XNNPACK backbone has documented host-to-Android numerical drift. Integration therefore preserves its directional criteria, reports strict mismatches, and requires the externally consumed decoder PCM to remain strict and bit-deterministic.'},'host_intermediate_comparison':runs,'pcm':{'sample_rate_hz':24000,'channels':1,'encoding':'S16LE','samples':int(raw.size),'bytes':pcm0.stat().st_size,'finite':True,'non_empty':raw.size>0,'sha256':sha(pcm0),'repeat_sha256':sha(pcm1),'deterministic':det},'timings_seconds':device.get('runs'),'memory_kib':device.get('memory_kib'),'host':host,'device':json.loads(a.device_properties.read_text()),'runtime':{'executorch':'1.2.0','backend':'xnnpack','qwen_precision':'int8','other_precision':'fp32'},'implementation_commits':[a.commit],'commands':['generation_android_io.py prepare','generation_android_io.py host','android/run-generation-probe.sh'],'conclusion':'Accepted: the Galaxy S23 Ultra chained actual component outputs without fixture substitution and emitted a deterministic finite mono 24 kHz PCM chunk matching host intermediates.' if accepted else 'Rejected: one or more chaining, host-intermediate, PCM, or determinism criteria failed.'}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if accepted else 2)

def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True);x=s.add_parser('prepare');x.add_argument('output',type=Path);x.set_defaults(f=prepare);x=s.add_parser('host');x.add_argument('inputs',type=Path);x.add_argument('output',type=Path);x.set_defaults(f=host);x=s.add_parser('compare');x.add_argument('host',type=Path);x.add_argument('artifacts',type=Path);x.add_argument('device_result',type=Path);x.add_argument('device_properties',type=Path);x.add_argument('output',type=Path);x.add_argument('--commit',required=True);x.set_defaults(f=compare);a=p.parse_args();a.f(a)
if __name__=='__main__':main()
