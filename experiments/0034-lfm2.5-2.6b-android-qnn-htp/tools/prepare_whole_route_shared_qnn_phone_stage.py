#!/usr/bin/env python3
"""Assemble ignored Android stage for one shared context containing 37 graphs."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def link(s,d):d.parent.mkdir(parents=True,exist_ok=True);os.link(s,d)
ap=argparse.ArgumentParser();ap.add_argument('--group-dir',type=Path,required=True);ap.add_argument('--prior-stage',type=Path,required=True);ap.add_argument('--runner',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args();out=a.output_dir
if out.exists():shutil.rmtree(out)
out.mkdir(parents=True);r=json.loads((a.group_dir/'result.json').read_text());rel=Path('contexts/whole-route-shared.bin');link(a.group_dir/r['shared_context_binary']['path'],out/rel);(out/'consolidated-contexts.tsv').write_text('\t'.join([str(rel),*r['execution_order']])+'\n')
for n in ('embedding-quant.u8','embedding-scales.f32le','embedding-zp.u8','short.int32le','libQnnHtp.so','libQnnSystem.so','libQnnHtpV73Stub.so','libQnnHtpV73Skel.so','libc++_shared.so'):link(a.prior_stage/n,out/n)
link(a.runner,out/'direct_lfm2_qnn_runner');files=sorted(x for x in out.rglob('*') if x.is_file());entries=[]
with (out/'SHA256SUMS').open('w') as f:
 for x in files:
  d=sha(x);relp=x.relative_to(out).as_posix();f.write(f'{d}  {relp}\n');entries.append({'path':relp,'bytes':x.stat().st_size,'sha256':d})
meta={'schema_version':1,'classification':'ignored_license_controlled_single_shared_context_android_stage','route':'one QNN context loaded once, containing 37 ordered fused graphs; no ORT/EPContext/reload','context_count':1,'graph_count':37,'source_part_count':263,'shared_weights':True,'host_retrieval_support':False,'physical_support':'unproven','files':entries,'total_bytes_excluding_manifests':sum(x['bytes'] for x in entries),'retained_outside_git':True};(out/'stage.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n')
with (out/'SHA256SUMS').open('a') as f:f.write(f"{sha(out/'stage.json')}  stage.json\n")
print(json.dumps({'stage':str(out),'payload_files':len(entries),'payload_bytes':meta['total_bytes_excluding_manifests']},indent=2))
