#!/usr/bin/env python3
"""Pull app-written WAVs with binary-safe Windows adb after exact gated readiness."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "experiments/0008-sherpa-onnx-android-tts-benchmark/host_runner/runner.py"
ADB = Path("/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe")
spec = importlib.util.spec_from_file_location("historic_runner", RUNNER)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--campaign-id", required=True)
    args = ap.parse_args()
    result = json.loads(args.result.read_text())
    runs = result.get("runs")
    if not isinstance(runs, list) or not runs:
        raise SystemExit("no successful runs to pull")
    if not ADB.is_file():
        raise SystemExit("exact Windows adb missing")
    commands = module.SubprocessCommands()
    runner = module.DeviceRunner(commands, lock_path=ROOT / "artifacts/locks/phone.lock", artifact_dir=args.output.parent)
    env = dict(os.environ, ADB_LIBUSB="1")
    with runner.safe_session() as device:
        serial = device["serial"]
        args.output.mkdir(parents=True, exist_ok=False)
        for row in runs:
            name = row["wav_path"]
            expected = row["wav_sha256"]
            remote = f"/sdcard/Android/data/dev.moket.ttsbench/files/results/{args.campaign_id}/{name}"
            proc = subprocess.run([str(ADB), "-s", serial, "exec-out", "cat", remote], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, close_fds=True, check=False)
            if proc.returncode != 0:
                raise SystemExit(f"binary pull failed for {name}: {proc.stderr.decode(errors='replace')}")
            observed = hashlib.sha256(proc.stdout).hexdigest()
            if observed != expected:
                raise SystemExit(f"binary pull hash mismatch for {name}: {observed}")
            (args.output / name).write_bytes(proc.stdout)
        print(f"pulled {len(runs)} verified WAVs from {serial}")


if __name__ == "__main__":
    main()
