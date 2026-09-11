#!/usr/bin/env python3
"""One owned Gemma full conversion, inside an externally bounded systemd cgroup.

Uses existing RAM/swap only. STOP, capacity pressure, disk growth or timeout stops
and reaps its own child. systemd KillMode=control-group covers remaining workers.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

GIB = 1024**3


def host_sample():
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, rest = line.split(':', 1)
        if key in ('MemAvailable', 'SwapFree', 'SwapTotal'):
            memory[key + '_bytes'] = int(rest.split()[0])*1024
    for kind in ('memory', 'io'):
        for line in (Path('/proc/pressure')/kind).read_text().splitlines():
            row = line.split()
            memory[kind + '_' + row[0] + '_avg10'] = float(row[1].split('=')[1])
    return memory


def capacity_ok(sample, ram, swap):
    return (sample['MemAvailable_bytes'] >= ram + 4*GIB
            and sample['SwapFree_bytes'] >= swap + 8*GIB
            and ram + swap >= 30*GIB)


def cgroup_path():
    line = next(x for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    return Path('/sys/fs/cgroup') / line[3:].lstrip('/')


def usage(root):
    # Count allocated bytes only under this fresh owned run, never old evidence.
    total = 0
    for p in root.rglob('*'):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_blocks*512
        except FileNotFoundError:
            # SDK temporary files may disappear between directory scan and stat.
            continue
    return total


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--ram-bytes', type=int, required=True)
    p.add_argument('--swap-bytes', type=int, required=True)
    p.add_argument('--seconds', type=int, default=1770)
    p.add_argument('command', nargs=argparse.REMAINDER)
    args = p.parse_args()
    root = args.root.resolve()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        p.error('command required')
    os.umask(0o077)
    cgroup = cgroup_path()
    def own_sample():
        d = {'time_ns': time.time_ns(), **host_sample()}
        for name in ('memory.current', 'memory.peak', 'memory.swap.current', 'memory.events', 'pids.current'):
            file = cgroup/name
            d[name] = file.read_text().strip() if file.exists() else None
        d['owned_allocated_bytes'] = usage(root)
        d['filesystem_free_bytes'] = os.statvfs(root).f_bavail*os.statvfs(root).f_frsize
        return d
    sample = own_sample()
    limits = {n: (cgroup/n).read_text().strip() for n in ('memory.high', 'memory.max', 'memory.swap.max', 'cpu.max')}
    preflight = {'sample': sample, 'limits': limits, 'requested_ram_bytes': args.ram_bytes,
                 'requested_swap_bytes': args.swap_bytes, 'capacity_ok': capacity_ok(sample, args.ram_bytes, args.swap_bytes)}
    (root/'guard-preflight.json').write_text(json.dumps(preflight, indent=2)+'\n')
    assert int(limits['memory.max']) == args.ram_bytes
    assert int(limits['memory.swap.max']) == args.swap_bytes
    assert preflight['capacity_ok'], 'Actual RAM/swap headroom no longer supports this launch'
    assert sample['filesystem_free_bytes'] >= 100*GIB
    (root/'child-command.json').write_text(json.dumps(command, indent=2)+'\n')
    requests = []
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda signum, frame: requests.append(str(signum)))
    started = time.monotonic()
    reason = None
    with (root/'child.stdout').open('w') as out, (root/'child.stderr').open('w') as err, (root/'resources.jsonl').open('w') as log:
        child = subprocess.Popen(command, stdout=out, stderr=err, close_fds=True)
        (root/'child.pid').write_text(str(child.pid)+'\n')
        bad = 0
        while True:
            sample = own_sample()
            log.write(json.dumps(sample)+'\n');log.flush()
            code = child.poll()
            if code is not None:
                break
            severe = sample['memory_full_avg10'] > 40 or sample['io_full_avg10'] > 85
            bad = bad + 1 if severe else 0
            if requests or (root/'STOP').exists():
                reason = 'operator_or_supervisor_stop'
            elif time.monotonic()-started > args.seconds:
                reason = 'wall_timeout'
            elif sample['MemAvailable_bytes'] < 2*GIB or sample['SwapFree_bytes'] < 8*GIB:
                reason = 'host_headroom_exhausted'
            elif sample['owned_allocated_bytes'] > 64*GIB or sample['filesystem_free_bytes'] < 64*GIB:
                reason = 'disk_bound'
            elif bad >= 8:
                reason = 'sustained_pressure'
            if reason:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait()
                break
            time.sleep(5)
        code = child.wait()
    result = {'exit_code': code, 'stop_reason': reason, 'elapsed_seconds': time.monotonic()-started,
              'final_sample': own_sample(), 'automatic_retry': False, 'phone_access': False,
              'remaining_worker_cleanup': 'systemd KillMode=control-group on service exit'}
    (root/'guard-result.json').write_text(json.dumps(result, indent=2)+'\n')
    return 0 if code == 0 and reason is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
