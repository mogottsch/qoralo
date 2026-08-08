#!/usr/bin/env python3
"""Host-validate first and cached decoder segment sets as one cache sequence."""

from __future__ import annotations

import argparse
import hashlib
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
    parser.add_argument("--precision", choices=("fp32", "fp16"), default="fp32")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument(
        "--atol",
        type=float,
        help="Absolute FP32-fixture tolerance (default: 2e-5 FP32, 2e-3 FP16)",
    )
    parser.add_argument(
        "--rtol",
        type=float,
        help="Relative FP32-fixture tolerance (default: 1e-5 FP32, 2e-3 FP16)",
    )
    parser.add_argument(
        "--cache-atol",
        type=float,
        help="Cache-only absolute tolerance (default: atol FP32, 5e-2 FP16)",
    )
    return parser.parse_args()


def version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def tensor_sha256(value: torch.Tensor) -> str:
    return hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def current_pss_kib() -> int | None:
    try:
        for line in Path("/proc/self/smaps_rollup").read_text().splitlines():
            if line.startswith("Pss:"):
                return int(line.split()[1])
    except OSError:
        pass
    return None


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
    cache_atol: float | None = None,
) -> tuple[float, float]:
    if len(actual) != len(expected):
        raise SystemExit(f"{label}: expected {len(expected)} outputs, got {len(actual)}")
    errors = [
        (value.float() - target.float()).abs()
        for value, target in zip(actual, expected)
    ]
    close = [
        torch.allclose(
            value.float(),
            target.float(),
            atol=atol if index == 0 or cache_atol is None else cache_atol,
            rtol=rtol,
        )
        for index, (value, target) in enumerate(zip(actual, expected))
    ]
    if not all(close):
        failed = [index for index, passed in enumerate(close) if not passed]
        raise SystemExit(f"{label}: output comparison failed at outputs {failed}")
    return errors[0].max().item(), max(
        (error.max().item() for error in errors[1:]), default=0.0
    )


def run_sequence(
    runtime: object,
    first_directory: Path,
    cached_directory: Path,
    atol: float,
    rtol: float,
    repeat: int,
    cache_atol: float | None = None,
) -> tuple[list[dict[str, object]], list[str]]:
    first_caches: dict[int, tuple[torch.Tensor, ...]] = {}
    calls: list[dict[str, object]] = []
    hashes: list[str] = []

    # Call 0: execute the first-chunk entry set and retain its actual cache outputs.
    activation: torch.Tensor | None = None
    first_segments: list[dict[str, object]] = []
    first_total_load = 0.0
    first_total_inference = 0.0
    first_final_expected: torch.Tensor | None = None
    first_fixture_pcm: torch.Tensor | None = None
    for segment in range(8):
        reference = torch.load(
            first_directory / f"segment-{segment}.reference.pt",
            map_location="cpu",
            weights_only=True,
        )
        inputs = list(reference["inputs"])
        if activation is not None:
            inputs[0] = activation
        actual, load_seconds, inference_seconds = execute_segment(
            runtime, first_directory, segment, tuple(inputs)
        )
        expected = tuple(reference["outputs"])
        activation_error, cache_error = compare_outputs(
            actual,
            expected,
            cache_atol if cache_atol is not None else atol,
            rtol,
            f"repeat {repeat} first segment {segment}",
            cache_atol,
        )
        activation = actual[0]
        first_caches[segment] = tuple(value.clone() for value in actual[1:])
        first_final_expected = expected[0]
        if reference.get("fixture_pcm") is not None:
            first_fixture_pcm = reference["fixture_pcm"]
        first_total_load += load_seconds
        first_total_inference += inference_seconds
        hashes.extend(tensor_sha256(value) for value in actual)
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
    if first_fixture_pcm is None:
        first_fixture_pcm = first_final_expected.float()
    first_backend_error = (activation.float() - first_final_expected.float()).abs()
    first_pcm_error = (activation.float() - first_fixture_pcm.float()).abs()
    calls.append(
        {
            "call": 0,
            "entry": "first",
            "segments": first_segments,
            "total_load_seconds": first_total_load,
            "total_inference_seconds": first_total_inference,
            "pcm_shape": list(activation.shape),
            "pcm_dtype": str(activation.dtype).removeprefix("torch."),
            "backend_pcm_max_abs_error": first_backend_error.max().item(),
            "pcm_max_abs_error": first_pcm_error.max().item(),
            "pcm_mean_abs_error": first_pcm_error.mean().item(),
            "allclose": bool(
                torch.allclose(activation.float(), first_fixture_pcm.float(), atol=atol, rtol=rtol)
            ),
        }
    )

    # Call 1 uses actual call-0 runtime caches rather than fixture pre-cache tensors.
    activation = None
    cached_segments: list[dict[str, object]] = []
    cached_total_load = 0.0
    cached_total_inference = 0.0
    cached_final_expected: torch.Tensor | None = None
    cached_fixture_pcm: torch.Tensor | None = None
    for segment in range(8):
        reference = torch.load(
            cached_directory / f"segment-{segment}.reference.pt",
            map_location="cpu",
            weights_only=True,
        )
        inputs = list(reference["inputs"])
        if activation is not None:
            inputs[0] = activation
        inputs[1:] = first_caches[segment]
        actual, load_seconds, inference_seconds = execute_segment(
            runtime, cached_directory, segment, tuple(inputs)
        )
        expected = tuple(reference["outputs"])
        activation_error, cache_error = compare_outputs(
            actual,
            expected,
            cache_atol if cache_atol is not None else atol,
            rtol,
            f"repeat {repeat} cached segment {segment}",
            cache_atol,
        )
        activation = actual[0]
        cached_final_expected = expected[0]
        if reference.get("fixture_pcm") is not None:
            cached_fixture_pcm = reference["fixture_pcm"]
        cached_total_load += load_seconds
        cached_total_inference += inference_seconds
        hashes.extend(tensor_sha256(value) for value in actual)
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
    if cached_fixture_pcm is None:
        cached_fixture_pcm = cached_final_expected.float()
    cached_backend_error = (activation.float() - cached_final_expected.float()).abs()
    cached_pcm_error = (activation.float() - cached_fixture_pcm.float()).abs()
    calls.append(
        {
            "call": 1,
            "entry": "cached",
            "cache_source": "actual call-0 ExecuTorch outputs",
            "segments": cached_segments,
            "total_load_seconds": cached_total_load,
            "total_inference_seconds": cached_total_inference,
            "pcm_shape": list(activation.shape),
            "pcm_dtype": str(activation.dtype).removeprefix("torch."),
            "backend_pcm_max_abs_error": cached_backend_error.max().item(),
            "pcm_max_abs_error": cached_pcm_error.max().item(),
            "pcm_mean_abs_error": cached_pcm_error.mean().item(),
            "allclose": bool(
                torch.allclose(activation.float(), cached_fixture_pcm.float(), atol=atol, rtol=rtol)
            ),
        }
    )
    if not all(bool(call["allclose"]) for call in calls):
        raise SystemExit(f"repeat {repeat}: final PCM comparison failed")
    return calls, hashes


def main() -> None:
    args = parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least one")
    from executorch.runtime import Runtime

    atol = args.atol if args.atol is not None else (2e-3 if args.precision == "fp16" else 2e-5)
    rtol = args.rtol if args.rtol is not None else (2e-3 if args.precision == "fp16" else 1e-5)
    cache_atol = args.cache_atol if args.cache_atol is not None else (
        5e-2 if args.precision == "fp16" else atol
    )
    runtime = Runtime.get()
    repeats: list[dict[str, object]] = []
    output_hashes: list[list[str]] = []
    for repeat in range(args.repeats):
        calls, hashes = run_sequence(
            runtime,
            args.first_directory,
            args.cached_directory,
            atol,
            rtol,
            repeat,
            cache_atol,
        )
        repeats.append({"repeat": repeat, "calls": calls})
        output_hashes.append(hashes)

    deterministic = all(hashes == output_hashes[0] for hashes in output_hashes[1:])
    result = {
        "schema_version": 2,
        "status": "passed",
        "scope": f"{args.precision.upper()} fixed-shape eight-segment streaming acoustic decoder host sequence",
        "precision": args.precision,
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": version("executorch"),
            "backend": "xnnpack",
        },
        "interface": {
            "segment_count": 8,
            "cache_tensor_count": 34,
            "first_entry": "latent -> PCM plus 34 cache tensors",
            "cached_entry": "latent plus 34 actual runtime cache tensors -> PCM plus 34 updated cache tensors",
        },
        "repeats": repeats,
        "deterministic_repeats": deterministic,
        "repeat_output_tensor_count": len(output_hashes[0]),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "current_pss_kib": current_pss_kib(),
        "pcm_atol": atol,
        "cache_atol": cache_atol,
        "rtol": rtol,
        "tolerance_scope": (
            "pcm_atol applies to final PCM versus the captured FP32 fixture; "
            "cache_atol applies to caches and chained intermediate activations"
        ),
        "allclose": True,
        "limitations": [
            "The eight PTEs duplicate weights between first and cached entry sets.",
            "The fixed batch, latent width, and one-step temporal shapes are part of the ABI.",
            "Host PSS is a post-run point measurement; peak RSS comes from ru_maxrss.",
        ],
    }
    if not deterministic:
        result["status"] = "failed"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if result["status"] != "passed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
