#!/usr/bin/env python3
"""Create the offline campaign checkpoint after an external device disconnect."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path: Path, root: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    completed_root = args.checkpoint_root / "completed"
    completed = []
    for directory in sorted(path for path in completed_root.iterdir() if path.is_dir()):
        analysis_path = directory / "analysis.json"
        analysis = json.loads(analysis_path.read_text())
        completed.append({
            "run": directory.name,
            "arm": analysis["arm"],
            "analysis": record(analysis_path, args.checkpoint_root),
            "setup_seconds": analysis["setup"]["seconds"],
            "first_rtf": analysis["first"]["rtf"],
            "warm_median_rtf": analysis["warm"]["median_rtf"],
            "wav_sha256": analysis["determinism"]["sha256"],
            "reference_behavior_all_match": analysis["reference_behavior"]["all_match_reference"],
            "stage_hashes_equal": analysis["safety"]["local_remote_stage_hashes_equal"],
            "runner_exit": analysis["safety"]["runner_exit"],
            "cleanup_exit": analysis["safety"]["cleanup_exit"],
            "cleanup_verified": analysis["safety"]["cleanup_verified"],
            "listening": analysis["listening"],
        })
    source = [item for item in completed if item["arm"] == "source"]
    context = [item for item in completed if item["arm"] == "context"]
    if len(source) != 3 or len(context) != 1:
        raise SystemExit("unexpected completed boundary")
    raw_root = args.checkpoint_root / "interrupted-context-2/raw"
    raw = [record(path, args.checkpoint_root) for path in sorted(raw_root.rglob("*")) if path.is_file()]
    required = {item["path"] for item in raw}
    if not any(path.endswith("cleanup-proof.txt") for path in required):
        raise SystemExit("misleading historical cleanup proof must be preserved byte-for-byte")
    local_manifest = (raw_root / "local-stage-sha256.txt").read_text()
    remote_manifest = (raw_root / "remote-stage-sha256.txt").read_text()
    if local_manifest != remote_manifest:
        raise SystemExit("interrupted run did not reach verified stage equality")
    result = {
        "schema_version": 1,
        "date": "2026-08-23",
        "status": "paused_external_device_disconnect_cleanup_pending",
        "route": "pocket-fixed-alba-text64-cache512-canonical-v2-0024-reconstruction-derivative",
        "completed_boundary": {
            "source_runs_complete": 3,
            "source_runs_required": 3,
            "context_runs_complete": 1,
            "context_runs_required": 3,
            "completed_runs": completed,
            "source_wav_deterministic": len({item["wav_sha256"] for item in source}) == 1,
            "context_run_1_structurally_valid": True,
            "context_wav_status": context[0]["listening"],
        },
        "interruption": {
            "run": "phone-context-20260823T085809Z-225310",
            "arm": "context",
            "classification": "external_device_disconnect_incomplete_excluded",
            "last_verified_gate": "Full local-versus-remote stage manifest equality after exact identity and context source-absence gates.",
            "runner_adb_exit_code": int((raw_root / "runner.exit").read_text()),
            "result_json_present": (raw_root / "result.json").exists(),
            "wav_present": any(raw_root.rglob("*.wav")),
            "measurement_included": False,
            "remote_root": "/data/local/tmp/experiment-0024-pocket-context-context-20260823T085809Z-225310",
            "cleanup_status": "pending_device_reconnect",
            "cleanup_command_exit": int((raw_root / "cleanup.exit").read_text()),
            "preserved_cleanup_proof": {
                "path": "interrupted-context-2/raw/cleanup-proof.txt",
                "contents": (raw_root / "cleanup-proof.txt").read_text().strip(),
                "valid": False,
                "reason": "The old two-state gate interpreted ADB transport failure as remote absence. Authoritative status is pending_device_reconnect."
            },
            "local_remote_stage_hashes_equal": True,
            "raw_local_evidence": raw,
        },
        "resume_contract": {
            "before_any_new_staging_or_run": "Acquire phone.lock nonblockingly, revalidate exact authorized device/transport, remove the exact pending remote root, and verify it is absent using the tri-state transport-aware cleanup gate.",
            "resume_run": "Use a fresh context run ID; never reuse or include interrupted context run 2.",
            "remaining": ["context benchmark run 2 of 3", "context benchmark run 3 of 3", "separate source physical proof", "separate context physical proof"],
        },
        "phone_lock_released": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "completed_boundary": result["completed_boundary"],
                      "interruption": {key: result["interruption"][key] for key in
                                       ("classification", "last_verified_gate", "runner_adb_exit_code", "remote_root", "cleanup_status")}}, indent=2))


if __name__ == "__main__":
    main()
