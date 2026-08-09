#!/usr/bin/env python3
"""Prepare raw tensors and compare the two-call Android semantic-path probe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

DTYPE = np.dtype("<f4")
FEATURE_SHAPE = (1, 1, 128)
EMBEDDING_SHAPE = (1, 1, 1536)
STRICT_ATOL = 1e-5
RTOL = 1e-4
CACHE_ATOL = 1e-3


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_tensor(path: Path, value: Any) -> None:
    array = value.detach().cpu().contiguous().numpy().astype(DTYPE, copy=False)
    path.write_bytes(array.tobytes())


def read_tensor(path: Path, shape: tuple[int, ...]) -> np.ndarray:
    value = np.fromfile(path, dtype=DTYPE)
    expected = int(np.prod(shape))
    if value.size != expected:
        raise ValueError(f"{path}: expected {expected} float32 values, got {value.size}")
    return value.reshape(shape)


def metadata(path: Path, shape: tuple[int, ...]) -> dict[str, Any]:
    value = read_tensor(path, shape)
    return {
        "file": path.name, "shape": list(shape), "dtype": "float32",
        "bytes": path.stat().st_size, "sha256": sha256(path),
        "finite": bool(np.isfinite(value).all()),
    }


def prepare(args: argparse.Namespace) -> None:
    import torch
    from executorch.runtime import Runtime

    args.output.mkdir(parents=True, exist_ok=True)
    fixture = torch.load(args.semantic_fixture, map_location="cpu", weights_only=False)
    connector_fixture = torch.load(args.connector_fixture, map_location="cpu", weights_only=True)
    calls = fixture["calls"]
    cache_names = tuple(fixture["cache_names"])
    if len(calls) != 2 or len(cache_names) != 34:
        raise ValueError("Expected exactly two semantic calls and 34 cache tensors")

    acoustic = connector_fixture["acoustic_features"].float().contiguous()
    write_tensor(args.output / "acoustic.f32le", acoustic)
    program = Runtime.get().load_program(str(args.connector_pte))
    method = program.load_method("forward")
    call_records = []
    cache_shapes: list[tuple[int, ...]] = []
    for call_index, call in enumerate(calls):
        audio = call["audio"].float().contiguous()
        features = call["features"].float().contiguous()
        write_tensor(args.output / f"call-{call_index}-audio.f32le", audio)
        write_tensor(args.output / f"call-{call_index}-expected-features.f32le", features)
        for cache_index, name in enumerate(cache_names):
            cache = call["post_cache"][f"{name}/sample_0"].unsqueeze(0).float().contiguous()
            if call_index == 0:
                cache_shapes.append(tuple(cache.shape))
            elif tuple(cache.shape) != cache_shapes[cache_index]:
                raise ValueError(f"Cache shape changed at {cache_index}")
            write_tensor(args.output / f"call-{call_index}-expected-cache-{cache_index:02d}.f32le", cache)
        embedding = method.execute((acoustic, features))[0].float().contiguous()
        if tuple(embedding.shape) != EMBEDDING_SHAPE:
            raise ValueError(f"Unexpected connector output {tuple(embedding.shape)}")
        write_tensor(args.output / f"call-{call_index}-expected-embedding.f32le", embedding)
        call_records.append({
            "call": call_index,
            "audio": metadata(args.output / f"call-{call_index}-audio.f32le", (1, 1, 3200)),
            "features": metadata(args.output / f"call-{call_index}-expected-features.f32le", FEATURE_SHAPE),
            "embedding": metadata(args.output / f"call-{call_index}-expected-embedding.f32le", EMBEDDING_SHAPE),
        })

    manifest = {
        "schema_version": 1,
        "call_count": 2,
        "cache_tensor_count": 34,
        "cache_names": list(cache_names),
        "cache_shapes": [list(shape) for shape in cache_shapes],
        "cache_transport": "call 1 consumes the actual device outputs of call 0",
        "acoustic": metadata(args.output / "acoustic.f32le", (1, 1, 64)),
        "calls": call_records,
        "connector_pte": {"path": str(args.connector_pte), "bytes": args.connector_pte.stat().st_size, "sha256": sha256(args.connector_pte)},
    }
    (args.output / "fixture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


def comparison(actual: np.ndarray, expected: np.ndarray, atol: float) -> dict[str, Any]:
    finite = bool(np.isfinite(actual).all())
    difference = np.abs(actual - expected)
    close = np.isclose(actual, expected, atol=atol, rtol=RTOL)
    return {
        "finite": finite, "allclose": bool(finite and close.all()),
        "mismatch_count": int((~close).sum()),
        "max_abs_error": float(difference.max(initial=0)),
        "mean_abs_error": float(difference.mean()), "atol": atol, "rtol": RTOL,
    }


def compare(args: argparse.Namespace) -> None:
    fixture = json.loads((args.fixture / "fixture-manifest.json").read_text())
    device = json.loads(args.device_result.read_text())
    cache_shapes = [tuple(shape) for shape in fixture["cache_shapes"]]
    runs: list[dict[str, Any]] = []
    accepted = device.get("status") == "passed"
    deterministic = True
    for run in range(2):
        calls: list[dict[str, Any]] = []
        for call in range(2):
            prefix = args.artifacts / f"run-{run}-call-{call}"
            actual_features = read_tensor(prefix.with_name(prefix.name + "-features.f32le"), FEATURE_SHAPE)
            expected_features = read_tensor(args.fixture / f"call-{call}-expected-features.f32le", FEATURE_SHAPE)
            feature_cmp = comparison(actual_features, expected_features, STRICT_ATOL)
            strict_cache_mismatches = 0
            bounded_cache_mismatches = 0
            cache_max_error = 0.0
            cache_hashes = []
            for index, shape in enumerate(cache_shapes):
                actual_path = prefix.with_name(prefix.name + f"-cache-{index:02d}.f32le")
                actual = read_tensor(actual_path, shape)
                expected = read_tensor(args.fixture / f"call-{call}-expected-cache-{index:02d}.f32le", shape)
                strict_cache_mismatches += int((~np.isclose(actual, expected, atol=STRICT_ATOL, rtol=RTOL)).sum())
                bounded_cache_mismatches += int((~np.isclose(actual, expected, atol=CACHE_ATOL, rtol=RTOL)).sum())
                cache_max_error = max(cache_max_error, float(np.abs(actual - expected).max(initial=0)))
                cache_hashes.append(sha256(actual_path))
            embedding_path = prefix.with_name(prefix.name + "-embedding.f32le")
            actual_embedding = read_tensor(embedding_path, EMBEDDING_SHAPE)
            expected_embedding = read_tensor(args.fixture / f"call-{call}-expected-embedding.f32le", EMBEDDING_SHAPE)
            embedding_cmp = comparison(actual_embedding, expected_embedding, STRICT_ATOL)
            record = {
                "call": call,
                "semantic_features": {**feature_cmp, "sha256": sha256(prefix.with_name(prefix.name + "-features.f32le"))},
                "caches": {
                    "tensor_count": 34, "strict_mismatch_count": strict_cache_mismatches,
                    "acceptance_atol": CACHE_ATOL, "acceptance_mismatch_count": bounded_cache_mismatches,
                    "accepted": bounded_cache_mismatches == 0, "max_abs_error": cache_max_error,
                    "aggregate_sha256": hashlib.sha256("".join(cache_hashes).encode()).hexdigest(),
                },
                # The accepted join PTE exposes its connector sum as the final LM embedding.
                "connector_output": {**embedding_cmp, "shape": list(EMBEDDING_SHAPE), "sha256": sha256(embedding_path)},
                "final_embedding": {**embedding_cmp, "shape": [1, 1536], "tensor_shape": list(EMBEDDING_SHAPE), "sha256": sha256(embedding_path)},
            }
            call_ok = feature_cmp["allclose"] and bounded_cache_mismatches == 0 and embedding_cmp["allclose"]
            accepted &= call_ok
            calls.append(record)
            if run == 1:
                prior = runs[0]["calls"][call]
                deterministic &= record["semantic_features"]["sha256"] == prior["semantic_features"]["sha256"]
                deterministic &= record["caches"]["aggregate_sha256"] == prior["caches"]["aggregate_sha256"]
                deterministic &= record["final_embedding"]["sha256"] == prior["final_embedding"]["sha256"]
        runs.append({"run": run, "temperature": "cold" if run == 0 else "warm_page_cache", "calls": calls})
    accepted &= deterministic

    result = {
        "schema_version": 1, "component": "semantic_path_android",
        "status": "passed" if accepted else "failed", "accepted": accepted,
        "chaining": {"call_2_cache_source": "actual Android call_1 outputs[1:35]", "cache_tensor_count": 34},
        "thresholds": {"strict_atol": STRICT_ATOL, "rtol": RTOL, "cache_acceptance_atol": CACHE_ATOL},
        "deterministic_repeat_hashes": deterministic,
        "runs": runs,
        "latency_seconds": device.get("runs"),
        "memory_kib": device.get("memory_kib"),
        "runtime": {"executorch": "1.2.0", "backend": "xnnpack", "precision": "fp32", "load_mode": "mmap"},
        "device": json.loads(args.device_properties.read_text()),
        "artifacts": device.get("artifacts"),
        "commands": [
            "artifacts/venv-executorch-1.2/bin/python experiments/0002-vibevoice-1.5b-executorch-android/export/semantic_android_io.py prepare artifacts/0002/lane-b/semantic-android-fixture --semantic-fixture artifacts/0002/lane-b/semantic-encoder/capture-1/fixture.pt --connector-fixture artifacts/0002/lane-b/connectors/capture-1/fixture.pt --connector-pte artifacts/0002/lane-b/connectors/connectors-xnnpack.pte",
            "experiments/0002-vibevoice-1.5b-executorch-android/android/run-semantic-probe.sh",
            f"artifacts/venv-executorch-1.2/bin/python experiments/0002-vibevoice-1.5b-executorch-android/export/semantic_android_io.py compare artifacts/0002/lane-b/semantic-android-fixture artifacts/0002/lane-b/semantic-android artifacts/0002/lane-b/semantic-android/device-result.json artifacts/0002/lane-b/semantic-android/device-properties.json experiments/0002-vibevoice-1.5b-executorch-android/results/semantic-path-android.json --implementation-commit {args.implementation_commit}",
        ],
        "commit_shas": [args.implementation_commit],
        "conclusion": "accepted: two Android semantic calls use device-produced cache state and their features, caches, connector output, and logical [1,1536] final embedding match host" if accepted else "rejected: Android semantic path did not satisfy all correctness and determinism checks",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not accepted:
        raise SystemExit(2)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("output", type=Path)
    prepare_parser.add_argument("--semantic-fixture", type=Path, required=True)
    prepare_parser.add_argument("--connector-fixture", type=Path, required=True)
    prepare_parser.add_argument("--connector-pte", type=Path, required=True)
    prepare_parser.set_defaults(func=prepare)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("fixture", type=Path)
    compare_parser.add_argument("artifacts", type=Path)
    compare_parser.add_argument("device_result", type=Path)
    compare_parser.add_argument("device_properties", type=Path)
    compare_parser.add_argument("output", type=Path)
    compare_parser.add_argument("--implementation-commit", required=True)
    compare_parser.set_defaults(func=compare)
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.func(arguments)
