#!/usr/bin/env python3
"""Assemble ignored x86 HTP-emulator stage for 37-context consolidated route."""
import argparse,json,shutil
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--pipeline-dir',type=Path,required=True);ap.add_argument('--asset-stage',type=Path,required=True);ap.add_argument('--runner',type=Path,required=True);ap.add_argument('--qnn-lib-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args();s=json.loads((a.pipeline_dir/'summary.json').read_text());out=a.output_dir
if out.exists():shutil.rmtree(out)
(out/'contexts').mkdir(parents=True)
def link(src,dst):dst.symlink_to(src.resolve())
for n in ('embedding-quant.u8','embedding-scales.f32le','embedding-zp.u8','short.int32le'):link(a.asset_stage/n,out/n)
link(a.runner,out/'direct_lfm2_qnn_runner');link(a.qnn_lib_dir/'libQnnHtp.so',out/'libQnnHtp.so');link(a.qnn_lib_dir/'libQnnSystem.so',out/'libQnnSystem.so')
lines=[]
for p in s['parts']:
 name=p['name'];src=a.pipeline_dir/name/p['context_binary']['path'];rel=Path('contexts')/(name+'.bin');link(src,out/rel);lines.append(f'{rel}\t{name}')
(out/'consolidated-contexts.tsv').write_text('\n'.join(lines)+'\n');print(json.dumps({'stage':str(out),'contexts':len(lines)},indent=2))
