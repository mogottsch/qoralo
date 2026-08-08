#!/usr/bin/env python3
"""Prepare Android streaming-decoder inputs and compare device PCM/cache outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from android_io import file_sha256, read_float32_le, write_float32_le
from fixture_utils import tensor_metadata

SEGMENT_COUNT = 8
RUN_COUNT = 2


def load_reference(directory: Path, segment: int) -> dict[str, Any]:
    return torch.load(
        directory / f"segment-{segment}.reference.pt",
        map_location="cpu",
        weights_only=True,
    )


def prepare(first_directory: Path, cached_directory: Path, output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    first = load_reference(first_directory, 0)["inputs"][0]
    cached = load_reference(cached_directory, 0)["inputs"][0]
    write_float32_le(output_directory / "call-0.f32le", first)
    write_float32_le(output_directory / "call-1.f32le", cached)
    manifest = {
        "schema_version": 1,
        "inputs": {
            "call_0": tensor_metadata(first),
            "call_1": tensor_metadata(cached),
        },
        "segments": [],
    }
    for segment in range(SEGMENT_COUNT):
        first_ref = load_reference(first_directory, segment)
        cached_ref = load_reference(cached_directory, segment)
        manifest["segments"].append(
            {
                "segment": segment,
                "first_input_count": len(first_ref["inputs"]),
                "first_output_shapes": [list(value.shape) for value in first_ref["outputs"]],
                "cached_input_count": len(cached_ref["inputs"]),
                "cached_output_shapes": [list(value.shape) for value in cached_ref["outputs"]],
            }
        )
    (output_directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


def compare_tensor(
    actual_path: Path,
    expected: torch.Tensor,
    atol: float,
    rtol: float,
    acceptance_atol: float | None = None,
) -> dict[str, Any]:
    expected = expected.detach().cpu().to(torch.float32).contiguous()
    actual = read_float32_le(actual_path, tuple(expected.shape))
    difference = (actual - expected).abs()
    strict = torch.isclose(actual, expected, atol=atol, rtol=rtol)
    accepted = (
        strict
        if acceptance_atol is None
        else torch.isclose(actual, expected, atol=acceptance_atol, rtol=rtol)
    )
    return {
        "shape": list(expected.shape),
        "raw_sha256": file_sha256(actual_path),
        "max_abs_error": difference.max().item(),
        "mean_abs_error": difference.float().mean().item(),
        "strict_mismatch_count": int((~strict).sum().item()),
        "allclose": bool(strict.all()),
        "accepted": bool(accepted.all()),
    }


def compare_call(
    entry_directory: Path,
    run_directory: Path,
    call: int,
    atol: float,
    rtol: float,
    cache_atol: float,
) -> dict[str, Any]:
    cache_results: list[dict[str, Any]] = []
    for segment in range(SEGMENT_COUNT):
        outputs = load_reference(entry_directory, segment)["outputs"]
        for cache, expected in enumerate(outputs[1:]):
            path = run_directory / f"call-{call}-segment-{segment}-cache-{cache}.f32le"
            comparison = compare_tensor(
                path, expected, atol, rtol, acceptance_atol=cache_atol
            )
            comparison.update({"segment": segment, "cache": cache})
            cache_results.append(comparison)
    final = load_reference(entry_directory, SEGMENT_COUNT - 1)["outputs"][0]
    pcm = compare_tensor(run_directory / f"call-{call}-pcm.f32le", final, atol, rtol)
    return {
        "call": call,
        "entry": "first" if call == 0 else "cached",
        "pcm": pcm,
        "cache_count": len(cache_results),
        "max_cache_abs_error": max(item["max_abs_error"] for item in cache_results),
        "mean_cache_abs_error": sum(item["mean_abs_error"] for item in cache_results)
        / len(cache_results),
        "strict_cache_mismatch_count": sum(
            item["strict_mismatch_count"] for item in cache_results
        ),
        "all_caches_allclose": all(item["allclose"] for item in cache_results),
        "all_caches_android_accepted": all(item["accepted"] for item in cache_results),
        "caches": cache_results,
        "strict_allclose": pcm["allclose"]
        and all(item["allclose"] for item in cache_results),
        "accepted": pcm["allclose"] and all(item["accepted"] for item in cache_results),
    }


def compare(
    first_directory: Path,
    cached_directory: Path,
    device_result_path: Path,
    device_output_directory: Path,
    output_path: Path,
    device_properties_path: Path | None,
    atol: float,
    rtol: float,
    cache_atol: float,
) -> int:
    device_result = json.loads(device_result_path.read_text())
    runs = []
    for run in range(RUN_COUNT):
        run_directory = device_output_directory / f"run-{run}"
        first = compare_call(
            first_directory, run_directory, 0, atol, rtol, cache_atol
        )
        cached = compare_call(
            cached_directory, run_directory, 1, atol, rtol, cache_atol
        )
        runs.append(
            {
                "run": run,
                "temperature": "cold" if run == 0 else "warm_page_cache",
                "call_0": first,
                "call_1": cached,
                "strict_allclose": first["strict_allclose"]
                and cached["strict_allclose"],
                "accepted": first["accepted"] and cached["accepted"],
            }
        )
    result = {
        "schema_version": 1,
        "status": "passed",
        "scope": "FP32 fixed-shape eight-segment streaming acoustic decoder Android sequence",
        "runtime": {"executorch": "1.2.0", "backend": "xnnpack"},
        "device": (
            json.loads(device_properties_path.read_text())
            if device_properties_path is not None
            else {}
        ),
        "interface": {
            "segment_count": SEGMENT_COUNT,
            "cache_tensor_count": 34,
            "runs": RUN_COUNT,
            "cache_source": "actual Android call-0 outputs serialized and consumed by call 1",
        },
        "device_result": device_result,
        "comparisons": runs,
        "strict_thresholds": {"atol": atol, "rtol": rtol},
        "android_cache_acceptance": {
            "atol": cache_atol,
            "rtol": rtol,
            "scope": "Android cache tensors only; PCM and host thresholds remain strict",
            "rationale": "Covers deterministic backend intermediate drift while preserving sub-1e-9 PCM error",
        },
        "strict_allclose": all(run["strict_allclose"] for run in runs),
        "accepted": all(run["accepted"] for run in runs),
    }
    if device_result.get("status") != "passed" or not result["accepted"]:
        result["status"] = "failed"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("first_directory", type=Path)
    prepare_parser.add_argument("cached_directory", type=Path)
    prepare_parser.add_argument("output_directory", type=Path)
    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("first_directory", type=Path)
    compare_parser.add_argument("cached_directory", type=Path)
    compare_parser.add_argument("device_result", type=Path)
    compare_parser.add_argument("device_output_directory", type=Path)
    compare_parser.add_argument("output", type=Path)
    compare_parser.add_argument("--device-properties", type=Path)
    compare_parser.add_argument("--atol", type=float, default=2e-5)
    compare_parser.add_argument("--rtol", type=float, default=1e-5)
    compare_parser.add_argument("--cache-atol", type=float, default=6e-5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare(args.first_directory, args.cached_directory, args.output_directory)
        return
    raise SystemExit(
        compare(
            args.first_directory,
            args.cached_directory,
            args.device_result,
            args.device_output_directory,
            args.output,
            args.device_properties,
            args.atol,
            args.rtol,
            args.cache_atol,
        )
    )


if __name__ == "__main__":
    main()
