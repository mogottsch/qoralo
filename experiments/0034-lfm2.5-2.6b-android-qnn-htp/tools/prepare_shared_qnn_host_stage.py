#!/usr/bin/env python3
"""Assemble an ignored x86 HTP-emulator stage for shared-context route validation."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--pipeline-dir',type=Path,required=True);ap.add_argument('--asset-stage',type=Path,required=True);ap.add_argument('--runner',type=Path,required=True);ap.add_argument('--qnn-lib-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args();s=json.loads((a.pipeline_dir/'summary.json').read_text());out=a.output_dir
if out.exists():shutil.rmtree(out)
(out/'shared-contexts').mkdir(parents=True)
def link(src,dst):dst.symlink_to(src.resolve())
for n in ('embedding-quant.u8','embedding-scales.f32le','embedding-zp.u8','short.int32le'):link(a.asset_stage/n,out/n)
link(a.runner,out/'direct_lfm2_qnn_runner');link(a.qnn_lib_dir/'libQnnHtp.so',out/'libQnnHtp.so');link(a.qnn_lib_dir/'libQnnSystem.so',out/'libQnnSystem.so')
lines=[]
for g in s['groups']:
 src=a.pipeline_dir/g['name']/g['shared_context_binary']['path'];rel=Path('shared-contexts')/(g['name']+'.bin');link(src,out/rel);lines.append('\t'.join([str(rel),*g['execution_order']]))
(out/'shared-contexts.tsv').write_text('\n'.join(lines)+'\n')
meta={'schema_version':1,'classification':'ignored_host_htp_emulator_shared_context_stage','shared_context_count':len(s['groups']),'graph_count':s['ordered_graph_count'],'loaded_route':True,'per_token_context_reload':False,'files':{}}
for p in sorted(x for x in out.rglob('*') if x.is_file()):
 h=hashlib.sha256(p.read_bytes()).hexdigest();meta['files'][str(p.relative_to(out))]={'bytes':p.stat().st_size,'sha256':h}
(out/'stage.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n');print(json.dumps({'stage':str(out),'contexts':len(s['groups']),'graphs':s['ordered_graph_count']},indent=2))
