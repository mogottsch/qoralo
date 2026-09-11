#!/usr/bin/env python3
"""Validate one HTP route's own extents/noise/indices and exact PCM assembly.

No neural execution, audio editing, ASR or listening verdict. Public metadata only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import wave
from materialize import ROOT, sha


def fp32(x):
    return struct.unpack('<f',struct.pack('<f',x))[0]


def pcm(path):
    with wave.open(str(path),'rb') as f:
        if (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getcomptype())!=(1,2,44100,'NONE'):
            raise ValueError('unexpected PCM format')
        n=f.getnframes(); data=f.readframes(n)
        if len(data)!=n*2:
            raise ValueError('incomplete PCM')
        return n,data


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--attempt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if not args.attempt.resolve().is_relative_to((ROOT/'.local').resolve()):
        p.error('private attempt required')
    attempt=json.loads((args.attempt/'attempt.json').read_text())
    if attempt['status']!='completed' or not attempt.get('remote_removed') or attempt.get('cleanup_error'):
        raise ValueError('run/cleanup incomplete; preserve first failure without relabelling')
    if not attempt.get('installed_apks_unchanged') or not attempt.get('app_database_files_unchanged'):
        raise ValueError('app preservation not verified')
    run=args.attempt/'evidence/run'; result=json.loads((run/'result.json').read_text())
    if result['result']!='passed' or result['provider']!='QNNExecutionProvider' or not result['cpu_fallback_disabled'] or result['profiling_enabled']:
        raise ValueError('HTP route contract mismatch')
    if result['chunk_count']!=15 or result['steps']!=8 or fp32(result['speed'])!=fp32(1.05):
        raise ValueError('provider recipe drift')
    if result['session_constructor_count']!=32 or result['neural_Run_calls']!=165:
        raise ValueError('unexpected case-specific session/Run count')
    freeze=json.loads((ROOT.parent/'protocol/freeze.json').read_text())
    protocol=json.loads((ROOT.parent/'protocol/inputs.json').read_text())
    bundle=ROOT.parent/'.local/common/bundle'
    if sha(bundle/'manifest.json')!=freeze['bundle_manifest_sha256'] or sha(bundle/'noise_stream.f32')!=freeze['bundle_files_sha256']['noise_stream.f32']:
        raise ValueError('frozen source bundle changed')
    stream=(bundle/'noise_stream.f32').read_bytes(); noise_offset=0; assembled=bytearray(); rows=[]
    for index,(row,frozen_chunk) in enumerate(zip(result['chunks'],protocol['chunks'],strict=True)):
        if row['index']!=index or row['text_extent']!=frozen_chunk['text_extent']:
            raise ValueError('provider chunk order/nativeT changed')
        d=fp32(fp32(row['raw_predicted_seconds'])/fp32(1.05)); wf=fp32(d*fp32(44100))
        length=int(fp32(fp32(fp32(wf+fp32(3072))-fp32(1))/fp32(3072)))
        mask_length=(int(wf)+3071)//3072
        if length!=row['native_latent'] or length!=mask_length or not 1<=length<=512 or fp32(row['speed_adjusted_seconds'])!=d:
            raise ValueError('own HTP extent/speed/mask calculation differs')
        if row['noise_offset']!=noise_offset:
            raise ValueError('Gaussian stream offset drift')
        initial=run/f'chunk-{index:03d}-initial.f32'; expected=stream[noise_offset*4:(noise_offset+144*length)*4]
        if initial.read_bytes()!=expected:
            raise ValueError('own native-layout Gaussian consumption mismatch')
        noise_offset+=144*length
        edge_hashes={}
        for radius in [2,4,8,16]:
            path=run/f'chunk-{index:03d}-edge-r{radius}.i32'
            expected=struct.pack('<'+'i'*(512+2*radius),*[min(max(j-radius,0),length-1) for j in range(512+2*radius)])
            if path.read_bytes()!=expected:
                raise ValueError('device indices not from own native boundary')
            edge_hashes[str(radius)]=sha(path)
        path=run/f'chunk-{index:03d}.wav'; frames,data=pcm(path)
        if frames!=length*3072 or row['emitted_frames']!=frames:
            raise ValueError('native audio cropped or bucket extension retained')
        if index:
            assembled.extend(bytes(13230*2))
        assembled.extend(data)
        row=dict(row,initial_noise_sha256=sha(initial),edge_index_sha256=edge_hashes,wav_sha256=sha(path))
        rows.append(row)
    chapter=run/'chapter.wav'; frames,data=pcm(chapter)
    if data!=assembled or frames!=result['emitted_frames'] or noise_offset!=result['noise_stream_draws_consumed']:
        raise ValueError('assembly/noise total mismatch')
    availability=json.loads((args.attempt/'chunk-availability.json').read_text())
    if len(availability)!=15:
        raise ValueError('complete chunk transport evidence missing')
    by_file={x['chunk_file']:x for x in availability}
    for i,row in enumerate(rows):
        transport=by_file[f'chunk-{i:03d}.wav']
        if transport['sha256']!=row['wav_sha256']:
            raise ValueError('first-available and final chunk hashes differ')
        row['host_availability']=transport
    log=args.attempt/'evidence/native-pid-logcat.txt'
    log_text=log.read_text(errors='replace') if log.exists() else ''
    markers={marker:len([line for line in log_text.splitlines() if marker.casefold() in line.casefold()])
             for marker in ['fastrpc','adsprpc','QnnHtp','V73Skel','remote_handle','cdsp']}
    report=dict(result,canonical=False,experiment='0037-supertonic-provider-pipeline',route='HTP',
        reference_sha256=protocol['reference_sha256'],bundle_manifest_sha256=freeze['bundle_manifest_sha256'],
        strict_source_numerical_gate='failed_preserved; explicitly non-bit-exact source lowering',
        memory_method='process getrusage(RUSAGE_SELF).ru_maxrss plus own-PID0.5s VmRSS/VmHWM/PSS samples; DSP/global allocations not fully represented',
        physical_runtime_evidence=dict(owned_pid_time_window_log_sha256=sha(log) if log.exists() else None,
            log_marker_line_counts=markers,hardware_cycle_hvx_counters=None,
            missing_counter_reason='profiling deliberately OFF after prior SET_PROFILE6006; no counter/cycle claim'),
        private_wav_path=str(chapter),wav_sha256=sha(chapter),wav_format='PCM16 mono44100Hz',
        assembly_verified_byte_exact=True,own_native_extent_noise_indices_verified=True,
        first_host_chunk_available_seconds=availability[0]['host_ready_since_command_seconds'],
        availability_boundary='atomic closed chunk files, not playback; host timing includes command transport/poll/pull',
        phone_lifecycle=attempt,listening_verdict='not_reviewed',asr_status='not_yet_run',chunks=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as f:
        json.dump(report,f,indent=2,allow_nan=False); f.write('\n')
    print(json.dumps(dict(wav_sha256=report['wav_sha256'],frames=frames,audio_seconds=frames/44100,
                         own_noise_verified=True,byte_exact_assembly=True,log_markers=markers),indent=2))


if __name__=='__main__':
    main()
