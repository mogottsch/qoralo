#!/usr/bin/env python3
"""Deterministically audit visible full-E2E registry rows without modifying them."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REGISTRY_COMMIT = "df11008fa808f9ba4ac5dad1f912863af13cbee9"
REGISTRY_PATH = "docs/android-benchmarks/registry.json"
OUT = Path(__file__).resolve().parents[1] / "results/registry-audit.json"


def main() -> None:
    registry = json.loads(subprocess.check_output(["git", "show", f"{REGISTRY_COMMIT}:{REGISTRY_PATH}"], cwd=ROOT, text=True))
    rows = []
    refresh_path = Path(__file__).resolve().parents[1] / "results/supertonic-3-int8-cpu-refresh.json"
    refresh = json.loads(refresh_path.read_text()) if refresh_path.exists() else None
    fields = ("load_seconds", "cold_rtf", "warm_median_rtf", "peak_pss_bytes", "peak_vm_hwm_bytes")
    for e in registry["entries"]:
        if e["scope"] != "full_e2e" or e["id"] == "0020-supertonic-cpu-refresh":
            # 0020 is nested provenance on 0008, never a separate visible route.
            continue
        missing = []
        if e["wav"] is None:
            missing.append("wav")
        for field in fields:
            if e["metrics"][field] is None:
                missing.append(field)
        if e["threads"] is None:
            missing.append("threads")
        completed = refresh if refresh is not None and refresh["route_id"] == e["id"] else None
        new_metrics = {field: None for field in fields}
        if completed:
            new_metrics = {
                "load_seconds": completed["new"]["setup_seconds"],
                "cold_rtf": completed["new"]["cold_rtf"],
                "warm_median_rtf": completed["new"]["warm_median_rtf"],
                "peak_pss_bytes": completed["new"]["peak_sampled_pss_bytes"],
                "peak_vm_hwm_bytes": completed["new"]["peak_vm_hwm_bytes"],
            }
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
            "rerun_status": "complete" if completed else "not_attempted; no exact rerun evidence in this refresh",
            "remeasured_at": completed["remeasured_at"] if completed else None,
            "refresh_provenance": "results/supertonic-3-int8-cpu-refresh.json" if completed else None,
            "new_metrics": new_metrics,
            "new_wav": completed["representative_wav"] if completed else None,
            "relative_rtf_change_percent": completed["comparison"]["warm_median_rtf_relative_change_percent"] if completed else None,
            "drift_flag": completed["comparison"]["rtf_change_over_10_percent"] if completed else None,
        })
    payload = {
        "schema_version": 1,
        "experiment": "0020",
        "registry_commit": REGISTRY_COMMIT,
        "registry_path": REGISTRY_PATH,
        "scope": "all visible full-E2E registry rows",
        "generated_by": "experiments/0020-historic-android-benchmark-refresh/tools/audit_registry.py",
        "rerun_blocker": None,
        "comparison_policy": {"rtf_denominator": "actual decoded audio duration", "relative_change_flag_percent": 10, "material_difference_requires_flag": True},
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"audited {len(rows)} full-E2E rows")


if __name__ == "__main__":
    main()
