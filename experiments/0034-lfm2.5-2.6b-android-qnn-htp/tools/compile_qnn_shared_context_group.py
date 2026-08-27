#!/usr/bin/env python3
"""Compile ordered pipeline parts into one shared multi-graph QNN context binary."""
from __future__ import annotations
import argparse,hashlib,json,time
from pathlib import Path
import onnxruntime as ort
import onnxruntime_qnn as qnn

def digest(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--parts-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--start',type=int,required=True);ap.add_argument('--count',type=int,required=True);a=ap.parse_args()
 manifest=json.loads((a.parts_dir/'manifest.json').read_text());parts=manifest['parts'][a.start:a.start+a.count]
 if not parts:raise SystemExit('empty group')
 a.output_dir.mkdir(parents=True,exist_ok=True);name=f"parts-{a.start:03d}-{a.start+len(parts)-1:03d}";out=a.output_dir/name;out.mkdir(exist_ok=True)
 reg='QNNExecutionProvider';ort.register_execution_provider_library(reg,qnn.get_library_path())
 try:
  dev=next(d for d in ort.get_ep_devices() if d.ep_name==reg)
  so=ort.SessionOptions();so.log_severity_level=2;so.add_session_config_entry('session.disable_cpu_ep_fallback','1');so.add_session_config_entry('ep.context_enable','1');so.add_session_config_entry('ep.context_embed_mode','0');so.add_session_config_entry('ep.share_ep_contexts','1')
  so.add_provider_for_devices([dev],{'backend_path':qnn.get_qnn_htp_path(),'soc_model':'43','htp_arch':'73','enable_htp_prepare_only':'1','enable_block_quant_weight_optimization':'1','enable_htp_fp16_precision':'1','htp_graph_finalization_optimization_mode':'1'})
  models=[];sessions=[];started=time.time_ns()
  for i,part in enumerate(parts):
   target=out/f"{i:03d}-{part['name']}-ctx.onnx";so.add_session_config_entry('ep.context_file_path',str(target))
   if i==len(parts)-1:so.add_session_config_entry('ep.stop_share_ep_contexts','1')
   sessions.append(ort.InferenceSession(str(a.parts_dir/part['path']),sess_options=so))
   models.append({'ordinal':a.start+i,'name':part['name'],'source_sha256':digest(a.parts_dir/part['path']),'context_model':target.name,'context_model_sha256':digest(target)})
  bins=sorted(out.glob('*.bin'))
  if len(bins)!=1:raise RuntimeError(f'expected one shared binary, got {bins}')
  result={'schema_version':1,'classification':'host_shared_multi_graph_qnn_context_preparation','group':name,'target':{'soc_model':43,'htp_arch':73},'graph_count':len(parts),'execution_order':[x['name'] for x in models],'models':models,'shared_context_binary':{'path':bins[0].name,'bytes':bins[0].stat().st_size,'sha256':digest(bins[0])},'fallback_disabled':True,'loaded_route_semantics':'one serialized QNN context contains all ordered graphs; no per-token context reload','started_ns':started,'stopped_ns':time.time_ns(),'claim_boundary':'Host AOT consolidation only; no physical HTP execution.'}
  (out/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
 finally:ort.unregister_execution_provider_library(reg)
if __name__=='__main__':main()
