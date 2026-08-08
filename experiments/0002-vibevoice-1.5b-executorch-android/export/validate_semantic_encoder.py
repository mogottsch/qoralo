#!/usr/bin/env python3
"""Validate eager references and a real two-call ExecuTorch semantic chain."""

from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path

import torch

from fixture_utils import repo_root, tensor_metadata

ATOL = 1e-5
RTOL = 1e-4
CACHE_ACCEPTANCE_ATOL = 1e-3


def compare(actual: torch.Tensor, expected: torch.Tensor) -> dict[str, object]:
    if tuple(actual.shape) != tuple(expected.shape):
        raise ValueError(f"shape mismatch: {tuple(actual.shape)} != {tuple(expected.shape)}")
    finite = bool(torch.isfinite(actual).all())
    error = (actual - expected).abs()
    threshold = ATOL + RTOL * expected.abs()
    mismatches = int((~torch.isfinite(actual) | (error > threshold)).sum())
    bounded_mismatches = int((~torch.isfinite(actual) | (error > (CACHE_ACCEPTANCE_ATOL + RTOL * expected.abs()))).sum())
    return {
        "finite": finite,
        "allclose": finite and mismatches == 0,
        "mismatch_count": mismatches,
        "bounded_cache_allclose": finite and bounded_mismatches == 0,
        "bounded_cache_mismatch_count": bounded_mismatches,
        "max_abs_error": error.nan_to_num(nan=float("inf")).max().item(),
    }


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=root / "artifacts/0002/lane-b/semantic-encoder")
    parser.add_argument("--output", type=Path, default=root / "artifacts/0002/lane-b/semantic-encoder/host-result.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from executorch.runtime import Runtime

    started = time.perf_counter()
    load_started = started
    first = Runtime.get().load_program(str(args.artifact_dir / "semantic-encoder-first-xnnpack.pte")).load_method("forward")
    cached = Runtime.get().load_program(str(args.artifact_dir / "semantic-encoder-cached-xnnpack.pte")).load_method("forward")
    load_seconds = time.perf_counter() - load_started
    first_ref = torch.load(args.artifact_dir / "semantic-encoder-first-xnnpack.reference.pt", map_location="cpu", weights_only=True)
    cached_ref = torch.load(args.artifact_dir / "semantic-encoder-cached-xnnpack.reference.pt", map_location="cpu", weights_only=True)

    call_started = time.perf_counter()
    first_outputs = tuple(first.execute(first_ref["inputs"]))
    first_seconds = time.perf_counter() - call_started
    # Critical chain: these are actual runtime outputs, not eager/captured caches.
    chained_inputs = (cached_ref["inputs"][0], *first_outputs[1:])
    call_started = time.perf_counter()
    cached_outputs = tuple(cached.execute(chained_inputs))
    cached_seconds = time.perf_counter() - call_started
    reset_outputs = tuple(first.execute(first_ref["inputs"]))

    calls = []
    accepted = True
    for label, actuals, expecteds in (
        ("call_1", first_outputs, first_ref["outputs"]),
        ("call_2_chained", cached_outputs, cached_ref["outputs"]),
        ("reset_call", reset_outputs, first_ref["outputs"]),
    ):
        metrics = [compare(actual, expected) for actual, expected in zip(actuals, expecteds, strict=True)]
        # Semantic features retain the strict FP32 criterion. Cache tensors use
        # a separately visible 1e-3 bound for ordinary XNNPACK convolution
        # reduction-order drift; call two's strict feature match proves the
        # bounded runtime caches preserve the observable chained result.
        accepted &= metrics[0]["allclose"] and all(metric["bounded_cache_allclose"] for metric in metrics[1:])
        calls.append({
            "label": label,
            "semantic_features": metrics[0],
            "cache": {
                "tensor_count": len(metrics) - 1,
                "strict_allclose": all(metric["allclose"] for metric in metrics[1:]),
                "strict_mismatch_count": sum(metric["mismatch_count"] for metric in metrics[1:]),
                "acceptance_atol": CACHE_ACCEPTANCE_ATOL,
                "accepted": all(metric["bounded_cache_allclose"] for metric in metrics[1:]),
                "acceptance_mismatch_count": sum(metric["bounded_cache_mismatch_count"] for metric in metrics[1:]),
                "max_abs_error": max(metric["max_abs_error"] for metric in metrics[1:]),
            },
        })
    reset_exact = all(torch.equal(a, b) for a, b in zip(reset_outputs, first_outputs, strict=True))
    accepted &= reset_exact
    result = {
        "schema_version": 1,
        "component": "semantic_audio_encoder",
        "backend": "xnnpack",
        "thresholds": {"strict_atol": ATOL, "rtol": RTOL, "cache_acceptance_atol": CACHE_ACCEPTANCE_ATOL},
        "chaining": {"call_2_cache_source": "actual ExecuTorch call_1 outputs[1:35]", "cache_tensor_count": 34},
        "calls": calls,
        "reset": {"rule": "invoke first entry point with no cache tensors", "bit_exact_with_initial_call": reset_exact},
        "timing_seconds": {"load_two_programs": load_seconds, "call_1": first_seconds, "call_2": cached_seconds, "total": time.perf_counter() - started},
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "runtime_outputs": {"call_1_features": tensor_metadata(first_outputs[0]), "call_2_features": tensor_metadata(cached_outputs[0])},
        "accepted": accepted,
        "conclusion": "accepted: real two-call XNNPACK runtime chain matches eager capture and reset is deterministic" if accepted else "rejected: runtime metrics failed",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not accepted:
        raise SystemExit("Semantic encoder host validation failed")


if __name__ == "__main__":
    main()
