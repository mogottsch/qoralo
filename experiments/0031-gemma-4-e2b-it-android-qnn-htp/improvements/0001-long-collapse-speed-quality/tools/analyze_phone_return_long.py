#!/usr/bin/env python3
"""Saved-data GateB analysis only; frozen text-tokenizer/metrics, no model or ADB.

Retain exact raw evidence first. Full battery histories stay private/hash-bound;
the provider log is retained losslessly compressed with original byte identity.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct

from analyze_phone_return_short import battery_extract, thermal_extract, profile_events, sha

TRACK = Path(__file__).resolve().parents[1]
EXP = TRACK.parents[1]
RESULT = TRACK / 'results/phone-return-long-attempt-01'
FROZEN = TRACK / 'results/exact-long-readiness/raw/control-inputs'
METRIC_TOOL = TRACK / 'tools/analyze_long_collapse.py'
METRIC_SHA = '6084bb73d60f7e68ac3f516fad6df3463fdc8adb6213ea9a9a36190099b4fb70'
TOKENIZER = TRACK / '.local/frozen-stages/stage-freeze-long-20260910T163842Z-01/tokenizer.json'
TOKENIZER_SHA = 'cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f'
BASELINE = EXP / 'results/android-qnn-physical-campaign-attempt-02'


def retain(run):
    raw = RESULT / 'raw/controller'
    raw.mkdir(parents=True, exist_ok=False)
    private = []
    compressed = None
    for source in sorted(run.rglob('*')):
        if not source.is_file(): continue
        rel = source.relative_to(run)
        if re.fullmatch(r'raw/commands/\d+-telemetry\.(before|after)\.battery\.stdout', str(rel)):
            phase = 'before' if '.before.' in source.name else 'after'
            private.append({'private_original_path': str(source), 'bytes': source.stat().st_size,
                            'sha256': sha(source), 'reason': 'Unrelated learned battery/sleep history retained privately, not rewritten.'})
            extract = RESULT / f'derived/battery-{phase}.json'; extract.parent.mkdir(exist_ok=True)
            extract.write_text(json.dumps(battery_extract(source.read_text()), indent=2) + '\n')
            continue
        destination = raw / rel
        if rel == Path('SHA256SUMS'):
            destination = RESULT / 'raw/controller-original-SHA256SUMS.txt'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if rel == Path('raw/device/genie-verbose.log'):
            destination = destination.with_suffix('.log.gz')
            with source.open('rb') as src, destination.open('wb') as output:
                with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as dst:
                    shutil.copyfileobj(src, dst, length=4*1024*1024)
            compressed = {'original_bytes': source.stat().st_size, 'original_sha256': sha(source),
                          'compressed_path': str(destination.relative_to(RESULT)),
                          'compressed_sha256': sha(destination), 'lossless': True}
        else:
            shutil.copy2(source, destination)
    shutil.copytree(TRACK / '.local/phone-return-launches' / run.name, RESULT / 'raw/launcher')
    collection = json.loads((raw / 'collection.json').read_text())
    shutil.copy2(TRACK / '.local/phone-return-slots' / (collection['pi_slot'] + '.json'), RESULT / 'raw/slot-use.json')
    return raw, private, compressed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', required=True, type=Path)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if run.parent.name != 'phone-return-long-runs': raise ValueError('wrong run scope')
    raw, private, compressed = retain(run)  # retain first, before optional extraction
    device = raw / 'raw/device'; collection = json.loads((raw / 'collection.json').read_text())
    events, profile_error = profile_events(device / 'long-profile.json')
    query = next((e for e in events if e.get('type') == 'GenieDialog_query'), {})
    create = next((e for e in events if e.get('type') == 'GenieDialog_create'), {})
    def metric(key): return query.get(key, {}).get('value')
    tokens = list(struct.unpack('<1929i', (FROZEN / 'token-ids/long.int32le').read_bytes()))
    patterns = {
        'context_deserialized': 'Context 1 deserialized on pd 0',
        'htp_initialized': 'HTP: initialization completed successfully',
        'two_graphs_initialized': 'qnn-api initialized with 2 graph(s)',
        'physical_soc_detected': 'Detected Snapdragon SOC SM8550',
        'stub_connection': 'First connection to QNN stub established',
        'weight_sharing': 'prepared with Weight Sharing enabled',
        'query_enter': 'Entering GenieDialog_query', 'query_return': 'Returning from GenieDialog_query',
        'dialog_create_enter': 'Entering GenieDialog_create', 'dialog_free_return': 'Returning from GenieDialog_free',
        'graphs_started': 'QnnGraph_execute started', 'graphs_status0': 'QnnGraph_execute done. status 0x0',
        'ar128_status0': 'Graph ar128_cl4096_1_of_1 execution finished with result 0',
        'ar1_status0': 'Graph ar1_cl4096_1_of_1 execution finished with result 0',
        'smart_mask': 'Initializing with KV$ update method = SMART_MASK',
        'cache_quantization_errors': 'Non-identical quantization parameters',
        'known_cross_attention_warning': 'qnn-htp-engine does not support usesCrossAttention',
    }
    counts = Counter({key: 0 for key in patterns})
    counts.update({'cpu_backend_markers': 0, 'runtime_fallback_markers': 0, 'graph_nonzero_status': 0})
    prefixes = []
    digest = hashlib.sha256(); decompressed_bytes = 0
    with gzip.open(RESULT / compressed['compressed_path'], 'rb') as stream:
        for line_bytes in stream:
            digest.update(line_bytes); decompressed_bytes += len(line_bytes)
            line = line_bytes.decode('utf-8', errors='replace')
            for key, marker in patterns.items(): counts[key] += marker in line
            counts['cpu_backend_markers'] += bool(re.search(r'QnnCpu|CPU backend', line, re.I))
            counts['runtime_fallback_markers'] += bool(re.search('fallback', line, re.I))
            status = re.search(r'QnnGraph_execute done\. status (\S+)', line)
            counts['graph_nonzero_status'] += bool(status and status[1] != '0x0')
            if 'embedding-tokens:' in line:
                tail = line.split('embedding-tokens:', 1)[1].strip()
                complete = [int(x) for x in re.findall(r'(-?\d+)\s*(?=[,\]])', tail)]
                prefixes.append({'complete_count': len(complete), 'matches_bound_prefix': complete == tokens[:len(complete)],
                                 'single_bos_prefix': complete[:2] == [2, 105], 'truncated': not tail.endswith(']')})
    assert digest.hexdigest() == compressed['original_sha256'] and decompressed_bytes == compressed['original_bytes']
    prompt = (FROZEN / 'prompts/long.txt').read_bytes(); stdout = (device / 'runner.stdout').read_bytes()
    pos = stdout.find(b'[PROMPT]: ')
    prompt_exact = pos >= 0 and stdout[pos+10:pos+10+len(prompt)] == prompt
    caps = re.findall(r'^> dialog setMaxNumTokens dialog1 (\d+)$', stdout.decode(), re.M)
    output_path = device / 'long-output.txt'; output_bytes = output_path.read_bytes(); output_text = output_bytes.decode('utf-8')

    # Reproduce exactly the predeclared function with the pinned text tokenizer.
    # This is output retokenization, not a neural/model inference call or direct emitted IDs.
    if sha(METRIC_TOOL) != METRIC_SHA or sha(TOKENIZER) != TOKENIZER_SHA:
        raise RuntimeError('frozen repetition metric or tokenizer identity changed')
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(TOKENIZER))
    spec = importlib.util.spec_from_file_location('frozen_repetition', METRIC_TOOL)
    metrics = importlib.util.module_from_spec(spec); spec.loader.exec_module(metrics)
    candidate_ids = tokenizer.encode(output_text, add_special_tokens=False).ids
    candidate_metrics = metrics.trajectory_metrics(candidate_ids, output_text)
    baseline_outputs = sorted((BASELINE / 'raw/campaign/outputs').glob('warm-long-*.txt'))
    if len(baseline_outputs) != 5: raise RuntimeError('retained baseline count changed')
    baseline_hashes = [sha(path) for path in baseline_outputs]
    baseline_text = baseline_outputs[0].read_text()
    baseline_metrics = metrics.trajectory_metrics(tokenizer.encode(baseline_text, add_special_tokens=False).ids, baseline_text)
    commands = [json.loads(path.read_text()) for path in sorted((raw / 'raw/commands').glob('*.json'))
                if not path.name.endswith('.host-pid.json')]
    names = [c['operation'] for c in commands]
    thermal = {}
    for phase in ('before', 'after'):
        paths = list((raw / 'raw/commands').glob(f'*-telemetry.{phase}.thermalservice.stdout'))
        thermal[phase] = thermal_extract(paths[0].read_text()) if paths else None
    issues = []
    frozen_manifest = json.loads((FROZEN / 'frozen-manifest.json').read_text())
    if (collection['reviewed_stage_digest'] != sha(FROZEN / 'frozen-manifest.json')
            or frozen_manifest['context_sha256'] != '1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8'):
        issues.append('reviewed stage/context identity mismatch')
    if not (prompt_exact and prefixes and all(p['matches_bound_prefix'] and p['single_bos_prefix'] for p in prefixes)):
        issues.append('effective prompt byte/prefix mismatch')
    if metric('num-prompt-tokens') not in (None, 1929): issues.append('prompt count mismatch')
    if not (counts['query_enter'] == counts['query_return'] == 1 and counts['graphs_status0'] > 0 and output_text.strip()):
        issues.append('query/provider completion not established beyond exit code')
    if any(counts[k] for k in ('graph_nonzero_status', 'cpu_backend_markers', 'runtime_fallback_markers', 'cache_quantization_errors')):
        issues.append('execution/route error marker observed')
    if not collection['input_hashes_verified'] or not collection['identity_verified']:
        issues.append('device/stage identity incomplete')
    raw_before_cleanup = names.index('raw.pull') < names.index('cleanup.remove') if 'cleanup.remove' in names else False
    result = {
        'schema_version': 1, 'experiment': '0031-gemma-4-e2b-it-android-qnn-htp',
        'improvement_track': '0001-long-collapse-speed-quality', 'run_id': run.name,
        'classification': 'physical_exact_long_htp_execution_repetition_unchanged' if not issues else 'physical_long_evidence_requires_review',
        'analysis_issues': issues,
        'claim_boundary': 'One real exact-long/max2048 query completed through QnnDsp/HTP on the frozen FP16-global-value context. The complete output is byte-identical to all five retained baseline long outputs and has unchanged declared repetition metrics. Global-value FP16 alone produced no observable text/repetition improvement on this request. This is not numerical-state equivalence, broad quality or speed acceptance, a baseline rerun, or a canonical campaign replacement.',
        'context_sha256': '1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8',
        'stage_digest': collection['reviewed_stage_digest'], 'adapter_commit': 'b43a57f', 'pi_slot': collection['pi_slot'],
        'collection': collection, 'provider_observations': dict(counts),
        'prompt': {'bytes_exact': prompt_exact, 'rendered_sha256': sha(FROZEN / 'prompts/long.txt'),
                   'token_ids_sha256': sha(FROZEN / 'token-ids/long.int32le'), 'expected_tokens': 1929,
                   'profile_tokens': metric('num-prompt-tokens'), 'logged_prefixes': prefixes},
        'output': {'path': 'raw/controller/raw/device/long-output.txt', 'bytes': len(output_bytes), 'sha256': sha(output_path),
                   'profile_generated_tokens': metric('num-generated-tokens'), 'retokenized_tokens': len(candidate_ids)},
        'output_sanity': {'looks_sensible': False, 'issue_notes': 'Severe repetition collapse with occasional <unk> leakage in the exact max-token output.'},
        'stop': {'configured_ceiling_observed': int(caps[-1]) if caps else None,
                 'ceiling_reached': metric('num-generated-tokens') == 2048 and caps == ['2048'],
                 'explicit_runtime_stop_reason': None,
                 'missing_reason': 'Configured2048 ceiling was reached and query returned; no independent EOS-versus-limit stop enum/event is exposed.'},
        'comparison': {'baseline_commit': '37a2953', 'baseline_output_count': 5, 'baseline_output_hashes': baseline_hashes,
                       'candidate_byte_identical_to_all_baselines': all(h == sha(output_path) for h in baseline_hashes),
                       'metric_source_sha256': METRIC_SHA, 'tokenizer_sha256': TOKENIZER_SHA,
                       'token_basis': 'Re-encoded output text using the same pinned tokenizer; not directly logged emitted IDs.',
                       'candidate_metrics': candidate_metrics, 'baseline_metrics': baseline_metrics,
                       'all_declared_metrics_equal': candidate_metrics == baseline_metrics,
                       'onset_boundary': 'Index83 is the START of the first qualifying128-token diversity window, not an exact causal onset or internal logit/state divergence.',
                       'cause_boundary': 'Negative result for this exact candidate/request only. Selected FP16 interfaces may retain internal quantization; this does not disprove all cache-precision causes.'},
        'raw_genie_profile': {'create_event': create or None, 'query_event': query or None, 'profile_error': profile_error,
                              'normalized_decode_tokens_per_second': None,
                              'reason': 'Genie rate first-token inclusion is unspecified. One observation with different thermal/run context is not a normalized speed win.'},
        'cleanup': {'remote_root_absent': collection['cleanup'] == 'verified_absent',
                    'recorded_roles_absent': collection['process_cleanup']['all_absent'], 'lock_released': collection['phone_lock_released'],
                    'live_native_pid_observed': collection['native_process_observed'],
                    'signal_commands': sum(n.startswith('signal.') for n in names), 'adb_calls': len(commands),
                    'all_calls_lock_guarded': all(c['lock_held'] and not c['lock_fd_inheritable'] for c in commands),
                    'raw_pull_before_cleanup': raw_before_cleanup},
        'memory': {'process_pss': None, 'process_vmhwm': None, 'htp_private_memory': None,
                   'reason': 'Controller collects PID identity but not these memory metrics; do not relabel stderr buffer allocation or /proc stat fields.'},
        'operating_context': {'battery_before': json.loads((RESULT / 'derived/battery-before.json').read_text()),
                              'battery_after': json.loads((RESULT / 'derived/battery-after.json').read_text()), 'thermal': thermal},
        'provider_log': compressed, 'privacy_retention': {'private_battery_originals': private, 'public_battery': 'Explicit core-field extracts only.'},
        'publication': {'registry_eligible': False, 'speed_acceptance': False, 'long_repetition_improved': False,
                        'completed_campaign_modified': False, 'uniform_integer_or_universal_cpu_free_claim': False},
        'next_gate': 'Pi findings review only. No further optimization, recompile, runtime, phone or push authorized.'}
    (RESULT / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    sums = RESULT / 'SHA256SUMS'; sums.write_text(''.join(f'{sha(path)}  {path.relative_to(RESULT)}\n' for path in sorted(RESULT.rglob('*')) if path.is_file() and path != sums))
    print(RESULT / 'result.json'); print('result_sha256=' + sha(RESULT / 'result.json'))


if __name__ == '__main__': main()
