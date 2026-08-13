#!/usr/bin/env python3
"""Assemble the retained failure and non-selected-trial record."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, load_json, sha256_file, write_json


def pin(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing retained evidence: {path}")
    return {
        "path": path.resolve().relative_to(EXPERIMENT_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_record(record: dict[str, Any]) -> None:
    path = EXPERIMENT_ROOT / record["path"]
    if not path.is_file() or path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
        raise RuntimeError(f"retained artifact drifted: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dynamic", type=Path, default=EXPERIMENT_ROOT / "reports/dynamic-qint8-failure.json")
    parser.add_argument("--full-quantization", type=Path, default=EXPERIMENT_ROOT / "reports/screening-full-eligible-quantization.json")
    parser.add_argument("--full-synthesis", type=Path, default=EXPERIMENT_ROOT / "reports/screening-full-eligible-synthesis.json")
    parser.add_argument("--full-analysis", type=Path, default=EXPERIMENT_ROOT / "reports/screening-full-eligible-analysis.json")
    parser.add_argument("--linear-quantization", type=Path, default=EXPERIMENT_ROOT / "reports/screening-linear-only-quantization.json")
    parser.add_argument("--linear-analysis", type=Path, default=EXPERIMENT_ROOT / "reports/screening-linear-only-analysis.json")
    parser.add_argument("--checker", type=Path, default=EXPERIMENT_ROOT / "reports/checker-limitation.json")
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "reports/failures.json")
    args = parser.parse_args()

    dynamic = load_json(args.dynamic)
    full_q, full_s, full_a = load_json(args.full_quantization), load_json(args.full_synthesis), load_json(args.full_analysis)
    linear_q, linear_a = load_json(args.linear_quantization), load_json(args.linear_analysis)
    checker = load_json(args.checker)
    verify_record(dynamic["output"])
    verify_record(full_q["candidate"])
    verify_record(linear_q["candidate"])
    if full_s["status"] != "matched_host_synthesis_passed" or full_a["status"] != "failed":
        raise RuntimeError("full-eligible failure chain is incomplete")
    spectral_key = "spectral_centroid_relative_difference_at_most_0_20"
    failed_pairs = [
        pair for pair in full_a["pairs"]
        if not pair["aggregate_acoustic_comparison"]["checks"][spectral_key]
    ]
    if len(failed_pairs) != 6:
        raise RuntimeError("expected all six full-eligible pairs to retain the spectral-screen failure")
    spectral_values = [
        pair["aggregate_acoustic_comparison"]["metrics"]["spectral_centroid_relative_difference"]
        for pair in failed_pairs
    ]
    if checker["status"] != "reproduced_quantizer_introduced_topological_order_limitation":
        raise RuntimeError("checker limitation evidence drifted")

    report = {
        "schema_version": 1,
        "scope": "Kokoro v1.0 INT8 quantization and host quality-gate preparation",
        "policy": "Failed candidates, rejected screens, and preparation errors are retained rather than silently discarded.",
        "failures": [
            {
                "id": "dynamic-qint8-convinteger-not-implemented",
                "stage": "candidate runtime load",
                "method": dynamic["method"],
                "output": dynamic["output"],
                "result": "rejected_cpu_incompatible",
                "error": dynamic["cpu_probe"]["error"],
                "why_it_matters": "A smaller model that cannot construct a CPU execution session is not CPU-compatible.",
                "resolution": "Reject dynamic QInt8 and use calibrated static S8S8 QDQ.",
                "evidence": [pin(args.dynamic), pin(EXPERIMENT_ROOT / "generated/reproduce-dynamic-failure.log")],
            },
            {
                "id": "static-s8s8-all-eligible-spectral-screen",
                "stage": "supporting host acoustic screen before blind packaging",
                "method": full_q["method"],
                "output": full_q["candidate"],
                "result": "rejected_from_listening_candidate_set",
                "cpu_load_and_synthesis_passed": True,
                "failed_pair_count": len(failed_pairs),
                "failure": {
                    "check": spectral_key,
                    "documented_maximum": 0.20,
                    "observed_minimum": min(spectral_values),
                    "observed_maximum": max(spectral_values),
                },
                "why_it_matters": "The shift was consistent across all six retained utterances; the more conservative generator-excluded recipe removes it while preserving useful size reduction.",
                "resolution": "Keep every eligible Conv/MatMul/Gemm node under /decoder/generator/ on its original FP32 weight input.",
                "subjective_claim": "none; this is an automated candidate-selection screen, not a listening verdict",
                "evidence": [
                    pin(args.full_quantization),
                    pin(args.full_synthesis),
                    pin(args.full_analysis),
                    pin(EXPERIMENT_ROOT / "generated/screening/full-eligible-quantize.log"),
                    pin(EXPERIMENT_ROOT / "generated/screening/full-eligible-synthesis.log"),
                    pin(EXPERIMENT_ROOT / "generated/screening/full-eligible-analysis.log"),
                ],
            },
            {
                "id": "first-calibration-phoneme-normalization",
                "stage": "static calibration input construction",
                "method": "eSpeak NG IPA output mapped through exact archive tokens.txt",
                "result": "preparation_error_fixed_before_candidate_build",
                "error": "A punctuation boundary in the numbers/currency utterance produced embedded newlines that were initially treated as unknown tokens.",
                "resolution": "Remove zero-width IPA tie markers, then normalize all eSpeak whitespace to one space. Every source corpus entry remains whole; this is phoneme normalization, not text splitting.",
                "evidence": [pin(EXPERIMENT_ROOT / "generated/quantize-static-qdq.log")],
            },
            {
                "id": "onnx-checker-loop-outer-scope",
                "stage": "structural validation",
                "result": "checker_not_used_as_executable_integrity_gate",
                "error": checker["candidate"]["error"],
                "source_comparison": "The exact FP32 source passes the pinned checker; ONNX Runtime quantization introduces the outer-graph ordering diagnostic.",
                "resolution": "Retain this structural limitation explicitly and require pinned CPU session construction/inference, sherpa-onnx CPU synthesis, and full WAV decode as the executable host gate. Reassess structural normalization before any later deployment.",
                "evidence": [pin(args.checker), pin(EXPERIMENT_ROOT / "generated/smoke-default.log")],
            },
        ],
        "non_selected_but_valid_trials": [
            {
                "id": "static-s8s8-linear-only",
                "result": "supporting_screen_passed_but_not_selected",
                "model": linear_q["candidate"],
                "reason": "Only 10.95% size reduction versus 46.05% for the selected generator-excluded recipe.",
                "pair_count": len(linear_a["pairs"]),
                "passed_pair_count": sum(int(pair["passed"]) for pair in linear_a["pairs"]),
                "evidence": [pin(args.linear_quantization), pin(args.linear_analysis)],
            }
        ],
        "warnings": [
            {
                "id": "onnxruntime-preprocessing-recommendation",
                "message": "ONNX Runtime 1.22.1 recommends graph preprocessing before quantization.",
                "handling": "No optimizer rewrite was inserted because the control-flow source triggers the checker limitation above. The exact recipe, calibration, graph audit, runtime inference, and synthesis gates are retained instead.",
            },
            {
                "id": "stochastic-model-operators",
                "message": "The exact model contains RandomUniformLike and RandomNormalLike nodes without exposed seeds.",
                "handling": "WAVs are hash-addressed; matched settings and corpus order are fixed. Supporting comparison uses aggregate distributions and ASR, never raw sample alignment. Listening remains decisive.",
            },
        ],
    }
    write_json(args.output, report)
    print(f"failure retention report: {args.output}")


if __name__ == "__main__":
    main()
