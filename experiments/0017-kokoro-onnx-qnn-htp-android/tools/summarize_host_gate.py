#!/usr/bin/env python3
"""Summarize ignored Kokoro/QNN host-gate evidence into a bounded checkpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

CAPABILITY = re.compile(
    r"Number of partitions supported by QNN EP: (\d+), number of nodes in the graph: (\d+), number of nodes supported by QNN: (\d+)"
)
UNSUPPORTED = re.compile(r"\{ name: (.*?), type: (.*?) \}")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def artifact(path: Path) -> dict[str, object]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def log_gate(directory: Path) -> dict[str, object]:
    stderr = directory / "stderr.log"
    text = ANSI.sub("", stderr.read_text(errors="replace"))
    passes = [
        {"partitions": int(p), "nodes": int(n), "qnn_nodes": int(q)}
        for p, n, q in CAPABILITY.findall(text)
    ]
    unsupported_lines = [line for line in text.splitlines() if "Unsupported nodes in QNN EP:" in line]
    unsupported = UNSUPPORTED.findall(unsupported_lines[-1]) if unsupported_lines else []
    retained_limit = 64
    result: dict[str, object] = {
        "exit_code": int((directory / "exit-code.txt").read_text().strip()),
        "capability_passes": passes,
        "last_unsupported_count": len(unsupported),
        "last_unsupported_operator_counts": dict(sorted(Counter(op for _, op in unsupported).items())),
        "last_unsupported_nodes": [
            {"name": name, "op_type": op} for name, op in unsupported[:retained_limit]
        ],
        "last_unsupported_nodes_omitted": max(0, len(unsupported) - retained_limit),
        "complete_list_location": "the hash-addressed ignored stderr log",
        "stderr": artifact(stderr),
        "stdout": artifact(directory / "stdout.log"),
    }
    dynamic = re.findall(r"Dynamic shape is not supported yet, for output: ([^\r\n]+)", text)
    if dynamic:
        result["dynamic_output_failures"] = dynamic
    return result


def compare(reference_path: Path, candidate_path: Path) -> dict[str, object]:
    reference = np.fromfile(reference_path, dtype="<f4").astype(np.float64)
    candidate = np.fromfile(candidate_path, dtype="<f4").astype(np.float64)
    if reference.shape != candidate.shape:
        return {"same_shape": False, "reference_elements": reference.size, "candidate_elements": candidate.size}
    delta = candidate - reference
    reference_norm = np.linalg.norm(reference)
    candidate_norm = np.linalg.norm(candidate)
    return {
        "same_shape": True,
        "elements": reference.size,
        "all_finite": bool(np.isfinite(candidate).all()),
        "reference_sha256": sha256(reference_path),
        "candidate_sha256": sha256(candidate_path),
        "bit_exact": bool(np.array_equal(reference, candidate)),
        "maximum_absolute_error": float(np.max(np.abs(delta))),
        "mean_absolute_error": float(np.mean(np.abs(delta))),
        "rmse": float(np.sqrt(np.mean(delta * delta))),
        "nrmse": float(np.linalg.norm(delta) / reference_norm),
        "cosine": float(np.dot(reference, candidate) / (reference_norm * candidate_norm)),
    }


def elapsed_seconds(run: Path) -> float | None:
    start, end = run / "start.txt", run / "end.txt"
    if not start.exists() or not end.exists():
        return None
    return (datetime.fromisoformat(end.read_text().strip()) - datetime.fromisoformat(start.read_text().strip())).total_seconds()


def finalization_progress(run: Path) -> dict[str, object]:
    stdout = (run / "stdout.json").read_text(errors="replace")
    stages = {
        name: int(microseconds) / 1_000_000.0
        for name, microseconds in re.findall(r"Completed stage: (.*?) \((\d+) us\)", stdout)
    }
    percentages = [int(value) for value in re.findall(r"\]\s+(\d+)%", stdout)]
    result: dict[str, object] = {
        "completed_stage_seconds": stages,
        "active_stage_at_termination": "Graph Sequencing for Target",
        "last_reported_graph_sequencing_percent": max(percentages) if percentages else None,
    }
    stderr = (run / "stderr.log").read_text(errors="replace")
    elapsed = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([0-9:.]+)", stderr)
    if elapsed:
        result["time_tool_elapsed"] = elapsed.group(1)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = args.experiment / "work"
    run = work / "host-run"
    rc_path = run / "exit-code.txt"
    if not rc_path.exists():
        raise RuntimeError("capped host run is still active or incomplete")
    run_rc = int(rc_path.read_text().strip())
    qnn_audio = run / "qnn.f32"
    qnn_duration = run / "qnn.i64"
    host_run: dict[str, object] = {
        "exit_code": run_rc,
        "elapsed_seconds_from_timestamp_files": elapsed_seconds(run),
        "finalization_progress": finalization_progress(run),
        "stdout": artifact(run / "stdout.json"),
        "stderr": artifact(run / "stderr.log"),
        "audio_output_present": qnn_audio.is_file(),
        "duration_output_present": qnn_duration.is_file(),
    }
    if (run / "termination.txt").exists():
        host_run["termination"] = (run / "termination.txt").read_text().strip()
    kernel_oom = run / "kernel-oom.txt"
    if kernel_oom.exists():
        oom_text = kernel_oom.read_text(errors="replace")
        match = re.search(
            r"Killed process (\d+) \(kokoro-ort-host\) total-vm:(\d+)kB, anon-rss:(\d+)kB, file-rss:(\d+)kB",
            oom_text,
        )
        host_run["kernel_oom"] = {
            **artifact(kernel_oom),
            "exact_excerpt": oom_text.strip(),
            "parsed": (
                {
                    "pid": int(match.group(1)),
                    "total_vm_kib": int(match.group(2)),
                    "anonymous_rss_kib": int(match.group(3)),
                    "file_rss_kib": int(match.group(4)),
                }
                if match
                else None
            ),
        }
    if qnn_audio.exists():
        host_run["audio"] = artifact(qnn_audio)
        host_run["audio_comparison_to_patched_ort_1_27_cpu"] = compare(
            work / "cpu127-equivalence/source.f32", qnn_audio
        )
    if qnn_duration.exists():
        host_run["duration"] = artifact(qnn_duration)
        host_run["duration_bit_exact"] = (
            (work / "cpu127-equivalence/source.i64").read_bytes() == qnn_duration.read_bytes()
        )
        host_run["duration_sum"] = int(np.fromfile(qnn_duration, dtype="<i8").sum())
    profiles = sorted(run.glob("profile*.json")) + sorted(run.glob("profile*.csv")) + sorted(run.glob("profile*.log"))
    host_run["profiles"] = [artifact(path) for path in profiles]

    cpu_equivalence = json.loads((work / "cpu127-equivalence/comparison.json").read_text())
    session_executed = (
        run_rc == 0
        and qnn_audio.is_file()
        and qnn_duration.is_file()
        and host_run.get("duration_bit_exact") is True
        and host_run.get("audio_comparison_to_patched_ort_1_27_cpu", {}).get("all_finite") is True
    )
    document = {
        "schema_version": 1,
        "route": "exact-source-derived unquantized FP32 fixed-contract Kokoro ONNX through QNN HTP preparation",
        "exact_controlled_graph": log_gate(work / "host-exact"),
        "metadata_only_basic_shaped_graph": log_gate(work / "host-basic-shaped"),
        "qnn_compatibility_rewrite": {
            "model": artifact(work / "rewrite/kokoro-qnn-compat.onnx"),
            "provenance": artifact(work / "rewrite/provenance.json"),
            "same_runtime_cpu_equivalence": cpu_equivalence,
            "capability_only_attempt": log_gate(work / "host-rewrite"),
            "capped_fallback_disabled_full_input_run": host_run,
        },
        "host_session_finalized_and_complete_input_executed": session_executed,
        "phone_eligible": session_executed,
        "phone_accessed": False,
        "claim_boundary": "QNN capability/partition reporting alone is assignment evidence, not execution or physical HTP proof. Physical HTP additionally requires a locked phone run with RPC, accelerator-time, cycle, and HVX evidence.",
    }
    if run_rc == 137 and kernel_oom.exists():
        document["status"] = "blocked_at_qnn_htp_graph_sequencing_kernel_oom"
        document["phone_eligible"] = False
    elif run_rc == 124:
        document["status"] = "blocked_at_qnn_htp_graph_finalization_timeout"
        document["phone_eligible"] = False
    elif session_executed:
        document["status"] = "host_gate_passed_pending_phone_policy_checks"
    else:
        document["status"] = "blocked_at_fallback_disabled_host_execution"
        document["phone_eligible"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": document["status"], "phone_eligible": document["phone_eligible"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
