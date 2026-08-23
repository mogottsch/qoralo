#!/usr/bin/env python3
"""Freeze already-pulled and offline-validated phone evidence after cleanup."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def require_text(path: Path, expected: str) -> None:
    actual = path.read_text().strip()
    if actual != expected:
        raise SystemExit(f"{path}: expected {expected!r}, got {actual!r}")


def battery_summary(path: Path) -> dict[str, Any]:
    wanted = {
        "AC powered",
        "USB powered",
        "Wireless powered",
        "status",
        "health",
        "present",
        "level",
        "scale",
        "voltage",
        "temperature",
        "current now",
    }
    result: dict[str, Any] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        if key not in wanted or key in result:
            continue
        value = value.strip()
        if value in {"true", "false"}:
            result[key] = value == "true"
        else:
            try:
                result[key] = int(value)
            except ValueError:
                result[key] = value
    if set(result) != wanted:
        raise SystemExit(f"missing bounded battery fields in {path}: {wanted - set(result)}")
    result["temperature_celsius"] = result["temperature"] / 10.0
    return result


def thermal_summary(path: Path) -> dict[str, Any]:
    text = path.read_text()
    match = re.search(r"^Thermal Status: (\d+)$", text, re.MULTILINE)
    if not match:
        raise SystemExit(f"missing thermal status in {path}")
    temperatures: dict[str, float] = {}
    for value, name in re.findall(
        r"Temperature\{mValue=([-0-9.]+), mType=\d+, mName=([^,}]+), mStatus=\d+\}",
        text,
    ):
        if name not in temperatures:
            temperatures[name] = float(value)
    required = {"AP", "PA", "BAT", "USB", "SKIN"}
    if not required.issubset(temperatures):
        raise SystemExit(f"missing bounded temperatures in {path}: {required - set(temperatures)}")
    return {"thermal_status": int(match.group(1)), "temperatures_celsius": temperatures}


def run(args: argparse.Namespace) -> None:
    campaign = args.campaign.resolve()
    validated_path = campaign / "phone-result.json"
    validated = json.loads(validated_path.read_text())
    if validated["status"] != "phone_campaign_pulled_and_validated_cleanup_pending":
        raise SystemExit("unexpected offline validation status")
    if not validated["structural_wav_valid"]:
        raise SystemExit("WAV structural validation failed")
    if not validated["physical_proof"]["physical_qnn_htp_proven"]:
        raise SystemExit("physical QNN proof failed")
    require_text(campaign / "cleanup.exit-code.txt", "0")
    require_text(campaign / "cleanup-verification.txt", "passed")
    require_text(campaign / "context-source-unavailable-gate.txt", "passed")
    for action in (
        "source-setup-1",
        "source-setup-2",
        "source-setup-3",
        "source-e2e",
        "context-setup-1",
        "context-setup-2",
        "context-setup-3",
        "context-e2e",
        "context-proof",
    ):
        require_text(campaign / f"{action}.adb-exit-code.txt", "0")

    args.phone_lock.parent.mkdir(parents=True, exist_ok=True)
    with args.phone_lock.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SystemExit("phone.lock remains held after campaign") from error
        lock_release_verified = True
        fcntl.flock(lock, fcntl.LOCK_UN)

    if args.output.exists():
        shutil.rmtree(args.output)
    evidence_output = args.output / "evidence"
    device_source = campaign / "device-evidence"
    for directory in sorted(path for path in device_source.iterdir() if path.is_dir()):
        for name in ("stdout.json", "stderr.log", "memory.txt"):
            copy(directory / name, evidence_output / directory.name / name)
    for arm in ("source-e2e", "context-e2e"):
        for name in ("output.raw", "output.wav"):
            copy(device_source / arm / name, evidence_output / arm / name)
    profiles = device_source / "context-proof/profiles"
    for source in sorted(path for path in profiles.iterdir() if path.is_file()):
        copy(source, evidence_output / "context-proof/profiles" / source.name)

    metadata_names = [
        "campaign-start.txt",
        "devices.txt",
        "identity.txt",
        "space-gate.txt",
        "local-stage-preflight.txt",
        "local-stage-preflight.stderr.log",
        "remote-stage-verification.txt",
        "remote-stage-verification.stderr.log",
        "context-source-unavailable-gate.txt",
        "thermal-campaign-before.txt",
        "thermal-campaign-after.txt",
        "thermal-source-before.txt",
        "thermal-source-after.txt",
        "thermal-context-before.txt",
        "thermal-context-after.txt",
        "push.stdout.log",
        "push.stderr.log",
        "pull.stdout.log",
        "pull.stderr.log",
        "cleanup.exit-code.txt",
        "cleanup.stdout.log",
        "cleanup.stderr.log",
        "cleanup-verification.txt",
        "cleanup-verify.stdout.log",
        "cleanup-verify.stderr.log",
    ]
    for name in metadata_names:
        copy(campaign / name, args.output / "metadata" / name)
    for source in sorted((campaign / "commands").iterdir()):
        copy(source, args.output / "commands" / source.name)
    for source in sorted(campaign.glob("*.adb-*.txt")):
        copy(source, args.output / "metadata" / source.name)
    for source in sorted(campaign.glob("*.adb-*.log")):
        copy(source, args.output / "metadata" / source.name)

    identity = {}
    for line in (campaign / "identity.txt").read_text().splitlines():
        key, value = line.split("=", 1)
        identity[key] = value
    expected_identity = {
        "serial": "R5CW81PR8SY",
        "manufacturer": "samsung",
        "model": "SM-S918B",
        "device": "dm3q",
        "soc": "SM8550",
        "abi": "arm64-v8a",
        "android_release": "16",
        "api": "36",
        "boot_completed": "1",
        "verified_boot": "green",
        "flash_locked": "1",
    }
    if identity != expected_identity:
        raise SystemExit(f"identity evidence drift: {identity}")

    validated["status"] = "phone_campaign_passed"
    validated["cleanup"] = {
        "remote_cleanup_exit_code": 0,
        "remote_root_absence_verified": True,
        "phone_lock_release_verified_nonblocking": lock_release_verified,
    }
    if args.environment_summary:
        validated["environment"] = json.loads(
            args.environment_summary.read_text()
        )["environment"]
    else:
        validated["environment"] = {
            phase: {
                "thermal_before": thermal_summary(campaign / f"thermal-{phase}-before.txt"),
                "thermal_after": thermal_summary(campaign / f"thermal-{phase}-after.txt"),
                "battery_before": battery_summary(campaign / f"battery-{phase}-before.txt"),
                "battery_after": battery_summary(campaign / f"battery-{phase}-after.txt"),
            }
            for phase in ("campaign", "source", "context")
        }
        validated["environment"]["privacy"] = {
            "committed_battery_evidence": "bounded power/level/temperature/current fields only",
            "full_dumpsys_battery_not_committed": True,
        }
    validated["execution"] = {
        "attempt_commit": "e3d5645",
        "campaign_start": (campaign / "campaign-start.txt").read_text().splitlines()[0].split("=", 1)[1],
        "device_identity": identity,
        "transport": "native Linux /usr/bin/adb 37.0.0",
        "remote_stage_hash_check": "passed",
        "source_unavailable_before_context": "passed",
        "all_nine_runner_processes_exit_zero": True,
        "validation": "offline parser fix applied to byte-preserved outputs; no phone rerun",
        "offline_validator": {
            "path": args.validator.name,
            "bytes": args.validator.stat().st_size,
            "sha256": sha(args.validator),
        },
        "finalizer": {
            "path": args.finalizer.name,
            "bytes": args.finalizer.stat().st_size,
            "sha256": sha(args.finalizer),
        },
    }
    validated["benchmark_protocol"] = {
        "setup": "three fresh native processes per arm; exact four-session sequence from immediately before duration construction through return of vocoder construction; no inference",
        "e2e": "one separate persistent-session process per arm; run 0 first plus runs 1-5 warm",
        "generation_state_reset": "Sessions are stateless for this route; each generation recreates duration/text inputs, latent mask, current/total step tensors and deterministic Gaussian latent from seed 20260813 before five vector steps.",
        "rtf": "complete generation seconds divided by actual 729746/44100-second emitted audio duration",
        "memory": "independent 100 ms samples of /proc/<pid>/smaps_rollup Pss plus /proc/<pid>/status VmHWM; runner also records getrusage maximum RSS",
        "profiled_proof": "one separate context generation with ORT and QNN detailed profiling, excluded from setup and E2E timing",
    }
    validated["parser_incident"] = {
        "classification": "post-pull local evidence-parser failure, not device/QNN execution failure",
        "original_failure": "json.loads rejected a QNN/libnative diagnostic prefix before source-arm runner JSON",
        "raw_stdout_preserved": True,
        "parser_rule": "exactly one line-start final JSON object; reject zero, multiple, malformed or non-whitespace suffix; retain and hash exact and stripped prefix",
        "phone_rerun": False,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    result_path = args.output / "phone-result.json"
    sidecar = args.output / "sha256-manifest.json"
    evidence_files = sorted(
        item
        for item in args.output.rglob("*")
        if item.is_file() and item not in {result_path, sidecar}
    )
    validated["evidence_manifest"] = [record(path, args.output) for path in evidence_files]
    result_path.write_text(json.dumps(validated, indent=2, sort_keys=True) + "\n")
    final_manifest = [
        record(path, args.output)
        for path in sorted(item for item in args.output.rglob("*") if item.is_file())
    ]
    sidecar.write_text(json.dumps(final_manifest, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": validated["status"],
                "setup_comparison": validated["setup_comparison"],
                "source_wav": validated["e2e"]["source"]["wav"],
                "context_wav": validated["e2e"]["context"]["wav"],
                "physical_qnn_htp_proven": validated["physical_proof"]["physical_qnn_htp_proven"],
                "cleanup": validated["cleanup"],
            },
            indent=2,
            sort_keys=True,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phone-lock", type=Path, required=True)
    parser.add_argument("--validator", type=Path, required=True)
    parser.add_argument("--finalizer", type=Path, required=True)
    parser.add_argument("--environment-summary", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
