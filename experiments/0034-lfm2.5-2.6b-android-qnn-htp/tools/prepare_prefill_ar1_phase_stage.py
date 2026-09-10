#!/usr/bin/env python3
"""Prepare ignored AR171→CPU-cache-bridge→AR1 diagnostic stage."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def link(s,d):d.parent.mkdir(parents=True,exist_ok=True);os.link(s,d)
ap=argparse.ArgumentParser();ap.add_argument('--ar171-context',type=Path,required=True);ap.add_argument('--ar1-context',type=Path,required=True);ap.add_argument('--prefill-inputs',type=Path,required=True);ap.add_argument('--qairt-root',type=Path,required=True);ap.add_argument('--bridge',type=Path,required=True);ap.add_argument('--embedding597',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args();o=a.output_dir
if o.exists():shutil.rmtree(o)
o.mkdir(parents=True);link(a.ar171_context,o/'contexts/ar171.bin');link(a.ar1_context,o/'contexts/ar1.bin');link(a.qairt_root/'bin/aarch64-android/qnn-net-run',o/'qnn-net-run');link(a.bridge,o/'prefill_ar1_state_bridge');link(a.embedding597,o/'embedding-597.raw')
for src,name in ((a.qairt_root/'lib/aarch64-android/libQnnHtp.so','libQnnHtp.so'),(a.qairt_root/'lib/aarch64-android/libQnnSystem.so','libQnnSystem.so'),(a.qairt_root/'lib/aarch64-android/libQnnHtpV73Stub.so','libQnnHtpV73Stub.so'),(a.qairt_root/'lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so','libQnnHtpV73Skel.so')):link(src,o/name)
s=json.loads((a.prefill_inputs/'result.json').read_text())
if s.get('position_file_mode')!='default-float32' or s.get('position_values')!={'start':0,'count':171}:raise SystemExit('prefill positions are not validated numeric FLOAT32 0..170')
pairs=[]
for x in s['inputs']:
 src=a.prefill_inputs/Path(x['path']).name;dst=o/'prefill-inputs'/src.name;link(src,dst);pairs.append((x['name'],dst.relative_to(o).as_posix()))
(o/'prefill-input-list.txt').write_text(' '.join(f'{n}:={p}' for n,p in pairs)+'\n');files=sorted(x for x in o.rglob('*') if x.is_file());entries=[]
with (o/'SHA256SUMS').open('w') as f:
 for x in files:
  h=sha(x);r=x.relative_to(o).as_posix();f.write(f'{h}  {r}\n');entries.append({'path':r,'bytes':x.stat().st_size,'sha256':h})
meta={'schema_version':1,'classification':'ignored_license_controlled_ar171_to_ar1_phase_switch_diagnostic_stage','phase_order':['qnn-net-run AR171 one call','AR171 process exits and frees context','CPU bridge expands 171 K/V positions to AR1 4095 cache and carries 22 conv states','qnn-net-run AR1 token597 position171 one call'],'qairt_build_id':'v2.49.40.260810104044','ar171_context_sha256':sha(a.ar171_context),'ar1_context_sha256':sha(a.ar1_context),'prefill_input_tensors':41,'prefill_input_bytes':s['total_input_bytes'],'embedding597_sha256':sha(a.embedding597),'bridge_sha256':sha(a.bridge),'simultaneous_context_residency':False,'context_streaming':False,'explicit_phase_transition_count':1,'payload_files':len(entries),'payload_bytes':sum(x['bytes'] for x in entries),'files':entries,'retained_outside_git':True};(o/'stage.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n')
with (o/'SHA256SUMS').open('a') as f:f.write(f"{sha(o/'stage.json')}  stage.json\n")
print(json.dumps({k:meta[k] for k in ('ar171_context_sha256','ar1_context_sha256','prefill_input_tensors','prefill_input_bytes','bridge_sha256','payload_files','payload_bytes')},indent=2))
