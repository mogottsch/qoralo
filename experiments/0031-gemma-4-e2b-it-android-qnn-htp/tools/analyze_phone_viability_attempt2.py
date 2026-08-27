#!/usr/bin/env python3
"""Retain and classify the corrected physical Gemma gate (attempt 02)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RESULTS = EXP / "results/android-qnn-physical-viability-attempt-02"


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
        "adb-state.txt", "identity.txt", "battery-before.txt", "battery-before.stderr",
        "battery-after.txt", "battery-after.stderr", "thermal-before.txt", "thermal-before.stderr",
        "thermal-after.txt", "thermal-after.stderr", "storage-before.txt", "local-hash-check.txt",
        "remote-hash-check.txt", "remote-hash-check.stderr", "runtime-completeness.txt", "push.txt",
        "runner.stdout", "runner.stderr", "memory-samples.txt", "memory-samples.stderr", "exit-code.txt",
        "genie-verbose.log", "viability-profile.json", "pull-viability-output.txt.txt",
        "pull-viability-profile.json.txt", "pull-genie-verbose.log.txt", "process-after.txt",
        "cleanup.stdout", "cleanup.stderr", "cleanup-status.txt",
    ]
    for name in retain:
        source = run / name
        if source.exists():
            shutil.copy2(source, raw / name)

    exit_code = int((raw / "exit-code.txt").read_text().strip())
    stderr = (raw / "runner.stderr").read_text(errors="replace")
    log = (raw / "genie-verbose.log").read_text(errors="replace")
    cleanup = (raw / "cleanup-status.txt").read_text().strip()
    identity = parse_identity(raw / "identity.txt")
    required_identity = {
        "manufacturer": "samsung", "model": "SM-S918B", "device": "dm3q", "soc": "SM8550",
        "abi": "arm64-v8a", "boot": "1", "verified_boot": "green", "flash_locked": "1",
    }
    if any(identity.get(key) != value for key, value in required_identity.items()):
        raise RuntimeError(f"device identity mismatch: {identity}")

    physical = {
        "backend_extension_requested_without_dlopen_error": (
            "Backend extensions lib path : libQnnHtpNetRunExtensions.so" in log
            and "Unable to load backend extensions" not in stderr
        ),
        "both_graphs_initialized": "qnn-api initialized with 2 graph(s)" in log,
        "physical_soc_detected": "Detected Snapdragon SOC SM8550" in log,
        "htp_provider_initialized": "HTP: initialization completed successfully" in log,
        "qnn_htp_backend_created": "QnnBackend_create done successfully" in log,
        "qnn_device_created": "QnnDevice_create done" in log,
        "v73_stub_loaded": "libQnnHtpV73Stub.so" in log,
        "qnn_stub_connection_established": "First connection to QNN stub established" in log,
        "context_deserialized": "Context 1 deserialized on pd 0" in log,
        "weight_sharing_context_detected": "prepared with Weight Sharing enabled" in log,
    }
    if not all(physical.values()):
        raise RuntimeError(f"missing corrected physical evidence: {physical}")

    mismatch_names = re.findall(
        r'ar128_cl4096_1_of_1 : ([^ ]+) - Non-identical quantization parameters', stderr
    )
    if exit_code != 1 or len(mismatch_names) != 30 or "Model Validation Errors found" not in stderr:
        raise RuntimeError("unexpected corrected-gate failure signature")
    if not all("_value_" in name for name in mismatch_names):
        raise RuntimeError(f"non-value-cache mismatch found: {mismatch_names}")
    if cleanup != "absent":
        raise RuntimeError("remote cleanup was not verified")
    profile = json.loads((raw / "viability-profile.json").read_text())
    if profile.get("components") is not None:
        raise RuntimeError("unexpected profile components despite pre-query failure")
    completeness = (raw / "runtime-completeness.txt").read_text().splitlines()
    if "lib/libQnnHtpNetRunExtensions.so" not in completeness:
        raise RuntimeError("corrected extension not present in runtime completeness proof")

    raw_files = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(raw.iterdir()) if path.is_file()
    }
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "run_id": run.name,
        "classification": "physical_qnn_htp_context_deserialized_model_validation_failure_before_execution",
        "claim_boundary": (
            "The corrected physical bundle loaded its backend extension, initialized QNN HTP on SM8550, "
            "and deserialized the two-graph weight-shared context. Genie then rejected cross-variant value-cache "
            "quantization mismatches before dialog creation/query. No QNN graph execution, generated output, or "
            "performance is claimed."
        ),
        "gate": {
            "bounded_viability_only": True,
            "canonical_campaign": False,
            "max_new_tokens": 16,
            "phone_lock_held_full_adb_lifecycle": True,
            "attempt": 2,
            "retry_performed": True,
            "further_retry_performed": False,
        },
        "device": identity,
        "stage": {
            "local_hash_check_passed": "FAILED" not in (raw / "local-hash-check.txt").read_text(),
            "remote_hash_check_passed": "FAILED" not in (raw / "remote-hash-check.txt").read_text(),
            "runtime_completeness_files": completeness,
            "remote_cleanup_status": cleanup,
        },
        "physical_provider_evidence": physical,
        "outcome": {
            "exit_code": exit_code,
            "result": "failed_model_validation_before_dialog_and_query",
            "validation_error_count": len(mismatch_names),
            "mismatched_tensors": sorted(mismatch_names),
            "mismatch_family": "15 AR128 value-cache inputs plus 15 AR128 value-cache outputs",
            "host_bound_root_cause": (
                "AR1 value-cache outputs are QNN_DATATYPE_FLOAT_16 while matching AR128 cache tensors are "
                "QNN_DATATYPE_UFIXED_POINT_16 with defined scale/offset encodings."
            ),
            "profile_created": True,
            "profile_components": None,
            "output_created": False,
            "graph_execution_observed": False,
            "generated_tokens": 0,
            "stop_reason": "error",
            "output_sanity": {"looks_sensible": None, "issue_notes": None},
        },
        "exact_unblock": (
            "Make all 15 AR1 value-cache outputs datatype/scale/offset identical to the corresponding AR128 "
            "value-cache tensors, then re-convert, recompile, and inspect host artifacts before requesting any new phone retry."
        ),
        "raw_evidence": raw_files,
    }
    (RESULTS / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(RESULTS / "result.json")


if __name__ == "__main__":
    main()
