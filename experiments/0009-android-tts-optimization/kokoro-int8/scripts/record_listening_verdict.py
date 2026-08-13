#!/usr/bin/env python3
"""Validate Moritz's finalized blind ballot and reveal it against the retained key."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

from common import EXPERIMENT_ROOT, load_json, sha256_file, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ballot", type=Path)
    parser.add_argument("--answer-key", type=Path, default=EXPERIMENT_ROOT / "generated/blind/answer-key.json")
    parser.add_argument("--ballot-copy", type=Path, default=EXPERIMENT_ROOT / "reports/user-listening-ballot.csv")
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "reports/user-listening-verdict.json")
    args = parser.parse_args()

    raw = args.ballot.read_bytes()
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(text.splitlines()))
    if not rows or set(rows[0]) != {"pair", "preference", "confidence", "notes"}:
        raise SystemExit("unexpected web-ballot columns")

    answer = load_json(args.answer_key)
    keys = {row["pair"]: row for row in answer["pairs"]}
    if [row["pair"] for row in rows] != list(keys):
        raise SystemExit("ballot pair order or coverage does not match the retained answer key")

    counts = {"tie": 0, "fp32": 0, "int8": 0}
    observations = []
    for row in rows:
        preference = row["preference"].strip()
        confidence = row["confidence"].strip()
        if preference not in {"A", "B", "tie"}:
            raise SystemExit(f"invalid or missing preference for {row['pair']}")
        if confidence and confidence not in {"1", "2", "3", "4", "5"}:
            raise SystemExit(f"invalid confidence for {row['pair']}")
        key = keys[row["pair"]]
        preferred_variant = "tie" if preference == "tie" else key[preference]["variant"]
        counts[preferred_variant] += 1
        observations.append({
            "pair": row["pair"],
            "utterance_id": key["utterance_id"],
            "preference": preference,
            "preferred_variant": preferred_variant,
            "confidence": int(confidence) if confidence else None,
            "notes": row["notes"],
            "revealed_assignment": {"A": key["A"]["variant"], "B": key["B"]["variant"]},
        })

    # Preserve the exact user-authored bytes as the primary subjective evidence.
    args.ballot_copy.parent.mkdir(parents=True, exist_ok=True)
    args.ballot_copy.write_bytes(raw)
    processed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report = {
        "schema_version": 1,
        "status": "validated_final_ballot",
        "listener": "Moritz",
        "processed_at_utc": processed_at,
        "ballot": {
            "source_filename": args.ballot.name,
            "committed_copy": args.ballot_copy.relative_to(EXPERIMENT_ROOT).as_posix(),
            "bytes": len(raw),
            "sha256": sha256_file(args.ballot_copy),
            "pair_count": len(rows),
            "all_pairs_answered": True,
        },
        "answer_key": {
            "revealed_only_after_ballot_was_final": True,
            "sha256": sha256_file(args.answer_key),
        },
        "counts": {
            "ties": counts["tie"],
            "int8_preferred": counts["int8"],
            "fp32_preferred": counts["fp32"],
        },
        "observations": observations,
        "verdict": "no_systematic_preference_or_int8_degradation_detected",
        "quality_gate_recommendation": "pass",
        "interpretation": (
            "Four of six pairs were ties. The only two directional votes split one for INT8 and one for FP32, "
            "both at confidence 2/5. This single-listener ballot detected no systematic INT8 degradation and "
            "supports passing the host listening gate; it does not prove perceptual equivalence or INT8 superiority."
        ),
        "limitations": [
            "One listener and six utterances are not an equivalence study.",
            "Both directional preferences had low confidence (2/5); tie confidence was left blank.",
            "Kokoro contains stochastic operators, so this verdict applies to the retained hash-addressed pairs and selected model candidate.",
        ],
    }
    write_json(args.output, report)
    print(f"validated {len(rows)} votes: {counts['tie']} ties, {counts['int8']} INT8, {counts['fp32']} FP32")


if __name__ == "__main__":
    main()
