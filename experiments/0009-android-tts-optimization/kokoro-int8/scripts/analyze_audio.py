#!/usr/bin/env python3
"""Validate matched WAV evidence and compare non-sample-aligned acoustic behavior."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT_ROOT,
    analyze_wav,
    compare_acoustic_behavior,
    contains_forbidden_mse_key,
    load_corpus,
    load_json,
    sha256_file,
    write_json,
)


def by_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in report["outputs"]}


def verify_wav_pin(item: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    pinned = item["wav"]
    path = EXPERIMENT_ROOT / pinned["path"]
    if not path.is_file() or path.stat().st_size != pinned["bytes"] or sha256_file(path) != pinned["sha256"]:
        raise RuntimeError(f"WAV evidence drifted: {path}")
    measured = analyze_wav(path)
    if measured["sha256"] != pinned["sha256"]:
        raise RuntimeError(f"decoded WAV pin mismatch: {path}")
    return path, measured


def integrity_checks(measured: dict[str, Any]) -> dict[str, bool]:
    integrity, audio_format = measured["integrity"], measured["format"]
    return {
        "full_decode_and_format_valid": (
            audio_format["sample_rate_hz"] == 24000
            and audio_format["channels"] == 1
            and audio_format["sample_width_bytes"] == 2
            and audio_format["frames"] > 0
        ),
        "finite_non_silent": integrity["finite"] and integrity["non_silent"],
        "no_pcm_clipping": integrity["pcm_clip_count"] == 0,
        "duration_between_0_25_and_60_seconds": 0.25 <= audio_format["duration_seconds"] <= 60.0,
        "silent_frame_fraction_below_0_80": integrity["silent_frame_fraction_below_minus_50_dbfs"] < 0.80,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fp32-report", type=Path, default=EXPERIMENT_ROOT / "reports" / "synthesis-fp32.json")
    parser.add_argument("--int8-report", type=Path, default=EXPERIMENT_ROOT / "reports" / "synthesis-int8.json")
    parser.add_argument("--corpus", type=Path, default=EXPERIMENT_ROOT / "corpus.json")
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "reports" / "audio-analysis.json")
    args = parser.parse_args()

    corpus = load_corpus(args.corpus)
    fp32_report, int8_report = load_json(args.fp32_report), load_json(args.int8_report)
    if fp32_report["variant"] != "fp32" or int8_report["variant"] != "int8":
        raise RuntimeError("synthesis reports are not the requested variants")
    shared_fp32 = fp32_report["exact_shared_inputs"]
    shared_int8 = int8_report["exact_shared_inputs"]
    if shared_fp32 != shared_int8 or shared_fp32["corpus_sha256"] != sha256_file(args.corpus):
        raise RuntimeError("FP32 and INT8 synthesis settings or corpus differ")

    fp32_items, int8_items = by_id(fp32_report), by_id(int8_report)
    expected_ids = [item["id"] for item in corpus["evaluation"]]
    if list(fp32_items) != expected_ids or list(int8_items) != expected_ids:
        raise RuntimeError("synthesis evidence is incomplete or reordered")

    pairs: list[dict[str, Any]] = []
    for utterance in corpus["evaluation"]:
        utterance_id = utterance["id"]
        fp32_path, fp32 = verify_wav_pin(fp32_items[utterance_id])
        int8_path, int8 = verify_wav_pin(int8_items[utterance_id])
        fp32_checks, int8_checks = integrity_checks(fp32), integrity_checks(int8)
        behavior = compare_acoustic_behavior(fp32, int8)
        pairs.append(
            {
                "id": utterance_id,
                "text": utterance["text"],
                "fp32": fp32,
                "int8": int8,
                "integrity_checks": {"fp32": fp32_checks, "int8": int8_checks},
                "aggregate_acoustic_comparison": behavior,
                "passed": all(fp32_checks.values()) and all(int8_checks.values()) and behavior["passed"],
            }
        )

    report = {
        "schema_version": 1,
        "status": "passed" if all(pair["passed"] for pair in pairs) else "failed",
        "purpose": "objective integrity and supporting acoustic behavior checks before blind listening",
        "matched_settings": shared_fp32,
        "pairs": pairs,
        "decision_policy": {
            "raw_sample_error": "not_computed_and_not_a_decision_signal",
            "reason": "Kokoro contains random operators; raw sample alignment is unstable and sample error is not perceptual quality.",
            "automated_checks_are_supporting_only": True,
            "subjective_equivalence_claimed": False,
        },
        "speaker_similarity": {
            "status": "not_run",
            "reason": "No voice-specific, calibrated, hash-pinned speaker verifier was available. An uncalibrated embedding score would overstate evidence; SID 3 provenance and blind listening are retained instead.",
        },
    }
    if contains_forbidden_mse_key(report):
        raise AssertionError("report accidentally introduced a forbidden MSE key")
    write_json(args.output, report)
    print(f"audio analysis {report['status']}: {args.output}")


if __name__ == "__main__":
    main()
