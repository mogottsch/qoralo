#!/usr/bin/env python3
"""Aggregate Android ORT JSON profiles by component, provider, and operator."""
import argparse, hashlib, json
from collections import defaultdict
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--profile-dir',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
components=('prefill','autoregressive_decode','local_decoder','audio_tokenizer')
out={'schema_version':1,'claim':'CPUExecutionProvider profiling only; this is not HTP evidence.','components':{}}
for component in components:
 candidates=sorted(x for x in a.profile_dir.glob(component+'*') if x.is_file())
 if len(candidates)!=1: raise SystemExit(f'{component}: expected one profile, found {candidates}')
 path=candidates[0]; events=json.loads(path.read_text())
 providers=defaultdict(lambda:{'events':0,'duration_us':0.0})
 operators=defaultdict(lambda:{'events':0,'duration_us':0.0,'providers':set()})
 node_events=0; total_us=0.0
 for event in events:
  if event.get('cat')!='Node' or not str(event.get('name','')).endswith('_kernel_time'): continue
  args=event.get('args') or {}; provider=str(args.get('provider') or 'UNKNOWN')
  op=str(args.get('op_name') or args.get('op_type') or event.get('name','UNKNOWN').removesuffix('_kernel_time'))
  dur=float(event.get('dur') or 0); node_events+=1; total_us+=dur
  providers[provider]['events']+=1;providers[provider]['duration_us']+=dur
  operators[op]['events']+=1;operators[op]['duration_us']+=dur;operators[op]['providers'].add(provider)
 def rounded(v):return round(v,3)
 out['components'][component]={
  'profile_file':path.name,'profile_bytes':path.stat().st_size,'profile_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
  'node_kernel_events':node_events,'node_kernel_duration_us':rounded(total_us),
  'providers':{k:{'events':v['events'],'duration_us':rounded(v['duration_us'])} for k,v in sorted(providers.items())},
  'operators':{k:{'events':v['events'],'duration_us':rounded(v['duration_us']),'providers':sorted(v['providers'])} for k,v in sorted(operators.items(),key=lambda x:(-x[1]['duration_us'],x[0]))},
 }
all_providers=sorted({p for c in out['components'].values() for p in c['providers']})
out['all_providers']=all_providers
out['cpu_only']=all_providers==['CPUExecutionProvider']
if not out['cpu_only']:raise SystemExit(f'unexpected providers: {all_providers}')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
