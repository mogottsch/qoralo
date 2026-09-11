#!/usr/bin/env python3
"""Retain the new exact-long collection, then apply frozen saved-data metrics.

Run with the existing QAIRT Python3.10 venv (installed tokenizers); no neural
model, SDK compilation, download or ADB. No historical outcome is assumed.
"""
import argparse
import gzip
import importlib.util
import inspect
import json
from pathlib import Path
import types
import hashlib

import phone_value_precision_long as scope
import analyze_phone_return_short as old_short
import analyze_phone_return_long as old_long
import analyze_value_precision_short as short_analysis

TRACK = Path(__file__).resolve().parents[1]
STAGE = TRACK/'.local/frozen-stages'/scope.STAGE_NAME
PINS = {
    'analyze_phone_return_short.py': '8cd98fe6cc5e28b72e1c2116c7658bd05c287779bf6669827eac2cca9c9c533f',
    'analyze_phone_return_long.py': '449ac2d0a0faabb4857b2f696208fe7385311639aca28d0ed018b06e8029cac6',
    'analyze_value_precision_short.py': '4f5857966a86fe3204622ba5fbf3e3334f466edc987638887b27c05dca96c5bb',
}
sha = old_short.sha


def adapted_functions():
    for name, expected in PINS.items():
        if sha(TRACK/'tools'/name) != expected:
            raise RuntimeError('saved-analysis source changed: '+name)
    source = inspect.getsource(old_short.observations)
    for before, after, count in [('short', 'long', 7), ('170', '1929', 2), ('16', '2048', 4)]:
        if source.count(before) != count:
            raise RuntimeError('observation scope substitution changed')
        source = source.replace(before, after)
    globals_ = dict(old_short.observations.__globals__, FROZEN=STAGE)
    exec(compile(source, '<frozen-long-observation-scope>', 'exec'), globals_)
    validation = inspect.getsource(short_analysis.validation_issues).replace('170', '1929').replace('16', '2048').replace('short ceiling', 'long ceiling')
    validation_globals = dict(short_analysis.validation_issues.__globals__, scope=scope)
    exec(compile(validation, '<long-validation-scope>', 'exec'), validation_globals)
    return globals_['observations'], validation_globals['validation_issues'], source, validation


def compare(output):
    if sha(old_long.METRIC_TOOL) != old_long.METRIC_SHA or sha(STAGE/'tokenizer.json') != old_long.TOKENIZER_SHA:
        raise RuntimeError('frozen metric/tokenizer identity changed')
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(STAGE/'tokenizer.json'))
    spec = importlib.util.spec_from_file_location('frozen_repetition', old_long.METRIC_TOOL)
    metrics = importlib.util.module_from_spec(spec); spec.loader.exec_module(metrics)
    text = output.read_text(); ids = tokenizer.encode(text, add_special_tokens=False).ids
    baselines = sorted((old_long.BASELINE/'raw/campaign/outputs').glob('warm-long-*.txt'))
    if len(baselines) != 5:
        raise RuntimeError('five saved canonical long outputs required for this comparison')
    baseline_text = baselines[0].read_text()
    candidate = metrics.trajectory_metrics(ids, text)
    baseline = metrics.trajectory_metrics(tokenizer.encode(baseline_text, add_special_tokens=False).ids, baseline_text)
    hashes = [sha(path) for path in baselines]
    if any(h != 'f0e9d284f679e2ae426264573bd2be16e7c1e4b190235a3511c5a92ecc097b2d' for h in hashes):
        raise RuntimeError('accepted baseline output identity changed; comparison withheld')
    return {'baseline_commit': '37a2953', 'baseline_output_hashes': hashes,
            'candidate_byte_identical_to_all_baselines': all(h == sha(output) for h in hashes),
            'retokenized_output_tokens': len(ids), 'candidate_metrics': candidate, 'baseline_metrics': baseline,
            'all_declared_metrics_equal': candidate == baseline,
            'metric_source_sha256': old_long.METRIC_SHA, 'tokenizer_sha256': old_long.TOKENIZER_SHA,
            'token_basis': 'Retokenized exact output text, not directly observed emitted IDs.',
            'causal_boundary': 'Descriptive repetition windows/suffix locations, not causal onset or hidden-state equality.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--result-dir', type=Path, required=True)
    p.add_argument('--sanity', choices=['unchecked', 'sensible', 'broken'], default='unchecked')
    p.add_argument('--issue-notes')
    p.add_argument('--reviewed-output-sha256')
    args = p.parse_args()
    run, result = args.run_dir.resolve(), args.result_dir.resolve()
    if run.parent != TRACK/'.local/value-precision-phone-long-runs':
        p.error('only the new candidate long collection root is accepted')
    if result.parent != TRACK/'results' or not result.name.startswith('value-precision-path-phone-long-'):
        p.error('fresh owned candidate-long result required')
    if args.sanity != 'unchecked' and not args.reviewed_output_sha256:
        p.error('sanity review requires exact output SHA')
    if (args.sanity == 'broken') != bool(args.issue_notes):
        p.error('only broken sanity requires notes')
    observe, validate, obs_source, validation_source = adapted_functions()
    # Reuse ONLY the old raw-retention function, with an isolated destination.
    # The fresh launch receipt uses .local/phone-return-launches/<new run ID>.
    retain = types.FunctionType(old_long.retain.__code__, dict(old_long.retain.__globals__, RESULT=result))
    raw, private, compressed = retain(run)
    (result/'adapted-observations.py').write_text(obs_source)
    (result/'adapted-validation.py').write_text(validation_source)
    collection = json.loads((raw/'collection.json').read_text())
    commands = [json.loads(path.read_text()) for path in sorted((raw/'raw/commands').glob('*.json'))
                if not path.name.endswith('.host-pid.json')]
    obs, comparison, issues = {}, None, []
    try:
        # The original private log remains intact; the public copy is lossless gzip.
        obs = observe(run, run/'raw/commands')
        obs['stop']['missing_reason'] = 'Genie exposes no independent EOS-versus-limit enum; normal query return is recorded separately.'
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        issues.append(f'saved observation extraction incomplete: {type(error).__name__}: {error}')
    manifest = json.loads((STAGE/'frozen-manifest.json').read_text())
    if sha(STAGE/'frozen-manifest.json') != scope.STAGE_DIGEST:
        issues.append('external stage digest changed')
    issues += validate(collection, obs, commands, manifest)
    output = raw/'raw/device/long-output.txt'
    comparison_error = None
    try:
        comparison = compare(output)
    except Exception as error:
        comparison_error = f'{type(error).__name__}: {error}'
    sanity = {'looks_sensible': None, 'issue_notes': None}
    if args.sanity != 'unchecked':
        if output.is_file() and sha(output) == args.reviewed_output_sha256:
            sanity = {'looks_sensible': args.sanity == 'sensible', 'issue_notes': args.issue_notes}
        else:
            issues.append('sanity review output identity mismatch')
    if compressed:
        digest = hashlib.sha256(); size = 0
        with gzip.open(result/compressed['compressed_path'], 'rb') as stream:
            for data in iter(lambda: stream.read(4*1024*1024), b''):
                digest.update(data); size += len(data)
        if digest.hexdigest() != compressed['original_sha256'] or size != compressed['original_bytes']:
            issues.append('provider compression not lossless')
    thermal = {}
    for phase in ('before', 'after'):
        paths = list((raw/'raw/commands').glob(f'*-telemetry.{phase}.thermalservice.stdout'))
        thermal[phase] = old_short.thermal_extract(paths[0].read_text()) if paths else None
    report = {'classification': 'physical_precision_path_exact_long_execution_only' if not issues else 'physical_long_evidence_requires_review',
        'analysis_issues': issues, 'run_id': run.name, 'context_sha256': scope.CONTEXT_SHA,
        'stage_digest': scope.STAGE_DIGEST, 'readiness_commit': '713a2fb',
        'collection': collection, 'observations': obs, 'output_sanity': sanity,
        'comparison': comparison, 'comparison_missing_reason': comparison_error,
        'provider_log': compressed, 'private_battery_originals': private,
        'operating_context': {'thermal': thermal, 'battery_extracts': {
            phase: json.loads((result/f'derived/battery-{phase}.json').read_text())
                   if (result/f'derived/battery-{phase}.json').exists() else None for phase in ('before','after')}},
        'memory': {'process_pss': None, 'process_vmhwm': None, 'htp_private_memory': None,
                   'reason': 'Not collected by the scoped controller; allocation logs are not total memory.'},
        'source_sha256': sha(Path(__file__)), 'helper_sources': PINS,
        'claim_boundary': 'One exact-long/max2048 request on this candidate. Comparison is of retained output bytes and frozen descriptive metrics, not hidden states, finalized arithmetic, root cause, universal CPU-free placement, broad quality or speed.',
        'registry_eligible': False, 'canonical_campaign_unchanged': True, 'prior_exact_long_negative_unchanged': True}
    (result/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    files = sorted(path for path in result.rglob('*') if path.is_file())
    (result/'SHA256SUMS').write_text(''.join(f'{sha(path)}  {path.relative_to(result)}\n' for path in files))
    print(json.dumps({'result': str(result/'result.json'), 'sha256': sha(result/'result.json'), 'issues': issues,
                      'comparison_error': comparison_error}))


if __name__ == '__main__':
    main()
