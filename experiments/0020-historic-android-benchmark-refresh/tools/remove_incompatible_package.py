#!/usr/bin/env python3
"""Remove only the historical runner package after exact gated readiness."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "experiments/0008-sherpa-onnx-android-tts-benchmark/host_runner/runner.py"
spec = importlib.util.spec_from_file_location("historic_runner", RUNNER)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

commands = module.SubprocessCommands()
runner = module.DeviceRunner(commands, lock_path=ROOT / "artifacts/locks/phone.lock", artifact_dir=Path(__file__).resolve().parents[1] / ".local/device-runs")
with runner.safe_session() as device:
    serial = device["serial"]
    package = "dev.moket.ttsbench"
    present = commands.run(["adb", "-s", serial, "shell", "pm", "path", package], timeout=15)
    if present.returncode != 0 or not present.stdout.strip().startswith("package:"):
        raise SystemExit("historical package not installed; refuse ambiguous cleanup")
    removed = commands.run(["adb", "-s", serial, "uninstall", package], timeout=120)
    if removed.returncode != 0 or "Success" not in removed.stdout:
        raise SystemExit("failed to remove incompatible historical package")
    print(f"removed {package} from exact device {serial}")
