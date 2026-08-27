#!/usr/bin/env python3
"""Stitch split pipeline parts into 30 layer graphs, final norm, and grouped LM heads."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil
from pathlib import Path
import onnx
from onnx import helper

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--parts-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--heads-per-graph',type=int,default=4);a=ap.parse_args();manifest=json.loads((a.parts_dir/'manifest.json').read_text());by={x['name']:x for x in manifest['parts']}
 if a.output_dir.exists():shutil.rmtree(a.output_dir)
 a.output_dir.mkdir(parents=True)
 for data in a.parts_dir.glob('*.onnx_data'):os.link(data,a.output_dir/data.name)
 groups=[]
 for layer in range(30):groups.append((f'layer-{layer:02d}',[f'layer-{layer:02d}-{s}' for s in ('core-norm','up-0','gate-activate-0','up-1','gate-activate-1','down-0','down-1','residual')]))
 groups.append(('final-norm',['final-norm']))
 heads=[x['name'] for x in manifest['parts'] if x['kind']=='lm_head_chunk']
 for i in range(0,len(heads),a.heads_per_graph):groups.append((f'heads-{i//a.heads_per_graph:02d}',heads[i:i+a.heads_per_graph]))
 results=[]
 for name,members in groups:
  models=[onnx.load(a.parts_dir/by[x]['path'],load_external_data=False) for x in members];produced={o for m in models for n in m.graph.node for o in n.output};inputs={v.name:v for m in models for v in m.graph.input if v.name not in produced};initializers={v.name:v for m in models for v in m.graph.initializer};value_info={v.name:v for m in models for v in (*m.graph.value_info,*m.graph.input,*m.graph.output)}
  if name.startswith('layer-'):
   layer=int(name[-2:]);wanted=[f'/model/layers.{layer}/Add_2/output_0',f'present_conv.{layer}'] if layer not in {2,5,9,13,17,21,24,27} else [f'/model/layers.{layer}/Add_2/output_0',f'present.{layer}.key',f'present.{layer}.value']
  elif name=='final-norm':wanted=[models[0].graph.output[0].name]
  else:wanted=[o.name for m in models for o in m.graph.output]
  opsets={x.domain:x.version for m in models for x in m.opset_import};graph=helper.make_graph([n for m in models for n in m.graph.node],name,list(inputs.values()),[value_info[x] for x in wanted],list(initializers.values()),value_info=list(value_info.values()));model=helper.make_model(graph,opset_imports=[helper.make_opsetid(k,v) for k,v in opsets.items()],ir_version=max(m.ir_version for m in models));model.producer_name='vibevoice-0034-consolidation';path=a.output_dir/f'{name}.onnx';onnx.save_model(model,path)
  results.append({'name':name,'path':path.name,'source_parts':members,'inputs':list(inputs),'outputs':wanted,'nodes':len(graph.node),'initializers':len(graph.initializer),'sha256':sha(path)})
 for item in results:item['kind']='consolidated_layer' if item['name'].startswith('layer-') else ('final_norm' if item['name']=='final-norm' else 'consolidated_lm_head')
 out={'schema_version':1,'classification':'exact_pipeline_graph_consolidation','source_manifest':str(a.parts_dir/'manifest.json'),'source_part_count':len(manifest['parts']),'consolidated_model_count':len(results),'heads_per_graph':a.heads_per_graph,'models':results,'parts':results,'execution_semantics':'Each layer graph fuses its eight former sequential parts; head graphs contain independent chunks sharing the same input. Explicit recurrent/attention state remains graph I/O.','claim_boundary':'Host model transformation only.'};(a.output_dir/'manifest.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'models':len(results),'layers':30,'head_groups':(len(heads)+a.heads_per_graph-1)//a.heads_per_graph},indent=2))
if __name__=='__main__':main()
