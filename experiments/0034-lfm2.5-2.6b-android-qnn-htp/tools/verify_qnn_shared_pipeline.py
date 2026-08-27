#!/usr/bin/env python3
"""Verify shared QNN context graph counts, order, references, and hashes."""
import argparse,hashlib,json
from pathlib import Path
import onnx

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
ap=argparse.ArgumentParser();ap.add_argument('--pipeline-dir',type=Path,required=True);ap.add_argument('--parts-dir',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
s=json.loads((a.pipeline_dir/'summary.json').read_text());source=json.loads((a.parts_dir/'manifest.json').read_text());expected=[x['name'] for x in source['parts']];observed=[];groups=[]
for group in s['groups']:
 d=a.pipeline_dir/group['name'];info=json.loads((d/'context-info.json').read_text())['info'];graphs=info['graphs'];models=[]
 if info['numGraphs']!=group['graph_count'] or len(graphs)!=group['graph_count']:raise SystemExit(f"count mismatch: {group['name']}")
 binary=d/group['shared_context_binary']['path']
 if sha(binary)!=group['shared_context_binary']['sha256']:raise SystemExit(f"hash mismatch: {binary}")
 for i,name in enumerate(group['execution_order']):
  model_path=d/f"{i:03d}-{name}-ctx.onnx";model=onnx.load(model_path);nodes=[n for n in model.graph.node if n.op_type=='EPContext']
  if len(nodes)!=1:raise SystemExit(f'EPContext node count: {model_path}')
  node=nodes[0];attrs={x.name:onnx.helper.get_attribute_value(x) for x in node.attribute};graph_name=graphs[i]['info']['graphName']
  if node.name!=graph_name or attrs['partition_name'].decode()!=graph_name:raise SystemExit(f'graph order mismatch: {name}')
  if attrs['ep_cache_context'].decode()!=binary.name:raise SystemExit(f'binary reference mismatch: {name}')
  models.append({'name':name,'graph_name':graph_name,'context_model_sha256':sha(model_path)})
 observed+=group['execution_order'];groups.append({'name':group['name'],'num_graphs':info['numGraphs'],'context_binary_bytes':binary.stat().st_size,'context_binary_sha256':sha(binary),'models':models})
if observed!=expected:raise SystemExit('global execution order mismatch')
r={'schema_version':1,'classification':'host_shared_qnn_metadata_verification','source_part_count':len(expected),'shared_context_count':len(groups),'all_graphs_present_once_in_order':True,'all_epcontext_models_reference_group_binary':True,'target':s['target'],'groups':groups,'claim_boundary':'Serialized metadata and hashes only; not physical execution.'}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(f"verified {len(expected)} graphs in {len(groups)} contexts")
