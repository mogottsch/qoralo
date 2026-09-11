#!/usr/bin/env python3
"""Labelled minimal extracts; full Samsung dumps remain private and hash-bound."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def extract(battery, thermal):
    core = {}
    numeric = {'level', 'scale', 'voltage', 'temperature', 'status', 'health'}
    boolean = {'AC powered', 'USB powered', 'Wireless powered', 'present'}
    active = False
    for line in battery.splitlines():
        if not active:
            if line.strip() == 'Current Battery Service state:':
                active = True
            continue
        if not line.strip() or not line.startswith(' '):
            break
        match = re.fullmatch(r'  ([A-Za-z ]+):\s*(-?\d+|true|false)\s*', line)
        if not match:
            continue
        key, value = match.groups()
        if key in core:
            continue
        if key in numeric and re.fullmatch(r'-?\d+', value):
            core[key] = int(value)
        elif key in boolean and value in ('true', 'false'):
            core[key] = value == 'true'
    status = re.search(r'^\s*Thermal Status:\s*(\d+)\s*$', thermal, re.MULTILINE)
    return {'battery_core': core, 'thermal_status': int(status.group(1)) if status else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--battery', type=Path, required=True)
    parser.add_argument('--thermal', type=Path, required=True)
    parser.add_argument('--battery-exit', type=int, required=True)
    parser.add_argument('--thermal-exit', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    battery, thermal = args.battery.read_bytes(), args.thermal.read_bytes()
    data = extract(battery.decode(errors='replace') if args.battery_exit == 0 else '',
                   thermal.decode(errors='replace') if args.thermal_exit == 0 else '')
    data.update({'classification': 'labelled_core_extract_NOT_raw_full_telemetry',
                 'private_originals': {'battery_sha256': hashlib.sha256(battery).hexdigest(), 'thermal_sha256': hashlib.sha256(thermal).hexdigest()},
                 'collection_exit_codes': {'battery': args.battery_exit, 'thermal': args.thermal_exit},
                 'battery_temperature_unit': 'tenths_degree_C_as_dumpsys',
                 'limitations': 'Only allowlisted numeric/boolean battery fields and aggregate thermal status. Full originals remain private; no learned sleep/charging history is copied. Missing fields/failed collection are not zero.'})
    with args.output.open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True); stream.write('\n')


if __name__ == '__main__':
    main()
