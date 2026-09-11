#!/usr/bin/env python3
"""Add qualified ASR, physical/thermal evidence and route comparison; no execution."""
import argparse
import json
from pathlib import Path
from materialize import REPO, ROOT, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--attempt',type=Path,required=True)
    p.add_argument('--asr',type=Path,required=True)
    args=p.parse_args()
    cpu_path=ROOT.parent/'cpu/results/first-chapter-01.json'
    cpu_asr_path=ROOT.parent/'cpu/results/asr-first-chapter-01.json'
    htp_path=ROOT/'results/first-chapter-01.json'
    cpu=json.loads(cpu_path.read_text()); htp=json.loads(htp_path.read_text())
    cpu_asr=json.loads(cpu_asr_path.read_text()); asr=json.loads((args.asr/'coverage.json').read_text())
    control_path=REPO/'experiments/0036-supertonic-whole-chapter-cpu-htp/cpu/results/asr-control-01.json'
    control=json.loads(control_path.read_text())
    if control['word_error_rate']!=0 or control['reference_words']!=36:
        raise ValueError('ASR control qualification missing')
    for key in ['model_sha256','whisper_version','torch_version','device','threads','settings']:
        if asr[key]!=control[key] or asr[key]!=cpu_asr[key]:
            raise ValueError('ASR qualification/runtime/settings drift')
    if asr['wav_sha256']!=htp['wav_sha256'] or asr['reference_sha256']!=cpu_asr['reference_sha256'] or asr['logical_asr_passes']!=1:
        raise ValueError('ASR not bound to this exact WAV/reference/one-pass route')
    asr.update(qualification='Same offline localWhisper-small model/runtime/settings as0036 canonical control0WER/36words',
        control_metadata=str(control_path.relative_to(REPO)),control_metadata_sha256=sha(control_path),
        coverage_assessment='strong_automatic_support_for_whole_chapter; no human listening acceptance',
        word_count_note='487raw whitespacewords;495regex comparisonwords from exactofficial perchunk normalizedreference')
    def save(name,value):
        with (ROOT/'results'/name).open('x') as f:
            json.dump(value,f,indent=2,allow_nan=False); f.write('\n')
    save('asr-first-chapter-01.json',asr)
    samples=[list(map(int,line.split())) for line in (args.attempt/'evidence/memory-samples.txt').read_text().splitlines()]
    before=json.loads((args.attempt/'preflight-bounds.json').read_text())
    log_path=args.attempt/'evidence/native-pid-logcat.txt'; log=log_path.read_text()
    physical=dict(device=json.loads((args.attempt/'identity.json').read_text()),
        owned_pid=int((args.attempt/'evidence/runner.pid').read_text()),
        log_sha256=sha(log_path),owned_pid_and_time_window_filtered=True,
        cdsp_library_loaded='libcdsprpc.so loaded' in log,
        qnn_v73_skel_opened='Successfully opened file libQnnHtpV73Skel.so' in log,
        qnn_skel_remote_handle_opened='qnn_2_49_0_skel_handle_invoke&_modver=1.0&_dom=cdsp on domain 3' in log,
        user_pd_created='Created user PD on domain 3' in log,
        dsp_queue_created='dspqueue_create: created Queue' in log,
        remote_handles_closed='num of open handles: 0' in log,
        kernel_dsp_perf_tracing_disabled='RPC traces (kernel 0, dsp 0)' in log,
        nonfatal_driver_warning_note='Startup lookup/control/watch and teardown diagnostics retained privately; no clean-log claim. Native route exit0.',
        counters=None,counter_reason='ProfileOFF; no DSP cycle/HVX counters or per-node device profiler claim',
        linux_memory=dict(ru_maxrss_kib=htp['maxrss_kib'],sampled_vmrss_peak_kib=max(x[1] for x in samples),
            sampled_vmhwm_peak_kib=max(x[2] for x in samples),sampled_pss_peak_kib=max(x[3] for x in samples),
            samples=len(samples),interval_target_seconds=0.5,
            qualification='Own-process Linux observations; sampled RSS/PSS can miss peaks and DSP/DMA/global memory is not fully represented. Not a total-memory win over CPU.'),
        device_available_kib=dict(before_stage=before['available_kib'],minimum_sampled=min(x[4] for x in samples)),
        battery_temperature_c=dict(before_stage=before['battery_temperature_tenths_c']/10,
            first_native_sample=samples[0][5]/10,maximum_sampled=max(x[5] for x in samples)/10,last_native_sample=samples[-1][5]/10),
        installed_apks_before=json.loads((args.attempt/'installed-apks-before.json').read_text()),
        installed_apks_after=json.loads((args.attempt/'installed-apks-after.json').read_text()),
        app_data_unchanged=htp['phone_lifecycle']['app_database_files_unchanged'],
        remote_removed=htp['phone_lifecycle']['remote_removed'])
    if not all(physical[k] for k in ['cdsp_library_loaded','qnn_v73_skel_opened','qnn_skel_remote_handle_opened','user_pd_created','dsp_queue_created','remote_handles_closed']):
        raise ValueError('expected physical RPC/lifecycle corroboration missing')
    save('physical-evidence-01.json',physical)
    noise=[]
    for a,b in zip(cpu['chunks'],htp['chunks'],strict=True):
        noise.append(dict(index=a['index'],cpu_nativeL=a['native_latent'],htp_nativeL=b['native_latent'],
            cpu_noise_offset=a['noise_offset'],htp_noise_offset=b['noise_offset'],
            cpu_active_noise_sha256=a['initial_noise_sha256'],htp_active_noise_sha256=b['initial_noise_sha256'],
            exact_active_noise_match=a['initial_noise_sha256']==b['initial_noise_sha256']))
    comparison=dict(schema_version=1,canonical=False,status='both_routes_complete_strong_qualified_automatic_coverage_human_review_pending',
        cpu_execution_metadata_sha256=sha(cpu_path),htp_execution_metadata_sha256=sha(htp_path),
        current_listening_verdicts={'CPU':'not_reviewed','HTP':'not_reviewed'},
        shared_reference_sha256=cpu['reference_sha256'],bundle_manifest_sha256=cpu['bundle_manifest_sha256'],
        CPU=dict(wav_sha256=cpu['wav']['sha256'],wav_private_path=cpu['wav']['private_path'],
            audio_seconds=cpu['emitted_audio_seconds'],generation_seconds=cpu['generation_wall_seconds'],
            entry_to_complete_seconds=cpu['entry_to_complete_seconds'],setup_seconds=cpu['setup_seconds'],
            first_device_playable_seconds=cpu['first_chunk_playable_from_entry_seconds'],
            first_host_available_seconds=cpu['host_chunk_availability'][0]['host_ready_since_command_seconds'],
            rtf_with_prescribed_gaps=cpu['rtf_including_prescribed_gaps'],ru_maxrss_kib=cpu['maxrss_kib'],
            session_lifecycle=cpu['session_lifecycle'],session_constructors=4,profiling=True,
            asr_wer=cpu_asr['word_error_rate'],asr_matches=cpu_asr['exactly_matched_reference_words'],asr_last30_matches=cpu_asr['last_30_reference_words_matched']),
        HTP=dict(wav_sha256=htp['wav_sha256'],wav_private_path=htp['private_wav_path'],
            audio_seconds=htp['emitted_audio_seconds'],generation_seconds_including_interleaved_setup=htp['generation_wall_including_interleaved_setup_seconds'],
            generation_seconds_excluding_interleaved_lifecycle=htp['generation_wall_excluding_interleaved_lifecycle_seconds'],
            entry_to_complete_seconds=htp['entry_to_complete_seconds'],all_constructor_seconds=htp['all_constructor_seconds'],
            interleaved_constructor_seconds=htp['interleaved_constructor_seconds'],interleaved_teardown_seconds=htp['interleaved_teardown_seconds'],
            first_device_playable_seconds=htp['first_chunk_playable_from_entry_seconds'],
            first_host_available_seconds=htp['first_host_chunk_available_seconds'],
            rtf_with_prescribed_gaps_and_interleaved_setup=htp['rtf_generation_including_gaps_and_interleaved_setup'],
            rtf_with_gaps_excluding_session_lifecycle=htp['rtf_excluding_session_lifecycle_including_gaps'],
            ru_maxrss_kib=htp['maxrss_kib'],session_lifecycle=htp['session_lifecycle'],session_constructors=32,
            max_resident_sessions=4,profiling=False,asr_wer=asr['word_error_rate'],
            asr_matches=asr['exactly_matched_reference_words'],asr_last30_matches=asr['last_30_reference_words_matched']),
        observed_generation_wall_ratio_cpu_over_htp=cpu['generation_wall_seconds']/htp['generation_wall_including_interleaved_setup_seconds'],
        noise_correspondence=noise,
        exact_noise_match_chunk_indices=[x['index'] for x in noise if x['exact_active_noise_match']],
        interpretation_limits=[
            'One first chapter per route, not warm medians or accepted-quality throughput.',
            'Same provider recipe but CPU native shapes/profileON vs HTP case-specific static geometry/profileOFF; setup lifecycle differs.',
            'HTP strict source maxabs/RMSE gate remains failed. Explicit structurally validated non-bit-exact source lowering; no retroactive pass.',
            'Source end-to-end observed error ledger max0.003733 fullscale /0.0929%reference RMS; not universal or a new acceptance threshold.',
            'Own duration changes L at006 and014; only000..005 active-noise hashes match. No blanket matched-noise claim.',
            'Own Linux RSS does not include all DSP/DMA/global memory; do not infer total-memory speed/provider efficiency.',
            'Host frontend preparation,32-context specialization/export/support checks/build/staging are outside device inference timings; not an app-ready generic pack.',
            'Qualified unprompted ASR supports broad coverage, not exact pronunciation, perceptual quality or human acceptance.',
            'Improvement over0036 is multifactored provider recipe change, not proof of a single cause or universal Supertonic quality.'
        ])
    save('comparison-01.json',comparison)
    print('published qualified ASR, physical evidence and first-route comparison; no execution')


if __name__=='__main__':
    main()
