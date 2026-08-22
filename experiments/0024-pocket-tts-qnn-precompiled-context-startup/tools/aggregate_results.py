#!/usr/bin/env python3
"""Aggregate three-or-more cold source/context processes and offline context costs."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def arm_summary(paths: list[Path], expected: str) -> dict[str, Any]:
    rows = [load(path) for path in paths]
    if len(rows) < 3 or any(row["arm"] != expected for row in rows):
        raise SystemExit(f"{expected}: require at least three matching cold results")
    setups = [row["setup"]["seconds"] for row in rows]
    first_rtfs = [row["first"]["rtf"] for row in rows]
    warm_rtfs = [value for row in rows for value in row["warm"]["rtf"]]
    return {
        "cold_process_count": len(rows),
        "setup_seconds": setups,
        "setup_median_seconds": statistics.median(setups),
        "setup_min_seconds": min(setups),
        "setup_max_seconds": max(setups),
        "first_rtf": first_rtfs,
        "first_rtf_median": statistics.median(first_rtfs),
        "warm_rtf": warm_rtfs,
        "warm_generation_count": len(warm_rtfs),
        "warm_rtf_median_pooled": statistics.median(warm_rtfs),
        "warm_rtf_min": min(warm_rtfs),
        "warm_rtf_max": max(warm_rtfs),
        "wav_sha256": sorted({row["determinism"]["sha256"] for row in rows}),
        "runs": [row["run"] for row in rows],
        "max_vm_hwm_kb": max(row["memory"]["max_vm_hwm_kb"] for row in rows),
        "listening": [row["listening"] for row in rows],
    }


def context_summary(root: Path) -> dict[str, Any]:
    components = []
    for component_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        generate = load(component_dir / "generate-result.json")
        reload_path = root.parent / "context-reload-isolated" / component_dir.name / "reload-result.json"
        reload = load(reload_path)
        if not (generate["qnn_only_provider_proof"] and reload["qnn_only_provider_proof"] and
                reload["source_onnx_absent_from_isolation_root"]):
            raise SystemExit(f"context proof failed for {component_dir.name}")
        components.append({
            "component": component_dir.name,
            "source_model": generate["artifacts"]["model_loaded"],
            "descriptor": generate["artifacts"]["descriptor"],
            "external_context_binary": generate["artifacts"]["external_context_binary"],
            "generation_session_seconds": generate["timing"]["session_create_seconds"],
            "isolated_reload_session_seconds": reload["timing"]["session_create_seconds"],
            "generate_provider_events": generate["provider_events"],
            "reload_provider_events": reload["provider_events"],
            "generate_reload_outputs_equal": [item["sha256"] for item in generate["outputs"]] ==
                                             [item["sha256"] for item in reload["outputs"]],
        })
    if len(components) != 8:
        raise SystemExit(f"expected eight contexts, got {len(components)}")
    return {
        "components": components,
        "offline_generation_session_seconds_sum": sum(item["generation_session_seconds"] for item in components),
        "host_isolated_reload_session_seconds_sum": sum(item["isolated_reload_session_seconds"] for item in components),
        "source_graph_bytes_sum": sum(item["source_model"]["bytes"] for item in components),
        "descriptor_bytes_sum": sum(item["descriptor"]["bytes"] for item in components),
        "external_context_bytes_sum": sum(item["external_context_binary"]["bytes"] for item in components),
        "all_generate_reload_outputs_equal": all(item["generate_reload_outputs_equal"] for item in components),
        "all_reload_source_onnx_absent": True,
        "all_host_provider_proofs_qnn_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--context", type=Path, action="append", required=True)
    parser.add_argument("--contexts-root", type=Path, required=True)
    parser.add_argument("--source-proof", type=Path)
    parser.add_argument("--context-proof", type=Path)
    parser.add_argument("--graph-inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = arm_summary(args.source, "source")
    context = arm_summary(args.context, "context")
    source_setup = source["setup_median_seconds"]
    context_setup = context["setup_median_seconds"]
    delta = source_setup - context_setup
    result = {
        "schema_version": 1,
        "status": "complete",
        "route": "pocket-fixed-alba-text64-cache512-canonical-v2-0024-reconstruction-derivative",
        "comparison": {
            "source": source,
            "context": context,
            "observed_setup_delta_seconds_source_minus_context": delta,
            "observed_setup_reduction_percent": 100.0 * delta / source_setup,
            "speedup_ratio_source_over_context": source_setup / context_setup,
            "minimum_speedup_gate": None,
            "interpretation": "Observed fresh-process setup delta only; no arbitrary minimum speedup gate was applied.",
        },
        "contexts": context_summary(args.contexts_root),
        "graph_inventory": {"path": str(args.graph_inventory), "sha256": sha(args.graph_inventory),
                            "evidence": load(args.graph_inventory)},
        "physical_proof": {
            "source": load(args.source_proof) if args.source_proof else None,
            "context": load(args.context_proof) if args.context_proof else None,
        },
        "output_comparison": {
            "source_wav_sha256": source["wav_sha256"],
            "context_wav_sha256": context["wav_sha256"],
            "byte_identical_between_arms": source["wav_sha256"] == context["wav_sha256"],
            "policy": "Numerical/WAV differences are descriptive, not automatic blockers. Exact byte-different WAVs remain not_reviewed pending Moritz.",
        },
        "benchmark_semantics": {
            "sessions_created_once_per_fresh_process": True,
            "first_complete_generations_per_process": 1,
            "warm_complete_generations_per_process": 5,
            "full_model_cache_decoder_noise_state_reset_before_each_generation": True,
            "rtf": "generation seconds / actual emitted audio seconds",
            "memory": "process-lifecycle cumulative VmHWM, not isolated model memory",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["comparison"], indent=2))


if __name__ == "__main__":
    main()
