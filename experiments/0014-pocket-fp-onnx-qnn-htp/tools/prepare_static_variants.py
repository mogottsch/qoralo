#!/usr/bin/env python3
"""Fix every graph I/O dimension to the observed 0014 Pocket call signatures."""
import argparse,hashlib,json
from pathlib import Path
import onnx

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def setshape(vi,shape):
 dims=vi.type.tensor_type.shape.dim
 if len(dims)!=len(shape):raise ValueError((vi.name,len(dims),shape))
 for d,n in zip(dims,shape):
  if n<0:raise ValueError((vi.name,shape))
  d.ClearField('dim_param');d.dim_value=n
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--shapes',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
observed=json.loads(a.shapes.read_text())['components']
variants={
 'text_conditioner':[('text26',observed['text_conditioner'][0])],
 'flow_lm_flow':[('flow1',observed['flow_lm_flow'][0])],
 'mimi_encoder':[('encoder240000',observed['mimi_encoder'][0])],
 'flow_lm_main':[('voice126',observed['flow_lm_main'][0]),('text26',observed['flow_lm_main'][1]),('ar1',observed['flow_lm_main'][2])],
 'mimi_decoder':[('decoder12',observed['mimi_decoder'][0])]
}
# Android's 78-frame oracle calls six 12-frame chunks plus one 6-frame tail.
# A one-frame variant also provides a bounded fallback for any honest EOS tail.
for frames in (6,1):
 d=json.loads(json.dumps(observed['mimi_decoder'][0]));d['inputs']['latent']['shape']=[1,frames,32];d['outputs'][0]['shape']=[1,1,1920*frames];d['calls']=1;variants['mimi_decoder'].append((f'decoder{frames}',d))
a.output.mkdir(parents=True,exist_ok=True);report={'schema_version':1,'source_shapes':str(a.shapes),'variants':[]}
for component,items in variants.items():
 src=a.source/f'{component}.onnx'
 for name,sig in items:
  model=onnx.load(str(src));ins={x.name:x for x in model.graph.input};outs=list(model.graph.output)
  if set(ins)!=set(sig['inputs']):raise ValueError((component,set(ins)^set(sig['inputs'])))
  if len(outs)!=len(sig['outputs']):raise ValueError((component,len(outs),len(sig['outputs'])))
  for key,item in sig['inputs'].items():setshape(ins[key],item['shape'])
  for vi,item in zip(outs,sig['outputs']):setshape(vi,item['shape'])
  model=onnx.shape_inference.infer_shapes(model,strict_mode=True);onnx.checker.check_model(model,full_check=True)
  dst=a.output/f'{component}-{name}.onnx';onnx.save(model,str(dst))
  report['variants'].append({'component':component,'variant':name,'source_sha256':sha(src),'path':str(dst),'bytes':dst.stat().st_size,'sha256':sha(dst),'inputs':{k:v['shape'] for k,v in sig['inputs'].items()},'outputs':{vi.name:v['shape'] for vi,v in zip(outs,sig['outputs'])}})
(a.output/'variants.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
