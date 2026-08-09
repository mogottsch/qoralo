#!/usr/bin/env python3
"""Run all model workers sequentially inside one exclusive preflight grant."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/task-5"
WORKER = ROOT / "tools/model_preflight.py"
GIB = 1024 ** 3
LIMIT_32_GIB = 32 * GIB
SAFETY_MARGIN = 4 * GIB


def meminfo() -> dict[str, int]:
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value, *_ = line.replace(":", "").split()
        if key in {"MemTotal", "MemAvailable", "MemFree", "Cached"}:
            values[key.lower() + "_bytes"] = int(value) * 1024
    return values


def snapshot(path: Path) -> dict[str, object]:
    files = [item for item in path.rglob("*") if item.is_file()] if path.exists() else []
    return {"root": str(path.relative_to(ROOT)), "file_count": len(files),
            "total_bytes": sum(item.stat().st_size for item in files)}


def main() -> None:
    if os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "preflight":
        raise SystemExit("refusing ungated preflights; use run-preflights.sh")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    pythons = {
        "realtime": ROOT / "models/vibevoice-realtime/artifacts/venv/bin/python",
        "pocket": ROOT / "artifacts/setup/pocket-tts/.venv/bin/python",
        "kokoro": ROOT / "artifacts/kokoro/venv/bin/python",
    }
    roots = {
        "realtime": ROOT / "models/vibevoice-realtime/artifacts",
        "pocket": ROOT / "artifacts/setup/pocket-tts",
        "kokoro": ROOT / "artifacts/kokoro",
    }
    baseline = meminfo()
    measurements = []
    for model in ("realtime", "pocket", "kokoro"):
        if not pythons[model].is_file():
            raise SystemExit(f"missing pinned environment for {model}: {pythons[model]}")
        before_files = snapshot(roots[model])
        before_memory = meminfo()
        output = ARTIFACTS / f"{model}.json"
        started = time.monotonic()
        completed = subprocess.run([str(pythons[model]), str(WORKER), model, str(output)],
            env=os.environ | {"PREVIEW_RESOURCE_GRANT_KIND": "preflight"}, timeout=900, check=False)
        after_memory = meminfo()
        if completed.returncode != 0 or not output.is_file():
            raise SystemExit(f"{model} bounded preflight failed with status {completed.returncode}")
        result = json.loads(output.read_text())
        after_files = snapshot(roots[model])
        result.update({
            "subprocess_exit_code": completed.returncode,
            "orchestrator_wall_seconds": time.monotonic() - started,
            "host_memory_before": before_memory,
            "host_memory_after_cleanup": after_memory,
            "cleanup": {"worker_exited": True, "grant_retained_by_sequential_orchestrator": True,
                        "available_memory_delta_bytes": after_memory["memavailable_bytes"] - before_memory["memavailable_bytes"]},
            "lazy_artifacts_before": before_files,
            "lazy_artifacts_after": after_files,
            "lazy_download_bytes": max(0, int(after_files["total_bytes"]) - int(before_files["total_bytes"])),
            "lazy_download_file_count": max(0, int(after_files["file_count"]) - int(before_files["file_count"])),
        })
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        measurements.append(result)

    by_model = {item["model"]: item for item in measurements}
    pocket_peak = int(by_model["pocket"]["peak_process_tree_rss_bytes"])
    kokoro_peak = int(by_model["kokoro"]["peak_process_tree_rss_bytes"])
    combined = pocket_peak + kokoro_peak
    required = combined + SAFETY_MARGIN
    host_total = baseline["memtotal_bytes"]
    effective_limit = min(host_total, LIMIT_32_GIB)
    headroom = effective_limit - required
    safe = headroom > 0
    if not safe:
        raise SystemExit("Pocket plus Kokoro peaks and safety margin do not fit below the 32 GiB/host limit")
    policy_measurements = [{
        "model": item["model"],
        "peak_process_tree_rss_bytes": item["peak_process_tree_rss_bytes"],
        "cold_load_peak_process_tree_rss_bytes": item["phase_peak_process_tree_rss_bytes"].get("cold_load", 0),
        "cold_inference_peak_process_tree_rss_bytes": item["phase_peak_process_tree_rss_bytes"].get("cold_short_inference", 0),
        "warm_inference_peak_process_tree_rss_bytes": item["phase_peak_process_tree_rss_bytes"].get("warm_short_inference", 0),
    } for item in measurements]
    covered = ["smoke-load", "preflight", "generation-realtime", "generation-pocket", "generation-kokoro", "capture", "export", "protocol-revision"]
    policy = {
        "$schema": "../schemas/generation-policy.schema.json", "schema_version": 1, "policy_version": 2,
        "mode": "measured-pocket-kokoro", "compatible_concurrent_sets": [["generation-pocket", "generation-kokoro"]],
        "covered_operations": covered, "host_memory_bytes": host_total, "host_limit_bytes": effective_limit,
        "safety_margin_bytes": SAFETY_MARGIN, "combined_pocket_kokoro_peak_bytes": combined,
        "combined_with_safety_margin_bytes": required, "headroom_bytes": headroom,
        "measurements": policy_measurements,
        "rule": "Capacity is at most two. Exactly one Pocket and one Kokoro generation may overlap. Realtime, every smoke-load, every preflight, capture, export, and protocol revision remain globally exclusive.",
    }
    candidate = ARTIFACTS / "measured-policy.json"
    candidate.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n")
    report = {
        "schema_version": 1, "status": "passed", "created_at": datetime.now(timezone.utc).isoformat(),
        "resource_gate": {"kind": "preflight", "scope": "one grant around all three sequential workers"},
        "baseline_host_memory": baseline, "measurement_order": ["realtime", "pocket", "kokoro"],
        "measurements": measurements, "capacity_arithmetic": {
            "pocket_peak_bytes": pocket_peak, "kokoro_peak_bytes": kokoro_peak, "combined_peak_bytes": combined,
            "safety_margin_bytes": SAFETY_MARGIN, "required_bytes": required, "host_physical_bytes": host_total,
            "ceiling_32_gib_bytes": LIMIT_32_GIB, "effective_limit_bytes": effective_limit,
            "explicit_headroom_bytes": headroom, "safe_for_exactly_pocket_plus_kokoro": safe, "maximum_slots": 2},
        "preflight_audio": "discarded_in_memory; never written, normalized, published, or accepted as a preview",
        "candidate_policy_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
    }
    (ARTIFACTS / "preflight-measurements.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
