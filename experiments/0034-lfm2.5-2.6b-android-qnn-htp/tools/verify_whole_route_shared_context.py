#!/usr/bin/env python3
"""Bind all 37 graph models/order to the single shared QNN context binary."""
import argparse,hashlib,json
from pathlib import Path
import onnx
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
ap=argparse.ArgumentParser();ap.add_argument('--group-dir',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();result=json.loads((a.group_dir/'result.json').read_text());info=json.loads((a.group_dir/'context-info.json').read_text())['info'];binary=a.group_dir/result['shared_context_binary']['path']
if result['graph_count']!=37 or info['numGraphs']!=37:raise SystemExit('expected 37 graphs')
models=[]
for i,item in enumerate(result['models']):
 p=a.group_dir/item['context_model'];m=onnx.load(p);nodes=[n for n in m.graph.node if n.op_type=='EPContext'];graph=info['graphs'][i]['info']['graphName']
 if len(nodes)!=1 or nodes[0].name!=graph:raise SystemExit(f'order mismatch {item["name"]}')
 attrs={x.name:onnx.helper.get_attribute_value(x) for x in nodes[0].attribute}
 if attrs['ep_cache_context'].decode()!=binary.name:raise SystemExit(f'binary mismatch {item["name"]}')
 models.append({'ordinal':i,'alias':item['name'],'graph_name':graph,'context_model_sha256':sha(p)})
out={'schema_version':1,'classification':'host_whole_route_single_shared_qnn_context_metadata','target':result['target'],'context_binary':{'bytes':binary.stat().st_size,'sha256':sha(binary),'build_id':info['buildId'],'blob_bytes':info['contextBlobSize']},'graph_count':37,'all_graphs_present_once_in_exact_order':True,'execution_order':result['execution_order'],'models':models,'host_retrieval':{'success':False,'exact_error':'Shared weights buffer is not supported on this platform','interpretation':'x86 HTP emulator limitation; physical Android support remains unproven'},'loaded_route_semantics':'one context loaded once containing all 37 ordered graphs; no per-layer/token reload','claim_boundary':'Host AOT and metadata only. The one-context binary has not executed on physical Android/HTP.'};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'graphs':37,'bytes':binary.stat().st_size,'sha256':sha(binary)},indent=2))
