#!/usr/bin/env python3
import time

SCRIPT_ENTRY = time.perf_counter()

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
from typing import Any

import onnxruntime as ort

COMPONENTS = ("duration", "text", "vector", "vocoder")
SOURCE_MODELS = {
    "duration": "duration_predictor.onnx",
    "text": "text_encoder.onnx",
    "vector": "vector_estimator-stable-softplus.onnx",
    "vocoder": "vocoder.onnx",
}
CONTEXT_MODELS = {name: f"{name}-context.onnx" for name in COMPONENTS}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def memory_status() -> dict[str, int | None]:
    values: dict[str, int | None] = {"vm_rss_kb": None, "vm_hwm_kb": None}
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            values["vm_rss_kb"] = int(line.split()[1])
        elif line.startswith("VmHWM:"):
            values["vm_hwm_kb"] = int(line.split()[1])
    return values


def session_options(mode: str, descriptor: Path | None) -> tuple[ort.SessionOptions, dict[str, str]]:
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    if mode == "context":
        assert descriptor is not None
        options.add_session_config_entry("ep.context_file_path", str(descriptor))
    provider = {
        "backend_path": "/opt/qairt/lib/x86_64-linux-clang/libQnnHtp.so",
        "offload_graph_io_quantization": "0",
        "htp_performance_mode": "burst",
        "soc_model": "43",
    }
    return options, provider


def run(args: argparse.Namespace) -> None:
    package = args.package.resolve()
    if args.mode == "context":
        unexpected = [
            path.name
            for path in package.glob("*.onnx")
            if path.name not in set(CONTEXT_MODELS.values())
        ]
        if unexpected:
            raise SystemExit(f"source/unexpected ONNX visible in context package: {unexpected}")
        missing_bins = [name for name in COMPONENTS if not (package / f"{name}-context_qnn.bin").is_file()]
        if missing_bins:
            raise SystemExit(f"missing external context binaries: {missing_bins}")

    model_names = SOURCE_MODELS if args.mode == "source" else CONTEXT_MODELS
    sessions = []
    session_records: dict[str, Any] = {}
    sequence_start = time.perf_counter()
    for component in COMPONENTS:
        model = package / model_names[component]
        if not model.is_file():
            raise SystemExit(f"missing model: {model}")
        descriptor = model if args.mode == "context" else None
        options, provider = session_options(args.mode, descriptor)
        started = time.perf_counter()
        session = ort.InferenceSession(
            str(model),
            sess_options=options,
            providers=[("QNNExecutionProvider", provider)],
        )
        ended = time.perf_counter()
        sessions.append(session)
        session_records[component] = {
            "model": model.name,
            "start_from_script_entry_seconds": started - SCRIPT_ENTRY,
            "end_from_script_entry_seconds": ended - SCRIPT_ENTRY,
            "create_seconds": ended - started,
            "providers": session.get_providers(),
        }
    ready = time.perf_counter()
    memory_at_ready = memory_status()

    artifacts: dict[str, Any] = {}
    for component in COMPONENTS:
        model = package / model_names[component]
        records = {
            "model": {"path": model.name, "bytes": model.stat().st_size, "sha256": sha(model)}
        }
        if args.mode == "context":
            binary = package / f"{component}-context_qnn.bin"
            records["external_context_binary"] = {
                "path": binary.name,
                "bytes": binary.stat().st_size,
                "sha256": sha(binary),
            }
        artifacts[component] = records

    result = {
        "schema_version": 1,
        "result": "passed",
        "experiment": "0023-supertonic-qnn-precompiled-context-startup",
        "mode": args.mode,
        "run_index": args.run_index,
        "schedule_position": args.schedule_position,
        "fresh_process": True,
        "fresh_container": True,
        "source_onnx_absent": args.mode == "context",
        "runtime": {
            "python": platform.python_version(),
            "onnxruntime": ort.__version__,
            "providers_available": ort.get_available_providers(),
            "pid": os.getpid(),
        },
        "configuration": {
            "session.disable_cpu_ep_fallback": "1",
            "ep.context_enable": "not_set",
            "ep.context_file_path": "per-component descriptor" if args.mode == "context" else "not_set",
            "provider_options": {
                "backend_path": "libQnnHtp.so",
                "offload_graph_io_quantization": "0",
                "htp_performance_mode": "burst",
                "soc_model": "43",
            },
            "threads": {"intra_op": 1, "inter_op": 1},
            "execution_mode": "ORT_SEQUENTIAL",
            "graph_optimization": "ORT_ENABLE_ALL",
            "profiling": False,
        },
        "timing": {
            "script_entry_to_ready_seconds": ready - SCRIPT_ENTRY,
            "session_sequence_seconds": ready - sequence_start,
            "component_session_create_seconds": {
                name: record["create_seconds"] for name, record in session_records.items()
            },
            "component_intervals": session_records,
            "ready_definition": "all four Ort InferenceSession constructors returned successfully and all session objects remain alive",
            "script_entry_definition": "first executable statement in the Python script, before argparse/json/onnxruntime imports",
            "session_sequence_definition": "immediately before the first constructor to immediately after the fourth constructor",
        },
        "memory_at_ready": memory_at_ready,
        "artifacts": artifacts,
        "cache_boundary": "fresh process and container; OS filesystem page cache was not dropped or claimed cold",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("source", "context"), required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--run-index", type=int, required=True)
    parser.add_argument("--schedule-position", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
