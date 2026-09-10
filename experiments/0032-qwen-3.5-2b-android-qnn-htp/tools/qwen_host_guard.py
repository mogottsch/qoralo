#!/usr/bin/env python3
"""Small host-only process supervisor. No automatic retry or phone access."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import time


def supervise(command, directory: Path, timeout: float, env=None, grace=20.0) -> dict:
    """Directory must belong to the caller; logs are exclusively created.

The wall deadline is enforced outside native QNN calls. TERM gets a bounded
checkpoint grace, then the entire owned process group is killed and reaped.
A STOP file or sustained actual resource pressure releases RAM, never SIGSTOP.
"""
    if any(os.path.lexists(directory / name) for name in ('stdout.log', 'stderr.log', 'resources.jsonl', 'pid.txt', 'supervisor.json')):
        raise FileExistsError('Supervisor evidence paths must be fresh')
    reason = None
    process = None
    code = None
    failure = None
    started = time.monotonic()
    old_handlers = {}

    def stop(signum, frame):
        nonlocal reason
        reason = f"supervisor_signal_{signum}"

    for sig in (signal.SIGINT, signal.SIGTERM):
        old_handlers[sig] = signal.signal(sig, stop)
    try:
        with (directory / 'stdout.log').open('xb') as stdout, (directory / 'stderr.log').open('xb') as stderr, (directory / 'resources.jsonl').open('x') as resources:
            process = subprocess.Popen(command, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            (directory / 'pid.txt').write_text(str(process.pid) + '\n')
            next_sample = 0.0
            low_samples = psi_samples = 0
            while process.poll() is None:
                now = time.monotonic()
                if now - started >= timeout:
                    reason = 'host_timeout'
                if (directory / 'STOP').exists():
                    reason = 'coordinator_requested_stop'
                if now >= next_sample:
                    mem = {s.split(':')[0]: int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
                    pressures = {k: Path('/proc/pressure/' + k).read_text() for k in ('memory', 'io')}
                    record = {'time_ns': time.time_ns(), 'available_kib': mem['MemAvailable'], 'swap_free_kib': mem['SwapFree'], 'pressure': pressures}
                    try:
                        record['process_status'] = Path(f'/proc/{process.pid}/status').read_text()
                    except FileNotFoundError:
                        pass
                    resources.write(json.dumps(record) + '\n'); resources.flush()
                    low_samples = low_samples + 1 if mem['MemAvailable'] < 1048576 else 0
                    full = {k: float(v.splitlines()[1].split('avg10=')[1].split()[0]) for k, v in pressures.items()}
                    psi_samples = psi_samples + 1 if full['memory'] > 20 or full['io'] > 50 else 0
                    if low_samples >= 3 or (mem['MemAvailable'] < 2097152 and mem['SwapFree'] < 2097152) or psi_samples >= 6:
                        reason = 'resource_pressure'
                    next_sample = now + 10
                if reason:
                    break
                time.sleep(min(0.2, max(0.01, timeout - (now - started))))
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=grace)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            code = process.wait()
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error)}
        reason = 'supervisor_error'
        code = -1
    finally:
        if process is not None:
            # No orphan descendants, even if the leader exited before its children.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        for sig, previous in old_handlers.items():
            signal.signal(sig, previous)
    result = {'exit_code': code, 'reason': reason or 'process_exit', 'child_pid': None if process is None else process.pid, 'child_reaped': process is not None, 'timeout_seconds': timeout, 'termination_grace_seconds': grace, 'elapsed_seconds': time.monotonic() - started, 'automatic_retry': False, 'error': failure}
    (directory / 'supervisor.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
