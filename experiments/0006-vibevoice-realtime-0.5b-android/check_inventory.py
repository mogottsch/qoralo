#!/usr/bin/env python3
"""Fail-closed structural and arithmetic checks for the committed inventory."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load() -> tuple[dict, dict]:
    return (
        json.loads((ROOT / "feasibility-inventory.json").read_text()),
        json.loads((ROOT / "feasibility-inventory.schema.json").read_text()),
    )


def check_structure(d: dict, schema: dict) -> None:
    missing = set(schema["required"]) - set(d)
    assert not missing, f"inventory missing keys: {sorted(missing)}"
    assert set(d) <= set(schema["properties"]), "inventory has undeclared top-level keys"
    assert d["$schema"] == "./feasibility-inventory.schema.json"
    assert d["schema_version"] == 1
    assert d["status"] == "recommendations_only_no_conversion_started"
    assert d["streaming_state"]["official_state_is_fixed_size"] is False
    assert d["decision"]["android_feasible"] == "unknown"
    assert d["decision"]["listening_quality"] == "pending_user_review"
    assert len(d["sources"]) >= 8 and all("supports" in x and ("url" in x or "path" in x) for x in d["sources"])


def check_arithmetic(d: dict) -> None:
    c = d["candidate"]
    assert c["checkpoint_parameters"] == 1_017_626_724
    assert c["inactive_duplicated_parameters"] == 151_936 * 896 == 136_134_656
    assert c["active_parameters"] == c["checkpoint_parameters"] - c["inactive_duplicated_parameters"]
    assert sum(x["checkpoint_parameters"] for x in d["components"]) == c["checkpoint_parameters"]
    assert sum(x["active_parameters"] for x in d["components"]) == c["active_parameters"]
    assert sum(x["inactive_duplicated_parameters"] for x in d["components"]) == c["inactive_duplicated_parameters"]

    estimates = {x["scheme"]: x for x in d["package_estimates"]["estimates"]}
    n = c["active_parameters"]
    assert estimates["fp16"]["lower_bytes"] == estimates["fp16"]["upper_bytes"] == n * 2
    assert estimates["int8_ideal"]["lower_bytes"] == estimates["int8_ideal"]["upper_bytes"] == n
    ideal4 = math.ceil(n / 2)
    assert estimates["mixed_groupwise_int4"]["lower_bytes"] == math.ceil(ideal4 * 1.03)
    assert estimates["mixed_groupwise_int4"]["upper_bytes"] == math.ceil(ideal4 * 1.12)
    assert all(x["runtime_support_claimed"] is False for x in estimates.values())

    # 24 layers * K/V * two KV heads * 8192 tokens * 64 head dim * BF16.
    assert 24 * 2 * 1 * 2 * 8192 * 64 * 2 == 100_663_296
    assert math.prod([8, 5, 5, 4, 2, 2]) == 3200


def check_recommendations(d: dict) -> None:
    qnn = next(x for x in d["runtime_recommendations"] if x["runtime"] == "Qualcomm QNN/HTP")
    assert qnn["required_schemes"] == ["8a8w", "16a8w", "16a4w"]
    evidence = " ".join(qnn["required_evidence_per_scheme"])
    for word in ("partition", "fallback", "transfers", "error", "latency"):
        assert word in evidence
    assert all("approval" in x["approval_gate"].lower() for x in d["runtime_recommendations"])
    assert "Begin no conversion" in d["decision"]["next_action"]


def main() -> None:
    d, schema = load()
    check_structure(d, schema)
    check_arithmetic(d)
    check_recommendations(d)
    print("inventory schema/structure and arithmetic checks: PASS")


if __name__ == "__main__":
    main()
