#!/usr/bin/env python3
"""Remove all experiment-0020 package/input/output state under exact gates and lock."""
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
package = "dev.moket.ttsbench"
with runner.safe_session() as device:
    serial = device["serial"]
    def run(*args, timeout=120):
        result = commands.run(["adb", "-s", serial, *args], timeout=timeout)
        if result.returncode != 0:
            raise SystemExit(f"cleanup command failed: {args}")
        return result
    run("shell", "am", "force-stop", package)
    internal = commands.run(["adb", "-s", serial, "shell", f"run-as {package} sh -c 'rm -rf files/* cache/*'"], timeout=120)
    if internal.returncode != 0:
        raise SystemExit("app-internal cleanup failed")
    run("shell", f"rm -rf /sdcard/Android/data/{package}")
    removed = run("uninstall", package)
    if "Success" not in removed.stdout:
        raise SystemExit("package uninstall did not report success")
    package_path = commands.run(["adb", "-s", serial, "shell", "pm", "path", package], timeout=15)
    external = commands.run(["adb", "-s", serial, "shell", f"test ! -e /sdcard/Android/data/{package}"], timeout=15)
    if package_path.returncode == 0 or external.returncode != 0:
        raise SystemExit("cleanup absence verification failed")
    print(f"cleanup verified on {serial}: package absent, external root absent")
