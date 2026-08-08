#!/usr/bin/env python3
"""Host-validate first and cached decoder segment sets as one cache sequence."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import resource
import sys
import time
from pathlib import Path

import torch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first_directory", type=Path)
    parser.add_argument("cached_directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--atol", type=float, default=2e-5)
    parser.add_argument("--rtol", type=float, default=1e-5)
    return parser.parse_args()


def version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def execute_segment(
    runtime: object,
    directory: Path,
    segment: int,
    inputs: tuple[torch.Tensor, ...],
) -> tuple[tuple[torch.Tensor, ...], float, float]:
    pte = directory / f"segment-{segment}.pte"
    started = time.perf_counter()
    program = runtime.load_program(str(pte))
    load_seconds = time.perf_counter() - started
    method = program.load_method("forward")
    started = time.perf_counter()
    outputs = tuple(method.execute(tuple(value.contiguous() for value in inputs)))
    inference_seconds = time.perf_counter() - started
    del method, program
    return outputs, load_seconds, inference_seconds


def compare_outputs(
    actual: tuple[torch.Tensor, ...],
    expected: tuple[torch.Tensor, ...],
    atol: float,
    rtol: float,
    label: str,
) -> tuple[float, float]:
    if len(actual) != len(expected):
        raise SystemExit(f"{label}: expected {len(expected)} outputs, got {len(actual)}")
    errors = [(value - target).abs() for value, target in zip(actual, expected)]
    if not all(
        torch.allclose(value, target, atol=atol, rtol=rtol)
        for value, target in zip(actual, expected)
    ):
        failed = [index for index, error in enumerate(errors) if error.max().item() > atol]
        raise SystemExit(f"{label}: output comparison failed at outputs {failed}")
    return errors[0].max().item(), max(
        (error.max().item() for error in errors[1:]), default=0.0
    )


def main() -> None:
    args = parse_args()
    from executorch.runtime import Runtime

    runtime = Runtime.get()
    first_caches: dict[int, tuple[torch.Tensor, ...]] = {}
    calls: list[dict[str, object]] = []

    # Call 0: execute the first-chunk entry set and retain its actual cache outputs.
    activation: torch.Tensor | None = None
    first_segments: list[dict[str, object]] = []
    first_total_load = 0.0
    first_total_inference = 0.0
    first_final_expected: torch.Tensor | None = None
    for segment in range(8):
        reference = torch.load(
            args.first_directory / f"segment-{segment}.reference.pt",
            map_location="cpu",
            weights_only=True,
        )
        inputs = list(reference["inputs"])
        if activation is not None:
            inputs[0] = activation
        actual, load_seconds, inference_seconds = execute_segment(
            runtime, args.first_directory, segment, tuple(inputs)
        )
        expected = tuple(reference["outputs"])
        activation_error, cache_error = compare_outputs(
            actual, expected, args.atol, args.rtol, f"first segment {segment}"
        )
        activation = actual[0]
        first_caches[segment] = tuple(value.clone() for value in actual[1:])
        first_final_expected = expected[0]
        first_total_load += load_seconds
        first_total_inference += inference_seconds
        first_segments.append(
            {
                "segment": segment,
                "input_count": len(inputs),
                "output_count": len(actual),
                "activation_max_abs_error": activation_error,
                "cache_max_abs_error": cache_error,
                "load_seconds": load_seconds,
                "inference_seconds": inference_seconds,
            }
        )
    assert activation is not None and first_final_expected is not None
    first_pcm_error = (activation - first_final_expected).abs()
    calls.append(
        {
            "call": 0,
            "entry": "first",
            "segments": first_segments,
            "total_load_seconds": first_total_load,
            "total_inference_seconds": first_total_inference,
            "pcm_shape": list(activation.shape),
            "pcm_max_abs_error": first_pcm_error.max().item(),
            "pcm_mean_abs_error": first_pcm_error.float().mean().item(),
            "allclose": True,
        }
    )

    # Call 1: use actual call-0 cache outputs rather than fixture pre-cache tensors.
    activation = None
    cached_segments: list[dict[str, object]] = []
    cached_total_load = 0.0
    cached_total_inference = 0.0
    cached_final_expected: torch.Tensor | None = None
    for segment in range(8):
        reference = torch.load(
            args.cached_directory / f"segment-{segment}.reference.pt",
            map_location="cpu",
            weights_only=True,
        )
        inputs = list(reference["inputs"])
        if activation is not None:
            inputs[0] = activation
        inputs[1:] = first_caches[segment]
        actual, load_seconds, inference_seconds = execute_segment(
            runtime, args.cached_directory, segment, tuple(inputs)
        )
        expected = tuple(reference["outputs"])
        activation_error, cache_error = compare_outputs(
            actual, expected, args.atol, args.rtol, f"cached segment {segment}"
        )
        activation = actual[0]
        cached_final_expected = expected[0]
        cached_total_load += load_seconds
        cached_total_inference += inference_seconds
        cached_segments.append(
            {
                "segment": segment,
                "input_count": len(inputs),
                "output_count": len(actual),
                "activation_max_abs_error": activation_error,
                "cache_max_abs_error": cache_error,
                "load_seconds": load_seconds,
                "inference_seconds": inference_seconds,
            }
        )
    assert activation is not None and cached_final_expected is not None
    cached_pcm_error = (activation - cached_final_expected).abs()
    calls.append(
        {
            "call": 1,
            "entry": "cached",
            "cache_source": "actual call-0 ExecuTorch outputs",
            "segments": cached_segments,
            "total_load_seconds": cached_total_load,
            "total_inference_seconds": cached_total_inference,
            "pcm_shape": list(activation.shape),
            "pcm_max_abs_error": cached_pcm_error.max().item(),
            "pcm_mean_abs_error": cached_pcm_error.float().mean().item(),
            "allclose": True,
        }
    )

    result = {
        "schema_version": 1,
        "status": "passed",
        "scope": "FP32 fixed-shape eight-segment streaming acoustic decoder host sequence",
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": version("executorch"),
            "backend": "xnnpack",
        },
        "interface": {
            "segment_count": 8,
            "cache_tensor_count": sum(len(values) for values in first_caches.values()),
            "first_entry": "latent -> PCM plus 34 cache tensors",
            "cached_entry": "latent plus 34 cache tensors -> PCM plus 34 updated cache tensors",
        },
        "calls": calls,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "atol": args.atol,
        "rtol": args.rtol,
        "allclose": True,
        "limitations": [
            "The eight PTEs duplicate weights between first and cached entry sets.",
            "This validates two host chunks only; Android execution is step 8.",
            "The fixed batch, latent width, and one-step temporal shapes are part of the ABI.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
