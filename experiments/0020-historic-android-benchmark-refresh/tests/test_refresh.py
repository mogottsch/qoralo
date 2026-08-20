from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_audit_covers_every_visible_full_e2e_row():
    registry = json.loads((ROOT / "docs/android-benchmarks/registry.json").read_text())
    audit = json.loads((Path(__file__).resolve().parents[1] / "results/registry-audit.json").read_text())
    expected = {e["id"] for e in registry["entries"] if e["scope"] == "full_e2e"}
    actual = {e["route_id"] for e in audit["rows"]}
    assert actual == expected


def test_no_new_values_when_readiness_blocked():
    audit = json.loads((Path(__file__).resolve().parents[1] / "results/registry-audit.json").read_text())
    assert audit["rerun_blocker"]
    assert all(row["rerun_status"].startswith("not_attempted") for row in audit["rows"])
    assert all(all(value is None for value in row["new_metrics"].values()) for row in audit["rows"])
    assert all(row["new_wav"] is None for row in audit["rows"])


def test_supertonic_priority_is_fail_closed():
    result = json.loads((Path(__file__).resolve().parents[1] / "results/rerun-supertonic-3-int8.json").read_text())
    assert result["route_id"] == "0008-supertonic-cpu-t1"
    assert result["status"] == "blocked_before_phone_rerun"
    assert result["new"]["warm_median_rtf"] is None
    assert result["relative_rtf_change_percent"] is None
