#!/usr/bin/env python3
"""Run the balanced physical-phone 1/2/4-thread sweep.

This command intentionally performs only ordinary adb install/push/read actions.
It never requests root, changes Android settings, clears page caches, or changes
CPU/thermal policy. A repository-wide phone lock is held for the complete sweep.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SWEEP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SWEEP_ROOT.parents[2]
EXP8_ROOT = REPO_ROOT / "experiments" / "0008-sherpa-onnx-android-tts-benchmark"
sys.path.insert(0, str(EXP8_ROOT))
sys.path.insert(0, str(EXP8_ROOT / "tools"))
from host_runner.runner import (  # noqa: E402
    DEFAULT_PACKAGE,
    DeviceRunner,
    PhoneLock,
    SubprocessCommands,
    ThermalEligibilityError,
    ThermalPoll,
    parse_battery_temperature,
    parse_thermal_status,
    sha256_file,
)
from host_wav import validate_file  # noqa: E402

PLAN_PATH = SWEEP_ROOT / "protocol" / "sweep-plan.json"
DESCRIPTOR_MANIFEST = SWEEP_ROOT / "descriptors" / "manifest.json"
DEPLOYMENT_INVENTORY = EXP8_ROOT / "artifacts" / "device-stage" / "deployment-inventory.json"
REMOTE_FILES = f"/sdcard/Android/data/{DEFAULT_PACKAGE}/files"
RESULTS = SWEEP_ROOT / "results"
EXPECTED_TRANSCRIPT = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
THERMAL_LEVELS = {
    "NONE": 0,
    "LIGHT": 1,
    "MODERATE": 2,
    "SEVERE": 3,
    "CRITICAL": 4,
    "EMERGENCY": 5,
    "SHUTDOWN": 6,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(argv: list[str], *, timeout: float = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, text=True, encoding="utf-8", errors="replace",
                            capture_output=True, timeout=timeout, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result


def adb(serial: str, *args: str, timeout: float = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["adb", "-s", serial, *args], timeout=timeout, check=check)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".incoming")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_json_once(path: Path, value: object) -> None:
    """Create immutable raw evidence without replacing an existing path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def thermal_level(status: str | None) -> int | None:
    if status is None:
        return None
    normalized = status.upper()
    if normalized in THERMAL_LEVELS:
        return THERMAL_LEVELS[normalized]
    match = re.fullmatch(r"STATUS_(\d+)", normalized)
    return None if match is None else int(match.group(1))


def thermal_is_eligible(status: str | None) -> bool:
    level = thermal_level(status)
    return level is not None and level < THERMAL_LEVELS["MODERATE"]


def extract_field(text: str, field: str) -> int | None:
    match = re.search(rf"^\s*{re.escape(field)}:\s*(-?\d+)\s*$", text, re.MULTILINE)
    return None if match is None else int(match.group(1))


def compact_package(package_dump: str) -> dict:
    def capture(pattern: str) -> str | None:
        match = re.search(pattern, package_dump, re.MULTILINE)
        return None if match is None else match.group(1)
    return {
        "version_code": capture(r"\bversionCode=(\d+)"),
        "version_name": capture(r"\bversionName=([^\s]+)"),
        "primary_cpu_abi": capture(r"^\s*primaryCpuAbi=([^\s]+)"),
        "debuggable": "DEBUGGABLE" in package_dump,
        "code_path": capture(r"^\s*codePath=([^\s]+)"),
    }


def capture_device_state(serial: str, raw_dir: Path, label: str) -> dict:
    commands = {
        "battery": ["shell", "dumpsys", "battery"],
        "thermal": ["shell", "dumpsys", "thermalservice"],
        "power": ["shell", "dumpsys", "power"],
        "uptime": ["shell", "cat", "/proc/uptime"],
        "device_time_utc": ["shell", "date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
        "low_power": ["shell", "settings", "get", "global", "low_power"],
    }
    raw: dict[str, dict] = {}
    for name, args in commands.items():
        result = adb(serial, *args, timeout=60, check=False)
        raw[name] = {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    raw_path = raw_dir / "device-state" / f"{label}.json"
    write_json(raw_path, raw)
    battery = raw["battery"]["stdout"]
    thermal = raw["thermal"]["stdout"]
    power = raw["power"]["stdout"]
    wakefulness = re.search(r"\bmWakefulness=([^\s]+)", power)
    interactive = re.search(r"\bmInteractive=(true|false)", power)
    return {
        "label": label,
        "observed_at_host_utc": utc_now(),
        "device_time_utc": raw["device_time_utc"]["stdout"].strip() or None,
        "battery": {
            "status_code": extract_field(battery, "status"),
            "health_code": extract_field(battery, "health"),
            "level_percent": extract_field(battery, "level"),
            "plugged_code": extract_field(battery, "plugged"),
            "temperature_c": parse_battery_temperature(battery),
            "voltage_mv": extract_field(battery, "voltage"),
        },
        "thermal_status": parse_thermal_status(thermal),
        "low_power_setting": raw["low_power"]["stdout"].strip() or None,
        "wakefulness": None if wakefulness is None else wakefulness.group(1),
        "interactive": None if interactive is None else interactive.group(1) == "true",
        "uptime": raw["uptime"]["stdout"].strip() or None,
        "raw_evidence": {
            "path": raw_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": sha256_file(raw_path),
            "bytes": raw_path.stat().st_size,
        },
    }


def batched(values: list[dict], size: int) -> Iterable[list[dict]]:
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


class SweepDeviceRunner(DeviceRunner):
    """Retain experiment-0008 orchestration with the amended status-only gate.

    Battery temperature is observed but never controls eligibility. Android
    statuses NONE and LIGHT are eligible; only MODERATE or higher (and an
    unavailable/unparseable status) cause a condition-driven wait. No setting
    is changed while waiting.
    """

    def thermal_wait(
        self,
        *,
        baseline_c: float | None,
        maximum_wait_seconds: float = 1200,
        poll_seconds: float = 10,
    ) -> list[ThermalPoll]:
        del baseline_c  # accepted for DeviceRunner compatibility; deliberately not a gate
        started = self.clock()
        polls: list[ThermalPoll] = []
        while True:
            thermal = self._adb("shell", "dumpsys", "thermalservice").stdout
            battery = self._adb("shell", "dumpsys", "battery").stdout
            status = parse_thermal_status(thermal)
            temperature = parse_battery_temperature(battery)
            eligible = thermal_is_eligible(status)
            reason = "eligible (NONE or LIGHT)" if eligible else "Android thermal status is MODERATE or higher, or unavailable"
            polls.append(ThermalPoll(self.clock(), status, temperature, eligible, reason))
            if eligible:
                return polls
            elapsed = self.clock() - started
            if elapsed >= maximum_wait_seconds:
                raise ThermalEligibilityError(f"thermal eligibility not restored: {reason}", polls)
            self.sleep(min(poll_seconds, maximum_wait_seconds - elapsed))


def verify_staged_inventory(
    serial: str,
    inventory: dict,
    raw_dir: Path,
    *,
    report_name: str = "staged-hash-verification.json",
) -> dict:
    rows = inventory.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("deployment inventory is empty")
    observed: list[dict] = []
    for batch_number, batch in enumerate(batched(rows, 24), start=1):
        remote_paths = [f"{REMOTE_FILES}/{row['path']}" for row in batch]
        quoted = " ".join(shlex.quote(path) for path in remote_paths)
        hashes = adb(serial, "shell", f"sha256sum -- {quoted}", timeout=900)
        sizes = adb(serial, "shell", f"stat -c '%s' -- {quoted}", timeout=120)
        hash_lines = [line for line in hashes.stdout.splitlines() if line.strip()]
        size_lines = [line.strip() for line in sizes.stdout.splitlines() if line.strip()]
        if len(hash_lines) != len(batch) or len(size_lines) != len(batch):
            raise RuntimeError(f"device inventory response count mismatch in batch {batch_number}")
        for row, hash_line, size_line in zip(batch, hash_lines, size_lines, strict=True):
            match = re.match(r"^([0-9a-fA-F]{64})\s+", hash_line)
            if match is None or not size_line.isdigit():
                raise RuntimeError(f"malformed device inventory response in batch {batch_number}")
            digest = match.group(1).lower()
            size = int(size_line)
            expected_size = int(row.get("bytes", row.get("size", -1)))
            expected_hash = str(row["sha256"]).lower()
            status = "match" if (digest, size) == (expected_hash, expected_size) else "mismatch"
            observed.append({
                "path": row["path"],
                "expected_bytes": expected_size,
                "observed_bytes": size,
                "expected_sha256": expected_hash,
                "observed_sha256": digest,
                "status": status,
            })
            if status != "match":
                raise RuntimeError(f"staged device file drift: {row['path']}")
        print(f"verified staged inventory batch {batch_number}", flush=True)
    raw_report = {
        "schema_version": 1,
        "observed_at_utc": utc_now(),
        "serial": serial,
        "remote_root": REMOTE_FILES,
        "inventory_sha256": sha256_file(DEPLOYMENT_INVENTORY),
        "files": observed,
    }
    raw_path = raw_dir / report_name
    write_json(raw_path, raw_report)
    committed = {
        **raw_report,
        "summary": {
            "expected_file_count": len(rows),
            "verified_match_count": len(observed),
            "mismatch_count": 0,
            "all_match": True,
        },
        "raw_evidence": {
            "path": raw_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": sha256_file(raw_path),
            "bytes": raw_path.stat().st_size,
        },
    }
    return committed


def stage_descriptors(serial: str, manifest: dict) -> list[dict]:
    # Reuse experiment 0008's app-owned descriptor directory. On Android's
    # scoped-storage FUSE layer, a new adb-created parent under the app tree is
    # owned by ``shell`` and is not traversable by the app even when its files
    # appear world-readable. Files pushed into this existing app-owned parent
    # are readable (the same path used by 0008's measured campaigns).
    remote_dir = f"{REMOTE_FILES}/descriptors"
    staged: list[dict] = []
    for row in manifest["descriptors"]:
        local = SWEEP_ROOT / "descriptors" / row["path"]
        if sha256_file(local) != row["sha256"] or local.stat().st_size != row["bytes"]:
            raise RuntimeError(f"local descriptor drift: {row['path']}")
        remote_name = f"0009-{row['path']}"
        remote = f"{remote_dir}/{remote_name}"
        existing = adb(serial, "shell", f"test -f {shlex.quote(remote)} && sha256sum {shlex.quote(remote)}",
                       check=False)
        if existing.returncode == 0:
            existing_hash = existing.stdout.split()[0].lower() if existing.stdout.split() else ""
            if existing_hash != row["sha256"]:
                raise RuntimeError(f"refusing to replace mismatched staged descriptor: {row['path']}")
            action = "already_present_and_matched"
        else:
            temporary = f"{remote}.incoming-{uuid.uuid4().hex}"
            adb(serial, "push", str(local), temporary, timeout=120)
            pushed = adb(serial, "shell", "sha256sum", shlex.quote(temporary)).stdout.split()
            if not pushed or pushed[0].lower() != row["sha256"]:
                adb(serial, "shell", "rm", "-f", shlex.quote(temporary), check=False)
                raise RuntimeError(f"descriptor device hash mismatch: {row['path']}")
            adb(serial, "shell", "mv", shlex.quote(temporary), shlex.quote(remote))
            action = "pushed_and_verified"
        final = adb(serial, "shell", "sha256sum", shlex.quote(remote)).stdout.split()
        if not final or final[0].lower() != row["sha256"]:
            raise RuntimeError(f"final descriptor hash mismatch: {row['path']}")
        staged.append({
            "candidate": row["candidate"],
            "threads": row["threads"],
            "local_path": f"descriptors/{row['path']}",
            "remote_path": f"descriptors/{remote_name}",
            "bytes": row["bytes"],
            "sha256": row["sha256"],
            "action": action,
        })
    return staged


def install_and_verify_apk(serial: str, apk: Path, raw_dir: Path) -> dict:
    local_hash = sha256_file(apk)
    install = adb(serial, "install", "-r", str(apk), timeout=300)
    paths = adb(serial, "shell", "pm", "path", DEFAULT_PACKAGE).stdout.splitlines()
    base = next((line.removeprefix("package:") for line in paths if line.startswith("package:") and line.endswith("base.apk")), None)
    if base is None:
        raise RuntimeError("installed base APK path is unavailable")
    pulled = raw_dir / "installed-base.apk"
    adb(serial, "pull", base, str(pulled), timeout=300)
    installed_hash = sha256_file(pulled)
    if installed_hash != local_hash:
        raise RuntimeError("installed APK bytes differ from locally inspected APK")
    package_dump = adb(serial, "shell", "dumpsys", "package", DEFAULT_PACKAGE, timeout=120).stdout
    package_path = raw_dir / "package.txt"
    package_path.write_text(package_dump, encoding="utf-8")
    return {
        "install_stdout": install.stdout.strip(),
        "local_ignored_path": apk.relative_to(REPO_ROOT).as_posix(),
        "local_bytes": apk.stat().st_size,
        "local_sha256": local_hash,
        "installed_path": base,
        "installed_bytes": pulled.stat().st_size,
        "installed_sha256": installed_hash,
        "byte_identical": True,
        "package": compact_package(package_dump),
        "package_dump_evidence": {
            "path": package_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": sha256_file(package_path),
            "bytes": package_path.stat().st_size,
        },
    }


def flatten_order(plan: dict) -> list[dict]:
    order: list[dict] = []
    for block_index, block in enumerate(plan["thermal_and_order"]["blocks"], start=1):
        for position, item in enumerate(block, start=1):
            order.append({**item, "block": block_index, "position_in_block": position})
    return order


def _contained_file(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file() or candidate.is_symlink():
        raise RuntimeError(f"missing, linked, or escaping evidence path: {relative}")
    return candidate


def verify_completed_run(run_row: dict, raw_dir: Path, expected: dict) -> dict:
    """Hash-check one ledger run and independently validate its WAVs/telemetry."""
    config_id = f"{expected['candidate']}_t{expected['threads']}"
    if (run_row.get("sequence") != expected["sequence"]
            or run_row.get("configuration_id") != config_id
            or run_row.get("outcome") != "success"):
        raise RuntimeError(f"ledger run {expected['sequence']} is not the registered successful configuration")
    run_dir = (REPO_ROOT / str(run_row["raw_run_path"])).resolve()
    device_runs_root = (raw_dir / "device-runs").resolve()
    if not run_dir.is_relative_to(device_runs_root) or not run_dir.is_dir() or run_dir.is_symlink():
        raise RuntimeError(f"run {expected['sequence']} escapes or is absent")
    if (run_dir / "failure.json").exists():
        raise RuntimeError(f"successful ledger run has failure evidence: {config_id}")

    host_path = _contained_file(run_dir, "host-run.json")
    host = json.loads(host_path.read_text(encoding="utf-8"))
    if not str(host.get("campaign_id", "")).startswith(config_id + "-"):
        raise RuntimeError(f"host campaign/configuration mismatch: {config_id}")
    evidence_rows = host.get("evidence")
    if not isinstance(evidence_rows, list) or not evidence_rows:
        raise RuntimeError(f"host evidence is empty: {config_id}")
    evidence_by_path: dict[str, dict] = {}
    for evidence in evidence_rows:
        relative = str(evidence.get("path", ""))
        if relative in evidence_by_path:
            raise RuntimeError(f"duplicate evidence path in {config_id}: {relative}")
        path = _contained_file(run_dir, relative)
        digest = sha256_file(path)
        if digest != evidence.get("sha256"):
            raise RuntimeError(f"retained evidence hash drift in {config_id}: {relative}")
        if "size" in evidence and path.stat().st_size != evidence["size"]:
            raise RuntimeError(f"retained evidence size drift in {config_id}: {relative}")
        evidence_by_path[relative] = evidence

    for required in ("thermal-polls.json", "logcat.txt", "telemetry.jsonl", "device-result.json"):
        if required not in evidence_by_path:
            raise RuntimeError(f"required retained evidence missing in {config_id}: {required}")
    result_path = _contained_file(run_dir, "device-result.json")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    runs = result.get("runs")
    if not isinstance(runs, list) or [row.get("state") for row in runs] != ["cold", "warm", "warm", "warm"]:
        raise RuntimeError(f"{config_id} does not contain exactly one cold and three warm runs")
    warm_rtfs = [float(row["rtf"]) for row in runs if row["state"] == "warm"]
    if abs(statistics.median(warm_rtfs) - float(result["warm_median_rtf"])) > 1e-12:
        raise RuntimeError(f"warm median mismatch in {config_id}")

    wavs: list[dict] = []
    for device_run in runs:
        relative = f"device/{host['campaign_id']}/{device_run['wav_path']}"
        if relative not in evidence_by_path:
            raise RuntimeError(f"WAV is not pinned by host evidence in {config_id}: {relative}")
        wav_path = _contained_file(run_dir, relative)
        report = validate_file(wav_path, str(device_run["wav_sha256"]))
        if (report.frames != int(device_run["sample_count"])
                or report.sample_rate_hz != int(device_run["sample_rate"])
                or abs(report.duration_seconds - float(device_run["duration_seconds"])) > 1e-12):
            raise RuntimeError(f"independent WAV decode disagrees with device metadata in {config_id}")
        audio = device_run.get("audio_validation", {})
        if audio.get("valid") is not True or audio.get("silent") is not False or audio.get("clipped") is not False:
            raise RuntimeError(f"device audio validation failed in {config_id}")
        wavs.append({
            "state": device_run["state"],
            "path": (run_dir / relative).relative_to(REPO_ROOT).as_posix(),
            "sha256": report.sha256,
            "bytes": wav_path.stat().st_size,
            "sample_rate_hz": report.sample_rate_hz,
            "frames": report.frames,
            "duration_seconds": report.duration_seconds,
            "peak": report.peak,
            "rms": report.rms,
        })

    telemetry_path = _contained_file(run_dir, "telemetry.jsonl")
    telemetry_statuses: list[str] = []
    telemetry_samples = 0
    with telemetry_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise RuntimeError(f"blank telemetry line in {config_id} at {line_number}")
            try:
                sample = json.loads(line)
            except ValueError as exc:
                raise RuntimeError(f"malformed telemetry in {config_id} at {line_number}") from exc
            if not isinstance(sample, dict) or "monotonic_seconds" not in sample:
                raise RuntimeError(f"malformed telemetry object in {config_id} at {line_number}")
            telemetry_samples += 1
            telemetry_statuses.append(parse_thermal_status(str(sample.get("thermal", ""))) or "UNAVAILABLE")
    if telemetry_samples == 0:
        raise RuntimeError(f"telemetry is empty in {config_id}")

    thermal_polls = json.loads(_contained_file(run_dir, "thermal-polls.json").read_text(encoding="utf-8"))
    if not isinstance(thermal_polls, list) or not thermal_polls:
        raise RuntimeError(f"thermal gate polls are empty in {config_id}")
    return {
        "sequence": expected["sequence"],
        "configuration_id": config_id,
        "raw_run_path": run_dir.relative_to(REPO_ROOT).as_posix(),
        "host_run_sha256": sha256_file(host_path),
        "evidence_file_count": len(evidence_rows) + 1,
        "telemetry_sha256": sha256_file(telemetry_path),
        "telemetry_sample_count": telemetry_samples,
        "telemetry_statuses": telemetry_statuses,
        "thermal_gate_statuses": [row.get("status") for row in thermal_polls],
        "wav_count": len(wavs),
        "wavs": wavs,
    }


def verify_resume_ledger(receipt: dict, raw_dir: Path, plan: dict, manifest: dict, order: list[dict]) -> dict:
    amendments = plan.get("protocol_amendments", [])
    if len(amendments) != 1 or amendments[0].get("effective_sequence") != 7:
        raise RuntimeError("resume requires the single registered sequence-7 protocol amendment")
    amendment = amendments[0]
    if receipt.get("plan_sha256") != amendment.get("supersedes_plan_sha256"):
        raise RuntimeError("campaign was not registered under the superseded plan hash")
    if receipt.get("descriptor_manifest_sha256") != sha256_file(DESCRIPTOR_MANIFEST):
        raise RuntimeError("campaign descriptor-manifest hash does not match")
    if receipt.get("raw_campaign_path") != raw_dir.relative_to(REPO_ROOT).as_posix():
        raise RuntimeError("campaign ledger path does not identify the resumed directory")
    if receipt.get("order") != order:
        raise RuntimeError("campaign registered order differs from the amended plan")
    if receipt.get("status") not in {"in_progress", "resuming"}:
        raise RuntimeError("campaign is not resumable")
    runs = receipt.get("runs")
    if not isinstance(runs, list) or not 6 <= len(runs) < 9:
        raise RuntimeError("narrow resume requires six to eight contiguous completed runs")

    manifest_by_key = {
        (row["candidate"], row["threads"]): row for row in manifest.get("descriptors", [])
    }
    checks: list[dict] = []
    for index, run_row in enumerate(runs):
        registered = {**order[index], "sequence": index + 1}
        descriptor = manifest_by_key[(registered["candidate"], registered["threads"])]
        if (run_row.get("descriptor_sha256") != descriptor["sha256"]
                or run_row.get("descriptor_path") != f"descriptors/{descriptor['path']}"):
            raise RuntimeError(f"descriptor pin mismatch at sequence {index + 1}")
        checks.append(verify_completed_run(run_row, raw_dir, registered))

    known = {(REPO_ROOT / row["raw_run_path"]).resolve() for row in runs}
    all_run_dirs = {path.resolve() for path in (raw_dir / "device-runs").iterdir() if path.is_dir()}
    abandoned = sorted(all_run_dirs - known)
    if len(abandoned) != 1 or "supertonic_3_t2" not in abandoned[0].name or any(abandoned[0].iterdir()):
        raise RuntimeError("expected exactly one empty interrupted pre-synthesis sequence-7 run directory")
    interrupted_state = next(
        (row for row in receipt.get("device_states", []) if row.get("label") == "07-supertonic_3_t2-pre"),
        None,
    )
    if interrupted_state is None:
        # The old runner captured this write-once raw pre-state, then entered
        # run_candidate's thermal wait before its next ledger checkpoint.
        state_path = raw_dir / "device-state" / "07-supertonic_3_t2-pre.json"
        if not state_path.is_file() or state_path.is_symlink():
            raise RuntimeError("interrupted sequence-7 raw pre-state is absent")
        raw_state = json.loads(state_path.read_text(encoding="utf-8"))
        battery = raw_state.get("battery", {}).get("stdout", "")
        thermal = raw_state.get("thermal", {}).get("stdout", "")
        interrupted_state = {
            "label": "07-supertonic_3_t2-pre",
            "ledger_checkpointed": False,
            "device_time_utc": raw_state.get("device_time_utc", {}).get("stdout", "").strip() or None,
            "thermal_status": parse_thermal_status(thermal),
            "battery_temperature_c": parse_battery_temperature(battery),
            "raw_evidence": {
                "path": state_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_file(state_path),
                "bytes": state_path.stat().st_size,
            },
        }
    state_path = REPO_ROOT / interrupted_state["raw_evidence"]["path"]
    if (not state_path.is_file()
            or sha256_file(state_path) != interrupted_state["raw_evidence"]["sha256"]
            or state_path.stat().st_size != interrupted_state["raw_evidence"]["bytes"]):
        raise RuntimeError("interrupted sequence-7 pre-state evidence drift")
    if sum(row["wav_count"] for row in checks[:6]) != 24:
        raise RuntimeError("the six original completed configurations do not contain 24 validated WAVs")
    return {
        "verified_at_utc": utc_now(),
        "registered_plan_sha256": receipt["plan_sha256"],
        "active_amended_plan_sha256": sha256_file(PLAN_PATH),
        "descriptor_manifest_sha256": receipt["descriptor_manifest_sha256"],
        "completed_run_count": len(checks),
        "original_completed_run_count": 6,
        "verified_wav_count": sum(row["wav_count"] for row in checks),
        "verified_telemetry_file_count": len(checks),
        "runs": checks,
        "interruption": {
            "declared_circumstance": "Prior runner was intentionally interrupted while waiting under the old NONE-only gate before sequence 7 synthesis.",
            "configuration_id": "supertonic_3_t2",
            "sequence": 7,
            "synthesis_begun": False,
            "empty_allocated_run_path": abandoned[0].relative_to(REPO_ROOT).as_posix(),
            "pre_state": interrupted_state,
        },
    }


def verify_current_install(serial: str, apk: Path, receipt: dict, attempt_dir: Path) -> dict:
    expected_hash = receipt["apk"]["local_sha256"]
    if sha256_file(apk) != expected_hash or apk.stat().st_size != receipt["apk"]["local_bytes"]:
        raise RuntimeError("resume APK differs from the campaign-pinned APK")
    paths = adb(serial, "shell", "pm", "path", DEFAULT_PACKAGE).stdout.splitlines()
    base = next((line.removeprefix("package:") for line in paths if line.startswith("package:") and line.endswith("base.apk")), None)
    if base is None:
        raise RuntimeError("installed base APK path is unavailable during resume")
    destination = attempt_dir / "installed-base.apk"
    temporary = destination.with_name(destination.name + ".incoming")
    if destination.exists() or temporary.exists():
        raise RuntimeError("refusing to overwrite resume APK evidence")
    adb(serial, "pull", base, str(temporary), timeout=300)
    digest = sha256_file(temporary)
    size = temporary.stat().st_size
    if digest != expected_hash or size != receipt["apk"]["local_bytes"]:
        raise RuntimeError("currently installed APK differs from the campaign-pinned APK")
    os.replace(temporary, destination)
    return {
        "installed_path": base,
        "bytes": size,
        "sha256": digest,
        "matches_registered_apk": True,
        "evidence_path": destination.relative_to(REPO_ROOT).as_posix(),
    }


def publish_completed_receipt(receipt: dict, raw_dir: Path, staged_report: dict) -> None:
    raw_ledger = raw_dir / "ledger.json"
    write_json(raw_ledger, receipt)
    published = json.loads(json.dumps(receipt))
    published["raw_ledger"] = {
        "path": raw_ledger.relative_to(REPO_ROOT).as_posix(),
        "sha256": sha256_file(raw_ledger),
        "bytes": raw_ledger.stat().st_size,
    }
    write_json(RESULTS / "campaign-receipt.json", published)
    write_json(RESULTS / "staged-hash-verification.json", staged_report)
    preflight = {
        "schema_version": 1,
        "experiment": receipt["experiment"],
        "observed_at_utc": receipt["started_at_utc"],
        "identity": receipt["device"],
        "identity_match": True,
        "campaign_start_thermal": receipt["campaign_start_thermal"],
        "initial_state": receipt["device_states"][0],
        "final_state": receipt["device_states"][-1],
        "apk": receipt["apk"],
        "resume_verification": receipt["resume_events"][-1]["verification_evidence"],
        "staged_inventory_summary": receipt["staged_inventory_summary"],
        "staged_descriptor_count": len(receipt["staged_descriptors"]),
        "no_tuning_or_root": True,
    }
    write_json(RESULTS / "device-preflight.json", preflight)


def resume_campaign(
    *,
    campaign_name: str,
    apk: Path,
    lock_path: Path,
    plan: dict,
    manifest: dict,
    inventory: dict,
    order: list[dict],
) -> int:
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}", campaign_name):
        raise SystemExit("resume campaign must be an exact generated campaign id")
    raw_dir = REPO_ROOT / "artifacts" / "0009" / "thread-sweep" / "campaigns" / campaign_name
    raw_ledger = raw_dir / "ledger.json"
    if not raw_ledger.is_file():
        raise SystemExit(f"resume ledger not found: {raw_ledger}")
    receipt = json.loads(raw_ledger.read_text(encoding="utf-8"))
    pre_resume_ledger = {
        "path": raw_ledger.relative_to(REPO_ROOT).as_posix(),
        "sha256": sha256_file(raw_ledger),
        "bytes": raw_ledger.stat().st_size,
    }
    runner = SweepDeviceRunner(
        SubprocessCommands(),
        lock_path=raw_dir / "internal-phone.lock",
        artifact_dir=raw_dir / "device-runs",
    )
    attempt_id = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:12]}"
    attempt_dir = raw_dir / "resume-attempts" / attempt_id
    staged_report: dict

    # The repository-wide public phone lock remains held from verification
    # through the final device-state capture. DeviceRunner nests its private lock.
    with PhoneLock(lock_path.resolve()):
        attempt_dir.mkdir(parents=True)
        readiness = runner.readiness()
        serial = readiness["serial"]
        expected_target = plan["target"]
        if (serial != expected_target["expected_serial"]
                or readiness["manufacturer"] != expected_target["manufacturer"]
                or readiness["model"] != expected_target["model"]
                or readiness["device"] != expected_target["device"]
                or readiness["abi"] != expected_target["abi"]):
            raise RuntimeError("connected device does not match the pinned target identity")

        verification = verify_resume_ledger(receipt, raw_dir, plan, manifest, order)
        verification["pre_resume_ledger"] = pre_resume_ledger
        verification["device_identity"] = {key: readiness[key] for key in (
            "serial", "manufacturer", "model", "device", "abi", "android_release",
            "api_level", "build_fingerprint", "kernel", "boot_completed",
        )}
        verification["installed_apk"] = verify_current_install(serial, apk, receipt, attempt_dir)
        staged_report = verify_staged_inventory(serial, inventory, attempt_dir)
        verification["staged_inventory"] = staged_report["summary"]
        verification["staged_inventory_evidence"] = staged_report["raw_evidence"]
        observed_descriptors = stage_descriptors(serial, manifest)
        registered_descriptors = {
            (row["candidate"], row["threads"]): (row["sha256"], row["remote_path"])
            for row in receipt["staged_descriptors"]
        }
        for row in observed_descriptors:
            if registered_descriptors.get((row["candidate"], row["threads"])) != (row["sha256"], row["remote_path"]):
                raise RuntimeError("staged descriptor differs from the registered campaign")
        verification["staged_descriptors"] = observed_descriptors
        verification_path = attempt_dir / "resume-verification.json"
        write_json_once(verification_path, verification)
        verification_evidence = {
            "path": verification_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": sha256_file(verification_path),
            "bytes": verification_path.stat().st_size,
        }

        amendment = plan["protocol_amendments"][0]
        receipt["active_plan_sha256"] = sha256_file(PLAN_PATH)
        receipt["protocol_amendments"] = [{**amendment, "verification_evidence": verification_evidence}]
        receipt["thermal_policy_history"] = [
            {
                "sequences": [1, 6],
                "eligible_android_thermal_statuses": ["NONE"],
                "fixed_passive_stabilization_seconds": "30 between runs; 60 between blocks",
                "source_plan_sha256": receipt["plan_sha256"],
            },
            {
                "sequences": [7, 9],
                "eligible_android_thermal_statuses": ["NONE", "LIGHT"],
                "wait_only_at_or_above": "MODERATE",
                "fixed_passive_stabilization_seconds": 0,
                "source_plan_sha256": receipt["active_plan_sha256"],
            },
        ]
        receipt["thermal_policy"] = {
            "eligibility_gate": "Android thermal status NONE or LIGHT",
            "wait_only_at_or_above": "MODERATE",
            "battery_temperature": "observed, retained, and not used as an eligibility gate",
            "all_statuses_recorded": True,
            "settings_changed": False,
        }
        receipt["interpretation_policy"] = {
            "below_5_percent": "inconclusive",
            "from_5_to_below_10_percent": "inconclusive",
            "at_or_above_10_percent": "directional only; one rotated campaign is not inferential replication",
        }
        receipt["interruption_before_sequence_7"] = verification["interruption"]
        resume_event = {
            "attempt_id": attempt_id,
            "resumed_at_utc": utc_now(),
            "starting_sequence": len(receipt["runs"]) + 1,
            "verification_evidence": verification_evidence,
            "status": "running",
        }
        receipt.setdefault("resume_events", []).append(resume_event)
        receipt["status"] = "resuming"
        write_json(raw_ledger, receipt)

        by_key = {(row["candidate"], row["threads"]): row for row in observed_descriptors}
        for index in range(len(receipt["runs"]), len(order)):
            config = order[index]
            config_id = f"{config['candidate']}_t{config['threads']}"
            sequence = index + 1
            pre_state = capture_device_state(
                serial, raw_dir, f"{sequence:02d}-{config_id}-resume-{attempt_id}-pre",
            )
            receipt["device_states"].append(pre_state)
            descriptor = by_key[(config["candidate"], config["threads"])]
            started_at = utc_now()
            print(f"[{sequence}/9] resuming {config_id}", flush=True)
            run_dir = runner.run_candidate(
                config_id,
                descriptor["remote_path"],
                descriptor["sha256"],
                baseline_c=None,
                timeout_seconds=1800,
                poll_seconds=1,
            )
            ended_at = utc_now()
            post_state = capture_device_state(
                serial, raw_dir, f"{sequence:02d}-{config_id}-resume-{attempt_id}-post",
            )
            receipt["device_states"].append(post_state)
            failure_path = run_dir / "failure.json"
            result_path = run_dir / "device-result.json"
            if failure_path.is_file():
                outcome = "failure"
                outcome_detail = json.loads(failure_path.read_text(encoding="utf-8"))
            elif result_path.is_file():
                device_result = json.loads(result_path.read_text(encoding="utf-8"))
                outcome = "success" if device_result.get("failure") is None else "device_failure"
                outcome_detail = device_result.get("failure")
            else:
                outcome = "failure"
                outcome_detail = {"reason": "run directory has no normalized result or failure"}
            thermal_polls_path = run_dir / "thermal-polls.json"
            thermal_polls = json.loads(thermal_polls_path.read_text(encoding="utf-8")) if thermal_polls_path.is_file() else []
            receipt["runs"].append({
                **config,
                "sequence": sequence,
                "configuration_id": config_id,
                "descriptor_path": descriptor["local_path"],
                "descriptor_sha256": descriptor["sha256"],
                "started_at_utc": started_at,
                "ended_at_utc": ended_at,
                "outcome": outcome,
                "outcome_detail": outcome_detail,
                "policy_phase": "amended_NONE_or_LIGHT",
                "thermal_gate_statuses": [row.get("status") for row in thermal_polls],
                "android_thermal_status_pre": pre_state["thermal_status"],
                "android_thermal_status_post": post_state["thermal_status"],
                "battery_temperature_c_pre": pre_state["battery"]["temperature_c"],
                "battery_temperature_c_post": post_state["battery"]["temperature_c"],
                "boundary_policy_eligible_pre": thermal_is_eligible(pre_state["thermal_status"]),
                "boundary_policy_eligible_post": thermal_is_eligible(post_state["thermal_status"]),
                "android_reported_boundary_throttling": (
                    pre_state["thermal_status"] != "NONE" or post_state["thermal_status"] != "NONE"
                ),
                "fixed_passive_sleep_seconds_after": 0,
                "raw_run_path": run_dir.relative_to(REPO_ROOT).as_posix(),
            })
            write_json(raw_ledger, receipt)
            if outcome != "success":
                resume_event["status"] = "failed"
                resume_event["ended_at_utc"] = utc_now()
                write_json(raw_ledger, receipt)
                raise RuntimeError(f"resumed configuration failed: {config_id}")

        receipt["device_states"].append(capture_device_state(
            serial, raw_dir, f"campaign-final-resume-{attempt_id}",
        ))
        resume_event["status"] = "complete"
        resume_event["ended_at_utc"] = utc_now()
        resume_event["completed_sequences"] = list(range(resume_event["starting_sequence"], 10))

    receipt["ended_at_utc"] = utc_now()
    receipt["status"] = "complete" if len(receipt["runs"]) == 9 else "incomplete"
    receipt["success_count"] = sum(row["outcome"] == "success" for row in receipt["runs"])
    receipt["failure_count"] = len(receipt["runs"]) - receipt["success_count"]
    receipt["android_reported_boundary_throttling"] = any(
        row["android_reported_boundary_throttling"] for row in receipt["runs"]
    )
    if receipt["status"] != "complete" or receipt["success_count"] != 9:
        raise RuntimeError("resume did not complete the exact nine-configuration matrix")
    publish_completed_receipt(receipt, raw_dir, staged_report)
    print(RESULTS / "campaign-receipt.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apk",
        type=Path,
        default=REPO_ROOT / "artifacts" / "0009" / "thread-sweep" / "android-build" /
                "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk",
    )
    parser.add_argument("--lock", type=Path, default=REPO_ROOT / "artifacts" / "locks" / "phone.lock")
    parser.add_argument(
        "--resume-campaign",
        metavar="CAMPAIGN_ID",
        help="narrowly verify and finish an existing contiguous six-to-eight-run campaign",
    )
    args = parser.parse_args()
    apk = args.apk.resolve()
    if not apk.is_file():
        raise SystemExit(f"built APK not found: {apk}")

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(DESCRIPTOR_MANIFEST.read_text(encoding="utf-8"))
    if manifest["transcript_sha256"] != EXPECTED_TRANSCRIPT:
        raise SystemExit("descriptor manifest transcript drift")
    if sha256_file(DEPLOYMENT_INVENTORY) != plan["source_experiment"]["deployment_inventory_sha256"]:
        raise SystemExit("experiment 0008 deployment inventory drift")
    inventory = json.loads(DEPLOYMENT_INVENTORY.read_text(encoding="utf-8"))
    order = flatten_order(plan)
    if len(order) != 9 or {(row["candidate"], row["threads"]) for row in order} != {
        (candidate, threads) for candidate in plan["candidates"] for threads in (1, 2, 4)
    }:
        raise SystemExit("sweep order does not cover the exact 3x3 matrix")
    if args.resume_campaign:
        return resume_campaign(
            campaign_name=args.resume_campaign,
            apk=apk,
            lock_path=args.lock,
            plan=plan,
            manifest=manifest,
            inventory=inventory,
            order=order,
        )

    campaign_name = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:12]}"
    raw_dir = REPO_ROOT / "artifacts" / "0009" / "thread-sweep" / "campaigns" / campaign_name
    raw_dir.mkdir(parents=True)
    runner = SweepDeviceRunner(
        SubprocessCommands(),
        lock_path=raw_dir / "internal-phone.lock",
        artifact_dir=raw_dir / "device-runs",
    )
    receipt: dict = {
        "schema_version": 1,
        "experiment": "0009-android-tts-optimization/thread-sweep",
        "sweep_id": campaign_name,
        "started_at_utc": utc_now(),
        "status": "in_progress",
        "plan_sha256": sha256_file(PLAN_PATH),
        "descriptor_manifest_sha256": sha256_file(DESCRIPTOR_MANIFEST),
        "raw_campaign_path": raw_dir.relative_to(REPO_ROOT).as_posix(),
        "order": order,
        "runs": [],
        "stabilization": [],
        "device_states": [],
        "prohibitions_observed": {
            "root_used": False,
            "system_tuning_used": False,
            "qnn_or_qairt_used": False,
            "proprietary_sdk_used": False,
            "text_splitting_used": False,
        },
        "thermal_policy": {
            "eligibility_gate": "Android thermal status NONE or LIGHT",
            "wait_only_at_or_above": "MODERATE",
            "battery_temperature": "observed, retained, and not used as an eligibility gate",
            "all_statuses_recorded": True,
            "settings_changed": False,
        },
    }
    raw_ledger = raw_dir / "ledger.json"

    # The public lock is deliberately held across install, verification,
    # stabilization, and all nine runs. DeviceRunner uses a private nested lock.
    with PhoneLock(args.lock.resolve()):
        readiness = runner.readiness()
        serial = readiness["serial"]
        expected = plan["target"]
        if (serial != expected["expected_serial"] or readiness["manufacturer"] != expected["manufacturer"]
                or readiness["model"] != expected["model"] or readiness["device"] != expected["device"]
                or readiness["abi"] != expected["abi"]):
            raise RuntimeError("connected device does not match the pinned target identity")
        package_dump = readiness.pop("package_version", "")
        receipt["device"] = {**readiness, "package_before_install": compact_package(package_dump)}
        receipt["host"] = {
            "observed_at_utc": utc_now(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "adb_version": run(["adb", "version"], timeout=30).stdout.splitlines()[0],
            "git_commit_before_results": run(["git", "rev-parse", "HEAD"], timeout=30).stdout.strip(),
        }
        receipt["apk"] = install_and_verify_apk(serial, apk, raw_dir)
        staged_report = verify_staged_inventory(serial, inventory, raw_dir)
        receipt["staged_inventory_summary"] = staged_report["summary"]
        receipt["staged_descriptors"] = stage_descriptors(serial, manifest)
        write_json(RESULTS / "staged-hash-verification.json", staged_report)

        initial = capture_device_state(serial, raw_dir, "campaign-baseline-before-wait")
        receipt["device_states"].append(initial)
        try:
            polls = runner.thermal_wait(
                baseline_c=None,
                maximum_wait_seconds=plan["thermal_and_order"]["maximum_wait_seconds"],
                poll_seconds=plan["thermal_and_order"]["poll_interval_seconds"],
            )
        except ThermalEligibilityError as exc:
            blocked_path = raw_dir / "campaign-start-thermal-polls.json"
            write_json(blocked_path, [poll.__dict__ for poll in exc.polls])
            receipt["status"] = "blocked_before_measurement"
            receipt["ended_at_utc"] = utc_now()
            receipt["campaign_start_thermal"] = {
                "eligibility_gate": "Android thermal status NONE or LIGHT",
                "battery_temperature_is_gate": False,
                "polls": [poll.__dict__ for poll in exc.polls],
                "evidence": {
                    "path": blocked_path.relative_to(REPO_ROOT).as_posix(),
                    "sha256": sha256_file(blocked_path),
                    "bytes": blocked_path.stat().st_size,
                },
            }
            write_json(raw_ledger, receipt)
            raise
        receipt["campaign_start_thermal"] = {
            "battery_temperature_c_observed": polls[-1].battery_temperature_c,
            "thermal_status": polls[-1].status,
            "eligibility_gate": "Android thermal status NONE or LIGHT",
            "battery_temperature_is_gate": False,
            "wait_seconds": max(0.0, polls[-1].monotonic_seconds - polls[0].monotonic_seconds),
            "polls": [poll.__dict__ for poll in polls],
        }
        write_json(raw_ledger, receipt)

        by_key = {(row["candidate"], row["threads"]): row for row in receipt["staged_descriptors"]}
        for index, config in enumerate(order):
            config_id = f"{config['candidate']}_t{config['threads']}"
            pre_state = capture_device_state(serial, raw_dir, f"{index + 1:02d}-{config_id}-pre")
            receipt["device_states"].append(pre_state)
            descriptor = by_key[(config["candidate"], config["threads"])]
            started_at = utc_now()
            print(f"[{index + 1}/9] running {config_id}", flush=True)
            run_dir = runner.run_candidate(
                config_id,
                descriptor["remote_path"],
                descriptor["sha256"],
                baseline_c=None,
                timeout_seconds=1800,
                poll_seconds=1,
            )
            ended_at = utc_now()
            post_state = capture_device_state(serial, raw_dir, f"{index + 1:02d}-{config_id}-post")
            receipt["device_states"].append(post_state)
            failure_path = run_dir / "failure.json"
            result_path = run_dir / "device-result.json"
            if failure_path.is_file():
                outcome = "failure"
                outcome_detail = json.loads(failure_path.read_text(encoding="utf-8"))
            elif result_path.is_file():
                device_result = json.loads(result_path.read_text(encoding="utf-8"))
                outcome = "success" if device_result.get("failure") is None else "device_failure"
                outcome_detail = device_result.get("failure")
            else:
                outcome = "failure"
                outcome_detail = {"reason": "run directory has no normalized result or failure"}
            receipt["runs"].append({
                **config,
                "sequence": index + 1,
                "configuration_id": config_id,
                "descriptor_path": descriptor["local_path"],
                "descriptor_sha256": descriptor["sha256"],
                "started_at_utc": started_at,
                "ended_at_utc": ended_at,
                "outcome": outcome,
                "outcome_detail": outcome_detail,
                "android_thermal_status_pre": pre_state["thermal_status"],
                "android_thermal_status_post": post_state["thermal_status"],
                "battery_temperature_c_pre": pre_state["battery"]["temperature_c"],
                "battery_temperature_c_post": post_state["battery"]["temperature_c"],
                "android_reported_boundary_throttling": (
                    pre_state["thermal_status"] != "NONE" or post_state["thermal_status"] != "NONE"
                ),
                "raw_run_path": run_dir.relative_to(REPO_ROOT).as_posix(), 
            })
            write_json(raw_ledger, receipt)

            if index < len(order) - 1:
                next_config = order[index + 1]
                receipt["stabilization"].append({
                    "after_configuration": config_id,
                    "before_configuration": f"{next_config['candidate']}_t{next_config['threads']}",
                    "reason": "no fixed passive sleep; next run performs its own condition-driven thermal gate",
                    "required_seconds": 0,
                    "observed_seconds": 0,
                    "settings_changed": False,
                })
                write_json(raw_ledger, receipt)

        receipt["device_states"].append(capture_device_state(serial, raw_dir, "campaign-final"))

    receipt["ended_at_utc"] = utc_now()
    receipt["status"] = "complete" if len(receipt["runs"]) == 9 else "incomplete"
    receipt["success_count"] = sum(row["outcome"] == "success" for row in receipt["runs"])
    receipt["failure_count"] = len(receipt["runs"]) - receipt["success_count"]
    receipt["android_reported_boundary_throttling"] = any(
        row["android_reported_boundary_throttling"] for row in receipt["runs"]
    )
    write_json(raw_ledger, receipt)
    receipt["raw_ledger"] = {
        "path": raw_ledger.relative_to(REPO_ROOT).as_posix(),
        "sha256": sha256_file(raw_ledger),
        "bytes": raw_ledger.stat().st_size,
    }
    write_json(RESULTS / "campaign-receipt.json", receipt)
    preflight = {
        "schema_version": 1,
        "experiment": receipt["experiment"],
        "observed_at_utc": receipt["started_at_utc"],
        "identity": receipt["device"],
        "identity_match": True,
        "campaign_start_thermal": receipt["campaign_start_thermal"],
        "initial_state": receipt["device_states"][0],
        "final_state": receipt["device_states"][-1],
        "apk": receipt["apk"],
        "staged_inventory_summary": receipt["staged_inventory_summary"],
        "staged_descriptor_count": len(receipt["staged_descriptors"]),
        "no_tuning_or_root": True,
    }
    write_json(RESULTS / "device-preflight.json", preflight)
    print(RESULTS / "campaign-receipt.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
