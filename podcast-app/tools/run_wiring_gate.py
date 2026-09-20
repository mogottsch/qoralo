#!/usr/bin/env python3
"""Opt-in, one-slot physical controller. Never invoke without Pi's phone assignment.

Default mode prints the plan only. Lock covers ALL ADB, restoration, capture and cleanup.
No native request retries; failed/partial results are retained, never overwritten.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time

from prepare_wiring_gate import CONTRACT_SHA, PROJECT, digest

APP = "dev.qoralo.podcast.internal"
TEST_APP = APP + ".test"
ANIMATIONS = ("window_animation_scale", "transition_animation_scale", "animator_duration_scale")


class DeviceSettings:
    def __init__(self, shell):
        self.shell = shell
        self.original = {}
        self.changed = []

    def capture(self):
        for key in ANIMATIONS:
            self.original[key] = self.shell(f"settings get global {key}").strip()
        return dict(self.original)

    def disable_animations(self):
        if len(self.original) != len(ANIMATIONS):
            raise ValueError("settings not fully captured")
        for key in ANIMATIONS:
            self.changed.append(key)  # record BEFORE mutation so partial failures restore too
            self.shell(f"settings put global {key} 0")

    def restore(self):
        failures = []
        for key in reversed(self.changed):
            original = self.original[key]
            command = f"settings delete global {key}" if original == "null" else f"settings put global {key} {shlex.quote(original)}"
            try:
                self.shell(command)
                if self.shell(f"settings get global {key}").strip() != original:
                    raise ValueError("read-back differs")
            except Exception as error:
                failures.append({"key": key, "error": str(error)})
        return failures


class Device:
    def __init__(self, adb, serial, output):
        self.prefix = [adb, "-s", serial]
        self.output = output
        self.counter = 0
        self.enforce_quota = True

    def run(self, arguments, timeout=30, check=True, binary=False):
        self.counter += 1
        base = self.output / f"{self.counter:03d}-command"
        command = self.prefix + arguments
        base.with_suffix(".json").write_text(json.dumps({"argv": command, "timeoutSeconds": timeout}) + "\n")
        with base.with_suffix(".stdout").open("wb") as out, base.with_suffix(".stderr").open("wb") as err:
            process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True, close_fds=True)
            try:
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(command, timeout)
                    if self.enforce_quota and sum(p.stat().st_size for p in self.output.iterdir() if p.is_file()) > 268435456:
                        raise RuntimeError("Host evidence limit exceeded; preserving raw files")
                    time.sleep(0.2)
                code = process.returncode
            except BaseException:
                stop_child(process)
                base.with_suffix(".interrupted").write_text("host timeout/signal; command child reaped; no retry\n")
                raise
        base.with_suffix(".exit").write_text(str(code))
        if code and check:
            raise RuntimeError(f"ADB command failed ({code}); raw files: {base}")
        if binary:
            return base.with_suffix(".stdout")
        return base.with_suffix(".stdout").read_text(errors="replace")

    def shell(self, command, **kwargs):
        return self.run(["shell", command], **kwargs)


def stop_child(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def check_candidate(candidate):
    if candidate.get("sourceDirty"):
        raise ValueError("candidate must be built/preflighted from a committed source tree")
    pinned_contract = json.loads((PROJECT / "app/src/debug/assets/wiring/contract.json").read_text())
    if candidate["contractSha256"] != CONTRACT_SHA or candidate["contract"] != pinned_contract:
        raise ValueError("unapproved wiring contract")
    if set(candidate["modelPacks"]) != {"gemma-4-e2b", "supertonic-3"}:
        raise ValueError("unexpected model pack routes")
    for key in ("app", "test"):
        item = candidate[key]
        path = Path(item["path"])
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise ValueError(f"{key} APK changed since exact-byte preflight")
    for entry in candidate["modelPacks"].values():
        if digest(Path(entry["root"]) / "manifest.json") != entry["manifestSha256"]:
            raise ValueError("prepared pack manifest changed")


def stage_pack(device, route, entry, remote):
    destination = f"no_backup/model-packs/{route}/current"
    observed = device.shell(f"run-as {APP} sh -c {shlex.quote(f'if test -f {destination}/manifest.json; then sha256sum {destination}/manifest.json; else echo MISSING; fi')}")
    if "MISSING" in observed:
        incoming = f"{remote}/{route}"
        device.run(["push", entry["root"], incoming], timeout=600)
        device.shell(f"chmod -R a+rX {shlex.quote(incoming)}")
        staged = f"no_backup/model-packs/{route}/.incoming-{Path(remote).name}"
        script = f"set -e; mkdir -p no_backup/model-packs/{route}; test ! -e {destination}; test ! -e {staged}; cp -R {incoming} {staged}; test ! -e {destination}; mv {staged} {destination}"
        device.shell(f"run-as {APP} sh -c {shlex.quote(script)}", timeout=600)
        observed = device.shell(f"run-as {APP} sha256sum {destination}/manifest.json")
    if observed.split()[0] != entry["manifestSha256"]:
        raise ValueError("installed model manifest mismatch; existing data not replaced")
    # The same pinned full-pack verifier runs once in :generation before either model loads.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approved-candidate-sha256", help="exact candidate digest explicitly approved at review")
    parser.add_argument("--suite", choices=("wiring", "ui"), default="wiring")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="R5CW81PR8SY")
    args = parser.parse_args()
    candidate = json.loads(args.candidate.read_text())
    if not re.fullmatch(r"wiring-[a-z0-9-]{1,64}", args.run_id):
        raise ValueError("unsafe run ID")
    check_candidate(candidate)
    if not args.execute:
        print(json.dumps({"mode": "plan_only", "suite": args.suite, "runId": args.run_id,
                          "timeLimitSeconds": 1260 if args.suite == "wiring" else 600, "adbUsed": False}))
        return
    if os.environ.get("PODCAST_PHONE_PRIORITY") != "approved":
        raise SystemExit("explicit Pi priority + PODCAST_PHONE_PRIORITY=approved required")
    if args.approved_candidate_sha256 != digest(args.candidate):
        raise SystemExit("exact reviewed candidate SHA-256 required before ADB")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "candidate.json").write_text(json.dumps(candidate, indent=2))
    lock = (PROJECT.parent / "artifacts/locks/phone.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    device = Device(args.adb, args.serial, args.output)
    settings = DeviceSettings(device.shell)
    remote = f"/data/local/tmp/podcast-wiring-{args.run_id}"
    logcat = None
    cleanup = {"settingsErrors": [], "errors": [], "appRetained": True, "testApkRetained": True}
    launched = False
    identity_verified = False
    remote_created = False
    def interrupted(signum, frame):
        raise InterruptedError(f"signal {signum}; preserving evidence and restoring settings")
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.serial != "R5CW81PR8SY" or device.shell("getprop ro.product.model").strip() != "SM-S918B" or device.shell("getprop ro.soc.model").strip() != "SM8550":
            raise ValueError("wrong phone identity")
        identity_verified = True
        (args.output / "settings-before.json").write_text(json.dumps(settings.capture(), indent=2))
        device.shell("getprop ro.build.fingerprint; df -k /data; dumpsys battery; dumpsys thermalservice", timeout=30)
        device.run(["install", "-r", "-t", candidate["app"]["path"]], timeout=180)
        device.run(["install", "-r", "-t", candidate["test"]["path"]], timeout=180)
        if args.suite == "wiring":
            device.shell(f"mkdir {remote}")
            remote_created = True
            for route, entry in candidate["modelPacks"].items():
                stage_pack(device, route, entry, remote)
        else:
            settings.disable_animations()
        with (args.output / "logcat.txt").open("wb") as out, (args.output / "logcat.stderr").open("wb") as err:
            logcat = subprocess.Popen(device.prefix + ["logcat", "-v", "threadtime", "-T", "1"], stdout=out, stderr=err, close_fds=True, start_new_session=True)
        test_class = "dev.qoralo.podcast.wiring.RealRuntimeWiringTest" if args.suite == "wiring" else "dev.qoralo.podcast.ui.ScreenSemanticsTest"
        command = f"am instrument -w -r -e class {test_class}"
        if args.suite == "wiring":
            command += f" -e wiringApproved {CONTRACT_SHA} -e wiringRunId {args.run_id} -e appApkSha256 {candidate['app']['sha256']} -e testApkSha256 {candidate['test']['sha256']}"
        else:
            command += " -e timeout_msec 60000"
        command += f" {TEST_APP}/androidx.test.runner.AndroidJUnitRunner"
        launched = True
        output = device.shell(command, timeout=1260 if args.suite == "wiring" else 600)
        if "FAILURES!!!" in output or "OK (" not in output:
            raise RuntimeError("instrumentation did not finish successfully; raw failure retained")
        device.run(["exec-out", "screencap", "-p"], binary=True)
        (args.output / "controller-result.json").write_text(json.dumps({"status": "instrumentation_completed", "suite": args.suite, "productE2e": False, "physicalProviderReview": "pending"}))
    except BaseException as error:
        (args.output / "controller-failure.json").write_text(json.dumps({"error": repr(error), "launched": launched}))
        raise
    finally:
        # Do not let a full evidence quota or a repeated termination signal skip restoration.
        device.enforce_quota = False
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        # Bound every cleanup call too; preserve errors rather than masking a failed restoration.
        for name, operation in [
            ("stop-app", lambda: device.shell(f"am force-stop {APP}; am force-stop {TEST_APP}") if launched else None),
            ("pull-evidence", lambda: device.run(["exec-out", "run-as", APP, "tar", "-cf", "-", f"files/wiring/{args.run_id}"], timeout=120, binary=True) if launched and args.suite == "wiring" else None),
            ("conditions-after", lambda: device.shell("dumpsys battery; dumpsys thermalservice", check=False) if identity_verified else None),
        ]:
            try:
                result = operation()
                if name == "pull-evidence" and result is not None:
                    result.rename(args.output / "private-evidence.tar")
            except Exception as error:
                cleanup["errors"].append({"phase": name, "error": repr(error)})
        cleanup["settingsErrors"] = settings.restore()
        try:
            if remote_created:
                device.shell(f"rm -rf {remote}; test ! -e {remote}")
        except Exception as error:
            cleanup["errors"].append({"phase": "remote-cleanup", "error": repr(error)})
        if logcat is not None:
            try:
                stop_child(logcat)
            except Exception as error:
                cleanup["errors"].append({"phase": "logcat-reap", "error": repr(error)})
        (args.output / "cleanup.json").write_text(json.dumps(cleanup, indent=2))
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
        if cleanup["errors"] or cleanup["settingsErrors"]:
            raise RuntimeError(f"cleanup incomplete; inspect {args.output / 'cleanup.json'}")


if __name__ == "__main__":
    main()
