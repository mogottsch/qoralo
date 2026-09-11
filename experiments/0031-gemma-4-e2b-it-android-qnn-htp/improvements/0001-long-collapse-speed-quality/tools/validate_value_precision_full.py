#!/usr/bin/env python3
"""Saved-only full-DLC core and coupled-exit validation. No SDK/model loading."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from value_precision_path import full_dlc_gate, parse_dlc_csv
from value_precision_exits import exit_gate

TRACK = Path(__file__).resolve().parents[1]
OLD = {1: TRACK/'results/global-value-fp16-attempt-05/raw/inspection-02/ar1.csv.gz',
       128: TRACK/'results/global-value-fp16-attempt-06/raw/inspection-01/ar128.csv.gz'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-root', type=Path, required=True)
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise RuntimeError('refusing to overwrite a saved validation; choose a fresh output name')
    run = args.run_root.resolve()
    converted_path = run/'work/result.json'
    converted = json.loads(converted_path.read_text())
    ar = converted['ar']
    assert converted['classification'] == 'full_dlc_converted_internal_precision_gate_pending'
    guard = json.loads((run/'guard-result.json').read_text())
    assert guard['exit_code'] == 0 and guard['stop_reason'] is None
    prep_path = args.prepared/'preparation.json'
    prep = json.loads(prep_path.read_text())
    assert prep['ar'] == ar and sha(prep_path) == converted['preparation_sha256']
    csv_path = run/'inspection-01/model.csv'
    current, previous = parse_dlc_csv(csv_path), parse_dlc_csv(OLD[ar])
    core = full_dlc_gate(current, previous, prep['all_layers'])
    exits = exit_gate(current, previous, prep['all_layers'])
    passed = core['passed'] and exits['passed'] and exits['head_group_count'] == 7
    outcome_path = run/'inspection-01/inspection-outcome.json'
    inspection_status = json.loads(outcome_path.read_text()).get('exit_code') if outcome_path.exists() else None
    result = {'classification': 'full_dlc_precision_island_validated' if passed else 'full_dlc_precision_island_gate_failed',
              'passed': passed, 'ar': ar, 'dlc': converted['dlc'],
              'converted_result_sha256': sha(converted_path), 'guard_result_sha256': sha(run/'guard-result.json'),
              'csv_sha256': sha(csv_path), 'previous_csv_gzip_sha256': sha(OLD[ar]),
              'preparation_sha256': sha(prep_path), 'core_gate': core, 'coupled_exit_gate': exits,
              'operator_count': len(current['operators']), 'previous_operator_count': len(previous['operators']),
              'source_identities': {p.name: sha(p) for p in [Path(__file__), Path(__file__).with_name('value_precision_path.py'), Path(__file__).with_name('value_precision_exits.py')]},
              'inspection_exit_status': inspection_status,
              'inspection_exit_status_limitation': None if inspection_status is not None else 'Post-GC systemd Result/ExecMainStatus defaults are not independent exit evidence; complete fresh CSV and exact operator/interface checks establish the metadata observations.',
              'scope': 'post-quantized-V-projection normalization/cache/FP16 value MatMul, with required FP16 head concatenation and return to original quantized output-projection input grids',
              'whole_model_fp16': False, 'compiled_full_context_proven': False,
              'numerical_equivalence_proven': False, 'inference': False, 'phone_access': False}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'ar': ar, 'passed': passed, 'core_issues': core['issues'], 'exit_issues': exits['issues'], 'head_groups': exits['head_group_count']}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
