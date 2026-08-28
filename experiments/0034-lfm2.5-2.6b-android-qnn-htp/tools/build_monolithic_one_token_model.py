#!/usr/bin/env python3
"""Merge the 37 ordered fused models into one ordinary one-token ONNX graph."""
import argparse,hashlib,json
from copy import deepcopy
from pathlib import Path
import onnx

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()

def unique(items):
 out={}
 for x in items:out.setdefault(x.name,deepcopy(x))
 return list(out.values())

ap=argparse.ArgumentParser();ap.add_argument('--models-dir',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--result',type=Path,required=True);a=ap.parse_args()
manifest=json.loads((a.models_dir/'manifest.json').read_text());models=[]
for item in manifest['models']:
 m=onnx.load(a.models_dir/item['path'],load_external_data=True);models.append((item,m))
produced={y for _,m in models for n in m.graph.node for y in n.output if y}
inputs=unique(x for _,m in models for x in m.graph.input if x.name not in produced)
# Preserve every explicit recurrent/attention state output and all independent logit chunks.
outputs=[]
for item,m in models:
 for x in m.graph.output:
  if x.name.startswith('present') or item['kind']=='consolidated_lm_head':outputs.append(x)
outputs=unique(outputs)
nodes=[deepcopy(n) for _,m in models for n in m.graph.node]
init_map={}
for _,m in models:
 for x in m.graph.initializer:
  if x.name in init_map and x.SerializeToString()!=init_map[x.name].SerializeToString():raise SystemExit(f'conflicting initializer {x.name}')
  init_map.setdefault(x.name,deepcopy(x))
inits=list(init_map.values())
vis=unique(x for _,m in models for x in list(m.graph.value_info)+list(m.graph.input)+list(m.graph.output) if x.name not in {y.name for y in inputs+outputs})
opsets={x.domain:x.version for _,m in models for x in m.opset_import};imports=[onnx.helper.make_opsetid(k,v) for k,v in sorted(opsets.items())]
g=onnx.helper.make_graph(nodes,'lfm2_one_token_ordinary_monolith',inputs,outputs,inits,value_info=vis)
out=onnx.helper.make_model(g,opset_imports=imports,producer_name='0034-build-monolithic-one-token-model')
out.ir_version=max(m.ir_version for _,m in models)
a.output.parent.mkdir(parents=True,exist_ok=True);data=a.output.name+'.data';# Keep tiny shape/axes tensors inline because ORT shape inference reads them before
# resolving external data; large weights remain in one ordinary external-data file.
onnx.save_model(out,a.output,save_as_external_data=True,all_tensors_to_one_file=True,location=data,size_threshold=1024,convert_attribute=False)
onnx.checker.check_model(str(a.output))
meta={'schema_version':1,'classification':'ordinary_monolithic_one_token_onnx','source_manifest_sha256':sha(a.models_dir/'manifest.json'),'source_model_count':len(models),'execution_order':[x['name'] for x,_ in models],'node_count':len(nodes),'initializer_count':len(inits),'input_names':[x.name for x in inputs],'output_names':[x.name for x in outputs],'explicit_state_input_count':sum(x.name.startswith('past_') for x in inputs),'explicit_state_output_count':sum(x.name.startswith('present') for x in outputs),'logit_chunk_output_count':sum(x.name.startswith('logits_vocab_') for x in outputs),'shared_resource_format':False,'weight_sharing_format':False,'context_streaming':False,'onnx_sha256':sha(a.output),'external_data':{'path':data,'bytes':(a.output.parent/data).stat().st_size,'sha256':sha(a.output.parent/data)},'claim_boundary':'Host ONNX construction only; not QNN compilation or physical execution.'};a.result.parent.mkdir(parents=True,exist_ok=True);a.result.write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n');print(json.dumps({k:meta[k] for k in ('node_count','initializer_count','explicit_state_input_count','explicit_state_output_count','logit_chunk_output_count','onnx_sha256')},indent=2))
