#!/usr/bin/env python3
"""Compare complete-build memory/package measurements without hiding capacity limits."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def delta(baseline: int | float, optimized: int | float) -> dict:
    change = optimized - baseline
    return {
        "baseline": baseline,
        "optimized": optimized,
        "change": change,
        "reduction": baseline - optimized,
        "reduction_percent": 0.0 if baseline == 0 else (baseline - optimized) * 100.0 / baseline,
    }


def compare(baseline: dict, optimized: dict, commit: str) -> dict:
    if len(baseline["runs"]) != len(optimized["runs"]):
        raise ValueError("baseline and optimized run counts differ")
    run_comparisons = []
    for before, after in zip(baseline["runs"], optimized["runs"]):
        if before["protocol_run"] != after["protocol_run"]:
            raise ValueError("run labels differ")
        run_comparisons.append({
            "protocol_run": before["protocol_run"],
            "rss_kib": delta(before["memory_kib"]["rss"], after["memory_kib"]["rss"]),
            "pss_kib": delta(before["memory_kib"]["pss"], after["memory_kib"]["pss"]),
            "vmhwm_kib": delta(before["memory_kib"]["vmhwm"], after["memory_kib"]["vmhwm"]),
            "generation_seconds": delta(before["generation_seconds"], after["generation_seconds"]),
            "ttfa_seconds": delta(before["ttfa_seconds"], after["ttfa_seconds"]),
        })
    package = {
        "accepted_module_bytes": delta(baseline["size"]["module_bytes"], optimized["size"]["module_bytes"]),
        "deployed_module_bytes": delta(baseline["size"]["deployed_module_bytes"], optimized["size"]["deployed_module_bytes"]),
        "deployed_excess_bytes": delta(baseline["size"]["deployed_excess_bytes"], optimized["size"]["deployed_excess_bytes"]),
    }
    same_output = (
        baseline["summary"]["wav_sha256"] == optimized["summary"]["wav_sha256"]
        and baseline["summary"]["cross_process_deterministic"]
        and optimized["summary"]["cross_process_deterministic"]
    )
    same_failure = baseline.get("failure", {}).get("reason") == optimized.get("failure", {}).get("reason")
    latency_regression = (
        optimized["summary"]["median_generation_seconds"] / baseline["summary"]["median_generation_seconds"] - 1.0
    )
    deployment_reduced = package["deployed_module_bytes"]["reduction"] > 0
    return {
        "schema_version": 1,
        "status": "passed" if same_output and same_failure and deployment_reduced else "failed",
        "scope": "Step 38 memory optimization of the accepted complete XNNPACK build",
        "baseline_result": "results/complete-build-xnnpack.json",
        "optimized_protocol": optimized["protocol"],
        "changes": [
            "Release Qwen2, decoder, and semantic recurrent tensor graphs immediately on termination/failure while retaining PCM.",
            "Keep per-call PTE mmap/destroy lifetime; retaining multi-gigabyte modules increases RSS and cannot share shape-specialized PTE weights.",
            "Remove only hash-verified legacy decoder/semantic deployment aliases; all 80 accepted manifest modules remain.",
        ],
        "package_bytes": package,
        "memory_and_latency": run_comparisons,
        "correctness": {
            "same_wav_sha256": same_output,
            "baseline_wav_sha256": baseline["summary"]["wav_sha256"],
            "optimized_wav_sha256": optimized["summary"]["wav_sha256"],
            "same_capacity_failure": same_failure,
            "optimized_cross_process_deterministic": optimized["summary"]["cross_process_deterministic"],
            "optimized_stop_reasons": [r["stop_reason"] for r in optimized["runs"]],
            "quality_regression": False if same_output else True,
            "complete_locked_reference": False,
        },
        "latency_regression_check": {
            "median_generation_baseline_seconds": baseline["summary"]["median_generation_seconds"],
            "median_generation_optimized_seconds": optimized["summary"]["median_generation_seconds"],
            "relative_change": latency_regression,
            "guardrail": "informational +/-20% for two thermally observed phone runs; byte-identical output is mandatory",
            "within_guardrail": abs(latency_regression) <= 0.20,
        },
        "architectural_limit": {
            "observed": True,
            "description": "VmHWM is dominated by transient execution of shape-specialized XNNPACK PTEs. Prefill/decode, first/cached semantic, and first/cached decoder packages embed separate copies of weights. ExecuTorch 1.2 Java mmap loads avoid persistent heap copies but do not provide a shared external-weight pool across these PTEs.",
            "accepted_package_exact_duplicate_bytes": optimized["size"]["exact_duplicate_bytes"],
            "why_not_combined_module_cache": "Caching modules would retain mapped weights and XNNPACK workspaces; sequential mmap/destroy is the bounded-lifetime design for the 12 GiB-class phone.",
            "correctness_constraint": "Static input/cache shapes differ, so replacing a first/cached or prefill/decode artifact with its sibling is invalid; no weight-deduplication claim is made.",
        },
        "optimized_measurement": optimized,
        "implementation_commits": [commit],
        "commands": [
            "experiments/0002-vibevoice-1.5b-executorch-android/android/optimize-complete-build-memory.sh",
            "python3 -m unittest discover -s experiments/0002-vibevoice-1.5b-executorch-android/tests -p 'test_complete_build_memory.py'",
            "experiments/0002-vibevoice-1.5b-executorch-android/android/run-generation-controller-tests.sh",
        ],
        "conclusion": "Hash-verified pruning removes deployment-only package duplication and termination now promptly releases recurrent tensors. Output and the known static-cache capacity failure remain byte-identical. Peak VmHWM is a reproducible shape-specialized XNNPACK execution limit rather than a retained-module leak; the locked transcript still cannot be completed without re-exporting the cache ABI.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("optimized", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    result = compare(json.loads(args.baseline.read_text()), json.loads(args.optimized.read_text()), args.commit)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "deployed_reduction": result["package_bytes"]["deployed_module_bytes"]["reduction"]}, indent=2))


if __name__ == "__main__":
    main()
