#!/usr/bin/env python3
"""Assemble ignored qnn-net-run stage for one fixed-width prefill diagnostic."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def link(s,d):d.parent.mkdir(parents=True,exist_ok=True);os.link(s,d)
ap=argparse.ArgumentParser();ap.add_argument('--sequence-length',type=int,required=True);ap.add_argument('--compiled-dir',type=Path,required=True);ap.add_argument('--inputs-dir',type=Path,required=True);ap.add_argument('--qairt-root',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args();out=a.output_dir
if out.exists():shutil.rmtree(out)
out.mkdir(parents=True);link(a.compiled_dir/'context_qnn.bin',out/'context_qnn.bin');link(a.qairt_root/'bin/aarch64-android/qnn-net-run',out/'qnn-net-run')
for src,name in ((a.qairt_root/'lib/aarch64-android/libQnnHtp.so','libQnnHtp.so'),(a.qairt_root/'lib/aarch64-android/libQnnSystem.so','libQnnSystem.so'),(a.qairt_root/'lib/aarch64-android/libQnnHtpV73Stub.so','libQnnHtpV73Stub.so'),(a.qairt_root/'lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so','libQnnHtpV73Skel.so')):link(src,out/name)
source=json.loads((a.inputs_dir/'result.json').read_text());items=[]
for x in source['inputs']:
 src=a.inputs_dir/Path(x['path']).name;dst=out/'inputs'/src.name;link(src,dst);items.append((x['name'],dst.relative_to(out).as_posix()))
(out/'input-list.txt').write_text(' '.join(f'{name}:={path}' for name,path in items)+'\n');files=sorted(x for x in out.rglob('*') if x.is_file());entries=[]
with (out/'SHA256SUMS').open('w') as f:
 for x in files:
  d=sha(x);r=x.relative_to(out).as_posix();f.write(f'{d}  {r}\n');entries.append({'path':r,'bytes':x.stat().st_size,'sha256':d})
meta={'schema_version':1,'classification':'ignored_license_controlled_ar_prefill_qnn_net_run_android_stage','sequence_length':a.sequence_length,'input_tensors':len(items),'input_bytes':source['total_input_bytes'],'input_list_sha256':sha(out/'input-list.txt'),'context_sha256':sha(out/'context_qnn.bin'),'qairt_android_runtime':'2.49.40.260810','qnn_backend_build_id_expected':'v2.49.40.260810104044','target':{'soc_model':43,'htp_arch':73},'direct_qnn':True,'neural_cpu_fallback_available':False,'payload_files':len(entries),'payload_bytes':sum(x['bytes'] for x in entries),'files':entries,'retained_outside_git':True};(out/'stage.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n')
with (out/'SHA256SUMS').open('a') as f:f.write(f"{sha(out/'stage.json')}  stage.json\n")
print(json.dumps({k:meta[k] for k in ('sequence_length','input_tensors','input_bytes','context_sha256','payload_files','payload_bytes')},indent=2))
