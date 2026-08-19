#!/usr/bin/env python3
"""Hash-bound QNN compatibility rewrites for Pocket Mimi static ONNX variants.

The transformations are deliberately narrow:
* remove an encoder Pad whose six pad extents are all zero;
* replace exact five-node erf-GELU decompositions with com.microsoft.Gelu;
* bypass NaN-scrubbing around Softmax (validated separately on real fixtures);
* expose unchanged decoder states directly as graph outputs instead of unsupported Identity nodes.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np,onnx
from onnx import helper,numpy_helper
EXPECTED={
 'mimi_encoder-encoder240000':'1cfec92031dd110be9392c6a2228e0794e6f3daff97c3d3fe99db4934b33f6a0',
 'mimi_decoder-decoder12':'8100e145bcff619be03146a051433c6ef293b99ecaf79490e34a360a051ff018',
 'mimi_decoder-decoder6':'ec676bd5302f35623923044107c3a89b6f4a8d94464be481d115b05062286d60',
 'mimi_decoder-decoder1':'bab1533646bb2c787635d570ce15ff47df8c4ce0e75f591a9881cf4138dffcb5',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def consumers(model):
 out={}
 for n in model.graph.node:
  for x in n.input:out.setdefault(x,[]).append(n)
 return out
def constants(model):
 d={x.name:numpy_helper.to_array(x) for x in model.graph.initializer}
 for n in model.graph.node:
  if n.op_type=='Constant' and len(n.output)==1:
   a=[x for x in n.attribute if x.name=='value']
   if len(a)==1:d[n.output[0]]=numpy_helper.to_array(a[0].t)
 return d
def replace_inputs(model,mapping):
 for n in model.graph.node:
  for i,x in enumerate(n.input):
   while x in mapping:x=mapping[x]
   n.input[i]=x
 for o in model.graph.output:
  x=o.name
  while x in mapping:x=mapping[x]
  o.name=x
def rewrite_encoder(model,report):
 by={n.output[0]:n for n in model.graph.node if len(n.output)==1};con=consumers(model);const=constants(model);remove=set();mapping={}
 pads=[n for n in model.graph.node if n.op_type=='Pad']
 if len(pads)!=1:raise ValueError(f'expected one Pad, got {len(pads)}')
 pad=pads[0];ext=np.asarray(const[pad.input[1]])
 if ext.shape!=(6,) or np.any(ext!=0):raise ValueError(f'Pad is not zero-only: {ext}')
 mapping[pad.output[0]]=pad.input[0];remove.add(pad.name);report['zero_pad_removed']=pad.name
 erfs=[n for n in model.graph.node if n.op_type=='Erf']
 if len(erfs)!=2:raise ValueError(f'expected two Erf, got {len(erfs)}')
 replacements={}
 for erf in erfs:
  div=by[erf.input[0]]
  if div.op_type!='Div' or len(div.input)!=2:raise ValueError(div.name)
  scalar=[x for x in div.input if x in const and np.asarray(const[x]).shape==()]
  if len(scalar)!=1 or not np.isclose(float(const[scalar[0]]),np.sqrt(2),rtol=0,atol=2e-7):raise ValueError(div.name)
  x=div.input[1] if div.input[0]==scalar[0] else div.input[0]
  c=con[erf.output[0]]
  if len(c)!=1 or c[0].op_type!='Add':raise ValueError(erf.name)
  add=c[0];c=con[add.output[0]]
  if len(c)!=1 or c[0].op_type!='Mul':raise ValueError(add.name)
  mul=c[0];c=con[mul.output[0]]
  if len(c)!=1 or c[0].op_type!='Mul':raise ValueError(mul.name)
  last=c[0]
  if x not in last.input:raise ValueError('GELU does not reuse x')
  half_inputs=[z for z in mul.input if z in const and np.asarray(const[z]).shape==()]
  if len(half_inputs)!=1 or float(const[half_inputs[0]])!=0.5:raise ValueError('GELU half constant mismatch')
  replacements[div.name]=helper.make_node('Gelu',[x],[last.output[0]],name=div.name+'_qnn_gelu',domain='com.microsoft')
  remove.update([div.name,erf.name,add.name,mul.name,last.name]);report.setdefault('gelu_rewrites',[]).append({'removed':[div.name,erf.name,add.name,mul.name,last.name],'x':x,'output':last.output[0]})
 report['_replacements']=replacements;report['_mapping']=mapping;report['_remove']=remove

def bypass_nan_scrub(model,report):
 con=consumers(model);mapping={};remove=set()
 for n in [x for x in model.graph.node if x.op_type=='IsNaN']:
  cs=con.get(n.output[0],[])
  if len(cs)!=1 or cs[0].op_type!='Where':raise ValueError(f'{n.name} not sole Where predicate')
  w=cs[0]
  if len(w.input)!=3 or w.input[2]!=n.input[0]:raise ValueError(f'{w.name} false branch is not IsNaN input')
  mapping[w.output[0]]=n.input[0];remove.update([n.name,w.name]);report.setdefault('nan_scrubs_bypassed',[]).append({'isnan':n.name,'where':w.name,'softmax':n.input[0],'output':w.output[0]})
 replace_inputs(model,mapping)
 return remove

def rewrite_decoder_identities(model,report):
 outputs={x.name:x for x in model.graph.output};remove=set();aliases=[]
 for n in [x for x in model.graph.node if x.op_type=='Identity']:
  if len(n.input)!=1 or len(n.output)!=1 or n.output[0] not in outputs:raise ValueError(f'Identity {n.name} is not graph-output-only')
  out=outputs[n.output[0]];old=out.name;out.name=n.input[0];aliases.append({'index':list(model.graph.output).index(out),'old_output':old,'direct_input_output':n.input[0]});remove.add(n.name)
 if len(remove)!=39:raise ValueError(f'expected 39 output Identity nodes, got {len(remove)}')
 if len({x.name for x in model.graph.output})!=len(model.graph.output):raise ValueError('duplicate output after aliases')
 report['direct_state_aliases']=aliases;return remove

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();key=a.input.stem
 actual=sha(a.input)
 if EXPECTED.get(key)!=actual:raise SystemExit(f'unexpected {key} hash {actual}')
 m=onnx.load(str(a.input));onnx.checker.check_model(m,full_check=True);before=len(m.graph.node);report={'schema_version':1,'derivative':'qnn-compatible-mimi-static','source':{'path':str(a.input),'sha256':actual,'bytes':a.input.stat().st_size},'variant':key}
 replacements={};remove=set()
 if key.startswith('mimi_encoder'):
  rewrite_encoder(m,report);replacements=report.pop('_replacements');remove|=report.pop('_remove');replace_inputs(m,report.pop('_mapping'))
 remove|=bypass_nan_scrub(m,report)
 if key.startswith('mimi_decoder'):remove|=rewrite_decoder_identities(m,report)
 nodes=[]
 for n in m.graph.node:
  if n.name in replacements:nodes.append(replacements[n.name])
  elif n.name not in remove:nodes.append(n)
 del m.graph.node[:];m.graph.node.extend(nodes);m.doc_string=(m.doc_string+'\n' if m.doc_string else '')+'Derivative: audited QNN compatibility rewrites; see provenance report.'
 onnx.checker.check_model(m,full_check=True);a.output.parent.mkdir(parents=True,exist_ok=True);onnx.save(m,str(a.output));m2=onnx.load(str(a.output));onnx.checker.check_model(m2,full_check=True)
 report['output']={'path':str(a.output),'sha256':sha(a.output),'bytes':a.output.stat().st_size};report['nodes']={'before':before,'after':len(m2.graph.node),'removed':before-len(m2.graph.node)};report['op_counts_after']={op:sum(x.op_type==op for x in m2.graph.node) for op in ['Pad','Erf','IsNaN','Identity','Gelu']};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
