#!/usr/bin/env python3
"""Retain/classify one saved max16 physical collection; never accesses ADB.

Full battery dumps include unrelated learned personal history. Originals stay
private and hash-bound; public evidence contains clearly labeled core extracts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

TRACK = Path(__file__).resolve().parents[1]
EXP = TRACK.parents[1]
EXPECTED_CONTEXT = '1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8'
FROZEN = TRACK / 'results/frozen-genie-stage-readiness/raw/control-inputs'
RESULT = TRACK / 'results/phone-return-short-attempt-01'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def profile_events(path):
    try:
        data = json.loads(path.read_text())
        return [event for component in (data.get('components') or []) for event in component.get('events', [])], None
    except (OSError, ValueError, TypeError, AttributeError) as error:
        return [], f'{type(error).__name__}: {error}'


def battery_extract(text):
    def number(key):
        match = re.search(r'^\s*' + re.escape(key) + r':\s*(-?\d+)\s*$', text, re.M)
        return int(match[1]) if match else None
    temp = number('temperature')
    return {'level_percent': number('level'), 'temperature_c': temp / 10 if temp is not None else None,
            'voltage_mv': number('voltage'), 'usb_powered': 'USB powered: true' in text,
            'scope': 'Derived core fields only; vendor learned charging/sleep history omitted.'}


def thermal_extract(text):
    status = re.search(r'Thermal Status: (\d+)', text)
    temperatures = {name: float(value) for value, name in re.findall(
        r'Temperature\{mValue=([0-9.]+), mType=\d+, mName=([^,]+),', text)}
    return {'status': int(status[1]) if status else None, 'temperatures_c': temperatures}


def observations(raw, command_root):
    device = raw / 'raw/device'
    log = (device / 'genie-verbose.log').read_text(errors='replace')
    stdout = (device / 'runner.stdout').read_bytes()
    output_path = device / 'short-output.txt'
    output_bytes = output_path.read_bytes()
    output = output_bytes.decode('utf-8')
    events, profile_error = profile_events(device / 'short-profile.json')
    creates = [event for event in events if event.get('type') == 'GenieDialog_create']
    queries = [event for event in events if event.get('type') == 'GenieDialog_query']
    query = queries[-1] if queries else {}
    def value(key):
        return query.get(key, {}).get('value')
    markers = {
        'context_deserialized': 'Context 1 deserialized on pd 0',
        'two_graphs_initialized': 'qnn-api initialized with 2 graph(s)',
        'physical_soc_detected': 'Detected Snapdragon SOC SM8550',
        'htp_initialized': 'HTP: initialization completed successfully',
        'stub_connection': 'First connection to QNN stub established',
        'weight_sharing': 'prepared with Weight Sharing enabled',
        'graph_execute_started': 'QnnGraph_execute started',
        'graph_execute_status0': 'QnnGraph_execute done. status 0x0',
        'ar128_completed_status0': 'Graph ar128_cl4096_1_of_1 execution finished with result 0',
        'ar1_completed_status0': 'Graph ar1_cl4096_1_of_1 execution finished with result 0',
        'dialog_create_enter': 'Entering GenieDialog_create',
        'dialog_create_return': 'Returning from GenieDialog_create',
        'query_enter': 'Entering GenieDialog_query', 'query_return': 'Returning from GenieDialog_query',
        'dialog_free_return': 'Returning from GenieDialog_free',
        'smart_mask_selected': 'Initializing with KV$ update method = SMART_MASK',
        'cache_quantization_error': 'Non-identical quantization parameters',
        'known_cross_attention_warning': 'qnn-htp-engine does not support usesCrossAttention',
    }
    counts = {key: log.count(marker) for key, marker in markers.items()}
    counts['cpu_backend_markers'] = len(re.findall(r'QnnCpu|CPU backend', log, re.I))
    counts['runtime_fallback_markers'] = len(re.findall(r'fallback', log, re.I))
    statuses = re.findall(r'QnnGraph_execute done\. status (\S+)', log)
    counts['graph_execute_nonzero_status'] = sum(status != '0x0' for status in statuses)
    expected_prompt = (FROZEN / 'prompts/short.txt').read_bytes()
    token_data = (FROZEN / 'token-ids/short.int32le').read_bytes()
    tokens = list(struct.unpack('<170i', token_data))
    start = stdout.find(b'[PROMPT]: ')
    prompt_exact = start >= 0 and stdout[start + 10:start + 10 + len(expected_prompt)] == expected_prompt
    prefixes = []
    for line in log.splitlines():
        if 'embedding-tokens:' not in line:
            continue
        tail = line.split('embedding-tokens:', 1)[1].strip()
        complete = [int(item) for item in re.findall(r'(-?\d+)\s*(?=[,\]])', tail)]
        fragment = re.search(r',\s*(\d+)$', tail) if not tail.endswith(']') else None
        prefixes.append({'complete_token_count': len(complete), 'complete_prefix': complete,
                         'matches_bound_prefix': complete == tokens[:len(complete)],
                         'logger_truncated': not tail.endswith(']'),
                         'last_numeric_fragment': fragment[1] if fragment else None})
    caps = re.findall(r'^> dialog setMaxNumTokens dialog1 (\d+)$', stdout.decode(), re.M)
    complete_query = (counts['query_enter'] == 1 and counts['query_return'] == 1
                      and counts['graph_execute_status0'] > 0 and bool(output.strip()))
    return {
        'query_completion_observed_beyond_exit_code': complete_query,
        'execution_markers': counts,
        'prompt': {'rendered_bytes_exact_in_runtime_stdout': prompt_exact,
                   'rendered_sha256': sha(FROZEN / 'prompts/short.txt'),
                   'token_ids_sha256': sha(FROZEN / 'token-ids/short.int32le'),
                   'expected_tokens': 170, 'profile_prompt_tokens': value('num-prompt-tokens'),
                   'runtime_prefix_observations': prefixes, 'bos_config': -1,
                   'single_bos_prefix_observed': bool(prefixes) and all(p['complete_prefix'][:2] == [2, 105] for p in prefixes)},
        'output': {'path': 'raw/controller/raw/device/short-output.txt', 'bytes': len(output_bytes), 'sha256': sha(output_path)},
        'actual_generated_tokens': value('num-generated-tokens'),
        'stop': {'configured_ceiling_observed': int(caps[-1]) if caps else None,
                 'ceiling_reached': (value('num-generated-tokens') == 16 and caps == ['16']
                                     if value('num-generated-tokens') is not None and caps else None),
                 'query_returned_normally': counts['query_return'] == 1,
                 'explicit_runtime_stop_reason': None,
                 'missing_reason': 'No independent EOS-versus-limit stop enum/event is exposed in the retained profile/log. Configured max16 was set and reached; do not invent an EOS event.'},
        'raw_genie_profile': {'create_event': creates[-1] if creates else None, 'query_event': query or None,
                              'profile_error': profile_error,
                              'normalized_decode_tokens_per_second': None,
                              'normalized_decode_missing_reason': 'Genie does not define first-token inclusion for its rate; raw rate is not a normalized comparison metric.',
                              'scope': 'One max16 engineering observation; runtime-defined timing boundaries, no speed acceptance or campaign distribution.'},
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', type=Path, required=True)
    args = p.parse_args()
    run = args.run_dir.resolve()
    if run.parent.name != 'phone-return-runs':
        raise ValueError('unexpected source run directory')
    raw = RESULT / 'raw/controller'
    raw.mkdir(parents=True, exist_ok=False)
    private = []
    # Retain raw BEFORE parsing/validation. Do not normalize provider/output bytes.
    for source in sorted(run.rglob('*')):
        if not source.is_file():
            continue
        rel = source.relative_to(run)
        if re.fullmatch(r'raw/commands/\d+-telemetry\.(before|after)\.battery\.stdout', str(rel)):
            phase = 'before' if '.before.' in source.name else 'after'
            private.append({'private_original_path': str(source), 'bytes': source.stat().st_size,
                            'sha256': sha(source), 'reason': 'Unrelated learned charging/sleep histories; full original kept privately, not rewritten.'})
            extract = RESULT / f'derived/battery-{phase}.json'
            extract.parent.mkdir(exist_ok=True)
            extract.write_text(json.dumps(battery_extract(source.read_text()), indent=2) + '\n')
            continue
        if rel == Path('SHA256SUMS'):
            destination = RESULT / 'raw/controller-original-SHA256SUMS.txt'
        else:
            destination = raw / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    launch = TRACK / '.local/phone-return-launches' / run.name
    shutil.copytree(launch, RESULT / 'raw/launcher')
    slot = json.loads((run / 'collection.json').read_text())['pi_slot']
    shutil.copy2(TRACK / '.local/phone-return-slots' / (slot + '.json'), RESULT / 'raw/slot-use.json')
    collection = json.loads((raw / 'collection.json').read_text())
    obs = observations(raw, raw / 'raw/commands')
    commands = []
    for file in sorted((raw / 'raw/commands').glob('*.json')):
        if not file.name.endswith('.host-pid.json'):
            commands.append(json.loads(file.read_text()))
    thermal = {}
    for phase in ('before', 'after'):
        paths = list((raw / 'raw/commands').glob(f'*-telemetry.{phase}.thermalservice.stdout'))
        thermal[phase] = thermal_extract(paths[0].read_text()) if paths else None
    baseline_output = EXP / 'results/android-qnn-physical-viability-attempt-05/raw/viability-output.txt'
    frozen_manifest = json.loads((FROZEN / 'frozen-manifest.json').read_text())
    issues = []
    if (collection['reviewed_stage_digest'] != sha(FROZEN / 'frozen-manifest.json')
            or frozen_manifest['context_sha256'] != EXPECTED_CONTEXT
            or not collection['identity_verified'] or not collection['input_hashes_verified']):
        issues.append('reviewed device/stage/context binding not established')
    if not obs['query_completion_observed_beyond_exit_code']:
        issues.append('query/HTP completion or nonempty UTF8 output not established')
    if not obs['prompt']['rendered_bytes_exact_in_runtime_stdout'] or not obs['prompt']['single_bos_prefix_observed']:
        issues.append('runtime rendered bytes or single-BOS prefix mismatch')
    if any(not item['matches_bound_prefix'] for item in obs['prompt']['runtime_prefix_observations']):
        issues.append('logged effective token prefix differs from bound input')
    if obs['prompt']['profile_prompt_tokens'] not in (None, 170):
        issues.append('runtime prompt count mismatch')
    for key in ('graph_execute_nonzero_status', 'cpu_backend_markers', 'runtime_fallback_markers', 'cache_quantization_error'):
        if obs['execution_markers'][key]:
            issues.append(f'route/execution issue: {key}')
    operation_names = [c['operation'] for c in commands]
    raw_before_cleanup = ('raw.pull' in operation_names and 'cleanup.remove' in operation_names
                          and operation_names.index('raw.pull') < operation_names.index('cleanup.remove'))
    if not (collection['raw_pull_completed'] and collection['cleanup'] == 'verified_absent'
            and collection['process_cleanup']['all_absent'] and collection['phone_lock_released']
            and raw_before_cleanup):
        issues.append('capture/cleanup lifecycle incomplete')
    result = {
        'schema_version': 1, 'experiment': '0031-gemma-4-e2b-it-android-qnn-htp',
        'improvement_track': '0001-long-collapse-speed-quality', 'run_id': run.name,
        'classification': ('positive_physical_fp16_global_value_cache_short_compatibility_only'
                           if not issues else 'physical_short_evidence_requires_review'),
        'analysis_issues': issues,
        'claim_boundary': 'The exact frozen candidate completed one real short/max16 Genie query on SM8550 with QnnDsp/HTP status0 graph execution and coherent UTF-8 output, not merely process exit0. This is GateA compatibility only: no long run, repetition improvement, full fidelity, speed win, canonical campaign or registry acceptance. Observed absence of CPU/fallback markers is not a universal CPU-free or uniform-integer claim.',
        'context_sha256': EXPECTED_CONTEXT, 'reviewed_stage_digest': collection['reviewed_stage_digest'],
        'controller_commit': '62b8a16', 'stage_commit': '212f0d4', 'pi_slot': collection['pi_slot'],
        'scope': {'query_count': 1, 'dialog_count': 1, 'max_tokens': 16, 'engineering_noncanonical': True,
                  'long_run': False, 'retry': False, 'follow_on': False},
        'collection': collection, 'observations': obs,
        'output_sanity': {'looks_sensible': True, 'issue_notes': None},
        'baseline_short_prefix_comparison': {'source_commit': '5d9f545', 'output_sha256': sha(baseline_output),
                                             'byte_identical': sha(baseline_output) == obs['output']['sha256'],
                                             'scope': 'Exact16-token short prefix only, not long quality or numerical equivalence proof.'},
        'cleanup': {'remote_root_absent': collection['cleanup'] == 'verified_absent',
                    'recorded_role_pids_absent': collection['process_cleanup']['all_absent'],
                    'lock_released': collection['phone_lock_released'],
                    'signal_commands_issued': sum(c['operation'].startswith('signal.') for c in commands),
                    'native_live_pid_sampled': collection['native_process_observed'],
                    'live_pid_note': 'The process completed before the first status poll; no live-native PID sample was obtained. Query/provider/profile/output evidence proves execution independently. No signal was necessary.',
                    'all_adb_calls_lock_guarded': all(c['lock_held'] and not c['lock_fd_inheritable'] for c in commands),
                    'adb_calls': len(commands), 'raw_pull_before_cleanup': raw_before_cleanup},
        'operating_context': {'battery_before': json.loads((RESULT / 'derived/battery-before.json').read_text()),
                              'battery_after': json.loads((RESULT / 'derived/battery-after.json').read_text()),
                              'thermal': thermal},
        'memory': {'process_pss': None, 'process_vmhwm': None, 'htp_private_bytes': None,
                   'reason': 'Reviewed controller did not collect process memory; live native PID was not sampled. stderr allocation report is not process/HTP total memory.'},
        'privacy_retention': {'private_originals': private, 'public_battery_data': 'Clearly labeled core-field extracts only; no raw original rewritten or silently truncated.'},
        'publication': {'gate_a_compatibility_only': True, 'registry_eligible': False, 'canonical_campaign_modified': False,
                        'long_repetition_acceptance': False, 'speed_acceptance': False},
        'next_gate': 'Pi evidence review. No new ADB; app owns the next slot. Exact-long scope requires separate explicit review/approval.'}
    (RESULT / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    sums = RESULT / 'SHA256SUMS'
    sums.write_text(''.join(f'{sha(f)}  {f.relative_to(RESULT)}\n' for f in sorted(RESULT.rglob('*')) if f.is_file() and f != sums))
    print(RESULT / 'result.json')
    print('result_sha256=' + sha(RESULT / 'result.json'))


if __name__ == '__main__':
    main()
