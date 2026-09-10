#!/usr/bin/env python3
"""Compare official qairt-dlc-info CSVs to the accepted baseline.

Always write observations, including failed datatype gates, before returning a
nonzero status. Legacy runtime support letters in CSV are not HTP delegation proof.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

EXP = Path(__file__).resolve().parents[3]
BASE = EXP / '.local/qairt-2.49.40-cache-aligned-v6-run'


def parse_csv(path):
    ios = {'input': {}, 'output': {}}
    operators = Counter()
    mode = None
    with path.open(newline='') as stream:
        for row in csv.reader(stream):
            if not row:
                continue
            if row[0] == 'Input Name':
                mode = 'input'
            elif row[0] == 'Output Name':
                mode = 'output'
            elif len(row) >= 4 and mode and not row[0].startswith('Total '):
                ios[mode][row[0]] = {'dimensions': row[1], 'datatype': row[2], 'encoding': row[3]}
            elif mode and row[0].startswith('Total '):
                mode = None
            elif len(row) >= 3 and row[0].isdigit():
                operators[row[2]] += 1
    return {'io': ios, 'operators': dict(sorted(operators.items())), 'operator_count': sum(operators.values())}


def compare(ar, path):
    old = parse_csv(BASE / f'ar{ar}.csv')
    new = parse_csv(path)
    selected = {f'past_value_{i}_h0_{suffix}' for i in (4, 9, 14) for suffix in ('in', 'out')}
    issues = []
    changes = []
    for role in ('input', 'output'):
        before, after = old['io'][role], new['io'][role]
        if set(before) != set(after):
            issues.append(f'{role} names changed')
        for name in before.keys() & after.keys():
            if name in selected:
                if after[name]['datatype'] != 'Float_16':
                    issues.append(f'{name}: wanted Float_16, observed {after[name]["datatype"]}')
                if before[name]['dimensions'] != after[name]['dimensions']:
                    issues.append(f'{name}: dimensions changed')
                changes.append({'name': name, 'role': role, 'before': before[name], 'after': after[name]})
            elif before[name] != after[name]:
                issues.append(f'unselected interface changed: {name}')
    return {'ar': ar, 'csv_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'baseline_csv_sha256': hashlib.sha256((BASE / f'ar{ar}.csv').read_bytes()).hexdigest(),
            'issues': issues, 'datatype_scope_passed': not issues,
            'selected_cache_interfaces': sorted(changes, key=lambda x: x['name']),
            'baseline_operator_counts': old['operators'], 'candidate_operator_counts': new['operators'],
            'convert_count_delta': new['operators'].get('Convert', 0) - old['operators'].get('Convert', 0),
            'baseline_operator_count': old['operator_count'], 'candidate_operator_count': new['operator_count'],
            'candidate_io': new['io'], 'full_htp_delegation_proven': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--ar', type=int, choices=(1, 128), required=True)
    p.add_argument('--csv', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = compare(args.ar, args.csv)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'ar': args.ar, 'datatype_scope_passed': result['datatype_scope_passed'],
                      'issues': result['issues'], 'convert_count_delta': result['convert_count_delta']}))
    raise SystemExit(0 if result['datatype_scope_passed'] else 1)
