#!/usr/bin/env python3
"""Publish the final before/after execution result from committed phone evidence."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

STAGES = ("qwen_prefill", "qwen_decode", "diffusion", "acoustic_decoder", "semantic_encoder", "connectors")


def pct_reduction(before: float, after: float) -> float:
    return (before - after) / before * 100.0 if before else 0.0


def variability(values: list[float]) -> dict:
    mean = statistics.mean(values)
    return {
        "values": values,
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
        "mean": mean,
        "population_cv": statistics.pstdev(values) / mean if mean else 0.0,
    }


def metrics(result: dict) -> dict:
    runs = result["runs"]
    stage = {
        name: {
            "median_seconds": statistics.median(float(run["component_seconds"][name]) for run in runs),
            "variability": variability([float(run["component_seconds"][name]) for run in runs]),
        }
        for name in STAGES
    }
    return {
        "stage_latency": stage,
        "ttfa": {"median_seconds": statistics.median(float(r["ttfa_seconds"]) for r in runs),
                 "variability": variability([float(r["ttfa_seconds"]) for r in runs])},
        "generation_wall": {"median_seconds": statistics.median(float(r["generation_seconds"]) for r in runs),
                            "variability": variability([float(r["generation_seconds"]) for r in runs])},
        "protocol_wall": {"median_seconds": statistics.median(float(r["protocol_wall_seconds"]) for r in runs),
                          "variability": variability([float(r["protocol_wall_seconds"]) for r in runs])},
        "rtf": {"median": statistics.median(float(r["rtf"]) for r in runs),
                "variability": variability([float(r["rtf"]) for r in runs])},
        "memory_kib": {
            key: {"max": max(int(r["memory_kib"][key]) for r in runs),
                  "values": [int(r["memory_kib"][key]) for r in runs]}
            for key in ("rss", "pss", "vmhwm")
        },
    }


def build(baseline_memory: dict, optimized: dict, audio: dict, commit: str) -> dict:
    baseline = baseline_memory["optimized_measurement"]
    before, after = metrics(baseline), metrics(optimized)
    reductions = {
        "stage_latency_percent": {name: pct_reduction(before["stage_latency"][name]["median_seconds"], after["stage_latency"][name]["median_seconds"]) for name in STAGES},
        "ttfa_percent": pct_reduction(before["ttfa"]["median_seconds"], after["ttfa"]["median_seconds"]),
        "generation_wall_percent": pct_reduction(before["generation_wall"]["median_seconds"], after["generation_wall"]["median_seconds"]),
        "rtf_percent": pct_reduction(before["rtf"]["median"], after["rtf"]["median"]),
    }
    deterministic = optimized["summary"]["cross_process_deterministic"] and optimized["summary"]["wav_sha256"] == baseline["summary"]["wav_sha256"]
    complete = optimized.get("failure") is None
    return {
        "schema_version": 1,
        "status": "rejected_not_feasible" if not complete else "passed",
        "scope": "final ExecuTorch 1.2/XNNPACK execution optimization and locked-reference conclusion",
        "optimization": {
            "change": "Retain per-call Module.destroy(), but replace explicit GC after every PTE with periodic collection after every eight PTE calls.",
            "rationale": "The baseline collector attributed load, forward, output-copy, destruction, and GC to one component timer. Periodic GC tests whether avoidable stop-the-world work can be reduced while retaining bounded module lifetime.",
            "telemetry": "Each device run records module call count and separate load, forward, output-copy, destroy, and explicit-GC time.",
        },
        "before": before,
        "after": after,
        "optimized_execution_profiles": [run.get("execution_breakdown") for run in optimized["runs"]],
        "reduction": reductions,
        "size": {
            "before": baseline["size"],
            "after": optimized["size"],
            "accepted_module_bytes_change": int(optimized["size"]["module_bytes"]) - int(baseline["size"]["module_bytes"]),
            "apk_plus_modules_bytes_change": int(optimized["size"]["apk_plus_modules_bytes"]) - int(baseline["size"]["apk_plus_modules_bytes"]),
        },
        "memory": {"before": before["memory_kib"], "after": after["memory_kib"],
                   "vmhwm_change_percent": -pct_reduction(before["memory_kib"]["vmhwm"]["max"], after["memory_kib"]["vmhwm"]["max"])},
        "correctness_and_determinism": {
            "same_wav_as_memory_baseline": deterministic,
            "cross_process_deterministic": optimized["summary"]["cross_process_deterministic"],
            "wav_sha256": optimized["summary"]["wav_sha256"],
            "same_capacity_failure": not complete and all(r["stop_reason"] == "CAPACITY" for r in optimized["runs"]),
        },
        "audio_comparison": {
            "status": audio["status"],
            "reference_duration_seconds": audio["duration"]["reference_seconds"],
            "android_duration_seconds": audio["duration"]["android_seconds"],
            "coverage_ratio": audio["duration"]["coverage_ratio"],
            "android_rms_dbfs": audio["waveform"]["android"]["rms_dbfs"],
            "omissions": audio["quality_rubric"]["omissions"]["status"],
            "repetitions": audio["quality_rubric"]["repetitions"]["status"],
            "corruption": audio["quality_rubric"]["corruption"]["status"],
            "speaker_consistency": audio["quality_rubric"]["speaker_consistency"]["status"],
            "evidence": "results/locked-reference-comparison.json",
        },
        "locked_reference": {
            "complete": complete,
            "requested_duration_seconds": optimized["failure"]["requested_duration_seconds"] if not complete else optimized["runs"][0]["audio_duration_seconds"],
            "produced_duration_seconds": optimized["runs"][0]["audio_duration_seconds"],
            "failure": optimized.get("failure"),
        },
        "device": optimized["device"], "runtime": optimized["runtime"], "thermal": optimized["thermal"],
        "evidence": {
            "baseline": "results/complete-build-memory-optimized.json",
            "optimized_raw": "artifacts/0002/lane-d/complete-build-final/",
            "optimized_measurement": "results/complete-build-final-measurement.json",
            "audio_comparison": "results/locked-reference-comparison.json",
        },
        "implementation_commits": [commit],
        "commands": [
            "flock artifacts/locks/phone.lock experiments/0002-vibevoice-1.5b-executorch-android/android/optimize-complete-build-execution.sh",
            "python3 -m unittest discover -s experiments/0002-vibevoice-1.5b-executorch-android/tests -p 'test_complete_build*.py'",
            "experiments/0002-vibevoice-1.5b-executorch-android/android/run-generation-controller-tests.sh",
        ],
        "conclusion": "Not feasible for local locked-reference speech on the Galaxy S23 Ultra with this ExecuTorch/XNNPACK export. Periodic GC yields only a 1.74% median prefix improvement, smaller than the two-run variability and therefore not a validated material speedup; profiling shows module forward time dominates. It cannot repair the two-chunk static-cache limit, 2.04% duration coverage, effectively silent audio, roughly 9.136 GB APK-plus-module footprint, or approximately 107x prefix RTF. Component execution is reproducible; usable end-to-end speech is rejected.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_memory", type=Path)
    parser.add_argument("optimized", type=Path)
    parser.add_argument("audio", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    result = build(*[json.loads(p.read_text()) for p in (args.baseline_memory, args.optimized, args.audio)], args.commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "wall_reduction_percent": result["reduction"]["generation_wall_percent"]}, indent=2))


if __name__ == "__main__":
    main()
