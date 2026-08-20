#!/usr/bin/env python3
"""Summarize a fixed-Alba Android CPU or QNN run, including physical profiles."""
from __future__ import annotations
import argparse,csv,hashlib,json,wave
from collections import Counter
from pathlib import Path
import numpy as np

def load_json(path):
 s=path.read_text();return json.loads(s[s.index('{'):])
def component(path):return path.name.split('_2026-')[0]
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--wav',required=True);p.add_argument('--host-reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=load_json(a.run/'result.json');profiles=[];providers=Counter()
 for path in sorted((a.run/'profiles').glob('*.json')):
  events=json.load(open(path));counts=Counter(e.get('args',{}).get('provider') for e in events if e.get('args',{}).get('provider'));providers.update(counts);profiles.append({'component':component(path),'ort_profile':path.name,'provider_events':dict(counts)})
 physical={}
 for path in sorted((a.run/'profiles').glob('*.qnn.csv')):
  counts=Counter();values=Counter()
  for row in csv.DictReader(open(path)):
   key=row['Event Identifier'];counts[key]+=1
   try:values[key]+=int(row['Time'])
   except ValueError:pass
  name=path.name.split('.qnn.csv')[0];physical[name]={'rpc_execute_events':counts['RPC (execute) time'],'rpc_execute_us':values['RPC (execute) time'],'accelerator_execute_events':counts['QNN accelerator (execute) time'],'accelerator_execute_us':values['QNN accelerator (execute) time'],'cycle_events':counts['Accelerator (execute) time (cycles)'],'accelerator_cycles':values['Accelerator (execute) time (cycles)'],'hvx_events':counts['Number of HVX threads used'],'hvx_thread_sum':values['Number of HVX threads used']}
 for row in profiles:row['physical']=physical.get(row['component'],{})
 wav_path=a.run/a.wav
 with wave.open(str(wav_path),'rb') as w:raw=w.readframes(w.getnframes());info={'channels':w.getnchannels(),'sample_width_bytes':w.getsampwidth(),'sample_rate_hz':w.getframerate(),'samples':w.getnframes(),'seconds':w.getnframes()/w.getframerate()}
 x=np.frombuffer(raw,dtype='<i2').astype(np.float64);info.update({'bytes':wav_path.stat().st_size,'sha256':hashlib.sha256(wav_path.read_bytes()).hexdigest(),'peak_abs_pcm16':int(np.max(np.abs(x))),'rms_pcm16':float(np.sqrt(np.mean(x*x))),'finite':bool(np.isfinite(x).all()),'non_silent':bool(np.any(x)),'unclipped':bool(np.max(np.abs(x))<32767)})
 with wave.open(str(a.host_reference),'rb') as w:host=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)
 comparison={'host_reference_sha256':hashlib.sha256(a.host_reference.read_bytes()).hexdigest(),'equal_length':len(host)==len(x)}
 if len(host)==len(x):
  d=host-x;comparison.update({'byte_identical':bool(np.array_equal(host,x)),'max_abs_pcm16':float(np.max(np.abs(d))),'mae_pcm16':float(np.mean(np.abs(d))),'correlation':float(np.corrcoef(host,x)[0,1]),'snr_db':float(10*np.log10(np.mean(host*host)/np.mean(d*d))) if np.any(d) else None})
 qnn=providers['QNNExecutionProvider'];cpu=providers['CPUExecutionProvider'];rpc=sum(v['rpc_execute_events'] for v in physical.values());acc=sum(v['accelerator_execute_events'] for v in physical.values());cyc=sum(v['cycle_events'] for v in physical.values());hvx=sum(v['hvx_events'] for v in physical.values())
 out={'schema_version':1,'run':a.run.name,'result':result,'profiles':profiles,'aggregate':{'provider_events':dict(providers),'qnn_provider_events':qnn,'cpu_provider_events':cpu,'physical_rpc_events':rpc,'physical_accelerator_events':acc,'physical_cycle_events':cyc,'physical_hvx_events':hvx,'all_invoked_calls_qnn_only':qnn>0 and cpu==0,'all_physical_event_counts_match_qnn':qnn>0 and qnn==rpc==acc==cyc==hvx,'unused_session_profiles':[x['component'] for x in profiles if not x['provider_events']]},'wav':info,'host_comparison':comparison,'system_evidence':{name:{'sha256':hashlib.sha256((a.run/name).read_bytes()).hexdigest(),'bytes':(a.run/name).stat().st_size} for name in ('thermal-before.txt','thermal-after.txt','battery-before.txt','battery-after.txt') if (a.run/name).exists()},'cleanup_verified':(a.run/'cleanup-proof.txt').read_text().strip()=='cleanup_ok'};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'aggregate':out['aggregate'],'wav':info,'host_comparison':comparison},indent=2))
if __name__=='__main__':main()
