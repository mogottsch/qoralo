#!/usr/bin/env python3
"""Summarize one 0014 phone run's ORT assignment, QNN physical profile, and WAV."""
import argparse,csv,glob,hashlib,json,wave
from collections import Counter
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
def obj(path):
 s=path.read_text();return json.loads(s[s.index('{'):])
def component(path):return path.name.split('_2026-')[0]
result=obj(a.run/'result.json');profiles=[];pt=Counter()
for path in sorted((a.run/'profiles').glob('*.json')):
 events=json.load(open(path));c=Counter(e.get('args',{}).get('provider') for e in events if e.get('args',{}).get('provider'));pt.update(c);profiles.append({'component':component(path),'ort_profile':path.name,'provider_events':dict(c)})
physical={}
for path in sorted((a.run/'profiles').glob('*.qnn.csv')):
 c=Counter();v=Counter()
 for r in csv.DictReader(open(path)):
  k=r['Event Identifier'];c[k]+=1
  try:v[k]+=int(r['Time'])
  except ValueError:pass
 name=path.name.split('.qnn.csv')[0];physical[name]={'rpc_execute_events':c['RPC (execute) time'],'rpc_execute_us':v['RPC (execute) time'],'accelerator_execute_events':c['QNN accelerator (execute) time'],'accelerator_execute_us':v['QNN accelerator (execute) time'],'cycle_events':c['Accelerator (execute) time (cycles)'],'accelerator_cycles':v['Accelerator (execute) time (cycles)'],'hvx_events':c['Number of HVX threads used'],'hvx_thread_sum':v['Number of HVX threads used']}
for x in profiles:x['physical']=physical.get(x['component'],{})
phy_events=sum(x['rpc_execute_events'] for x in physical.values());wav_path=a.run/'full-qnn.wav'
with wave.open(str(wav_path),'rb') as w:raw=w.readframes(w.getnframes());info={'channels':w.getnchannels(),'sample_width_bytes':w.getsampwidth(),'sample_rate_hz':w.getframerate(),'samples':w.getnframes(),'seconds':w.getnframes()/w.getframerate()}
y=np.frombuffer(raw,dtype='<i2').astype(np.float64);info.update({'bytes':wav_path.stat().st_size,'sha256':hashlib.sha256(wav_path.read_bytes()).hexdigest(),'peak_abs_pcm16':int(np.max(np.abs(y))),'rms_pcm16':float(np.sqrt(np.mean(y*y))),'finite':bool(np.isfinite(y).all()),'non_silent':bool(np.any(y!=0)),'unclipped':bool(np.max(np.abs(y))<32767)})
out={'schema_version':1,'run':a.run.name,'result':result,'profiles':profiles,'aggregate':{'provider_events':dict(pt),'qnn_provider_events':pt['QNNExecutionProvider'],'cpu_provider_events':pt['CPUExecutionProvider'],'physical_rpc_events':phy_events,'all_invoked_calls_qnn_only':pt['QNNExecutionProvider']>0 and pt['CPUExecutionProvider']==0,'physical_event_count_matches_qnn':phy_events==pt['QNNExecutionProvider'],'unused_session_profiles':[x['component'] for x in profiles if not x['provider_events']]},'wav':info,'cleanup_verified':(a.run/'cleanup-proof.txt').read_text().strip()=='cleanup_ok'};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['aggregate'],indent=2))
