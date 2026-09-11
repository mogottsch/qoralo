#!/usr/bin/env python3
"""Preserve one NEW candidate collection before saved-only short analysis.

No ADB/model execution. Missing optional metrics remain nullable. Sanity is an
explicit exact-output review, never inherited from the earlier candidate.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import re
import shutil
import types

import phone_value_precision_short as scope

TRACK = Path(__file__).resolve().parents[1]
HELPER_SHA = '8cd98fe6cc5e28b72e1c2116c7658bd05c287779bf6669827eac2cca9c9c533f'
STAGE = TRACK/'.local/frozen-stages'/scope.STAGE_NAME


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_helpers():
    path = TRACK/'tools/analyze_phone_return_short.py'
    if sha(path) != HELPER_SHA:
        raise RuntimeError('saved-observation helper source changed')
    helpers = importlib.import_module('analyze_phone_return_short')
    # Isolated globals for just the existing observation function; neither its
    # original module nor its hard-coded historical main/result is modified/run.
    observe = types.FunctionType(helpers.observations.__code__,
                                 dict(helpers.observations.__globals__, FROZEN=STAGE))
    return helpers, observe


def validation_issues(collection, obs, commands, manifest):
    issues = []
    if (collection.get('reviewed_stage_digest') != scope.STAGE_DIGEST or
            manifest.get('context_sha256') != scope.CONTEXT_SHA or
            not collection.get('identity_verified') or not collection.get('input_hashes_verified')):
        issues.append('reviewed device/stage/context binding not established')
    if collection.get('error') or collection.get('process_timeout') or collection.get('process_exit_code') != 0:
        issues.append('controller reported an error, timeout or nonzero/unknown process exit')
    if not obs.get('query_completion_observed_beyond_exit_code'):
        issues.append('query/HTP completion with nonempty UTF8 output not established')
    prompt = obs.get('prompt', {})
    if not prompt.get('rendered_bytes_exact_in_runtime_stdout') or not prompt.get('single_bos_prefix_observed'):
        issues.append('runtime rendered bytes or single-BOS prefix not established')
    if any(not item['matches_bound_prefix'] for item in prompt.get('runtime_prefix_observations', [])):
        issues.append('logged token prefix differs from frozen input')
    if prompt.get('profile_prompt_tokens') not in (None, 170):
        issues.append('runtime prompt count differs from170')
    if obs.get('stop', {}).get('configured_ceiling_observed') != 16:
        issues.append('requested max16 setting not observed')
    generated = obs.get('actual_generated_tokens')
    if generated is not None and not 0 < generated <= 16:
        issues.append('generated count outside the short ceiling')
    for name in ('graph_execute_nonzero_status', 'cpu_backend_markers', 'runtime_fallback_markers', 'cache_quantization_error'):
        if obs.get('execution_markers', {}).get(name):
            issues.append('route/execution marker requires review: '+name)
    operations = [c.get('operation') for c in commands]
    ordered = ('raw.pull' in operations and 'cleanup.remove' in operations and
               operations.index('raw.pull') < operations.index('cleanup.remove'))
    if not (collection.get('raw_pull_completed') and collection.get('cleanup') == 'verified_absent' and
            collection.get('process_cleanup', {}).get('all_absent') and collection.get('phone_lock_released') and ordered):
        issues.append('capture/cleanup lifecycle incomplete')
    if not commands or not all(c.get('lock_held') and c.get('lock_fd_inheritable') is False for c in commands):
        issues.append('full noninherited phone-lock coverage not established')
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--result-dir', type=Path, required=True)
    parser.add_argument('--sanity', choices=['unchecked', 'sensible', 'broken'], default='unchecked')
    parser.add_argument('--issue-notes')
    parser.add_argument('--reviewed-output-sha256')
    args = parser.parse_args()
    run, result = args.run_dir.resolve(), args.result_dir.resolve()
    if run.parent != (TRACK/'.local/value-precision-phone-short-runs').resolve():
        parser.error('only the new candidate short collection root is accepted')
    if result.parent != TRACK/'results' or not result.name.startswith('value-precision-path-phone-short-'):
        parser.error('result must be a fresh owned candidate-short result directory')
    if ((args.sanity == 'broken') != bool(args.issue_notes) or
            (args.sanity != 'unchecked' and not args.reviewed_output_sha256)):
        parser.error('reviewed sanity requires output SHA; only broken requires nonempty notes')
    helpers, observe = load_helpers()
    result.mkdir(parents=True, exist_ok=False)
    raw = result/'raw/controller'; raw.mkdir(parents=True)
    private, battery, errors = [], {}, []
    # First retain all returned evidence; raw battery originals remain private.
    for source in sorted(run.rglob('*')):
        if not source.is_file():
            continue
        rel = source.relative_to(run)
        match = re.fullmatch(r'raw/commands/\d+-telemetry\.(before|after)\.battery\.stdout', str(rel))
        if match:
            private.append({'path': str(source), 'bytes': source.stat().st_size, 'sha256': sha(source),
                            'reason': 'Original may include unrelated learned charging/sleep history; retained privately without rewriting.'})
            text = source.read_text(errors='replace')
            core = helpers.battery_extract(text)
            usb = re.search(r'^\s*USB powered:\s*(true|false)\s*$', text, re.M)
            core['usb_powered'] = (usb[1] == 'true') if usb else None
            battery[match[1]] = core
            continue
        dest = raw/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    (result/'raw-capture.json').write_text(json.dumps({'source': str(run), 'private_originals': private,
        'battery_core_extracts': battery, 'raw_retained_before_analysis': True}, indent=2)+'\n')
    obs, collection, commands = {}, {}, []
    manifest = json.loads((STAGE/'frozen-manifest.json').read_text())
    if sha(STAGE/'frozen-manifest.json') != scope.STAGE_DIGEST:
        errors.append('external frozen manifest digest changed')
    try:
        collection = json.loads((raw/'collection.json').read_text())
        for path in sorted((raw/'raw/commands').glob('*.json')):
            if not path.name.endswith('.host-pid.json'):
                commands.append(json.loads(path.read_text()))
        obs = observe(raw, raw/'raw/commands')
        obs['stop']['missing_reason'] = ('No independent EOS-versus-limit enum is exposed in the retained Genie profile/log. '
                                        'A normal return or reaching the ceiling does not independently distinguish them.')
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        errors.append(f'optional/saved parsing incomplete: {type(error).__name__}: {error}')
    errors += validation_issues(collection, obs, commands, manifest)
    sanity = {'looks_sensible': None, 'issue_notes': None}
    if args.sanity != 'unchecked':
        output = raw/'raw/device/short-output.txt'
        if not output.is_file() or sha(output) != args.reviewed_output_sha256:
            errors.append('sanity review does not match the exact retained output')
        else:
            sanity = {'looks_sensible': args.sanity == 'sensible', 'issue_notes': args.issue_notes}
    thermal = {}
    for phase in ('before', 'after'):
        files = list((raw/'raw/commands').glob(f'*-telemetry.{phase}.thermalservice.stdout'))
        thermal[phase] = helpers.thermal_extract(files[0].read_text(errors='replace')) if files else None
    output = {
        'classification': 'physical_precision_path_short_compatibility_only' if not errors else 'physical_short_evidence_requires_review',
        'analysis_issues': errors, 'run_id': run.name, 'context_sha256': scope.CONTEXT_SHA,
        'reviewed_stage_digest': scope.STAGE_DIGEST, 'readiness_commit': 'a6515c9',
        'collection': collection, 'observations': obs, 'output_sanity': sanity,
        'operating_context': {'battery_core_extracts': battery, 'thermal': thermal},
        'memory': {'process_pss': None, 'process_vmhwm': None, 'htp_private_bytes': None,
                   'reason': 'The scoped controller did not measure process/HTP memory; allocation messages are not total-memory measurements.'},
        'claim_boundary': 'One short/max16 compatibility diagnostic. No exact-long, canonical campaign, numerical-fidelity, root-cause or speed-improvement conclusion. Absence of CPU/fallback markers is not universal CPU-free proof.',
        'privacy_retention': private, 'registry_eligible': False,
        'source_sha256': sha(Path(__file__)), 'observation_helper_sha256': HELPER_SHA,
        'next_step': 'If compatible, freeze and run one exact-long/max2048 request in a separately coordinated phone slot; no automatic replay.'}
    (result/'result.json').write_text(json.dumps(output, indent=2, sort_keys=True)+'\n')
    files = sorted(p for p in result.rglob('*') if p.is_file())
    (result/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(result)}\n' for p in files))
    print(json.dumps({'result': str(result/'result.json'), 'sha256': sha(result/'result.json'), 'issues': errors}))


if __name__ == '__main__':
    main()
