#!/usr/bin/env python3
"""Restage a verified inventory as app-owned scoped-storage files under phone.lock."""
from __future__ import annotations
import argparse
import importlib.util
import shlex
import sys
import uuid
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "experiments/0008-sherpa-onnx-android-tts-benchmark/host_runner/runner.py"
spec = importlib.util.spec_from_file_location("historic_runner", RUNNER)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def must(result, what):
    if result.returncode != 0:
        raise SystemExit(f"{what} failed: {result.stderr.strip()}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--model-dir", type=Path, required=True)
    args = ap.parse_args()
    files = module.load_inventory(args.inventory, args.model_dir)
    commands = module.SubprocessCommands()
    runner = module.DeviceRunner(commands, lock_path=ROOT / "artifacts/locks/phone.lock", artifact_dir=Path(__file__).resolve().parents[1] / ".local/device-runs")
    package = "dev.moket.ttsbench"
    with runner.safe_session() as device:
        serial = device["serial"]
        remote_stage = f"/data/local/tmp/experiment-0020-app-owned-{uuid.uuid4().hex}"
        must(commands.run(["adb", "-s", serial, "shell", "mkdir", "-p", remote_stage]), "mkdir remote stage")
        try:
            for item in files:
                source = item.source.resolve()
                temp = f"{remote_stage}/{uuid.uuid4().hex}"
                must(commands.run(["adb", "-s", serial, "push", str(source), temp], timeout=600), f"push {item.relative_path}")
                must(commands.run(["adb", "-s", serial, "shell", "chmod", "0644", temp]), f"chmod {item.relative_path}")
                observed = must(commands.run(["adb", "-s", serial, "shell", "sha256sum", temp]), f"shell hash {item.relative_path}").stdout.split()
                if not observed or observed[0].lower() != item.sha256:
                    raise SystemExit(f"shell hash mismatch: {item.relative_path}")
                destination = f"/sdcard/Android/data/{package}/files/{item.relative_path}"
                parent = str(PurePosixPath(destination).parent)
                incoming = f"{destination}.incoming-{uuid.uuid4().hex}"
                command = f"mkdir -p {shlex.quote(parent)} && cat {shlex.quote(temp)} > {shlex.quote(incoming)} && mv {shlex.quote(incoming)} {shlex.quote(destination)} && sha256sum {shlex.quote(destination)}"
                app = must(commands.run(["adb", "-s", serial, "shell", "run-as", package, "sh", "-c", command], timeout=600), f"app-owned copy {item.relative_path}")
                app_hash = app.stdout.split()
                if not app_hash or app_hash[0].lower() != item.sha256:
                    raise SystemExit(f"app-owned hash mismatch: {item.relative_path}")
        finally:
            commands.run(["adb", "-s", serial, "shell", "rm", "-rf", remote_stage], timeout=120)
        print(f"restaged {len(files)} app-owned files on {serial}; temp cleanup requested")


if __name__ == "__main__":
    main()
