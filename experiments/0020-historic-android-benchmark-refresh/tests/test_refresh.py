from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_audit_covers_every_visible_full_e2e_row():
    commit = "df11008fa808f9ba4ac5dad1f912863af13cbee9"
    registry = json.loads(subprocess.check_output(["git", "show", f"{commit}:docs/android-benchmarks/registry.json"], cwd=ROOT, text=True))
    audit = json.loads((Path(__file__).resolve().parents[1] / "results/registry-audit.json").read_text())
    expected = {e["id"] for e in registry["entries"] if e["scope"] == "full_e2e"}
    actual = {e["route_id"] for e in audit["rows"]}
    assert len(expected) == 26
    assert "0020-supertonic-cpu-refresh" not in expected
    assert actual == expected


def test_only_exact_completed_route_has_new_values():
    audit = json.loads((Path(__file__).resolve().parents[1] / "results/registry-audit.json").read_text())
    completed = [row for row in audit["rows"] if row["rerun_status"] == "complete"]
    assert [row["route_id"] for row in completed] == ["0008-supertonic-cpu-t1"]
    assert completed[0]["new_metrics"]["warm_median_rtf"] == 0.39308571289407546
    assert completed[0]["new_wav"]["sha256"] == "1cf003d55c81e49983cbe385fdb98868ccdf4b1a6b1482e21bab020c7567ee6e"
    for row in audit["rows"]:
        if row["route_id"] == "0008-supertonic-cpu-t1":
            continue
        assert all(value is None for value in row["new_metrics"].values())
        assert row["new_wav"] is None


def test_supertonic_refresh_keeps_old_and_new_and_flags_setup():
    result = json.loads((Path(__file__).resolve().parents[1] / "results/supertonic-3-int8-cpu-refresh.json").read_text())
    assert result["route_id"] == "0008-supertonic-cpu-t1"
    assert result["status"] == "exact_historical_contract_rerun_complete"
    assert result["old"]["warm_median_rtf"] == 0.3703028479158501
    assert result["new"]["warm_median_rtf"] == 0.39308571289407546
    assert result["comparison"]["rtf_change_over_10_percent"] is False
    assert result["comparison"]["setup_change_over_10_percent"] is True
    review = result["representative_wav"]["listening_review"]
    assert review["status"] == "accepted"
    assert review["reviewer"] == "Moritz"
    assert review["date"] == "2026-08-20"
    assert review["sample_sha256"] == result["representative_wav"]["sha256"]
