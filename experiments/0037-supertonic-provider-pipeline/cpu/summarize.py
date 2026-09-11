#!/usr/bin/env python3
"""Non-sensitive evidence for exact native provider-pipeline CPU output."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import wave

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def pcm(path):
    with wave.open(str(path),'rb') as f:
        frames=f.getnframes();info={'frames':frames,'sample_rate':f.getframerate(),'channels':f.getnchannels(),'sample_width_bytes':f.getsampwidth()};data=f.readframes(frames)
    if info['sample_rate']!=44100 or info['channels']!=1 or info['sample_width_bytes']!=2 or len(data)!=frames*2:raise ValueError('WAVformat/payload mismatch')
    info.update(bytes=path.stat().st_size,sha256=sha(path),audio_seconds=frames/44100,private_path=str(path));return info,data

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.attempt/'phone/output'
    x=json.loads((out/'result.json').read_text());contract=json.loads((ROOT/'protocol/inputs.json').read_text());freeze=json.loads((ROOT/'protocol/freeze.json').read_text())
    if x['chunk_count']!=15 or x['steps']!=8 or x['session_count']!=4:raise ValueError('recipe execution mismatch')
    x['reference_sha256']=contract['reference_sha256'];x['upstream_commit']=contract['upstream']['commit'];x['bundle_manifest_sha256']=freeze['bundle_manifest_sha256'];x['canonical']=False
    x['attempt']=json.loads((a.attempt/'attempt.json').read_text());x['device']=json.loads((a.attempt/'identity.json').read_text());x['cleanup']=json.loads((a.attempt/'cleanup.json').read_text());x['stage_sha256']=json.loads((a.attempt/'stage-hashes.json').read_text())
    x['provider_evidence']={}
    for profile in out.glob('*_*.json'):
        component=profile.name.split('_')[0]
        if component not in {'duration','text','vector','vocoder'}:continue
        events=json.loads(profile.read_text());counts={};names=set();calls=sum(e.get('name')=='model_run' for e in events)
        for e in events:
            provider=e.get('args',{}).get('provider')
            if provider:counts[provider]=counts.get(provider,0)+1;names.add(e.get('name'))
        if set(counts)!={'CPUExecutionProvider'}:raise ValueError('nonCPU/missing profile evidence')
        expected=120 if component=='vector' else 15
        if calls!=expected:raise ValueError('wrong model_run count '+component+':'+str(calls))
        x['provider_evidence'][component]={'model_run_calls':calls,'kernel_events_by_provider':counts,'distinct_kernel_names':len(names),'profile_sha256':sha(profile)}
    if set(x['provider_evidence'])!={'duration','text','vector','vocoder'}:raise ValueError('missing component profiles')
    stream=ROOT/'.local/common/bundle/noise_stream.f32';assembly=[];offset=0;predicted_sum=0
    with stream.open('rb') as rng:
        for index,record in enumerate(x['chunks']):
            if record['index']!=index or record['text_extent']!=contract['chunks'][index]['text_extent'] or record['noise_offset']!=offset:raise ValueError('chunk ordering/layout mismatch')
            info,data=pcm(out/f'chunk-{index:03d}.wav')
            if info['frames']!=record['native_latent']*3072 or info['frames']!=record['emitted_frames']:raise ValueError('native whole vocoder output extent mismatch')
            initial=out/f'chunk-{index:03d}-initial.f32';draws=144*record['native_latent'];expected=rng.read(draws*4)
            if initial.read_bytes()!=expected:raise ValueError('noise stream continuity mismatch')
            record['initial_noise_sha256']=sha(initial);record['wav']=info;record['exact_saved_rng_correspondence']=True;offset+=draws;predicted_sum+=record['speed_adjusted_seconds']
            if index:assembly.append(bytes(contract['gap_frames']*2))
            assembly.append(data)
    if offset!=x['noise_stream_draws_consumed']:raise ValueError('stream consumption mismatch')
    final,data=pcm(out/'chapter.wav')
    if data!=b''.join(assembly):raise ValueError('final chapter is not exactchunk+gap assembly')
    if final['frames']!=x['emitted_frames']:raise ValueError('final frame count mismatch')
    x['wav']=final;x['assembly_verified_exact_pcm']=True;x['sum_speed_adjusted_predictions_seconds']=predicted_sum;x['speech_audio_seconds']=x['speech_vocoder_frames']/44100;x['gap_audio_seconds']=x['total_gap_frames']/44100;x['vocoder_grid_tail_seconds']=x['speech_audio_seconds']-predicted_sum
    x['host_chunk_availability']=json.loads((a.attempt/'chunk-availability.json').read_text())
    if len(x['host_chunk_availability'])!=15:raise ValueError('missing promptlypulled chunk files')
    for record in x['host_chunk_availability']:
        i=int(record['chunk_file'][6:9])
        if record['sha256']!=x['chunks'][i]['wav']['sha256']:raise ValueError('early available chunk differs fromfinal source')
    x['thermal']={}
    for when in ('before','after'):
        text=(a.attempt/f'thermal-{when}.txt').read_text()
        def value(key):
            match=re.search(r'^\s*'+key+r':\s*(\d+)',text,re.M);return int(match.group(1)) if match else None
        x['thermal'][when]={'mem_available_kib':value('MemAvailable'),'battery_temperature_tenths_c':value('temperature')}
    monitor=json.loads((a.attempt/'monitor.json').read_text());x['sampled_rss_peak_kib']=max((s.get('rss_kib') or 0 for s in monitor),default=0) or None
    x['memory_method']='Android getrusage ru_maxrss KiB over four resident CPU sessions; host1s polling /proc/PID/status. Host publication transfers occur duringinference.'
    x['timing_definitions']={'setup':'four native session constructors; host frontend/noise preparation excluded','first_playable':'complete first chunkWAV closed and atomically published ondevice; not token/audioframeTTFT','host_first_available':'first complete chunkpulled tohost, includes launch/observation/transfer delay','generation':'from all4sessionsready through finalassembledWAVclose; perchunkWAV/initialnoise evidencewrites/livepull overhead included; final EndProfiling flush excluded','rtf':'generation wall / actualemitted speech+provider gaps; alternate speechonly denominator also supplied'}
    x['warm_median_rtf']=None;x['warm_median_reason']='one noncanonical first completechapter; no automaticwarmcampaign';x['listening_acceptance']='not_reviewed';x['coverage_status']='not_yet_assessed'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(x,indent=2)+'\n')
    print(json.dumps({k:x[k] for k in ['chunk_count','emitted_audio_seconds','setup_seconds','first_chunk_playable_from_entry_seconds','first_chunk_playable_from_generation_seconds','generation_wall_seconds','rtf_including_prescribed_gaps','maxrss_kib']},indent=2));print('wav_sha256',final['sha256'])

if __name__=='__main__':main()
