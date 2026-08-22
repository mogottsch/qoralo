#!/usr/bin/env python3
"""Generate or independently reload one external Pocket QNN EPContext.

The reload mode is designed to run in a fresh process inside an isolation root
that contains only the EPContext descriptor, its external QNN binary, the QNN
backend, and optional immutable fixtures. CPU EP fallback is always disabled.
"""
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


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)}


def shape_of(meta: Any) -> tuple[int, ...]:
    shape: list[int] = []
    for value in meta.shape:
        if not isinstance(value, int) or value <= 0:
            raise SystemExit(f"non-static input {meta.name}: {meta.shape}")
        shape.append(value)
    return tuple(shape)


def deterministic_feed(session: ort.InferenceSession, component: str,
                       token_fixture: Path | None) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    feed: dict[str, np.ndarray] = {}
    records: dict[str, Any] = {}
    for meta in session.get_inputs():
        shape = shape_of(meta)
        if meta.type == "tensor(float)":
            value = np.zeros(shape, dtype=np.float32)
            if meta.name == "valid_mask":
                value.fill(-10000.0)
                value[..., -126:] = 0.0
            elif meta.name == "t":
                value.fill(1.0)
        elif meta.type == "tensor(int64)":
            if meta.name == "token_ids":
                if token_fixture is None:
                    raise SystemExit("text component requires --token-fixture")
                value = np.fromfile(token_fixture, dtype="<i8").reshape(shape)
            elif meta.name == "positions":
                start = {"prefill": 126, "bos": 190, "latent": 191}.get(component, 0)
                value = np.arange(start, start + int(np.prod(shape)), dtype=np.int64).reshape(shape)
            else:
                value = np.zeros(shape, dtype=np.int64)
        elif meta.type == "tensor(bool)":
            value = np.ones(shape, dtype=np.bool_)
        else:
            raise SystemExit(f"unsupported input dtype {meta.type} for {meta.name}")
        value = np.ascontiguousarray(value)
        feed[meta.name] = value
        records[meta.name] = {
            "shape": list(value.shape),
            "dtype": value.dtype.name,
            "sha256": hashlib.sha256(value.tobytes()).hexdigest(),
        }
    return feed, records


def provider_events(profile: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    events = json.loads(profile.read_text())
    for event in events:
        provider = event.get("args", {}).get("provider")
        if provider:
            counts[provider] = counts.get(provider, 0) + 1
    return counts


def options(args: argparse.Namespace) -> tuple[ort.SessionOptions, dict[str, str]]:
    session = ort.SessionOptions()
    session.intra_op_num_threads = 1
    session.inter_op_num_threads = 1
    session.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
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
        "enable_htp_fp16_precision": "0",
    }
    return session, provider


def output_record(value: np.ndarray) -> dict[str, Any]:
    array = np.ascontiguousarray(value)
    record: dict[str, Any] = {
        "shape": list(array.shape),
        "dtype": array.dtype.name,
        "elements": int(array.size),
        "sha256": hashlib.sha256(array.tobytes()).hexdigest(),
    }
    if np.issubdtype(array.dtype, np.floating):
        record.update({
            "finite": bool(np.all(np.isfinite(array))),
            "min": float(np.min(array)),
            "max": float(np.max(array)),
            "mean": float(np.mean(array, dtype=np.float64)),
        })
    return record


def run(args: argparse.Namespace) -> None:
    process_start = time.perf_counter()
    for path in (args.model, args.backend):
        if not path.exists():
            raise SystemExit(f"missing required path: {path}")
    if args.token_fixture is not None and not args.token_fixture.exists():
        raise SystemExit(f"missing token fixture: {args.token_fixture}")
    if args.mode == "generate" and args.descriptor.exists():
        raise SystemExit(f"refusing to overwrite descriptor: {args.descriptor}")
    if args.mode == "reload" and not args.descriptor.exists():
        raise SystemExit(f"missing descriptor: {args.descriptor}")
    if args.require_source_absent:
        allowed = {args.descriptor.resolve()}
        unexpected = [path for path in args.isolation_root.rglob("*.onnx")
                      if path.resolve() not in allowed]
        if unexpected:
            raise SystemExit(f"source/unexpected ONNX visible in isolation root: {unexpected}")

    session_options, provider_options = options(args)
    session_start = time.perf_counter()
    session = ort.InferenceSession(
        str(args.model), sess_options=session_options,
        providers=[("QNNExecutionProvider", provider_options)],
    )
    session_seconds = time.perf_counter() - session_start
    feed, input_records = deterministic_feed(session, args.component, args.token_fixture)
    run_start = time.perf_counter()
    outputs = session.run(None, feed)
    run_seconds = time.perf_counter() - run_start
    if not outputs:
        raise SystemExit("component returned no outputs")
    output_records = [output_record(value) for value in outputs]
    if any(record.get("finite") is False for record in output_records):
        raise SystemExit("component output contains non-finite values")
    ort_profile = Path(session.end_profiling())

    binary = args.descriptor.with_name(args.descriptor.stem + "_qnn.bin")
    qnn_profile = Path(str(args.profile_prefix) + ".qnn.csv")
    for path in (args.descriptor, binary, ort_profile, qnn_profile):
        if not path.exists():
            raise SystemExit(f"missing generated evidence: {path}")
    events = provider_events(ort_profile)
    if events.get("QNNExecutionProvider", 0) < 1 or events.get("CPUExecutionProvider", 0) != 0:
        raise SystemExit(f"provider proof failed: {events}")

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
            "graph_optimization": "ORT_ENABLE_BASIC",
        },
        "provider_events": events,
        "qnn_only_provider_proof": True,
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
        "outputs": output_records,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "reload"))
    parser.add_argument("--component", choices=("text", "prefill", "bos", "latent", "flow",
                                                   "decoder12", "decoder6", "decoder1"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--profile-prefix", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--token-fixture", type=Path)
    parser.add_argument("--require-source-absent", action="store_true")
    parser.add_argument("--isolation-root", type=Path, default=Path("."))
    args = parser.parse_args()
    for name in ("model", "descriptor", "backend", "profile_prefix", "result", "isolation_root"):
        setattr(args, name, getattr(args, name).resolve())
    if args.token_fixture is not None:
        args.token_fixture = args.token_fixture.resolve()
    return args


if __name__ == "__main__":
    run(parse_args())
