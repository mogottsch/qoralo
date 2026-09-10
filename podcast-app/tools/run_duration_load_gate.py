#!/usr/bin/env python3
"""Plan-only by default; one separately approved duration LOAD-ONLY phone attempt."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess

from prepare_wiring_gate import PROJECT, digest
from prepare_duration_load_gate import CONTRACT_SHA
from run_wiring_gate import APP, TEST_APP, Device, DeviceSettings, stop_child


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--approved-candidate-sha256")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="R5CW81PR8SY")
    args = parser.parse_args()
    value = json.loads(args.candidate.read_text())
    if not re.fullmatch(r"duration-[a-z0-9-]{1,64}", args.run_id):
        raise ValueError("unsafe diagnostic run ID")
    if value.get("sourceDirty") or value.get("kind") != "duration-load-only" or value["contractSha256"] != CONTRACT_SHA:
        raise ValueError("unreviewable diagnostic candidate")
    pinned = json.loads((PROJECT / "app/src/debug/assets/duration-load/contract.json").read_text())
    if value["contract"] != pinned:
        raise ValueError("diagnostic contract changed")
    for kind in ("app", "test"):
        item = value[kind]
        path = Path(item["path"])
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise ValueError("diagnostic APK changed since preflight")
    if not args.execute:
        print(json.dumps({"mode": "plan_only", "kind": "duration-load-only", "adbUsed": False, "sessionRunCalls": 0, "gemmaRequests": 0, "hostTimeoutSeconds": 150}))
        return
    if os.environ.get("PODCAST_PHONE_PRIORITY") != "approved" or args.approved_candidate_sha256 != digest(args.candidate):
        raise SystemExit("separate Pi phone slot and exact candidate approval required")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "candidate.json").write_text(json.dumps(value, indent=2))
    lock = (PROJECT.parent / "artifacts/locks/phone.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    device = Device(args.adb, args.serial, args.output)
    settings = DeviceSettings(device.shell)
    identity_ok = False
    launched = False
    logs = None
    cleanup = {"errors": [], "settingsErrors": [], "scratchCreated": False, "packagesRetained": True}
    def interrupted(signum, frame):
        raise InterruptedError(f"signal {signum}; cleanup only, no retry")
    signal.signal(signal.SIGINT, interrupted); signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.serial != "R5CW81PR8SY" or device.shell("getprop ro.product.model").strip() != "SM-S918B" or device.shell("getprop ro.soc.model").strip() != "SM8550":
            raise ValueError("unexpected device")
        identity_ok = True
        (args.output / "settings-before.json").write_text(json.dumps(settings.capture(), indent=2))
        device.shell("dumpsys battery; dumpsys thermalservice", timeout=30)
        # Reuse installed data only. No Gemma or new model staging is allowed in this gate.
        observed = device.shell(f"run-as {APP} sha256sum no_backup/model-packs/supertonic-3/current/manifest.json")
        if observed.split()[0] != pinned["manifestSha256"]:
            raise ValueError("installed Supertonic pack mismatch or absent")
        device.run(["install", "-r", "-t", value["app"]["path"]], timeout=180)
        device.run(["install", "-r", "-t", value["test"]["path"]], timeout=180)
        with (args.output / "logcat.txt").open("wb") as out, (args.output / "logcat.stderr").open("wb") as err:
            logs = subprocess.Popen(device.prefix + ["logcat", "-v", "threadtime", "-T", "1"], stdout=out, stderr=err, start_new_session=True, close_fds=True)
        command = ("am instrument -w -r -e class dev.vibevoice.podcast.wiring.DurationLoadOnlyTest"
                   f" -e durationLoadApproved {CONTRACT_SHA} -e durationLoadRunId {args.run_id}"
                   f" -e appApkSha256 {value['app']['sha256']} -e testApkSha256 {value['test']['sha256']}"
                   f" {TEST_APP}/androidx.test.runner.AndroidJUnitRunner")
        launched = True
        output = device.shell(command, timeout=150)
        (args.output / "controller-result.json").write_text(json.dumps({"instrumentationCompleted": "OK (" in output and "FAILURES!!!" not in output,
            "nativeOutcome": "inspect service-result.json in archive; test completion does not mean QNN load succeeded", "neuralInference": False, "gemmaRequests": 0}))
        if "OK (" not in output or "FAILURES!!!" in output:
            raise RuntimeError("diagnostic instrumentation failed; preserve raw evidence")
    except BaseException as error:
        (args.output / "controller-failure.json").write_text(json.dumps({"error": repr(error), "launched": launched}))
        raise
    finally:
        device.enforce_quota = False
        signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if launched:
            for name, action in [
                ("stop-app", lambda: device.shell(f"am force-stop {APP}; am force-stop {TEST_APP}")),
                ("pull", lambda: device.run(["exec-out", "run-as", APP, "tar", "-cf", "-", f"files/duration-load/{args.run_id}"], timeout=120, binary=True)),
                ("pid-absence", lambda: device.shell(f"pidof {APP} {APP}:generation {TEST_APP}", check=False)),
            ]:
                try:
                    result = action()
                    if name == "pull":
                        result.rename(args.output / "private-evidence.tar")
                    elif name == "pid-absence":
                        cleanup["pidStdout"] = result
                        # Exact exit/stdout/stderr remain in the command record for review.
                        last = args.output / f"{device.counter:03d}-command"
                        absent = last.with_suffix(".exit").read_text() == "1" and not result.strip() and not last.with_suffix(".stderr").read_text().strip()
                        cleanup["appGenerationTestPidsAbsent"] = absent
                        if not absent:
                            raise RuntimeError("process still present or absence unproven; no additional action")
                except Exception as error:
                    cleanup["errors"].append({"phase": name, "error": repr(error)})
        if identity_ok:
            try:
                device.shell("dumpsys battery; dumpsys thermalservice", check=False)
            except Exception as error:
                cleanup["errors"].append({"phase": "conditions-after", "error": repr(error)})
        cleanup["settingsErrors"] = settings.restore()  # no mutations in this gate
        if logs is not None:
            try:
                stop_child(logs)
            except Exception as error:
                cleanup["errors"].append({"phase": "logcat-reap", "error": repr(error)})
        (args.output / "cleanup.json").write_text(json.dumps(cleanup, indent=2))
        fcntl.flock(lock, fcntl.LOCK_UN); lock.close()
        if cleanup["errors"] or cleanup["settingsErrors"]:
            raise RuntimeError("cleanup incomplete; see retained cleanup.json")


if __name__ == "__main__":
    main()
