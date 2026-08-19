#!/usr/bin/env python3
"""Summarize Pocket mixed-provider phone evidence deterministically."""
import argparse,csv,glob,hashlib,json,statistics,wave
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--cpu-wav',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
def json_object(path):
 s=path.read_text();return json.loads(s[s.index('{'):])
def wav(path):
 with wave.open(str(path),'rb') as w:return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)/32768,w.getframerate()
components=['flow_lm_flow','flow_lm_main','mimi_encoder','mimi_decoder','text_conditioner'];profiles=[]
for component,path in zip(components,sorted((a.run/'profiles').glob('ort*.json'))):
 events=json.load(open(path));counts=Counter();dur=Counter();unique=defaultdict(set)
 for e in events:
  provider=e.get('args',{}).get('provider')
  if provider:counts[provider]+=1;dur[provider]+=e.get('dur',0);unique[provider].add(e.get('name'))
 profiles.append({'component':component,'file':path.name,'events':dict(counts),'unique_kernel_events':{k:len(v) for k,v in unique.items()},'summed_event_duration_us':dict(dur)})
physical_counts=Counter();physical_values=Counter()
for r in csv.DictReader(open(a.run/'profiles/qnn.csv')):
 k=r['Event Identifier'];physical_counts[k]+=1
 try:physical_values[k]+=int(r['Time'])
 except ValueError:pass
keys=['RPC (execute) time','QNN accelerator (execute) time','Accelerator (execute) time (cycles)','Number of HVX threads used']
perf=json_object(a.run/'perf.json');warm=perf['runs'][1:];hybrid_path=a.run/'output-perf/pocket-hybrid-cold-0.wav';cpu,rate=wav(a.cpu_wav);hybrid,hrate=wav(hybrid_path);assert rate==hrate==24000;n=min(len(cpu),len(hybrid));err=cpu[:n]-hybrid[:n]
out={'schema_version':1,'route':'mixed_qnn_htp_cpu','perf':perf,'warm_summary':{'seconds_median':statistics.median(x['seconds'] for x in warm),'seconds_min':min(x['seconds'] for x in warm),'seconds_max':max(x['seconds'] for x in warm),'rtf_median':statistics.median(x['rtf'] for x in warm),'rtf_min':min(x['rtf'] for x in warm),'rtf_max':max(x['rtf'] for x in warm)},'provider_profiles':profiles,'provider_event_totals':{},'physical_qnn':{k:{'events':physical_counts[k],'sum':physical_values[k]} for k in keys},'output':{'path':str(hybrid_path.resolve()),'bytes':hybrid_path.stat().st_size,'sha256':hashlib.sha256(hybrid_path.read_bytes()).hexdigest(),'samples':len(hybrid),'seconds':len(hybrid)/rate,'all_runs_byte_identical':len({hashlib.sha256(x.read_bytes()).hexdigest() for x in (a.run/'output-perf').glob('*.wav')})==1},'cpu_comparison':{'cpu_samples':len(cpu),'hybrid_samples':len(hybrid),'overlap_samples':n,'overlap_correlation':float(np.corrcoef(cpu[:n],hybrid[:n])[0,1]),'overlap_mae':float(np.mean(abs(err))),'overlap_max_abs':float(np.max(abs(err))),'overlap_snr_db':float(10*np.log10(np.mean(cpu[:n]**2)/np.mean(err**2)))}}
for x in profiles:
 for provider,count in x['events'].items():out['provider_event_totals'][provider]=out['provider_event_totals'].get(provider,0)+count
a.output.write_text(json.dumps(out,indent=2)+'\n')
