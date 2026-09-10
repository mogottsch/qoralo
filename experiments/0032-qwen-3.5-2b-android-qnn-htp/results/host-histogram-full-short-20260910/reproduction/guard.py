"""Local host-step supervisor; no device access, no automatic restarts."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

out = Path(sys.argv[1])
command = sys.argv[2:]
out.mkdir(parents=True, exist_ok=False)
(out / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
stop_reason = None

def stop(signum, frame):
    global stop_reason
    stop_reason = f'supervisor_signal_{signum}'

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def snapshot():
    mem = {s.split(':')[0]: int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
    pressure = {name: Path(f'/proc/pressure/{name}').read_text() for name in ('memory', 'io')}
    return {'time_ns': time.time_ns(), 'available_kib': mem['MemAvailable'], 'swap_free_kib': mem['SwapFree'], 'pressure': pressure}

start = time.monotonic()
with (out / 'stdout.log').open('wb') as stdout, (out / 'stderr.log').open('wb') as stderr, (out / 'resources.jsonl').open('w') as resources:
    process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
    (out / 'pid.txt').write_text(str(process.pid) + '\n')
    low_count = 0
    io_count = 0
    memory_count = 0
    print(f'START {out.name} pid={process.pid}', flush=True)
    while process.poll() is None:
        record = snapshot()
        try:
            record['process_status'] = Path(f'/proc/{process.pid}/status').read_text()
            record['process_io'] = Path(f'/proc/{process.pid}/io').read_text()
        except FileNotFoundError:
            pass
        resources.write(json.dumps(record) + '\n'); resources.flush()
        low_count = low_count + 1 if record['available_kib'] < 1048576 else 0
        io_full = float(record['pressure']['io'].splitlines()[1].split('avg10=')[1].split()[0])
        io_count = io_count + 1 if io_full > 50 else 0
        memory_full = float(record['pressure']['memory'].splitlines()[1].split('avg10=')[1].split()[0])
        memory_count = memory_count + 1 if memory_full > 20 else 0
        if low_count >= 3 or (record['available_kib'] < 2097152 and record['swap_free_kib'] < 2097152):
            stop_reason = 'memory_pressure_releasing_resources'
        if memory_count >= 6:
            stop_reason = 'sustained_memory_pressure_releasing_resources'
        if io_count >= 6:
            stop_reason = 'sustained_io_pressure_releasing_resources'
        if time.monotonic() - start >= 7200:
            stop_reason = 'host_timeout_7200_seconds'
        if (out.parent / 'STOP').exists():
            stop_reason = 'coordinator_requested_stop'
        if stop_reason:
            print(f'STOP {out.name} {stop_reason}', flush=True)
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            break
        time.sleep(10)
    code = process.wait()
result = {'exit_code': code, 'termination_reason': stop_reason or 'process_exit', 'elapsed_seconds': time.monotonic() - start, 'child_pid': process.pid, 'child_reaped': True, 'timeout_seconds': 7200}
(out / 'exit.json').write_text(json.dumps(result, indent=2) + '\n')
print(f'COMPLETE {out.name} ' + json.dumps(result), flush=True)
sys.exit(0 if code == 0 and stop_reason is None else 1)
