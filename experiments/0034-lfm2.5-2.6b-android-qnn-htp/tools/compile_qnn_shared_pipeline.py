#!/usr/bin/env python3
"""Compile all ordered pipeline parts into bounded shared multi-graph contexts."""
from __future__ import annotations
import argparse,json,math,subprocess,sys,time
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--parts-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--group-size',type=int,default=8);ap.add_argument('--python',type=Path,default=Path(sys.executable));a=ap.parse_args()
 if not 2<=a.group_size<=16:raise SystemExit('group size must be 2..16')
 manifest=json.loads((a.parts_dir/'manifest.json').read_text());total=len(manifest['parts']);worker=Path(__file__).with_name('compile_qnn_shared_context_group.py');a.output_dir.mkdir(parents=True,exist_ok=True);groups=[];started=time.time_ns()
 for start in range(0,total,a.group_size):
  count=min(a.group_size,total-start);name=f'parts-{start:03d}-{start+count-1:03d}';result=a.output_dir/name/'result.json'
  if not result.exists():
   log=a.output_dir/f'{name}.log'
   with log.open('wb') as f:r=subprocess.run([str(a.python),str(worker),'--parts-dir',str(a.parts_dir),'--output-dir',str(a.output_dir),'--start',str(start),'--count',str(count)],stdout=f,stderr=subprocess.STDOUT)
   if r.returncode:raise RuntimeError(f'{name} failed; see {log}')
  d=json.loads(result.read_text());groups.append({'name':name,'graph_count':d['graph_count'],'execution_order':d['execution_order'],'shared_context_binary':d['shared_context_binary']});print(f'[{len(groups)}/{math.ceil(total/a.group_size)}] {name}',flush=True)
 summary={'schema_version':1,'classification':'host_shared_multi_graph_qnn_pipeline_preparation','source_manifest':str(a.parts_dir/'manifest.json'),'target':{'soc_model':43,'htp_arch':73},'source_part_count':total,'shared_context_count':len(groups),'group_size_ceiling':a.group_size,'ordered_graph_count':sum(x['graph_count'] for x in groups),'execution_order':[n for g in groups for n in g['execution_order']],'fallback_disabled':True,'loaded_route_semantics':'all contexts loaded once; each contains multiple ordered graphs; no request/token reload','groups':groups,'started_ns':started,'stopped_ns':time.time_ns(),'claim_boundary':'Host AOT consolidation only; physical execution requires separate authorization.'}
 if summary['execution_order'] != [p['name'] for p in manifest['parts']]:raise RuntimeError('order mismatch')
 (a.output_dir/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n');print(a.output_dir/'summary.json')
if __name__=='__main__':main()
