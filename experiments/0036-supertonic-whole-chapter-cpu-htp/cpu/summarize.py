#!/usr/bin/env python3
"""Publish only non-content CPU metrics, hashes and provider-count evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import wave


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    attempt=a.attempt;output=attempt/'phone/output'
    x=json.loads((attempt/'phone/stdout.json').read_text())
    x['canonical']=False;x['reference_sha256']='cbfd5bbef581f0e793b86a568f8d4aa87fe857f413e5c2ea4780b558fc71600b'
    x['attempt']=json.loads((attempt/'attempt.json').read_text());x['cleanup']=json.loads((attempt/'cleanup.json').read_text());x['device']=json.loads((attempt/'identity.json').read_text());x['private_evidence_path']=str(attempt)
    x['provider_evidence']={}
    for profile in sorted(output.glob('*_*.json')):
        events=json.loads(profile.read_text());counts={};node_names=set()
        for e in events:
            provider=e.get('args',{}).get('provider')
            if provider:
                counts[provider]=counts.get(provider,0)+1;node_names.add(e.get('name'))
        if not counts or set(counts)!={'CPUExecutionProvider'}:raise ValueError('profile provider mismatch')
        x['provider_evidence'][profile.name.split('_')[0]]={'profile_sha256':sha(profile),'kernel_events_by_provider':counts,'distinct_profile_kernel_names':len(node_names)}
    expected={'duration'} if x['action']=='dp' else {'duration','text','vector','vocoder'}
    if set(x['provider_evidence'])!=expected:raise ValueError('missing stage profiles')
    x['input_and_binary_sha256']=json.loads((attempt/'stage-hashes.json').read_text())
    x['predicted_duration_scalar_sha256']=sha(output/'duration.f32')
    x['thermal_context']={}
    for moment in ('before','after'):
        text=(attempt/('thermal-'+moment+'.txt')).read_text()
        def value(name):
            m=re.search(r'^\s*'+name+r':\s*(\d+)',text,re.M);return int(m.group(1)) if m else None
        x['thermal_context'][moment]={'mem_available_kib':value('MemAvailable'),'battery_temperature_tenths_c':value('temperature')}
    monitor=json.loads((attempt/'monitor.json').read_text());x['sampled_rss_peak_kib']=max((s.get('rss_kib') or 0 for s in monitor),default=0) or None
    x['memory_method']='Android runner getrusage(RUSAGE_SELF).ru_maxrss KiB; host samples /proc/PID/status every2s where process remains alive. Unsampled short run peak is null, never zero.'
    x['session_lifetime']='Sequential per-stage create/run/destroy; not four resident sessions'
    x['listening_acceptance']='not_reviewed';x['entire_chapter_spoken']=None;x['coverage_status']='not yet assessed'
    x['warm_median_rtf']=None;x['warm_median_reason']='one noncanonical first full generation, no warm campaign' if x['action']=='full' else 'duration-only calibration, no WAV or RTF claim'
    if x['action']=='dp':
        x['audio_seconds']=None;x['rtf_stage_sum']=None;x['result_scope']='duration calibration only, not full CPU completion'
    else:
        wav=output/'cpu.wav'
        with wave.open(str(wav),'rb') as f:
            params={'frames':f.getnframes(),'sample_rate':f.getframerate(),'channels':f.getnchannels(),'sample_width':f.getsampwidth()};data=f.readframes(f.getnframes())
        if params!={'frames':x['emitted_frames'],'sample_rate':44100,'channels':1,'sample_width':2}:raise ValueError('WAV format/frame mismatch')
        samples=struct.unpack(f'<{len(data)//2}h',data)
        x['wav']={**params,'bytes':wav.stat().st_size,'sha256':sha(wav),'private_path':str(wav),'duration_seconds':params['frames']/44100,'pcm_peak_abs':max(abs(v) for v in samples),'pcm_rms':(sum(float(v)*v for v in samples)/len(samples))**0.5,'pcm_clipped_samples':sum(abs(v)>=32767 for v in samples)}
        x['generation_wall_excluding_session_setup_seconds']=x['pipeline_wall_seconds']-x['setup_seconds']
        x['rtf_generation_wall_excluding_session_setup']=x['generation_wall_excluding_session_setup_seconds']/x['wav']['duration_seconds']
        x['rtf_pipeline_including_session_setup']=x['pipeline_wall_seconds']/x['wav']['duration_seconds']
        x['result_scope']='one complete four-stage Android CPU execution, not yet full-content/listening acceptance'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(x,indent=2)+'\n')

if __name__=='__main__':main()
