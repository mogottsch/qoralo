#!/usr/bin/env python3
"""Retain and classify canonical campaign attempt 01 before any harness changes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RESULTS = EXP / "results/android-qnn-physical-campaign-attempt-01"
EXPECTED_CONTEXT = "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394"


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
    if not run.is_dir() or run.parent.name != "campaign-runs":
        raise ValueError(f"unexpected run directory: {run}")

    if RESULTS.exists():
        shutil.rmtree(RESULTS)
    raw = RESULTS / "raw"
    shutil.copytree(run, raw)

    exit_code = int((raw / "exit-code.txt").read_text().strip())
    launcher_exit = int((raw / "launcher-exit-code.txt").read_text().strip())
    stderr = (raw / "runner.stderr").read_text(errors="replace")
    log = (raw / "campaign/genie-verbose.log").read_text(errors="replace")
    cleanup = (raw / "cleanup-status.txt").read_text().strip()
    identity = parse_identity(raw / "identity.txt")
    required_identity = {
        "serial": "R5CW81PR8SY", "manufacturer": "samsung", "model": "SM-S918B",
        "device": "dm3q", "soc": "SM8550", "abi": "arm64-v8a", "boot": "1",
        "verified_boot": "green", "flash_locked": "1",
    }
    if any(identity.get(key) != value for key, value in required_identity.items()):
        raise RuntimeError(f"device identity mismatch: {identity}")
    if exit_code != 1 or launcher_exit != 1:
        raise RuntimeError("campaign failure exit mismatch")
    unknown_count = stderr.count("Unknown engine config key: cache-groups")
    create_failure_count = stderr.count("Failed to create the dialog (-1)")
    dialog_missing_count = stderr.count("Dialog does not exist")
    if unknown_count != 17 or create_failure_count != 17 or dialog_missing_count != 65:
        raise RuntimeError("campaign shared-engine schema failure signature mismatch")
    if log.count("Entering GenieDialog_create") != 17 or log.count("Returning from GenieDialog_create") != 17:
        raise RuntimeError("campaign dialog creation attempt count mismatch")
    forbidden_runtime_markers = {
        "qnn_api_initialized": "qnn-api initialized" in log,
        "htp_provider_initialized": "Initializing HtpProvider" in log,
        "context_deserialized": "Context 1 deserialized" in log,
        "query_entered": "Entering GenieDialog_query" in log,
        "graph_execute": "QnnGraph_execute" in log,
    }
    if any(forbidden_runtime_markers.values()):
        raise RuntimeError(f"campaign advanced beyond claimed boundary: {forbidden_runtime_markers}")

    profile_paths = [raw / "campaign/setup-profile.json", *sorted((raw / "campaign/profiles").glob("*.json"))]
    if len(profile_paths) != 17:
        raise RuntimeError("campaign profile file count mismatch")
    for path in profile_paths:
        profile = json.loads(path.read_text())
        if profile.get("components") is not None:
            raise RuntimeError(f"unexpected campaign profile components: {path}")
    output_paths = list((raw / "campaign/outputs").glob("*")) if (raw / "campaign/outputs").exists() else []
    if output_paths:
        raise RuntimeError("unexpected campaign output despite pre-query failure")
    if cleanup != "absent" or (raw / "process-after.txt").read_text().strip():
        raise RuntimeError("campaign cleanup/process boundary mismatch")
    for check_name in ("local-hash-check.txt", "remote-hash-check.txt"):
        check = (raw / check_name).read_text()
        if "FAILED" in check or ": OK" not in check:
            raise RuntimeError(f"campaign stage hash check failed: {check_name}")
    completeness = (raw / "runtime-completeness.txt").read_text().splitlines()
    if len(completeness) != 8:
        raise RuntimeError("runtime completeness proof mismatch")

    manifest = json.loads((EXP / ".local/campaign-stage/campaign-manifest.json").read_text())
    if manifest["context_sha256"] != EXPECTED_CONTEXT or manifest["request_count"] != 16:
        raise RuntimeError("campaign stage identity mismatch")
    memory_text = (raw / "monitor-and-memory.txt").read_text()
    pids = re.findall(r"pid=(\d+)", memory_text)
    vmhwm = [int(value) for value in re.findall(r"VmHWM:\s+(\d+) kB", memory_text)]
    if not pids or not vmhwm:
        raise RuntimeError("campaign Genie process evidence missing")

    raw_files = {
        str(path.relative_to(raw)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(raw.rglob("*")) if path.is_file()
    }
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "run_id": run.name,
        "classification": "physical_campaign_setup_shared_engine_schema_failure_before_provider_context_or_request",
        "status": "campaign_attempt_01_failed_shared_engine_cache_groups_schema_host_fix_required",
        "claim_boundary": (
            "The approved campaign entered the locked phone lifecycle, passed device identity and local/remote "
            "stage hashes, and started genie-app. Shared-engine extraction then passed the dialog-only cache-groups "
            "key into standalone Engine validation, which rejected it before QNN provider initialization, context "
            "loading, dialog creation, query, or graph execution. The keeper and all 16 request dialogs failed; "
            "all 17 profiles have null components and no output exists. This is physical setup/configuration "
            "failure evidence, not a logical request, campaign performance, or registry result."
        ),
        "gate": {
            "canonical_campaign_authorized": True,
            "phone_lock_held_full_adb_lifecycle": True,
            "attempt": 1, "planned_request_count": 16,
            "context_sha256": EXPECTED_CONTEXT,
            "automatic_retry_performed": False,
        },
        "device": identity,
        "stage": {
            "local_hash_check_passed": True, "remote_hash_check_passed": True,
            "runtime_completeness_files": completeness,
            "remote_cleanup_status": cleanup, "residual_process_observed": False,
        },
        "outcome": {
            "exit_code": exit_code,
            "result": "failed_shared_engine_configuration_schema_before_provider_context_or_query",
            "genie_process_started": True,
            "unknown_cache_groups_engine_key_count": unknown_count,
            "dialog_create_failure_count": create_failure_count,
            "keeper_dialog_created": False,
            "request_dialogs_created": 0,
            "logical_requests_started": 0,
            "profile_files_created": len(profile_paths),
            "profiles_with_components": 0,
            "output_files_created": 0,
            "qnn_provider_initialized": False,
            "context_deserialized": False,
            "graph_execution_observed": False,
            "generated_tokens": 0,
            "output_sanity": {"looks_sensible": None, "issue_notes": None},
        },
        "host_bound_root_cause": (
            "Dialog shared-engine extraction moved the full dialog engine object into standalone Engine config; "
            "cache-groups is accepted at the dialog/QnnHtp orchestration layer but is not an accepted standalone "
            "Engine key."
        ),
        "memory_observations": {
            "genie_pid_observed": True,
            "peak_process_vmhwm_kb_before_failure": max(vmhwm),
            "not_model_or_campaign_memory": True,
        },
        "exact_unblock": (
            "After this evidence is reviewed, host-only derive a Registry-accepted standalone shared-engine object "
            "without moving dialog-only cache-groups into Engine schema, retain cache behavior at the correct level, "
            "rebuild/source-prove/test the stage, and obtain a new explicit handoff before any retry."
        ),
        "raw_evidence": raw_files,
    }
    (RESULTS / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(RESULTS / "result.json")


if __name__ == "__main__":
    main()
