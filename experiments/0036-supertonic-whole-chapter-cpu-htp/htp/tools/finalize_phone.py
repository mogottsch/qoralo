#!/usr/bin/env python3
"""Validate first retained HTP outcome; publish only numeric/content-free metadata."""
import argparse
import array
import hashlib
import json
import math
import re
from pathlib import Path
import sys
import wave


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    evidence=a.run/'evidence'
    d=json.loads((evidence/'result.json').read_text())
    if d['result']!='passed' or d['provider']!='QNNExecutionProvider' or not d['cpu_fallback_disabled'] or d['profiling_enabled']:
        raise ValueError('full HTP proof contract differs')
    if d['action']!='full' or d['text_extent']!=3200 or d['active_text_positions']!=3167 or d['latent_extent']!=512:
        raise ValueError('wrong shape or run contract')
    mem=dict(line.split('=',1) for line in (evidence/'memory.txt').read_text().splitlines())
    if mem['runner_exit_code']!='0' or mem['guard_reason']!='none':raise ValueError('native failure/guard stop')
    if (a.run/'command-exit.txt').read_text().strip()!='0' or (a.run/'remote-cleanup-exit.txt').read_text().strip()!='0':raise ValueError('transport/cleanup failure')
    manifest=json.loads((a.stage/'bundle/manifest.json').read_text())
    pcm_path=evidence/'run/htp.wav'
    with wave.open(str(pcm_path),'rb') as f:
        metadata={'channels':f.getnchannels(),'sample_width_bytes':f.getsampwidth(),'sample_rate_hz':f.getframerate(),'frames':f.getnframes()}
        raw=f.readframes(f.getnframes())
    if metadata!={'channels':1,'sample_width_bytes':2,'sample_rate_hz':44100,'frames':d['emitted_frames']} or d['emitted_frames']!=d['natural_wave_frames']:
        raise ValueError('WAV/natural frame count differs')
    pcm=array.array('h',raw)
    if sys.byteorder!='little':pcm.byteswap()
    count=len(pcm)
    audio_seconds=count/44100
    rms=math.sqrt(sum(float(x)*x for x in pcm)/count)/32768
    peak=max(abs(x) for x in pcm)/32768
    stage=json.loads((a.stage/'stage-provenance.json').read_text())
    latmask=evidence/'run/latent_mask.f32'
    initial=evidence/'run/initial_latent.f32'
    masks=array.array('f',latmask.read_bytes());noise=array.array('f',(a.stage/'bundle/noise.f32').read_bytes());actual=array.array('f',initial.read_bytes())
    if sys.byteorder!='little':
        for values in (masks,noise,actual):values.byteswap()
    active=d['natural_active_latent']
    if list(masks)!=[1.]*active+[0.]*(512-active):raise ValueError('own natural mask differs')
    for c in range(144):
        for pos in range(512):
            i=c*512+pos
            if actual[i]!=(noise[i] if pos<active else 0.):raise ValueError('own masked common noise differs')
    metrics={k:d[k] for k in ('runtime','provider','profiling_enabled','threads','text_extent','active_text_positions','latent_extent','natural_active_latent','predicted_duration_seconds','natural_wave_frames','emitted_frames','vocoder_output_frames','setup_seconds','render_stage_seconds','pipeline_wall_seconds','maxrss_kib','stage_setup_seconds','stage_run_seconds')}
    metrics['stage_names']=d.get('stage_names',['duration','text','vector','vocoder'])
    native_stderr=(evidence/'stderr.log').read_text()
    if re.findall(r'^session_ready (\w+)',native_stderr,re.M)!=metrics['stage_names']:raise ValueError('session readiness sequence differs')
    if re.findall(r'^vector_step_complete (\d+)',native_stderr,re.M)!=['0','1','2','3','4']:raise ValueError('vector step receipt differs')
    pid_log=evidence/'native-pid-logcat.txt'
    pid_log_text=pid_log.read_text() if pid_log.exists() else ''
    if len(metrics['stage_names'])!=len(d['stage_run_seconds']):raise ValueError('stage timing layout differs')
    stage_seconds=dict(zip(metrics['stage_names'],d['stage_run_seconds']))
    metrics['logical_stage_run_seconds']={name:(sum(value for key,value in stage_seconds.items() if key.startswith('text')) if name=='text' else stage_seconds[name]) for name in ('duration','text','vector','vocoder')}
    metrics.update(audio_seconds=audio_seconds,rtf_stage_sum=d['render_stage_seconds']/audio_seconds,
                   setup_excluded_pipeline_seconds=d['pipeline_wall_seconds']-d['setup_seconds'],
                   rtf_setup_excluded_pipeline=(d['pipeline_wall_seconds']-d['setup_seconds'])/audio_seconds,
                   peak_observed_vmhwm_kib=int(mem['peak_observed_vmhwm_kib']),peak_sampled_pss_kib=int(mem['peak_sampled_pss_kib']))
    result={'experiment':'0036','route':'Android physical QNN/HTP all four neural stages',
            'status':'one_full_pipeline_completed_not_listening_acceptance','canonical':False,'runs':1,
            'reference_sha256':manifest['reference_sha256'],'reference_bytes':manifest['reference_bytes'],
            'voice':'M1/SID5','speed':1.0,'steps':5,'device_serial':'R5CW81PR8SY',
            'model':'SM-S918B/SM8550/v73','cpu_fallback_disabled':True,
            'neural_calls':stage.get('actual_neural_Run_calls',{'duration':1,'text':1,'vector':5,'vocoder':1}),
            'text_depth_parts':stage.get('text_depth_parts',1),'logical_neural_stages':4,'metrics':metrics,
            'input_tensor_hashes':{k:v['sha256'] for k,v in manifest['tensors'].items()},
            'own_latent_mask_sha256':sha(latmask),'own_initial_latent_sha256':sha(initial),
            'saved_noise_and_own_natural_mask_verified':True,
            'wav':{**metadata,'bytes':pcm_path.stat().st_size,'sha256':sha(pcm_path),
                   'rms_full_scale':rms,'peak_full_scale':peak,'zero_fraction':sum(x==0 for x in pcm)/count,
                   'clip_32767_fraction':sum(abs(x)>=32767 for x in pcm)/count},
            'context_and_runtime_hashes':{k:v for k,v in stage['files'].items() if k.startswith(('lib/','contexts/')) or k=='runner'},
            'memory_method':'runner getrusage ru_maxrss and0.5s /proc own-PID VmHWM/PSS sampling; excludes DSP/VTCM',
            'timing_method':'steady_clock per constructor and stage; sequential load/run/release, no warm campaigns. Pipeline includes constructor/destructor/host IO; setup-excluded difference is explicitly derived.',
            'profile_metrics':{'rpc_microseconds':None,'accelerator_cycles':None,'hvx_cycles':None,
                               'reason':'profiling intentionally off; earlier large profile-enabled path failed SET_PROFILE6006; no fabricated counters'},
            'physical_backend_evidence':{'owned_pid_logcat_sha256':sha(pid_log) if pid_log.exists() else None,'QnnHtpV73Skel_observed':'libQnnHtpV73Skel.so' in pid_log_text,'cdsp_domain_observed':'_dom=cdsp' in pid_log_text,'boundary':'Process-scoped native backend/RPC evidence, not per-stage profiler counters.'},
            'thermal_evidence':'private thermal-before.txt and thermal-after.txt retained',
            'private_evidence_dir':str(a.run.resolve()),'private_wav_path':str(pcm_path.resolve()),
            'listening_verdict':'not_reviewed','entire_chapter_intelligible':None,
            'coverage_boundary':'A complete all-stage run and naturally trimmed valid WAV are not proof every unchanged word was spoken. Qualified unprompted local ASR and Moritz listening remain separate.',
            'no_app_or_data_changes':True,'remote_cleanup_verified':True}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':result['status'],'metrics':metrics,'wav':result['wav']},indent=2))


if __name__=='__main__':main()
