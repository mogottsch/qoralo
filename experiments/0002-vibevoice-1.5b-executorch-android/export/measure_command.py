#!/usr/bin/env python3
"""Run one reproducible benchmark command and sample its Linux process memory."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=0.05)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    return args


def status_kib(pid: int, field: str) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith(field + ":"):
                return int(line.split()[1])
    except (FileNotFoundError, ProcessLookupError):
        pass
    return None


def pss_kib(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
            if line.startswith("Pss:"):
                return int(line.split()[1])
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
    return None


def main() -> None:
    args = parse_args()
    for path in (args.output, args.stdout, args.stderr):
        path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    max_rss = 0
    max_hwm = 0
    max_pss = 0
    samples = 0
    with args.stdout.open("wb") as stdout, args.stderr.open("wb") as stderr:
        process = subprocess.Popen(args.command, stdout=stdout, stderr=stderr)
        while process.poll() is None:
            rss = status_kib(process.pid, "VmRSS")
            hwm = status_kib(process.pid, "VmHWM")
            pss = pss_kib(process.pid)
            max_rss = max(max_rss, rss or 0)
            max_hwm = max(max_hwm, hwm or 0)
            max_pss = max(max_pss, pss or 0)
            samples += 1
            time.sleep(args.interval)
        returncode = process.wait()
    result = {
        "schema_version": 1,
        "command": args.command,
        "returncode": returncode,
        "wall_seconds": time.perf_counter() - started,
        "sample_interval_seconds": args.interval,
        "samples": samples,
        "peak_rss_kib": max_rss,
        "peak_process_hwm_kib": max_hwm,
        "peak_observed_pss_kib": max_pss,
        "stdout": str(args.stdout),
        "stderr": str(args.stderr),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if returncode:
        raise SystemExit(returncode)


if __name__ == "__main__":
    main()
