#!/usr/bin/env python3
"""Prepare ignored AR1 max-token resume stage from bridged physical prefill state."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def link(s,d):d.parent.mkdir(parents=True,exist_ok=True);os.link(s,d)
ap=argparse.ArgumentParser();ap.add_argument('--ar1-context',type=Path,required=True);ap.add_argument('--runner',type=Path,required=True);ap.add_argument('--runtime-stage',type=Path,required=True);ap.add_argument('--resume-input-list',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args();o=a.output_dir
if o.exists():shutil.rmtree(o)
o.mkdir(parents=True);link(a.ar1_context,o/'contexts/monolith.bin');link(a.runner,o/'direct_lfm2_qnn_runner');(o/'monolithic-contexts.tsv').write_text('contexts/monolith.bin\tmonolith\n')
for n in ('embedding-quant.u8','embedding-scales.f32le','embedding-zp.u8','libQnnHtp.so','libQnnSystem.so','libQnnHtpV73Stub.so','libQnnHtpV73Skel.so','libc++_shared.so'):link(a.runtime_stage/n,o/n)
fields=[]
for field in a.resume_input_list.read_text().split():
 name,path=field.split(':=',1);src=Path(path);dst=o/'resume-inputs'/src.name;link(src,dst);fields.append(f'{name}:=resume-inputs/{dst.name}')
(o/'resume-input-list.txt').write_text(' '.join(fields)+'\n');files=sorted(x for x in o.rglob('*') if x.is_file());entries=[]
with (o/'SHA256SUMS').open('w') as f:
 for x in files:
  h=sha(x);r=x.relative_to(o).as_posix();f.write(f'{h}  {r}\n');entries.append({'path':r,'bytes':x.stat().st_size,'sha256':h})
meta={'schema_version':1,'classification':'ignored_license_controlled_ar1_resume_from_physical_ar171_state_stage','route':'one AR1 context loaded once; initial 38 states from CPU-bridged retained physical AR171 output; max16 greedy decode in process','start_token':597,'start_position':171,'max_new_tokens':16,'context_sha256':sha(a.ar1_context),'runner_sha256':sha(a.runner),'resume_input_list_sha256':sha(o/'resume-input-list.txt'),'resume_input_files':41,'context_streaming':False,'context_reloads':0,'cpu_work':'state file loading, selected-row Q4 embedding dequantization each token, position/mask update, global argmax','qnn_htp_work':'all model layers/state updates/final norm/LM head each decode token','payload_files':len(entries),'payload_bytes':sum(x['bytes'] for x in entries),'retained_outside_git':True};(o/'stage.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n')
with (o/'SHA256SUMS').open('a') as f:f.write(f"{sha(o/'stage.json')}  stage.json\n")
print(json.dumps({k:meta[k] for k in ('context_sha256','runner_sha256','resume_input_files','payload_files','payload_bytes')},indent=2))
