#!/usr/bin/env python3
"""Deterministically audit visible full-E2E registry rows without modifying them."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "docs/android-benchmarks/registry.json"
OUT = Path(__file__).resolve().parents[1] / "results/registry-audit.json"


def main() -> None:
    registry = json.loads(REGISTRY.read_text())
    rows = []
    fields = ("load_seconds", "cold_rtf", "warm_median_rtf", "peak_pss_bytes", "peak_vm_hwm_bytes")
    for e in registry["entries"]:
        if e["scope"] != "full_e2e":
            continue
        missing = []
        if e["wav"] is None:
            missing.append("wav")
        for field in fields:
            if e["metrics"][field] is None:
                missing.append(field)
        if e["threads"] is None:
            missing.append("threads")
        rows.append({
            "route_id": e["id"],
            "experiment": e["experiment"],
            "model": e["model"],
            "route": e["route"],
            "historical_status": e["attempt_status"],
            "provider": e["provider"],
            "threads": e["threads"],
            "model_identity": e["model_identity"],
            "quantization": e["quantization"],
            "old_metrics": e["metrics"],
            "old_wav": e["wav"],
            "missing_fields": missing,
            "rerun_status": "not_attempted; device readiness blocked before phone execution",
            "new_metrics": {field: None for field in fields},
            "new_wav": None,
            "relative_rtf_change_percent": None,
            "drift_flag": None,
        })
    payload = {
        "schema_version": 1,
        "experiment": "0020",
        "registry_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scope": "all visible full-E2E registry rows",
        "generated_by": "experiments/0020-historic-android-benchmark-refresh/tools/audit_registry.py",
        "rerun_blocker": "device readiness observed zero Android devices before any phone launch",
        "comparison_policy": {"rtf_denominator": "actual decoded audio duration", "relative_change_flag_percent": 10, "material_difference_requires_flag": True},
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"audited {len(rows)} full-E2E rows")


if __name__ == "__main__":
    main()
