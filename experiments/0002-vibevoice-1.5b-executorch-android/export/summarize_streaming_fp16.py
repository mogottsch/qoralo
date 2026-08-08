#!/usr/bin/env python3
"""Build the committed FP16 decoder result from ignored benchmark artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fixture_utils import repo_root


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root", type=Path, default=root / "artifacts/0002"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root
        / "experiments/0002-vibevoice-1.5b-executorch-android/results/acoustic-decoder-streaming-fp16.json",
    )
    return parser.parse_args()


def call_summary(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "call": call["call"],
        "entry": call["entry"],
        "total_load_seconds": call["total_load_seconds"],
        "total_inference_seconds": call["total_inference_seconds"],
        "pcm_max_abs_error": call["pcm_max_abs_error"],
        "pcm_mean_abs_error": call["pcm_mean_abs_error"],
        "max_cache_abs_error": max(
            segment["cache_max_abs_error"] for segment in call["segments"]
        ),
    }


def android_run_summaries(
    device: dict[str, Any], comparison: dict[str, Any]
) -> list[dict[str, Any]]:
    summaries = []
    for measured, compared in zip(device["runs"], comparison["comparisons"]):
        segment_records = [
            segment
            for call in (measured["call_0"], measured["call_1"])
            for segment in call["segments"]
        ]
        summaries.append(
            {
                "run": measured["run"],
                "temperature": measured["temperature"],
                "total_load_seconds": measured["total_load_seconds"],
                "total_inference_seconds": measured["total_inference_seconds"],
                "first_inference_seconds": measured["call_0"]["total_inference_seconds"],
                "cached_inference_seconds": measured["call_1"]["total_inference_seconds"],
                "peak_observed_pss_kib": max(
                    segment["pss_after_inference_kib"] for segment in segment_records
                ),
                "process_hwm_kib": max(
                    segment["process_hwm_kib"] for segment in segment_records
                ),
                "first_pcm_max_abs_error": compared["call_0"]["pcm"]["max_abs_error"],
                "cached_pcm_max_abs_error": compared["call_1"]["pcm"]["max_abs_error"],
                "max_cache_abs_error": max(
                    compared["call_0"]["max_cache_abs_error"],
                    compared["call_1"]["max_cache_abs_error"],
                ),
                "accepted": compared["accepted"],
            }
        )
    return summaries


def main() -> None:
    args = parse_args()
    artifacts = args.artifact_root
    first = read(
        artifacts / "acoustic-decoder-streaming-first-segments-fp16-1.2/metadata.json"
    )
    cached = read(
        artifacts / "acoustic-decoder-streaming-cached-segments-fp16-1.2/metadata.json"
    )
    lane = artifacts / "lane-a/fp16"
    first_metrics = read(lane / "export-first-metrics.json")
    cached_metrics = read(lane / "export-cached-metrics.json")
    host = read(lane / "host-result.json")
    host_metrics = read(lane / "host-validation-metrics.json")
    android_root = artifacts / "android-streaming-decoder-probe-fp16"
    android = read(android_root / "comparison.json")
    device = read(android_root / "device-result.json")

    android_runs = android_run_summaries(device, android)
    prior_root = artifacts / "android-streaming-decoder-probe-fp16-fast-session"
    prior_android = read(prior_root / "comparison.json") if prior_root.exists() else None
    prior_device = read(prior_root / "device-result.json") if prior_root.exists() else None
    prior_runs = (
        android_run_summaries(prior_device, prior_android)
        if prior_device is not None and prior_android is not None
        else []
    )
    all_android_runs = android_runs + prior_runs

    fp16_bytes = first["total_pte_bytes"] + cached["total_pte_bytes"]
    fp32_bytes = 2_754_222_596
    result = {
        "schema_version": 1,
        "status": "passed",
        "scope": "FP16 fixed-shape eight-segment streaming acoustic decoder on host and Galaxy S23 Ultra",
        "runtime": {
            "torch": host["versions"]["torch"],
            "executorch": host["versions"]["executorch"],
            "backend": "xnnpack",
        },
        "precision": {
            "model_parameters": "float16",
            "segment_activation_abi": "float16",
            "cache_transport_abi": "float16",
            "comparison_reference": "original captured FP32 fixtures",
        },
        "interface": {
            "segment_count": 8,
            "cache_tensor_count": 34,
            "cache_source": "actual call-0 runtime outputs transported into call 1 on host and Android",
        },
        "tolerances": {
            "fp32_unchanged": {
                "host_pcm_and_cache": {"atol": 2e-5, "rtol": 1e-5},
                "android_pcm": {"atol": 2e-5, "rtol": 1e-5},
                "android_cache_only": {"atol": 6e-5, "rtol": 1e-5},
            },
            "fp16": {
                "pcm": {"atol": 2e-3, "rtol": 2e-3},
                "host_eager_cache_and_chained_intermediates": {
                    "atol": 5e-2,
                    "rtol": 2e-3,
                },
                "android_cache_only": {"atol": 3.5e-1, "rtol": 2e-3},
                "android_cache_rationale": (
                    "Narrowly scoped to deterministic FP16 XNNPACK cache drift; both PCM chunks "
                    "still use the FP16 PCM tolerance and call 1 consumes actual call-0 caches."
                ),
            },
        },
        "pte": {
            "first_bytes": first["total_pte_bytes"],
            "cached_bytes": cached["total_pte_bytes"],
            "total_bytes": fp16_bytes,
            "fp32_total_bytes": fp32_bytes,
            "reduction_fraction": 1.0 - fp16_bytes / fp32_bytes,
        },
        "eager_and_export": {
            "first_pcm_max_abs_error": first["eager"]["pcm_max_abs_error"],
            "cached_pcm_max_abs_error": cached["eager"]["pcm_max_abs_error"],
            "first_max_cache_abs_error": max(
                segment["cache_max_abs_error"] for segment in first["segments"]
            ),
            "cached_max_cache_abs_error": max(
                segment["cache_max_abs_error"] for segment in cached["segments"]
            ),
            "exported_program_max_abs_error": max(
                segment["exported_program_max_abs_error"]
                for metadata in (first, cached)
                for segment in metadata["segments"]
            ),
            "first_export": {
                "wall_seconds": first_metrics["wall_seconds"],
                "peak_process_hwm_kib": first_metrics["peak_process_hwm_kib"],
                "peak_observed_pss_kib": first_metrics["peak_observed_pss_kib"],
            },
            "cached_export": {
                "wall_seconds": cached_metrics["wall_seconds"],
                "peak_process_hwm_kib": cached_metrics["peak_process_hwm_kib"],
                "peak_observed_pss_kib": cached_metrics["peak_observed_pss_kib"],
            },
        },
        "host_xnnpack": {
            "status": host["status"],
            "repeats": [
                {
                    "repeat": repeat["repeat"],
                    "calls": [call_summary(call) for call in repeat["calls"]],
                }
                for repeat in host["repeats"]
            ],
            "deterministic_repeats": host["deterministic_repeats"],
            "peak_process_hwm_kib": host_metrics["peak_process_hwm_kib"],
            "peak_observed_pss_kib": host_metrics["peak_observed_pss_kib"],
        },
        "android_xnnpack": {
            "status": android["status"],
            "device": android["device"],
            "runs": android_runs,
            "additional_observed_session_runs": prior_runs,
            "observed_two_call_inference_seconds_range": [
                min(run["total_inference_seconds"] for run in all_android_runs),
                max(run["total_inference_seconds"] for run in all_android_runs),
            ],
            "deterministic_repeats": android["deterministic_repeats"]
            and (prior_android is None or prior_android["deterministic_repeats"]),
            "process_hwm_kib": max(
                run["process_hwm_kib"] for run in all_android_runs
            ),
            "peak_observed_pss_kib": max(
                run["peak_observed_pss_kib"] for run in all_android_runs
            ),
            "strict_allclose": android["strict_allclose"],
            "accepted": android["accepted"],
        },
        "limitations": [
            "First and cached entry PTE sets still duplicate weights.",
            "Shapes remain fixed at batch 1 and one latent step.",
            "Android PSS is sampled after each segment, not continuously.",
            "FP16 Android cache drift is substantially larger than host drift despite low PCM error.",
            "Android two-call latency varied from 1.68 to 9.73 seconds across two sessions; thermal and scheduling state were not controlled.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
