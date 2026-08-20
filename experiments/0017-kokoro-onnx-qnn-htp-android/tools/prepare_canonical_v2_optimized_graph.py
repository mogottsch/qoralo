#!/usr/bin/env python3
"""Serialize/profile the canonical-v2 fixed ONNX graph with ORT basic optimization."""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from collections import Counter
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort

PINS = {
    "model": (338478095, "26120b192f2ad7567c6c1215ccbcf374d1946460c4589c1098941ab15e43aa73"),
    "tokens": (1880, "9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280"),
    "style": (1024, "8acaca07623d98a1085f6b182fb997d715dd1d67862e350567e6d9b1bc8ec71b"),
    "speed": (4, "e00e5eb9444182f352323374ef4e08ebcb784725fdd4fd612d7730540b3e0c8c"),
}
TOKEN_COUNT = 235
AUDIO_SAMPLES = 361200
DURATION_SUM = 602


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, key: str) -> None:
    size, expected = PINS[key]
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"{key} is not a regular file")
    if path.stat().st_size != size or sha256(path) != expected:
        raise RuntimeError(f"{key} pin mismatch: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--tokens", type=Path, required=True)
    parser.add_argument("--style", type=Path, required=True)
    parser.add_argument("--speed", type=Path, required=True)
    parser.add_argument("--optimized-model", type=Path, required=True)
    parser.add_argument("--profile-prefix", type=Path, required=True)
    parser.add_argument("--audio-output", type=Path, required=True)
    parser.add_argument("--duration-output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    for key in PINS:
        verify(getattr(args, key), key)

    tokens = np.fromfile(args.tokens, dtype="<i8").reshape(1, TOKEN_COUNT)
    style = np.fromfile(args.style, dtype="<f4").reshape(1, 256)
    speed = np.fromfile(args.speed, dtype="<f4").reshape(1)
    args.optimized_model.parent.mkdir(parents=True, exist_ok=True)
    args.profile_prefix.parent.mkdir(parents=True, exist_ok=True)

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    options.optimized_model_filepath = str(args.optimized_model)
    options.enable_profiling = True
    options.profile_file_prefix = str(args.profile_prefix)
    create_start = time.perf_counter()
    session = ort.InferenceSession(
        str(args.model), sess_options=options, providers=["CPUExecutionProvider"]
    )
    create_seconds = time.perf_counter() - create_start
    run_start = time.perf_counter()
    audio, duration = session.run(
        ["audio", "pred_dur"],
        {"tokens": tokens, "style": style, "speed": speed},
    )
    run_seconds = time.perf_counter() - run_start
    profile_path = Path(session.end_profiling())

    audio = np.ascontiguousarray(audio, dtype="<f4")
    duration = np.ascontiguousarray(duration, dtype="<i8")
    if audio.shape != (AUDIO_SAMPLES,) or duration.shape != (TOKEN_COUNT,):
        raise RuntimeError(f"runtime output shape drift: {audio.shape} {duration.shape}")
    if int(duration.sum()) != DURATION_SUM:
        raise RuntimeError("duration sum drift")
    if not np.isfinite(audio).all():
        raise RuntimeError("non-finite audio")
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    clipped = int(np.count_nonzero(np.abs(audio) >= 1.0))
    if not (1e-4 <= peak < 1 and rms >= 1e-5 and clipped == 0):
        raise RuntimeError("optimized CPU structural audio gate failed")
    args.audio_output.parent.mkdir(parents=True, exist_ok=True)
    args.audio_output.write_bytes(audio.tobytes())
    args.duration_output.write_bytes(duration.tobytes())

    optimized = onnx.load(str(args.optimized_model), load_external_data=False)
    onnx.checker.check_model(optimized, full_check=True)
    operators = Counter(node.op_type for node in optimized.graph.node)
    quantized = sum(
        operators.get(name, 0)
        for name in (
            "QuantizeLinear",
            "DequantizeLinear",
            "DynamicQuantizeLinear",
            "MatMulInteger",
            "QLinearConv",
            "QLinearMatMul",
        )
    )
    if quantized:
        raise RuntimeError("quantized operator appeared")
    record = {
        "schema_version": 1,
        "status": "passed",
        "runtime": {
            "onnxruntime": ort.__version__,
            "provider": "CPUExecutionProvider",
            "optimization": "basic",
            "threads": 1,
        },
        "source": {
            "ignored_path": str(args.model),
            "bytes": args.model.stat().st_size,
            "sha256": sha256(args.model),
        },
        "inputs": {
            "tokens_sha256": sha256(args.tokens),
            "style_sha256": sha256(args.style),
            "speed_sha256": sha256(args.speed),
        },
        "optimized": {
            "ignored_path": str(args.optimized_model),
            "bytes": args.optimized_model.stat().st_size,
            "sha256": sha256(args.optimized_model),
            "nodes": len(optimized.graph.node),
            "initializers": len(optimized.graph.initializer),
            "operators": dict(sorted(operators.items())),
            "quantized_operator_count": quantized,
        },
        "profile": {
            "ignored_path": str(profile_path),
            "bytes": profile_path.stat().st_size,
            "sha256": sha256(profile_path),
        },
        "outputs": {
            "audio": {
                "ignored_path": str(args.audio_output),
                "shape": [AUDIO_SAMPLES],
                "bytes": args.audio_output.stat().st_size,
                "sha256": sha256(args.audio_output),
                "absolute_peak": peak,
                "rms": rms,
                "clipped_float_samples": clipped,
            },
            "duration": {
                "ignored_path": str(args.duration_output),
                "shape": [TOKEN_COUNT],
                "sum": int(duration.sum()),
                "bytes": args.duration_output.stat().st_size,
                "sha256": sha256(args.duration_output),
            },
        },
        "timing": {
            "session_creation_seconds": create_seconds,
            "run_seconds": run_seconds,
        },
        "memory": {
            "ru_maxrss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "semantics": "process-lifetime resident-set high-water; includes Python, ORT session/optimization/serialization, inference, profile and ONNX validation; not steady PSS or component-isolated",
        },
        "claim_boundary": "Metadata/optimization preparation and CPU execution only; not QNN assignment, physical HTP proof, benchmark performance, or listening acceptance.",
    }
    args.provenance.parent.mkdir(parents=True, exist_ok=True)
    args.provenance.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
