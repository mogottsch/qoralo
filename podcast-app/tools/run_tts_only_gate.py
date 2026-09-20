#!/usr/bin/env python3
"""Plan-only by default; one separately approved TTS-only first-request attempt."""
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
CONTRACT_SHA = "5844320c0ce2442e16d2d837fc1239bf8e9da05ede672d1249f125d91fdf57ca"
from run_wiring_gate import APP, TEST_APP, Device, DeviceSettings, stop_child
from duration_phone_guard import PhoneGuard, close_inherited_fds, host_identity


def check_controller(args):
    if digest(Path(__file__)) != args.approved_tts_controller_sha256:
        raise ValueError("reviewed TTS controller changed under lock")


def core_conditions(raw):
    """Labelled derived whitelist; never publish Samsung sleep/charging histories."""
    battery, separator, thermal = raw.partition("PODCAST_THERMAL_SECTION")
    core = {}
    lines = battery.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "Current Battery Service state:"), None)
    if start is not None:
        for line in lines[start + 1:start + 33]:
            match = re.fullmatch(r"\s*(AC powered|USB powered|Wireless powered|status|health|present|level|scale|voltage|temperature):\s*(true|false|-?\d+)\s*", line)
            if match and match.group(1) not in core:
                core[match.group(1)] = match.group(2)
    samples = []
    if separator:
        for value, kind, status in re.findall(r"Temperature\{mValue=(-?\d+(?:\.\d+)?), mType=(-?\d+), mName=[^,{}]{1,128}, mStatus=(-?\d+)\}", thermal):
            samples.append({"value": float(value), "type": int(kind), "status": int(status)})
    return {"evidenceKind": "derived whitelisted current core battery and numeric thermal samples; not raw dumpsys", "battery": core,
            "thermalSamples": samples[:64], "unavailable": [] if core else ["recognized core battery fields absent"],
            "privacy": "full originals private; learned histories, timestamps, sensor names and unrelated fields excluded"}


def capture_conditions(device, output, label):
    private = output / ".private-conditions"
    private.mkdir(mode=0o700, exist_ok=True)
    counter = device.counter + 1
    destination = private / (label + ".stdout")
    error = None
    try:
        device.shell("dumpsys battery; printf '\\nPODCAST_THERMAL_SECTION\\n'; dumpsys thermalservice", timeout=30)
    except Exception as failure:
        error = repr(failure)
    finally:
        raw = output / f"{counter:03d}-command.stdout"
        if raw.exists():
            raw.rename(destination); destination.chmod(0o600)
    record = core_conditions(destination.read_text(errors="replace")) if destination.exists() else {"evidenceKind": "core condition extract unavailable"}
    record.update(sourceSha256=digest(destination) if destination.exists() else None, captureError=error)
    (output / f"conditions-core-{label}.json").write_text(json.dumps(record, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--approved-candidate-sha256")
    parser.add_argument("--approved-host-guard-sha256")
    parser.add_argument("--approved-tts-controller-sha256")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="R5CW81PR8SY")
    args = parser.parse_args()
    value = json.loads(args.candidate.read_text())
    if not re.fullmatch(r"tts-only-[a-z0-9-]{1,64}", args.run_id):
        raise ValueError("unsafe diagnostic run ID")
    if value.get("sourceDirty") or value.get("kind") != "tts-only" or value["contractSha256"] != CONTRACT_SHA:
        raise ValueError("unreviewable diagnostic candidate")
    pinned = json.loads((PROJECT / "app/src/debug/assets/tts-only/contract.json").read_text())
    if value["contract"] != pinned:
        raise ValueError("diagnostic contract changed")
    for kind in ("app", "test"):
        item = value[kind]
        path = Path(item["path"])
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise ValueError("diagnostic APK changed since preflight")
    host = host_identity()
    if not args.execute:
        print(json.dumps({"mode": "plan_only", "kind": "tts-only", "adbUsed": False, "logicalTtsRequests": 1, "gemmaRequests": 0, "hostTimeoutSeconds": 360, "ttsControllerSha256": digest(Path(__file__)), "hostGuard": host}))
        return
    if (os.environ.get("PODCAST_PHONE_PRIORITY") != "approved" or args.approved_candidate_sha256 != digest(args.candidate)
            or args.approved_host_guard_sha256 != host["sha256"]
            or args.approved_tts_controller_sha256 != digest(Path(__file__))):
        raise SystemExit("separate Pi phone slot, exact candidate, reviewed guard AND TTS controller approval required")
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "candidate.json").write_text(json.dumps(value, indent=2))
    lock = (PROJECT.parent / "artifacts/locks/phone.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.set_inheritable(lock.fileno(), False)
    (args.output / "host-guard-identity.json").write_text(json.dumps({**host, "lockInheritable": os.get_inheritable(lock.fileno()), "ttsControllerSha256": digest(Path(__file__))}, indent=2))
    device = Device(args.adb, args.serial, args.output)
    guard = PhoneGuard(device, args.output, args.candidate, args.approved_candidate_sha256, args.approved_host_guard_sha256)
    settings = DeviceSettings(device.shell)
    identity_ok = False
    launched = False
    logs = None
    cleanup = {"errors": [], "settingsErrors": [], "scratchCreated": False, "packagesRetained": True}
    def interrupted(signum, frame):
        raise InterruptedError(f"signal {signum}; cleanup only, no retry")
    signal.signal(signal.SIGINT, interrupted); signal.signal(signal.SIGTERM, interrupted)
    try:
        guard.identity()
        identity_ok = True
        (args.output / "settings-before.json").write_text(json.dumps(settings.capture(), indent=2))
        capture_conditions(device, args.output, "before")
        # Reuse installed data only. No Gemma or new model staging is allowed in this gate.
        observed = device.shell(f"run-as {APP} sha256sum no_backup/model-packs/supertonic-3/current/manifest.json")
        if observed.split()[0] != pinned["supertonicManifestSha256"]:
            raise ValueError("installed Supertonic pack mismatch or absent")
        check_controller(args); guard.checkpoint("before-app-install")
        device.run(["install", "-r", "-t", value["app"]["path"]], timeout=180)
        check_controller(args); guard.checkpoint("before-test-install")
        device.run(["install", "-r", "-t", value["test"]["path"]], timeout=180)
        with (args.output / "logcat.txt").open("wb") as out, (args.output / "logcat.stderr").open("wb") as err:
            logs = subprocess.Popen(device.prefix + ["logcat", "-v", "threadtime", "-T", "1"], stdout=out, stderr=err, start_new_session=True, close_fds=True)
        command = ("am instrument -w -r -e class dev.qoralo.podcast.wiring.TtsOnlyTest"
                   f" -e ttsOnlyApproved {CONTRACT_SHA} -e ttsOnlyRunId {args.run_id}"
                   f" -e appApkSha256 {value['app']['sha256']} -e testApkSha256 {value['test']['sha256']}"
                   f" {TEST_APP}/androidx.test.runner.AndroidJUnitRunner")
        check_controller(args); guard.checkpoint("before-instrument")
        launched = True
        output = device.shell(command, timeout=360)
        (args.output / "controller-result.json").write_text(json.dumps({"instrumentationCompleted": "OK (" in output and "FAILURES!!!" not in output,
            "nativeOutcome": "inspect service-result.json in archive; test completion does not mean synthesis/provider verification succeeded", "neuralInferenceRequested": True, "logicalTtsRequestsAuthorized": 1, "gemmaRequests": 0}))
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
                ("pull", lambda: device.run(["exec-out", "run-as", APP, "tar", "-cf", "-", f"files/tts-only/{args.run_id}"], timeout=120, binary=True)),
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
                capture_conditions(device, args.output, "after")
            except Exception as error:
                cleanup["errors"].append({"phase": "conditions-after", "error": repr(error)})
        if identity_ok and not launched:
            try:
                guard.idle()
                cleanup["appGenerationTestPidsAbsent"] = True
            except Exception as error:
                cleanup["errors"].append({"phase": "prelaunch-pid-absence", "error": repr(error)})
        cleanup["settingsErrors"] = settings.restore() + guard.readback_settings()  # read-only guard; no repairs
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
    close_inherited_fds()
    main()
