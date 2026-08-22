#!/usr/bin/env python3
"""Normalize the clean fresh-process source-vs-context setup campaign."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import statistics
from pathlib import Path
from typing import Any

COMPONENTS = ("duration", "text", "vector", "vocoder")
EXPECTED_SCHEDULE = ["source", "context", "context", "source", "context", "source", "source", "context", "source", "context"]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path: Path) -> dict[str, Any]:
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)}


def copy(source: Path, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return record(destination)


def summary(values: list[float]) -> dict[str, Any]:
    return {
        "values_seconds": values,
        "count": len(values),
        "median_seconds": statistics.median(values),
        "minimum_seconds": min(values),
        "maximum_seconds": max(values),
        "mean_seconds": statistics.fmean(values),
        "population_stddev_seconds": statistics.pstdev(values),
        "range_seconds": max(values) - min(values),
    }


def load_runs(campaign: Path, output: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = list(csv.DictReader((campaign / "schedule.tsv").open(), delimiter="\t"))
    if [row["mode"] for row in rows] != EXPECTED_SCHEDULE:
        raise SystemExit("campaign schedule mismatch")
    if any(row["exit_code"] != "0" for row in rows):
        raise SystemExit("campaign contains a failed process")
    raw_dir = output / "raw"
    runs: list[dict[str, Any]] = []
    normalized_schedule: list[dict[str, Any]] = []
    for row in rows:
        position = int(row["schedule_position"])
        mode = row["mode"]
        run_index = int(row["run_index"])
        run_dir = campaign / "runs" / f"{position:02d}-{mode}-{run_index}"
        source = run_dir / "result.json"
        result = json.loads(source.read_text())
        if result["result"] != "passed" or result["mode"] != mode:
            raise SystemExit(f"invalid result at schedule position {position}")
        if result["run_index"] != run_index or result["schedule_position"] != position:
            raise SystemExit(f"run identity mismatch at schedule position {position}")
        if result["configuration"]["session.disable_cpu_ep_fallback"] != "1":
            raise SystemExit(f"fallback was not disabled at schedule position {position}")
        if any("QNNExecutionProvider" not in item["providers"] for item in result["timing"]["component_intervals"].values()):
            raise SystemExit(f"QNN provider missing at schedule position {position}")
        if result["fresh_process"] is not True or result["fresh_container"] is not True:
            raise SystemExit(f"fresh-process boundary missing at schedule position {position}")
        if result["source_onnx_absent"] != (mode == "context"):
            raise SystemExit(f"source absence mismatch at schedule position {position}")
        destination = raw_dir / f"{position:02d}-{mode}-{run_index}.json"
        copied = copy(source, destination)
        result["committed_raw_record"] = copied
        runs.append(result)
        normalized_schedule.append(
            {
                "schedule_position": position,
                "mode": mode,
                "run_index": run_index,
                "start_utc": row["start_utc"],
                "end_utc": row["end_utc"],
                "exit_code": 0,
                "raw_record": copied,
            }
        )
    return runs, normalized_schedule


def stable_artifacts(runs: list[dict[str, Any]]) -> dict[str, Any]:
    reference = runs[0]["artifacts"]
    for run in runs[1:]:
        for component in COMPONENTS:
            current = run["artifacts"][component]
            if run["mode"] == runs[0]["mode"]:
                if current != reference[component]:
                    raise SystemExit(f"artifact drift for {run['mode']} {component}")
    by_mode: dict[str, Any] = {}
    for mode in ("source", "context"):
        selected = [run for run in runs if run["mode"] == mode]
        mode_reference = selected[0]["artifacts"]
        if any(run["artifacts"] != mode_reference for run in selected[1:]):
            raise SystemExit(f"artifact drift within {mode} arm")
        by_mode[mode] = mode_reference
    return by_mode


def run(args: argparse.Namespace) -> None:
    args.output.mkdir(parents=True, exist_ok=True)
    runs, schedule = load_runs(args.campaign, args.output)
    artifacts = stable_artifacts(runs)
    start = json.loads((args.campaign / "campaign-start.json").read_text())
    end = json.loads((args.campaign / "campaign-end.json").read_text())
    campaign_files = {
        "campaign_start": copy(args.campaign / "campaign-start.json", args.output / "campaign-start.json"),
        "campaign_end": copy(args.campaign / "campaign-end.json", args.output / "campaign-end.json"),
        "schedule": copy(args.campaign / "schedule.tsv", args.output / "schedule.tsv"),
    }

    arm_runs = {mode: sorted((item for item in runs if item["mode"] == mode), key=lambda item: item["run_index"]) for mode in ("source", "context")}
    sequence = {
        mode: summary([item["timing"]["session_sequence_seconds"] for item in selected])
        for mode, selected in arm_runs.items()
    }
    entry_to_ready = {
        mode: summary([item["timing"]["script_entry_to_ready_seconds"] for item in selected])
        for mode, selected in arm_runs.items()
    }
    per_component = {
        component: {
            mode: summary(
                [item["timing"]["component_session_create_seconds"][component] for item in selected]
            )
            for mode, selected in arm_runs.items()
        }
        for component in COMPONENTS
    }
    source_median = sequence["source"]["median_seconds"]
    context_median = sequence["context"]["median_seconds"]
    delta = source_median - context_median
    comparison = {
        "source_median_seconds": source_median,
        "context_median_seconds": context_median,
        "source_minus_context_median_seconds": delta,
        "source_over_context_median_ratio": source_median / context_median,
        "context_over_source_median_ratio": context_median / source_median,
        "context_setup_reduction_percent": delta / source_median * 100.0,
        "interpretation": "For this exact four-session host QNN setup boundary, external EPContext loading reduced observed median session setup versus source-ONNX QNN compilation. No minimum speedup threshold was applied.",
    }

    functional = json.loads(args.functional.read_text())
    functional_sha = sha(args.functional)
    result = {
        "schema_version": 1,
        "experiment": "0023-supertonic-qnn-precompiled-context-startup",
        "recorded_date": "2026-08-22",
        "status": "clean_host_setup_campaign_passed",
        "question": "Does external QNN EPContext loading reduce setup versus source-ONNX QNN compilation for the exact accepted four-session Supertonic route?",
        "answer": "yes_for_this_clean_host_campaign",
        "primary_timing_boundary": {
            "name": "four_session_sequence_ready",
            "start": "immediately before constructing the duration Ort InferenceSession",
            "end": "immediately after the vocoder Ort InferenceSession constructor returns; all four session objects remain alive",
            "excludes": ["Python interpreter startup/imports", "inference", "WAV generation", "process teardown", "artifact hashing"],
            "filesystem_cache": "Fresh process and container for every run; OS filesystem page cache was not dropped or called cold.",
        },
        "secondary_timing_boundary": {
            "name": "python_script_entry_to_ready",
            "start": "first executable Python statement before argparse/json/onnxruntime imports",
            "end": "same all-four-sessions-ready point",
            "excludes": ["Python interpreter startup before script execution", "inference", "WAV generation", "process teardown", "artifact hashing"],
        },
        "campaign_isolation": {
            "lock_start_utc": start["start_utc"],
            "lock_end_utc": end["end_utc"],
            "lock": start["heavy_ram_lock"],
            "lock_release": "parent shell released heavy-ram.lock immediately after campaign-end.json was written",
            "prelaunch_process_scan": start["prelaunch_process_scan"],
            "docker_image": start["docker_image"],
            "docker_image_id": start["docker_image_id"],
            "fresh_processes_per_arm": 5,
            "fresh_container_per_run": True,
            "balanced_schedule": EXPECTED_SCHEDULE,
            "phone_access": False,
            "other_qnn_campaign_overlap": False,
        },
        "configuration": arm_runs["source"][0]["configuration"],
        "source_arm_context_difference": {
            "source": "loads exact source ONNX with ep.context_enable and ep.context_file_path unset; QNN compilation occurs inside each constructor",
            "context": "loads exact external descriptors/binaries with per-session ep.context_file_path; source ONNX absent from the package",
            "otherwise_matched": "same script, container image, ORT/QNN runtime, provider options, graph optimization, threads, session order and host",
        },
        "schedule": schedule,
        "session_sequence": sequence,
        "script_entry_to_ready": entry_to_ready,
        "per_component_session_create": per_component,
        "comparison": comparison,
        "memory_at_ready_kb": {
            mode: {
                "vm_hwm": [item["memory_at_ready"]["vm_hwm_kb"] for item in selected],
                "vm_rss": [item["memory_at_ready"]["vm_rss_kb"] for item in selected],
            }
            for mode, selected in arm_runs.items()
        },
        "artifact_identities": artifacts,
        "provider_and_fallback_evidence": {
            "timed_processes": "Every constructor used QNNExecutionProvider with session.disable_cpu_ep_fallback=1; all constructors returned. Profiling was disabled to avoid perturbing timing, so timed processes make no node-event or physical-execution claim.",
            "functional_companion": {
                "path": args.functional.relative_to(args.repo).as_posix(),
                "sha256": functional_sha,
                "same_artifact_identities": True,
                "all_ort_node_events_qnn_only": functional["aggregate"]["all_ort_node_events_qnn_only"],
                "all_source_absent_reload_checks_passed": functional["aggregate"]["all_functional_checks_passed"],
            },
            "physical_phone_proof": False,
        },
        "campaign_files": campaign_files,
        "claim_boundary": {
            "established": [
                "Five fresh-process/fresh-container setup observations per arm under one full-lifetime exclusive heavy-RAM lock.",
                "Observed host four-session QNN setup distribution and source-vs-context median delta for exact matched artifacts/configuration.",
                "Context packages contained no source ONNX.",
            ],
            "not_established": [
                "inference latency or end-to-end RTF",
                "physical phone HTP execution",
                "phone setup reduction",
                "WAV validity or listening quality",
                "cold OS filesystem-cache behavior",
            ],
        },
        "next_gate": "Review this committed host campaign before any phone work.",
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"session_sequence": sequence, "comparison": comparison}, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--functional", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
