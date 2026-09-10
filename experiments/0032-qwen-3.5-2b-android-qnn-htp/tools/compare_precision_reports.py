#!/usr/bin/env python3
"""Summarize paired QDQ/QNN reports without conflating positions or references."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def summarize_reports(baseline: dict, candidate: dict) -> dict:
    for key in ("token_position", "token_id"):
        if baseline[key] != candidate[key]:
            raise ValueError(f"Cannot compare different {key} values")
    before = baseline["outputs"]
    after = candidate["outputs"]
    if len(before) != len(after):
        raise ValueError("Diagnostic output count differs")
    records = []
    for left, right in zip(before, after):
        for key in ("output_index", "kind", "layer", "layer_type"):
            if left[key] != right[key]:
                raise ValueError(f"Output identity differs at {key}")
        shapes = [row[route]["shape"] for row in (left, right) for route in ("qdq", "qnn_x86")]
        if any(shape != shapes[0] for shape in shapes):
            raise ValueError("Output geometry differs")
        b, c = left["comparison"], right["comparison"]
        records.append({
            "output_index": left["output_index"], "kind": left["kind"],
            "layer": left["layer"], "layer_type": left["layer_type"],
            "baseline_cosine": b["cosine"], "candidate_cosine": c["cosine"],
            "cosine_delta": c["cosine"] - b["cosine"],
            "baseline_max_abs": b["max_abs"], "candidate_max_abs": c["max_abs"],
            "baseline_mean_abs": b["mean_abs"], "candidate_mean_abs": c["mean_abs"],
            "all_finite": all(row[route]["finite"] for row in (left, right) for route in ("qdq", "qnn_x86")),
        })
    hidden = [r for r in records if r["kind"] == "hidden_after_layer"]
    return {
        "schema_version": 1,
        "token_position": baseline["token_position"], "token_id": baseline["token_id"],
        "reference_boundary": "Each route is compared to its own QDQ graph; changing calibration changes the QDQ reference as well as QNN encodings.",
        "baseline_argmax": {k: baseline[k]["argmax"] for k in ("qdq_logits", "qnn_x86_logits")},
        "candidate_argmax": {k: candidate[k]["argmax"] for k in ("qdq_logits", "qnn_x86_logits")},
        "hidden_layers_compared": len(hidden),
        "hidden_layers_with_higher_cosine": sum(r["cosine_delta"] > 0 for r in hidden),
        "all_outputs_finite": all(r["all_finite"] for r in records),
        "outputs": records,
        "claim_limits": [
            "Same-position, zero-initial-state host comparison only; no full-prompt or Android equivalence follows.",
            "Cosine improvement is not a generated-text quality score or proof of exact numerical equivalence.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    b, c = args.baseline.read_bytes(), args.candidate.read_bytes()
    result = summarize_reports(json.loads(b), json.loads(c))
    result["input_report_sha256"] = {
        "baseline": hashlib.sha256(b).hexdigest(), "candidate": hashlib.sha256(c).hexdigest()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
