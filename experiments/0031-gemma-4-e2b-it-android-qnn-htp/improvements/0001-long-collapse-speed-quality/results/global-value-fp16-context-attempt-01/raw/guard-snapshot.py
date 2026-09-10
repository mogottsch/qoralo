#!/usr/bin/env python3
"""Run one host command at low priority, retaining raw logs even on pressure stop.

STOP in the run directory or TERM to this supervisor terminates/reaps only its
own process group. Swap is allowed. No automatic resume/retry; no phone access.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time


def sample():
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemAvailable', 'SwapFree', 'SwapTotal'):
            memory[key + '_kB'] = int(value.split()[0])
    pressures = {}
    for kind in ('memory', 'io'):
        for line in Path('/proc/pressure/' + kind).read_text().splitlines():
            parts = line.split()
            pressures[kind + '_' + parts[0] + '_avg10'] = float(parts[1].split('=')[1])
    return {'timestamp_ns': time.time_ns(), **memory, **pressures}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        parser.error('command required')
    run = args.run_dir.resolve()
    run.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.umask(0o077)
    requested_stop = []
    def stop_handler(signum, frame):
        requested_stop.append('supervisor_signal_' + str(signum))
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    (run / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    (run / 'supervisor.pid').write_text(str(os.getpid()) + '\n')
    start = time.monotonic()
    reason = None
    with (run / 'stdout.log').open('w') as out, (run / 'stderr.log').open('w') as err, (run / 'resources.jsonl').open('w') as telemetry:
        proc = subprocess.Popen(['nice', '-n', '15', 'ionice', '-c', '3', *command],
                                stdout=out, stderr=err, start_new_session=True)
        (run / 'child.pid').write_text(str(proc.pid) + '\n')
        pressure_count = 0
        while proc.poll() is None:
            obs = sample()
            telemetry.write(json.dumps(obs) + '\n')
            telemetry.flush()
            near_oom = obs['MemAvailable_kB'] + obs['SwapFree_kB'] < 3 * 1024**2
            severe_pressure = obs['memory_full_avg10'] > 40 or obs['io_full_avg10'] > 70
            pressure_count = pressure_count + 1 if severe_pressure else 0
            if requested_stop or (run / 'STOP').exists() or near_oom or pressure_count >= 4:
                reason = (requested_stop[0] if requested_stop else 'operator_STOP' if (run / 'STOP').exists()
                          else 'near_oom' if near_oom else 'sustained_pressure')
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                break
            time.sleep(10)
        code = proc.wait()
        # A stopped parent must not leave a native worker running.
        if reason:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    receipt = {'exit_code': code, 'stop_reason': reason, 'elapsed_seconds': time.monotonic() - start,
               'child_ru_maxrss_kB': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
               'automatic_retry': False, 'phone_access': False}
    (run / 'exit-code.txt').write_text(str(code) + '\n')
    (run / 'supervisor-result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return 0 if code == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
