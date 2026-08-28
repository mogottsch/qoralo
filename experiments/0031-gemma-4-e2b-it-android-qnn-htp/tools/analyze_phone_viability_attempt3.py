#!/usr/bin/env python3
"""Retain and classify the cache-corrected physical Gemma gate (attempt 03)."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RESULTS = EXP / "results/android-qnn-physical-viability-attempt-03"
EXPECTED_CONTEXT = "a1d52d0087a0719d5907a98d99e8bc5996b699c9cf8f3a21b301588b9f51cc44"


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
        "launcher.stdout", "launcher.stderr", "launcher-exit-code.txt", "genie-verbose.log",
        "viability-profile.json", "pull-viability-output.txt.txt", "pull-viability-profile.json.txt",
        "pull-genie-verbose.log.txt", "process-after.txt", "cleanup.stdout", "cleanup.stderr",
        "cleanup-status.txt",
    ]
    for name in retain:
        source = run / name
        if source.exists():
            shutil.copy2(source, raw / name)

    exit_code = int((raw / "exit-code.txt").read_text().strip())
    launcher_exit = int((raw / "launcher-exit-code.txt").read_text().strip())
    stderr = (raw / "runner.stderr").read_text(errors="replace")
    log = (raw / "genie-verbose.log").read_text(errors="replace")
    cleanup = (raw / "cleanup-status.txt").read_text().strip()
    identity = parse_identity(raw / "identity.txt")
    required_identity = {
        "serial": "R5CW81PR8SY", "manufacturer": "samsung", "model": "SM-S918B",
        "device": "dm3q", "soc": "SM8550", "abi": "arm64-v8a", "boot": "1",
        "verified_boot": "green", "flash_locked": "1",
    }
    if any(identity.get(key) != value for key, value in required_identity.items()):
        raise RuntimeError(f"device identity mismatch: {identity}")

    stage_result = json.loads((EXP / "results/cache-corrected-phone-stage/result.json").read_text())
    if stage_result["stage"]["corrected_context_sha256"] != EXPECTED_CONTEXT:
        raise RuntimeError("durable corrected stage identity mismatch")
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
        raise RuntimeError(f"missing physical evidence: {physical}")

    expected_failure = {
        "corrected_cache_validation_error_absent": (
            "Non-identical quantization parameters" not in stderr
            and "Model Validation Errors found" not in stderr
            and "Non-identical quantization parameters" not in log
        ),
        "global_cos_unconnected": (
            'Unconnected input tensor "position_ids_global_cos"' in log
        ),
        "global_sin_unconnected": (
            'Unconnected input tensor "position_ids_global_sin"' in log
        ),
        "generic_cos_missing": "Tensor not found: position_ids_cos" in log,
        "generic_sin_missing": "Tensor not found: position_ids_sin" in log,
        "io_discovery_failed": "Could not find I/O tensors in loaded graphs" in stderr,
        "dialog_creation_failed": "Failed to create the dialog (-1)" in stderr,
    }
    if exit_code != 1 or launcher_exit != 1 or not all(expected_failure.values()):
        raise RuntimeError(f"unexpected attempt-03 failure: {expected_failure}")
    if cleanup != "absent" or (raw / "process-after.txt").read_text().strip():
        raise RuntimeError("scoped cleanup or process termination was not verified")
    profile = json.loads((raw / "viability-profile.json").read_text())
    if profile.get("components") is not None:
        raise RuntimeError("unexpected profile components despite pre-dialog failure")
    completeness = (raw / "runtime-completeness.txt").read_text().splitlines()
    if len(completeness) != 8 or "lib/libQnnHtpNetRunExtensions.so" not in completeness:
        raise RuntimeError("runtime completeness proof mismatch")
    local_check = (raw / "local-hash-check.txt").read_text()
    remote_check = (raw / "remote-hash-check.txt").read_text()
    if "FAILED" in local_check or "FAILED" in remote_check or ": OK" not in local_check or ": OK" not in remote_check:
        raise RuntimeError("local or remote hash validation failed")

    raw_files = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(raw.iterdir()) if path.is_file()
    }
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "run_id": run.name,
        "classification": "physical_qnn_htp_context_deserialized_io_tensor_discovery_failure_before_execution",
        "status": "phone_attempt_03_failed_position_id_tensor_name_binding_host_fix_required",
        "claim_boundary": (
            "The cache-corrected physical bundle passed local/remote hashes, loaded its extension, initialized "
            "QNN HTP on the verified SM8550 phone, and deserialized the two-graph weight-shared context. The prior "
            "30 cache-quantization validation errors were absent. Genie then failed dialog creation because the "
            "context exposes position_ids_global_cos/sin while runtime positional binding searched for "
            "position_ids_cos/sin. No graph execution, generated output, or performance is claimed."
        ),
        "gate": {
            "bounded_viability_only": True,
            "canonical_campaign": False,
            "max_new_tokens": 16,
            "phone_lock_held_full_adb_lifecycle": True,
            "attempt": 3,
            "corrected_context_sha256": EXPECTED_CONTEXT,
            "further_retry_performed": False,
        },
        "device": identity,
        "stage": {
            "local_hash_check_passed": True,
            "remote_hash_check_passed": True,
            "runtime_completeness_files": completeness,
            "remote_cleanup_status": cleanup,
            "residual_process_observed": False,
        },
        "physical_provider_evidence": physical,
        "outcome": {
            "exit_code": exit_code,
            "result": "failed_io_tensor_discovery_before_dialog_and_graph_execution",
            "prior_cache_quantization_validation_error_count": 0,
            "prior_cache_quantization_blocker_cleared_on_physical_load": True,
            "unconnected_context_inputs": ["position_ids_global_cos", "position_ids_global_sin"],
            "runtime_requested_missing_inputs": ["position_ids_cos", "position_ids_sin"],
            "host_bound_root_cause": (
                "The first positional-encoding entry has no prefix, so Genie searches for position_ids_cos/sin; "
                "the transformed context names the corresponding global inputs position_ids_global_cos/sin."
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
            "Correct and host-validate the Genie positional-encoding-to-context tensor-name binding for the "
            "global cos/sin inputs, rebuild/hash the private config/stage, report for review, and obtain a new "
            "explicit phone handoff before any retry."
        ),
        "raw_evidence": raw_files,
    }
    (RESULTS / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(RESULTS / "result.json")


if __name__ == "__main__":
    main()
