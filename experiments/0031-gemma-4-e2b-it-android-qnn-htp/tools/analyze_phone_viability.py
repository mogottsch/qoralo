#!/usr/bin/env python3
"""Retain and classify the first bounded physical Gemma QnnHtp phone gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RESULTS = EXP / "results/android-qnn-physical-viability-attempt-01"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_identity(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if not run.is_dir() or run.parent.name != "phone-runs":
        raise ValueError(f"unexpected run directory: {run}")

    if RESULTS.exists():
        shutil.rmtree(RESULTS)
    raw = RESULTS / "raw"
    raw.mkdir(parents=True)
    retain = [
        "adb-state.txt",
        "identity.txt",
        "battery-before.txt",
        "battery-before.stderr",
        "battery-after.txt",
        "battery-after.stderr",
        "thermal-before.txt",
        "thermal-before.stderr",
        "thermal-after.txt",
        "thermal-after.stderr",
        "storage-before.txt",
        "local-hash-check.txt",
        "remote-hash-check.txt",
        "remote-hash-check.stderr",
        "push.txt",
        "runner.stdout",
        "runner.stderr",
        "memory-samples.txt",
        "memory-samples.stderr",
        "exit-code.txt",
        "genie-verbose.log",
        "pull-viability-output.txt.txt",
        "pull-viability-profile.json.txt",
        "pull-genie-verbose.log.txt",
        "process-after.txt",
        "cleanup.stdout",
        "cleanup.stderr",
        "cleanup-status.txt",
    ]
    for name in retain:
        source = run / name
        if source.exists():
            shutil.copy2(source, raw / name)

    exit_code = int((raw / "exit-code.txt").read_text().strip())
    runner_stderr = (raw / "runner.stderr").read_text(errors="replace")
    genie_log = (raw / "genie-verbose.log").read_text(errors="replace")
    cleanup = (raw / "cleanup-status.txt").read_text().strip()
    identity = parse_identity(raw / "identity.txt")
    required_identity = {
        "manufacturer": "samsung",
        "model": "SM-S918B",
        "device": "dm3q",
        "soc": "SM8550",
        "abi": "arm64-v8a",
        "boot": "1",
        "verified_boot": "green",
        "flash_locked": "1",
    }
    if any(identity.get(key) != value for key, value in required_identity.items()):
        raise RuntimeError(f"device identity mismatch: {identity}")
    checks = {
        "qnn_htp_config_parsed": '"type":"qnn-htp"' in genie_log,
        "both_graphs_initialized": "qnn-api initialized with 2 graph(s)" in genie_log,
        "ar1_graph_loaded": "Graph ar1_cl4096_1_of_1" in genie_log,
        "ar128_graph_loaded": "Graph ar128_cl4096_1_of_1" in genie_log,
        "swa_ar1_width_513": "AR-1 CL-513" in genie_log,
        "swa_ar128_width_640": "AR-128 CL-640" in genie_log,
        "physical_soc_detected": "Detected Snapdragon SOC SM8550" in genie_log,
        "htp_provider_initialized": "HTP: initialization completed successfully" in genie_log,
        "qnn_htp_backend_created": "QnnBackend_create done successfully" in genie_log,
        "v73_stub_loaded": "libQnnHtpV73Stub.so" in genie_log,
        "qnn_stub_connection_established": "First connection to QNN stub established" in genie_log,
        "qnn_device_created": "QnnDevice_create done" in genie_log,
    }
    if not all(checks.values()):
        raise RuntimeError(f"expected physical context-load evidence missing: {checks}")
    missing_extension = "libQnnHtpNetRunExtensions.so" in runner_stderr and "not found" in runner_stderr
    if exit_code != 139 or not missing_extension or "Segmentation fault" not in runner_stderr:
        raise RuntimeError("unexpected first-gate failure signature")
    if cleanup != "absent":
        raise RuntimeError("remote cleanup was not verified")

    raw_files = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(raw.iterdir())
        if path.is_file()
    }
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "run_id": run.name,
        "classification": "physical_qnn_htp_context_load_partial_failure_before_inference",
        "claim_boundary": (
            "On the authorized physical SM8550 phone, Genie parsed QnnHtp, discovered both compiled graphs, "
            "initialized the HTP provider/backend/device, loaded the v73 stub, and established a QNN stub "
            "connection. Dialog creation then segfaulted because the staged bundle omitted the requested HTP "
            "backend-extension library. No graph execution, generated token/text, or performance is claimed."
        ),
        "gate": {
            "bounded_viability_only": True,
            "canonical_campaign": False,
            "max_new_tokens": 16,
            "phone_lock_held_full_adb_lifecycle": True,
            "attempt": 1,
            "retry_performed": False,
        },
        "device": identity,
        "stage": {
            "local_hash_check_passed": "FAILED" not in (raw / "local-hash-check.txt").read_text(),
            "remote_hash_check_passed": "FAILED" not in (raw / "remote-hash-check.txt").read_text(),
            "remote_cleanup_status": cleanup,
        },
        "physical_provider_evidence": checks,
        "outcome": {
            "exit_code": exit_code,
            "result": "failed_before_dialog_creation_and_inference",
            "missing_library": "libQnnHtpNetRunExtensions.so",
            "failure": "Backend-extension dlopen failed; Genie continued and segfaulted during dialog create.",
            "output_created": False,
            "profile_created": False,
            "graph_execution_observed": False,
            "generated_tokens": 0,
            "stop_reason": "error",
            "output_sanity": {"looks_sensible": None, "issue_notes": None},
        },
        "exact_unblock": (
            "Add and hash QAIRT 2.49.40 lib/aarch64-android/libQnnHtpNetRunExtensions.so, rebuild and verify "
            "the private stage, then obtain explicit authorization for exactly one retry under phone.lock."
        ),
        "raw_evidence": raw_files,
    }
    (RESULTS / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(RESULTS / "result.json")


if __name__ == "__main__":
    main()
