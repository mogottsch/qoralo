#!/usr/bin/env python3
"""Derive the retained candidate-selection record from verifiable host evidence."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, load_json, sha256_file, write_json


def evidence_pin(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing selection evidence: {path}")
    return {
        "path": path.resolve().relative_to(EXPERIMENT_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_candidate(report: dict[str, Any]) -> None:
    candidate = report["candidate"]
    path = EXPERIMENT_ROOT / candidate["path"]
    if (
        not path.is_file()
        or path.stat().st_size != candidate["bytes"]
        or sha256_file(path) != candidate["sha256"]
    ):
        raise RuntimeError(f"candidate pin drifted: {path}")


def verify_synthesis(report: dict[str, Any]) -> None:
    model = report["model"]
    model_path = EXPERIMENT_ROOT / model["path"]
    if not model_path.exists():
        # FP32 paths are project-relative; selection inputs here are INT8 only.
        raise RuntimeError(f"screening model is not inside the experiment: {model_path}")
    if model_path.stat().st_size != model["bytes"] or sha256_file(model_path) != model["sha256"]:
        raise RuntimeError(f"screening synthesis model pin drifted: {model_path}")
    for output in report["outputs"]:
        wav = output["wav"]
        path = EXPERIMENT_ROOT / wav["path"]
        if not path.is_file() or path.stat().st_size != wav["bytes"] or sha256_file(path) != wav["sha256"]:
            raise RuntimeError(f"screening WAV pin drifted: {path}")


def acoustic_summary(analysis: dict[str, Any]) -> dict[str, Any]:
    pairs = analysis["pairs"]
    metric_names = (
        "duration_ratio_int8_over_fp32",
        "pitch_median_relative_difference",
        "voiced_fraction_absolute_difference",
        "spectral_centroid_relative_difference",
        "normalized_32_band_power_cosine",
    )
    ranges: dict[str, Any] = {}
    for name in metric_names:
        values = [pair["aggregate_acoustic_comparison"]["metrics"][name] for pair in pairs]
        finite = [value for value in values if value is not None]
        ranges[name] = {"minimum": min(finite), "maximum": max(finite)} if finite else None
    check_failures: dict[str, int] = {}
    for pair in pairs:
        for name, passed in pair["aggregate_acoustic_comparison"]["checks"].items():
            check_failures[name] = check_failures.get(name, 0) + int(not passed)
    return {
        "pair_count": len(pairs),
        "passed_pair_count": sum(int(pair["passed"]) for pair in pairs),
        "failed_pair_count": sum(int(not pair["passed"]) for pair in pairs),
        "metric_ranges": ranges,
        "failed_check_counts": dict(sorted(check_failures.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected-quantization", type=Path, default=EXPERIMENT_ROOT / "reports/quantization-report.json")
    parser.add_argument("--selected-analysis", type=Path, default=EXPERIMENT_ROOT / "reports/audio-analysis.json")
    parser.add_argument("--full-quantization", type=Path, default=EXPERIMENT_ROOT / "reports/screening-full-eligible-quantization.json")
    parser.add_argument("--full-synthesis", type=Path, default=EXPERIMENT_ROOT / "reports/screening-full-eligible-synthesis.json")
    parser.add_argument("--full-analysis", type=Path, default=EXPERIMENT_ROOT / "reports/screening-full-eligible-analysis.json")
    parser.add_argument("--linear-quantization", type=Path, default=EXPERIMENT_ROOT / "reports/screening-linear-only-quantization.json")
    parser.add_argument("--linear-synthesis", type=Path, default=EXPERIMENT_ROOT / "reports/screening-linear-only-synthesis.json")
    parser.add_argument("--linear-analysis", type=Path, default=EXPERIMENT_ROOT / "reports/screening-linear-only-analysis.json")
    parser.add_argument("--dynamic-failure", type=Path, default=EXPERIMENT_ROOT / "reports/dynamic-qint8-failure.json")
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "reports/candidate-selection.json")
    args = parser.parse_args()

    selected_q = load_json(args.selected_quantization)
    selected_a = load_json(args.selected_analysis)
    full_q, full_s, full_a = load_json(args.full_quantization), load_json(args.full_synthesis), load_json(args.full_analysis)
    linear_q, linear_s, linear_a = load_json(args.linear_quantization), load_json(args.linear_synthesis), load_json(args.linear_analysis)
    dynamic = load_json(args.dynamic_failure)
    for report in (selected_q, full_q, linear_q):
        verify_candidate(report)
    for report in (full_s, linear_s):
        verify_synthesis(report)

    selected_summary = acoustic_summary(selected_a)
    full_summary = acoustic_summary(full_a)
    linear_summary = acoustic_summary(linear_a)
    if selected_a["status"] != "passed" or selected_summary["passed_pair_count"] != 6:
        raise RuntimeError("selected candidate did not pass all six retained acoustic screens")
    spectral_check = "spectral_centroid_relative_difference_at_most_0_20"
    if (
        full_a["status"] != "failed"
        or full_summary["failed_pair_count"] != 6
        or full_summary["failed_check_counts"].get(spectral_check) != 6
    ):
        raise RuntimeError("all-eligible candidate no longer has the retained six-pair spectral rejection")
    if linear_a["status"] != "passed" or linear_summary["passed_pair_count"] != 6:
        raise RuntimeError("linear-only candidate no longer passes its retained supporting screen")
    if dynamic["status"] != "reproduced_rejected_cpu_incompatible":
        raise RuntimeError("dynamic-QInt8 failure evidence drifted")

    def candidate_record(report: dict[str, Any], summary: dict[str, Any], disposition: str, rationale: str) -> dict[str, Any]:
        candidate = report["candidate"]
        return {
            "name": report["candidate_name"],
            "method": report["method"],
            "model": {
                "path": candidate["path"],
                "bytes": candidate["bytes"],
                "sha256": candidate["sha256"],
                "size_reduction_bytes": candidate["size_reduction_bytes"],
                "size_reduction_fraction": candidate["size_reduction_fraction"],
            },
            "cpu_runtime_probe_passed": report["status"] == "candidate_built_host_cpu_probe_passed",
            "acoustic_screen": summary,
            "disposition": disposition,
            "rationale": rationale,
        }

    evidence_paths = [
        args.selected_quantization,
        args.selected_analysis,
        args.full_quantization,
        args.full_synthesis,
        args.full_analysis,
        args.linear_quantization,
        args.linear_synthesis,
        args.linear_analysis,
        args.dynamic_failure,
        EXPERIMENT_ROOT / "quantization-config.json",
        EXPERIMENT_ROOT / "screening/full-eligible-s8s8.json",
        EXPERIMENT_ROOT / "screening/linear-only-s8s8.json",
    ]
    report = {
        "schema_version": 1,
        "status": "selected_candidate_ready_for_blind_listening",
        "decision_scope": "host candidate selection before subjective listening; not an Android benchmark or a subjective equivalence verdict",
        "source_model": {
            "deployment_variant": "kokoro-multi-lang-v1_0",
            "bytes": selected_q["candidate"]["source_model_bytes"],
            "sha256": selected_q["candidate"]["source_model_sha256"],
            "speaker_id": 3,
            "speaker": "af_heart",
        },
        "attempts": {
            "dynamic_default_qint8": {
                "method": dynamic["method"],
                "model": dynamic["output"],
                "disposition": "rejected_cpu_incompatible",
                "rationale": dynamic["cpu_probe"]["error"]["message"],
            },
            "static_s8s8_all_eligible": candidate_record(
                full_q,
                full_summary,
                "rejected_before_listening_on_supporting_acoustic_screen",
                "All six pairs exceeded the documented 0.20 spectral-centroid relative-difference limit; automated rejection does not assert subjective quality.",
            ),
            "static_s8s8_linear_only": candidate_record(
                linear_q,
                linear_summary,
                "not_selected_lower_size_reduction",
                "All six supporting screens passed, but the model was only about 11% smaller than FP32.",
            ),
            "static_s8s8_generator_excluded": candidate_record(
                selected_q,
                selected_summary,
                "selected_for_blind_listening_pending_user_verdict",
                "All six supporting screens passed with about 46% size reduction; subjective acceptability remains for Moritz to decide blindly.",
            ),
        },
        "selected_candidate_sha256": selected_q["candidate"]["sha256"],
        "selected_candidate_subjective_status": "awaiting_user_listening",
        "raw_sample_error_used": False,
        "android_performance_used": False,
        "evidence": [evidence_pin(path) for path in evidence_paths],
    }
    write_json(args.output, report)
    print(f"candidate selection retained: {args.output}")


if __name__ == "__main__":
    main()
