#!/usr/bin/env python3
"""Generate or independently reload one external QNN EPContext component."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

SPECS = {
    "duration": [
        ("text_ids", "text_ids.raw", np.int64, (1, 239)),
        ("style_dp", "style_dp.raw", np.float32, (1, 8, 16)),
        ("text_mask", "text_mask.raw", np.float32, (1, 1, 239)),
    ],
    "text": [
        ("text_ids", "text_ids.raw", np.int64, (1, 239)),
        ("style_ttl", "style_ttl.raw", np.float32, (1, 50, 256)),
        ("text_mask", "text_mask.raw", np.float32, (1, 1, 239)),
    ],
    "vector": [
        ("noisy_latent", "step0_noisy_latent.raw", np.float32, (1, 144, 238)),
        ("text_emb", "text_emb.raw", np.float32, (1, 256, 239)),
        ("style_ttl", "style_ttl.raw", np.float32, (1, 50, 256)),
        ("latent_mask", "latent_mask.raw", np.float32, (1, 1, 238)),
        ("text_mask", "text_mask.raw", np.float32, (1, 1, 239)),
        ("current_step", "current_step.raw", np.float32, (1,)),
        ("total_step", "total_step.raw", np.float32, (1,)),
    ],
    "vocoder": [
        ("latent", "final_latent.raw", np.float32, (1, 144, 238)),
    ],
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)}


def load_inputs(component: str, root: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    feed: dict[str, np.ndarray] = {}
    records: dict[str, Any] = {}
    for name, filename, dtype, shape in SPECS[component]:
        path = root / filename
        value = np.fromfile(path, dtype=dtype)
        expected = int(np.prod(shape))
        if value.size != expected:
            raise SystemExit(f"{path}: expected {expected} values, got {value.size}")
        feed[name] = np.ascontiguousarray(value.reshape(shape))
        records[name] = {**file_record(path), "dtype": np.dtype(dtype).name, "shape": list(shape)}
    return feed, records


def options(args: argparse.Namespace) -> tuple[ort.SessionOptions, dict[str, str]]:
    session = ort.SessionOptions()
    session.intra_op_num_threads = 1
    session.inter_op_num_threads = 1
    session.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session.enable_profiling = True
    session.profile_file_prefix = str(args.profile_prefix)
    session.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    session.add_session_config_entry("ep.context_file_path", str(args.descriptor))
    if args.mode == "generate":
        session.add_session_config_entry("ep.context_enable", "1")
        session.add_session_config_entry("ep.context_embed_mode", "0")
    provider = {
        "backend_path": str(args.backend),
        "profiling_level": "detailed",
        "profiling_file_path": str(args.profile_prefix) + ".qnn.csv",
        "offload_graph_io_quantization": "0",
        "htp_performance_mode": "burst",
        "soc_model": "43",
    }
    return session, provider


def run(args: argparse.Namespace) -> None:
    process_start = time.perf_counter()
    for path in (args.model, args.inputs, args.backend):
        if not path.exists():
            raise SystemExit(f"missing required path: {path}")
    if args.mode == "generate" and args.descriptor.exists():
        raise SystemExit(f"refusing to overwrite descriptor: {args.descriptor}")
    if args.mode == "reload" and not args.descriptor.exists():
        raise SystemExit(f"missing descriptor: {args.descriptor}")
    if args.require_source_absent:
        forbidden = list(args.isolation_root.rglob("*.onnx"))
        allowed = {args.descriptor.resolve()}
        unexpected = [path for path in forbidden if path.resolve() not in allowed]
        if unexpected:
            raise SystemExit(f"source/unexpected ONNX visible in isolation root: {unexpected}")

    feed, input_records = load_inputs(args.component, args.inputs)
    session_options, provider_options = options(args)
    session_start = time.perf_counter()
    session = ort.InferenceSession(
        str(args.model),
        sess_options=session_options,
        providers=[("QNNExecutionProvider", provider_options)],
    )
    session_seconds = time.perf_counter() - session_start
    run_start = time.perf_counter()
    outputs = session.run(None, feed)
    run_seconds = time.perf_counter() - run_start
    if not outputs:
        raise SystemExit("component returned no output")
    output = np.ascontiguousarray(outputs[0])
    if not np.all(np.isfinite(output)):
        raise SystemExit("component output contains non-finite values")
    ort_profile = Path(session.end_profiling())

    binary = args.descriptor.with_name(args.descriptor.stem + "_qnn.bin")
    if not binary.exists():
        raise SystemExit(f"external context binary not found: {binary}")
    qnn_profile = Path(str(args.profile_prefix) + ".qnn.csv")
    if not qnn_profile.exists():
        raise SystemExit(f"QNN profile not found: {qnn_profile}")
    output_record = {
        "shape": list(output.shape),
        "dtype": output.dtype.name,
        "elements": int(output.size),
        "sha256": hashlib.sha256(output.tobytes()).hexdigest(),
        "finite": True,
        "min": float(np.min(output)),
        "max": float(np.max(output)),
        "mean": float(np.mean(output, dtype=np.float64)),
    }
    result = {
        "schema_version": 1,
        "result": "passed",
        "mode": args.mode,
        "component": args.component,
        "fresh_process": True,
        "source_onnx_absent_from_isolation_root": bool(args.require_source_absent),
        "runtime": {
            "python": platform.python_version(),
            "onnxruntime": ort.__version__,
            "providers_available": ort.get_available_providers(),
            "providers_session": session.get_providers(),
            "pid": os.getpid(),
        },
        "configuration": {
            "session.disable_cpu_ep_fallback": "1",
            "ep.context_enable": "1" if args.mode == "generate" else "not_set",
            "ep.context_embed_mode": "0" if args.mode == "generate" else "not_set",
            "ep.context_file_path": args.descriptor.name,
            "provider_options": {**provider_options, "backend_path": args.backend.name},
            "threads": {"intra_op": 1, "inter_op": 1},
            "execution_mode": "ORT_SEQUENTIAL",
            "graph_optimization": "ORT_ENABLE_ALL",
        },
        "artifacts": {
            "model_loaded": file_record(args.model),
            "descriptor": file_record(args.descriptor),
            "external_context_binary": file_record(binary),
            "ort_profile": file_record(ort_profile),
            "qnn_profile": file_record(qnn_profile),
            "backend": file_record(args.backend),
            "inputs": input_records,
        },
        "timing": {
            "session_create_seconds": session_seconds,
            "first_run_seconds": run_seconds,
            "process_to_completed_run_seconds": time.perf_counter() - process_start,
            "session_boundary": "immediately before to immediately after ort.InferenceSession construction",
            "run_boundary": "immediately before to immediately after session.run",
        },
        "output": output_record,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "reload"))
    parser.add_argument("--component", choices=tuple(SPECS), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--profile-prefix", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--require-source-absent", action="store_true")
    parser.add_argument("--isolation-root", type=Path, default=Path("."))
    args = parser.parse_args()
    args.model = args.model.resolve()
    args.inputs = args.inputs.resolve()
    args.descriptor = args.descriptor.resolve()
    args.backend = args.backend.resolve()
    args.profile_prefix = args.profile_prefix.resolve()
    args.result = args.result.resolve()
    args.isolation_root = args.isolation_root.resolve()
    return args


if __name__ == "__main__":
    run(parse_args())
