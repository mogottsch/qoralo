#!/usr/bin/env python3
"""Freeze an externally interrupted staged Kokoro QNN host run.

This tool is deliberately fail-closed: it accepts only a still-``running``
checkpoint with an exact completed-stage prefix, proves provider/profile/output
facts for that prefix, and records the next stage's partial compiler evidence
without relabeling it as a technical QNN failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from summarize_staged_qnn_run import compare, local, qnn_csv_metrics, sha256, tensor


def file_record(path: Path) -> dict[str, object]:
    return {
        "ignored_path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def provider_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in json.loads(path.read_text()):
        if event.get("cat") != "Node":
            continue
        provider = event.get("args", {}).get("provider", "<none>")
        counts[provider] = counts.get(provider, 0) + 1
    return counts


def parse_monitor(path: Path) -> dict[str, object]:
    rows = []
    for line in path.read_text().splitlines():
        fields: dict[str, object] = {"timestamp": line.split()[0]}
        for item in line.split()[1:]:
            key, value = item.split("=", 1)
            fields[key] = int(value)
        rows.append(fields)
    if not rows:
        raise RuntimeError("memory monitor is empty")
    initial_swap = int(rows[0]["swap_free_kib"])
    pause_path = path.with_name("pause-events.log")
    return {
        "ignored_path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "samples": len(rows),
        "first_timestamp": rows[0]["timestamp"],
        "last_timestamp": rows[-1]["timestamp"],
        "minimum_mem_available_kib": min(
            int(row["mem_available_kib"]) for row in rows
        ),
        "initial_swap_free_kib": initial_swap,
        "minimum_swap_free_kib": min(int(row["swap_free_kib"]) for row in rows),
        "maximum_swap_consumption_delta_kib": initial_swap
        - min(int(row["swap_free_kib"]) for row in rows),
        "maximum_concurrent_ben_pid_47353_rss_kib": max(
            int(row["ben_pid_47353_rss_kib"]) for row in rows
        ),
        "pause_event_file_exists": pause_path.exists(),
        "pause_event_file": file_record(pause_path) if pause_path.exists() else None,
        "interpretation": "Host-wide sampled memory. MemAvailable and SwapFree are not process-isolated memory measurements.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--cpu-checkpoint", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--expected-completed", type=int, required=True)
    parser.add_argument("--active-stage-index", type=int, required=True)
    parser.add_argument("--active-stage-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    run = json.loads(args.checkpoint.read_text())
    cpu = json.loads(args.cpu_checkpoint.read_text())
    if run.get("status") != "running":
        raise RuntimeError(f"expected running checkpoint, got {run.get('status')}")
    if len(run.get("stages", [])) != args.expected_completed:
        raise RuntimeError("completed-stage prefix length drift")
    if (
        len(cpu.get("stages", [])) != 18
        or len(manifest.get("stages", [])) != 18
    ):
        raise RuntimeError("manifest/CPU stage count drift")
    if args.active_stage_index != args.expected_completed + 1:
        raise RuntimeError("active stage is not the next sequential stage")
    active_spec = manifest["stages"][args.active_stage_index - 1]
    if active_spec["name"] != args.active_stage_name:
        raise RuntimeError("active stage name/index drift")
    if run["manifest"]["sha256"] != sha256(args.manifest):
        raise RuntimeError("manifest hash drift")

    completed = []
    total_provider_counts: dict[str, int] = {}
    for spec, cpu_stage, qnn_stage in zip(
        manifest["stages"], cpu["stages"], run["stages"]
    ):
        if not (
            spec["index"] == cpu_stage["index"] == qnn_stage["index"]
            and spec["name"] == cpu_stage["name"] == qnn_stage["name"]
            and spec["model"]["sha256"] == qnn_stage["model_sha256"]
            and qnn_stage["exit_code"] == 0
            and qnn_stage["runtime"]["status"] == "passed"
            and qnn_stage["runtime"]["provider"] == "qnn"
        ):
            raise RuntimeError(f"completed-stage contract drift: {spec['name']}")
        profile_paths = [local(item["path"]) for item in qnn_stage["profile_files"]]
        ort_profiles = [path for path in profile_paths if path.suffix == ".json"]
        qnn_csvs = [path for path in profile_paths if path.name.endswith(".qnn.csv")]
        qnn_logs = [path for path in profile_paths if path.name.endswith("_qnn.log")]
        if len(ort_profiles) != 1 or len(qnn_csvs) != 1 or len(qnn_logs) != 1:
            raise RuntimeError(f"profile file set drift: {spec['name']}")
        counts = provider_counts(ort_profiles[0])
        if counts != {"QNNExecutionProvider": 1}:
            raise RuntimeError(f"provider proof failed: {spec['name']} {counts}")
        for provider, count in counts.items():
            total_provider_counts[provider] = total_provider_counts.get(provider, 0) + count
        comparisons = {}
        for name, qnn_output in qnn_stage["outputs"].items():
            cpu_output = cpu_stage["outputs"][name]
            comparisons[name] = compare(
                tensor(local(cpu_output["path"])), tensor(local(qnn_output["path"]))
            )
        completed.append(
            {
                "index": spec["index"],
                "name": spec["name"],
                "role": spec["role"],
                "model": {
                    "bytes": spec["model"]["bytes"],
                    "sha256": spec["model"]["sha256"],
                    "source_nodes": spec["structure"]["nodes"],
                },
                "execution": {
                    "exit_code": 0,
                    "wall_seconds": qnn_stage["wall_seconds"],
                    "session_creation_seconds": qnn_stage["runtime"][
                        "session_creation_seconds"
                    ],
                    "run_seconds": qnn_stage["runtime"]["run_seconds"],
                    "ru_maxrss_kib": qnn_stage["runtime"]["max_rss_kib"],
                    "provider_counts": counts,
                    "qnn_profile_metrics": qnn_csv_metrics(qnn_csvs[0]),
                },
                "outputs": qnn_stage["outputs"],
                "comparison_to_same_stage_cpu": comparisons,
                "evidence": {
                    "stdout": qnn_stage["stdout"],
                    "stderr": qnn_stage["stderr"],
                    "ort_profile": file_record(ort_profiles[0]),
                    "qnn_csv": file_record(qnn_csvs[0]),
                    "qnn_log": file_record(qnn_logs[0]),
                },
            }
        )

    prefix = f"{args.active_stage_index:02d}-{args.active_stage_name}"
    stdout = args.run_dir / "logs" / f"{prefix}.stdout.json"
    stderr = args.run_dir / "logs" / f"{prefix}.stderr.log"
    partial_profiles = sorted((args.run_dir / "profiles").glob(f"{prefix}*"))
    if not stdout.is_file() or not stderr.is_file():
        raise RuntimeError("active-stage partial log set is missing")
    progress_text = stdout.read_text(errors="replace")
    progress = [int(value) for value in re.findall(r"(\d+)%", progress_text)]
    if not progress:
        raise RuntimeError("active-stage compiler progress is absent")
    if any(path.stat().st_size for path in partial_profiles):
        raise RuntimeError("active stage unexpectedly produced non-empty profile evidence")
    active = {
        "index": active_spec["index"],
        "name": active_spec["name"],
        "role": active_spec["role"],
        "model": {
            "bytes": active_spec["model"]["bytes"],
            "sha256": active_spec["model"]["sha256"],
            "source_nodes": active_spec["structure"]["nodes"],
        },
        "observed_compiler_state": {
            "graph_preparation_initializing_completed_us": int(
                re.search(
                    r"Completed stage: Graph Preparation Initializing \((\d+) us\)",
                    progress_text,
                ).group(1)
            ),
            "graph_optimizations_completed_us": int(
                re.search(
                    r"Completed stage: Graph Optimizations \((\d+) us\)",
                    progress_text,
                ).group(1)
            ),
            "post_graph_optimization_completed_us": int(
                re.search(
                    r"Completed stage: Post Graph Optimization \((\d+) us\)",
                    progress_text,
                ).group(1)
            ),
            "graph_sequencing_for_target_maximum_progress_percent": max(progress),
            "session_finalized": False,
            "inference_executed": False,
            "output_produced": False,
            "provider_profile_produced": False,
            "runner_exit_code": None,
        },
        "evidence": {
            "stdout": file_record(stdout),
            "stderr": file_record(stderr),
            "partial_profile_files": [file_record(path) for path in partial_profiles],
        },
    }

    unattempted = [
        {
            "index": spec["index"],
            "name": spec["name"],
            "role": spec["role"],
            "model_sha256": spec["model"]["sha256"],
        }
        for spec in manifest["stages"][args.active_stage_index :]
    ]
    start_path = args.run_dir / "start.txt"
    monitor_path = args.run_dir / "memory-monitor.log"
    result = {
        "schema_version": 1,
        "status": "externally_interrupted",
        "route": "canonical_v2_official_frontend_fixed_fp32_staged_qnn_host",
        "comparability": "canonical_v2",
        "transcript_sha256": "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67",
        "interruption": {
            "classification": "external infrastructure interruption, not a technical QNN stage failure",
            "operator_context": "Moritz stopped/restarted WSL while increasing memory; the process was externally interrupted.",
            "evidence": [
                "The durable pipeline checkpoint remains status=running and contains 15 completed stage records.",
                "Stage 16 has only compiler progress through Graph Sequencing for Target at 12%; it has no runner JSON, non-empty provider profile, output, or exit code.",
                "The top-level run directory has no end.txt or exit-code.txt.",
                "No ORT/QNN error or kernel OOM is present in the partial stage-16 logs.",
            ],
            "must_not_be_called": [
                "stage-16 QNN failure",
                "OOM",
                "complete 18-stage host gate",
                "phone eligible",
            ],
        },
        "source": {
            "manifest": file_record(args.manifest),
            "pipeline_checkpoint": file_record(args.checkpoint),
            "cpu_checkpoint": file_record(args.cpu_checkpoint),
            "runner": run["runner"],
            "start": {
                **file_record(start_path),
                "timestamp": start_path.read_text().strip(),
            },
            "end_file_exists": (args.run_dir / "end.txt").exists(),
            "exit_code_file_exists": (args.run_dir / "exit-code.txt").exists(),
        },
        "completed_prefix": {
            "count": len(completed),
            "indices": [stage["index"] for stage in completed],
            "provider_counts": total_provider_counts,
            "cpu_provider_node_events": total_provider_counts.get(
                "CPUExecutionProvider", 0
            ),
            "sum_session_creation_seconds": sum(
                stage["execution"]["session_creation_seconds"] for stage in completed
            ),
            "sum_single_run_seconds": sum(
                stage["execution"]["run_seconds"][0] for stage in completed
            ),
            "sum_stage_wall_seconds": sum(
                stage["execution"]["wall_seconds"] for stage in completed
            ),
            "maximum_per_process_ru_maxrss_kib": max(
                stage["execution"]["ru_maxrss_kib"] for stage in completed
            ),
            "memory_semantics": "maximum of separate process-lifetime ru_maxrss high-water marks; not additive, not steady PSS, and not component-isolated",
            "stages": completed,
        },
        "interrupted_active_stage": active,
        "unattempted_stages": unattempted,
        "resource_monitor": parse_monitor(monitor_path),
        "phone_eligibility": False,
        "final_audio_produced": False,
        "next_action": {
            "rule": "Reconstruct all hash-pinned ignored inputs/models, verify every committed hash and test, then restart the complete canonical 18-stage serial host run from stage 1. Do not treat the partial stage-16 artifacts as resumable proof.",
            "reason": "All 18 stages must pass in a complete durable pipeline record using real upstream tensors before phone access.",
        },
        "claim_boundary": "The first 15 canonical stages have fallback-disabled host QNN finalization, complete-input execution, one QNNExecutionProvider event each, zero CPU provider events, and detailed host QNN profile metrics. Stage 16 did not finalize or execute, stages 17-18 were not attempted, no final audio exists, and there is no physical phone HTP or listening evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "completed": result["completed_prefix"]["count"],
                "active": result["interrupted_active_stage"]["name"],
                "unattempted": [item["name"] for item in unattempted],
                "minimum_mem_available_kib": result["resource_monitor"][
                    "minimum_mem_available_kib"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
