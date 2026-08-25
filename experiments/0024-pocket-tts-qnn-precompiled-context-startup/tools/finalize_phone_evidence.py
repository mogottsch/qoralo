#!/usr/bin/env python3
"""Validate and hash-bind the completed 0024 phone evidence package."""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    source = result["comparison"]["source"]
    context = result["comparison"]["context"]
    if source["cold_process_count"] != 3 or context["cold_process_count"] != 3:
        raise SystemExit("cold distribution incomplete")
    if source["wav_sha256"] != ["028f8a1e1861f8004619294738d9aa14509b2c3e5e5e626d99113700ab574241"]:
        raise SystemExit("source WAV drift")
    if context["wav_sha256"] != ["7c3fc41d320e391ed39c10398f9c013d01cba93b9c733d3df546d31a0d006d81"]:
        raise SystemExit("context WAV drift")
    for arm in ("source", "context"):
        proof = result["physical_proof"][arm]
        aggregate = proof["aggregate"]
        if aggregate["provider_events"] != {"QNNExecutionProvider": 344}:
            raise SystemExit(f"{arm} provider proof failed")
        if not aggregate["all_invoked_calls_qnn_only"] or not aggregate["all_physical_event_counts_match_qnn"]:
            raise SystemExit(f"{arm} physical proof failed")
        archive = args.root / "physical" / arm / "profiles.tar.gz"
        with tarfile.open(archive, "r:gz") as stream:
            members = [member for member in stream.getmembers() if member.isfile()]
        if len(members) != 24:
            raise SystemExit(f"{arm} profile archive count: {len(members)}")
    cleanup = result["campaign_history"]["pending_root_cleanup_resume"]
    if cleanup["tri_state_status"] != "verified_absent" or not cleanup["phone_lock_released"]:
        raise SystemExit("pending root cleanup was not closed")
    records: list[dict[str, Any]] = []
    for path in sorted(args.root.rglob("*")):
        if path.is_file() and path.resolve() != args.output.resolve():
            records.append({"path": str(path.relative_to(args.root)), "bytes": path.stat().st_size,
                            "sha256": sha(path)})
    result_record = {"path": str(args.result), "bytes": args.result.stat().st_size, "sha256": sha(args.result)}
    manifest = {
        "schema_version": 1,
        "status": "complete_hash_bound_phone_evidence",
        "result": result_record,
        "file_count": len(records),
        "file_bytes_sum": sum(record["bytes"] for record in records),
        "files": records,
        "validation": {
            "source_cold_processes": 3,
            "context_cold_processes": 3,
            "profiled_proofs": ["source", "context"],
            "profile_files_per_proof": 24,
            "pending_remote_root_cleanup": "verified_absent",
            "source_listening": "not_reviewed",
            "context_listening": "not_reviewed",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({key: manifest[key] for key in ("status", "file_count", "file_bytes_sum", "validation")}, indent=2))


if __name__ == "__main__":
    main()
