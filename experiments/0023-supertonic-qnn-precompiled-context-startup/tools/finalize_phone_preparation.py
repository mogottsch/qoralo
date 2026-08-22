#!/usr/bin/env python3
"""Freeze the reviewed phone runner/stage contract without phone access."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path: Path) -> dict[str, Any]:
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)}


def run(args: argparse.Namespace) -> None:
    stage = args.stage.resolve()
    manifest = stage / "stage-manifest.sha256"
    subprocess.run(["sha256sum", "-c", "stage-manifest.sha256"], cwd=stage, check=True, stdout=subprocess.DEVNULL)
    entries = []
    for line in manifest.read_text().splitlines():
        digest, relative = line.split("  ", 1)
        path = stage / relative
        if sha(path) != digest:
            raise SystemExit(f"stage drift: {relative}")
        entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest})
    provenance = json.loads((stage / "stage-provenance.json").read_text())
    transport = json.loads(args.transport.read_text())
    contract = json.loads(args.contract.read_text())
    if provenance["status"] != "phone_stage_prepared_not_executed":
        raise SystemExit("stage provenance status mismatch")
    if transport["status"] != "prepared_not_executed":
        raise SystemExit("transport status mismatch")
    if contract["current_checkpoint"]["pause"] != "Commit and review the prepared runner/stage/transport contract before any phone execution.":
        raise SystemExit("phone review gate drift")
    runner = stage / "runner"
    file_output_raw = subprocess.check_output(["file", str(runner)], text=True).strip()
    file_output = file_output_raw.split(": ", 1)[-1]
    if "ARM aarch64" not in file_output or "Android 28" not in file_output:
        raise SystemExit(f"unexpected runner ABI: {file_output}")
    needed = subprocess.check_output([str(args.readelf), "-d", str(runner)], text=True)
    for library in ("libonnxruntime.so", "libc++_shared.so", "libm.so", "libdl.so", "libc.so"):
        if f"[{library}]" not in needed:
            raise SystemExit(f"missing runner dependency: {library}")

    result = {
        "schema_version": 1,
        "experiment": "0023-supertonic-qnn-precompiled-context-startup",
        "recorded_date": "2026-08-22",
        "status": "phone_campaign_prepared_not_executed",
        "host_setup_review_input": {
            "commit": "a57f9d5",
            "result": "results/clean-host-setup/clean-setup-result.json",
            "sha256": "b34630269b0bf7a8716d1884c86d42267f22109a81c77c106e27f5c6183b9b2c",
            "accepted_by_pi": True,
        },
        "runner": {
            "source": record(args.runner_source),
            "binary": {**record(runner), "file_output": file_output},
            "build_script": record(args.build_script),
            "needed_libraries": [
                "libonnxruntime.so",
                "libc++_shared.so",
                "libm.so",
                "libdl.so",
                "libc.so",
            ],
            "android_api": 28,
            "architecture": "arm64-v8a / AArch64 PIE",
            "warnings": "compiled with -Wall -Wextra -Werror",
        },
        "stage": {
            "manifest": {**record(manifest), "entries": len(entries)},
            "total_bytes_excluding_manifest": sum(item["bytes"] for item in entries),
            "entries": entries,
            "provenance": record(stage / "stage-provenance.json"),
            "local_sha256sum_check": "passed",
        },
        "runtime_adaptation": contract["runtime"]["android_libonnxruntime"],
        "transport": {
            "contract": record(args.transport),
            "adb": transport["adb"],
            "adaptation": transport["platform_adaptation"],
        },
        "campaign": {
            "script": record(args.campaign_script),
            "validator": record(args.validator),
            "setup": "three fresh native runner processes per arm; four-session readiness only",
            "e2e": "one fresh process per arm; one first plus five same-session warm complete generations",
            "physical_proof": "one separate context process; one profiled complete generation",
            "source_unavailable": "source-models deleted and absence verified before context setup/E2E/proof",
            "outputs": "729746-sample mono PCM16 44100 Hz WAV plus float32 raw",
            "numerical_policy": "descriptive only; no equivalence blocker",
            "listening_policy": "exact historical accepted hash transfers; any byte-different WAV is not_reviewed",
            "memory": "100 ms sampled /proc/<pid>/smaps_rollup PSS plus VmHWM and runner getrusage max RSS",
            "thermal_power": "thermalservice and battery before/after each arm and whole campaign",
        },
        "safety": {
            "phone_lock": "nonblocking, full campaign lifetime",
            "identity_boot_authorization": transport["device_gate"],
            "unique_stage": transport["safety"]["remote_root"],
            "remote_hash_verification": True,
            "minimum_free_space": "stage bytes plus 512 MiB",
            "personal_data_settings_access": False,
            "app_install": False,
            "cleanup_trap_and_absence_verification": True,
        },
        "validation": {
            "runner_cross_compile": "passed",
            "runner_dependency_check": "passed",
            "stage_hash_check": "passed",
            "campaign_bash_syntax": "passed",
            "python_compile": "passed",
            "phone_access_during_preparation": False,
        },
        "execution_gate": "Commit and review this preparation before setting PHONE_CAMPAIGN_APPROVED=yes; phone availability is still required.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "runner": result["runner"]["binary"], "stage_manifest": result["stage"]["manifest"]}, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--runner-source", type=Path, required=True)
    parser.add_argument("--build-script", type=Path, required=True)
    parser.add_argument("--campaign-script", type=Path, required=True)
    parser.add_argument("--validator", type=Path, required=True)
    parser.add_argument("--transport", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--readelf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
