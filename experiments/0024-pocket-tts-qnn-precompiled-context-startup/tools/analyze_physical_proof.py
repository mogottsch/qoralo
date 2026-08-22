#!/usr/bin/env python3
"""Aggregate canonical-v2 fallback-disabled QNN provider and physical proof."""
from __future__ import annotations
import argparse,csv,hashlib,json,re,wave
from collections import Counter
from pathlib import Path
import numpy as np
def load(path):
 s=path.read_text();return json.loads(s[s.index('{'):])
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def component(path):return path.name.split('_2026-')[0]
def thermal(path):
 text=path.read_text();status=re.search(r'Thermal Status: (\d+)',text);values={m.group(2):float(m.group(1)) for m in re.finditer(r'mValue=([0-9.]+).*mName=(AP|SKIN|BAT)',text)};return {'status':int(status.group(1)) if status else None,'temperatures_c':values,'sha256':sha(path)}
def battery(path):
 text=path.read_text();value=lambda key:(re.search(rf'^  {key}: (.+)$',text,re.M).group(1) if re.search(rf'^  {key}: (.+)$',text,re.M) else None);return {'level_percent':int(value('level')) if value('level') else None,'temperature_c':int(value('temperature'))/10 if value('temperature') else None,'usb_powered':value('USB powered')=='true','ac_powered':value('AC powered')=='true','sha256':sha(path)}
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=load(a.run/'result.json');assert result['profiled'] and result['cpu_fallback'] is False and len(result['iterations'])==1;providers=Counter();rows=[]
 for path in sorted((a.run/'profiles').glob('*.json')):
  events=json.load(open(path));counts=Counter(e.get('args',{}).get('provider') for e in events if e.get('args',{}).get('provider'));providers.update(counts);rows.append({'component':component(path),'ort_profile':path.name,'provider_events':dict(counts)})
 physical={}
 for path in sorted((a.run/'profiles').glob('*.qnn.csv')):
  counts=Counter();values=Counter()
  for row in csv.DictReader(open(path)):
   key=row['Event Identifier'];counts[key]+=1
   try:values[key]+=int(row['Time'])
   except ValueError:pass
  physical[path.name.split('.qnn.csv')[0]]={'rpc_execute_events':counts['RPC (execute) time'],'rpc_execute_us':values['RPC (execute) time'],'accelerator_execute_events':counts['QNN accelerator (execute) time'],'accelerator_execute_us':values['QNN accelerator (execute) time'],'cycle_events':counts['Accelerator (execute) time (cycles)'],'accelerator_cycles':values['Accelerator (execute) time (cycles)'],'hvx_events':counts['Number of HVX threads used'],'hvx_thread_sum':values['Number of HVX threads used']}
 for row in rows:row['physical']=physical.get(row['component'],{})
 qnn=providers['QNNExecutionProvider'];cpu=providers['CPUExecutionProvider'];sums={key:sum(x.get(key,0) for x in physical.values()) for key in ('rpc_execute_events','rpc_execute_us','accelerator_execute_events','accelerator_execute_us','cycle_events','accelerator_cycles','hvx_events','hvx_thread_sum')};wav=a.run/'outputs/first.wav'
 with wave.open(str(wav),'rb') as w:raw=w.readframes(w.getnframes());info={'sha256':sha(wav),'bytes':wav.stat().st_size,'channels':w.getnchannels(),'sample_width_bytes':w.getsampwidth(),'sample_rate_hz':w.getframerate(),'samples':w.getnframes(),'seconds':w.getnframes()/w.getframerate()}
 x=np.frombuffer(raw,'<i2').astype(float);info.update({'peak_abs_pcm16':int(np.max(np.abs(x))),'rms_pcm16':float(np.sqrt(np.mean(x*x))),'finite':bool(np.isfinite(x).all()),'non_silent':bool(np.any(x)),'unclipped':bool(np.max(np.abs(x))<32767)});assert qnn>0 and cpu==0 and qnn==sums['rpc_execute_events']==sums['accelerator_execute_events']==sums['cycle_events']==sums['hvx_events'];assert sums['hvx_thread_sum']==4*qnn;assert (a.run/'local-stage-sha256.txt').read_text()==(a.run/'remote-stage-sha256.txt').read_text()
 accepted='601cd622dd0598c23dd7275074763aa37ae79b18a9d777ad946b1eaebd2c58e5';listening=({'status':'accepted','authority':'Moritz','verbatim':'good','sha256':info['sha256'],'reason':'Byte-identical to the exact accepted 0014 canonical-v2 QNN WAV.'} if info['sha256']==accepted else {'status':'not_reviewed','sha256':info['sha256'],'reason':'Byte-different output requires exact-hash Moritz review; numerical differences are descriptive only.'})
 out={'schema_version':1,'run':a.run.name,'route':result['route'],'arm':result['arm'],'model_format':result['model_format'],'source_onnx_unavailable':result['source_onnx_unavailable'],'canonical_transcript':result['canonical_transcript'],'frontend':result['frontend'],'static_abi':result['static_abi'],'cpu_fallback_disabled':True,'profiles':rows,'aggregate':{'provider_events':dict(providers),**sums,'all_invoked_calls_qnn_only':True,'all_physical_event_counts_match_qnn':True},'result':result,'wav':info,'memory':{'method':'getrusage(RUSAGE_SELF).ru_maxrss / process VmHWM on Android','vm_hwm_kb':result['iterations'][0]['vm_hwm_kb'],'lifecycle':'cumulative process high-water including profiled sessions, QNN contexts, caches, buffers, profiles, and output'},'thermal':{'before':thermal(a.run/'thermal-before.txt'),'after':thermal(a.run/'thermal-after.txt')},'battery':{'before':battery(a.run/'battery-before.txt'),'after':battery(a.run/'battery-after.txt')},'safety':{'identity':(a.run/'identity.txt').read_text().splitlines(),'stage_hashes_equal':True,'runner_exit':int((a.run/'runner.exit').read_text()),'cleanup_exit':int((a.run/'cleanup.exit').read_text()),'cleanup_verified':(a.run/'cleanup-proof.txt').read_text().strip()=='cleanup_ok'},'listening':listening};assert out['safety']['runner_exit']==0 and out['safety']['cleanup_exit']==0 and out['safety']['cleanup_verified'];a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['aggregate'],indent=2))
if __name__=='__main__':main()
