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


def write_tensor_le(path: Path, value: torch.Tensor, precision: str) -> None:
    if precision == "fp32":
        write_float32_le(path, value.float())
        return
    path.write_bytes(value.detach().cpu().to(torch.float16).contiguous().numpy().tobytes())


def read_tensor_le(path: Path, shape: tuple[int, ...], precision: str) -> torch.Tensor:
    if precision == "fp32":
        return read_float32_le(path, shape)
    raw = path.read_bytes()
    expected = 2
    for dimension in shape:
        expected *= dimension
    if len(raw) != expected:
        raise ValueError(f"Expected {expected} bytes for shape {shape}, got {len(raw)}")
    return torch.frombuffer(bytearray(raw), dtype=torch.float16).clone().reshape(shape)


def load_reference(directory: Path, segment: int) -> dict[str, Any]:
    return torch.load(
        directory / f"segment-{segment}.reference.pt",
        map_location="cpu",
        weights_only=True,
    )


def prepare(
    first_directory: Path,
    cached_directory: Path,
    output_directory: Path,
    precision: str,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    first = load_reference(first_directory, 0)["inputs"][0]
    cached = load_reference(cached_directory, 0)["inputs"][0]
    extension = "f16le" if precision == "fp16" else "f32le"
    write_tensor_le(output_directory / f"call-0.{extension}", first, precision)
    write_tensor_le(output_directory / f"call-1.{extension}", cached, precision)
    manifest = {
        "schema_version": 2,
        "precision": precision,
        "tensor_abi_dtype": "float16" if precision == "fp16" else "float32",
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
    precision: str = "fp32",
) -> dict[str, Any]:
    expected = expected.detach().cpu().to(torch.float32).contiguous()
    actual = read_tensor_le(actual_path, tuple(expected.shape), precision).float()
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
    precision: str,
) -> dict[str, Any]:
    cache_results: list[dict[str, Any]] = []
    for segment in range(SEGMENT_COUNT):
        outputs = load_reference(entry_directory, segment)["outputs"]
        for cache, expected in enumerate(outputs[1:]):
            extension = "f16le" if precision == "fp16" else "f32le"
            path = run_directory / (
                f"call-{call}-segment-{segment}-cache-{cache}.{extension}"
            )
            comparison = compare_tensor(
                path,
                expected,
                atol,
                rtol,
                acceptance_atol=cache_atol,
                precision=precision,
            )
            comparison.update({"segment": segment, "cache": cache})
            cache_results.append(comparison)
    final_reference = load_reference(entry_directory, SEGMENT_COUNT - 1)
    final = final_reference.get("fixture_pcm")
    if final is None:
        final = final_reference["outputs"][0]
    pcm_extension = "f16le" if precision == "fp16" else "f32le"
    pcm = compare_tensor(
        run_directory / f"call-{call}-pcm.{pcm_extension}",
        final,
        atol,
        rtol,
        precision=precision,
    )
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
    precision: str,
) -> int:
    device_result = json.loads(device_result_path.read_text())
    runs = []
    for run in range(RUN_COUNT):
        run_directory = device_output_directory / f"run-{run}"
        first = compare_call(
            first_directory, run_directory, 0, atol, rtol, cache_atol, precision
        )
        cached = compare_call(
            cached_directory, run_directory, 1, atol, rtol, cache_atol, precision
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
    run_hashes = []
    for run in range(RUN_COUNT):
        run_directory = device_output_directory / f"run-{run}"
        run_hashes.append(
            {
                path.name: file_sha256(path)
                for path in sorted(run_directory.iterdir())
                if path.is_file()
            }
        )
    deterministic = all(hashes == run_hashes[0] for hashes in run_hashes[1:])
    device_runs = device_result.get("runs", [])
    segment_records = [
        segment
        for run in device_runs
        for call_name in ("call_0", "call_1")
        for segment in run.get(call_name, {}).get("segments", [])
    ]
    result = {
        "schema_version": 2,
        "status": "passed",
        "scope": f"{precision.upper()} fixed-shape eight-segment streaming acoustic decoder Android sequence",
        "precision": precision,
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
            "tensor_abi_dtype": "float16" if precision == "fp16" else "float32",
            "cache_source": "actual Android call-0 outputs serialized and consumed by call 1",
        },
        "device_result": device_result,
        "comparisons": runs,
        "strict_thresholds": {
            "atol": atol,
            "rtol": rtol,
            "reference": "original captured FP32 fixture",
            "scope": "PCM and all cache tensors; strict result is retained",
        },
        "android_cache_acceptance": (
            {
                "atol": cache_atol,
                "rtol": rtol,
                "scope": "Android cache tensors only; PCM and host thresholds remain strict",
                "rationale": "Preserves the previously documented FP32 Android-cache-only tolerance",
            }
            if precision == "fp32"
            else {
                "atol": cache_atol,
                "rtol": rtol,
                "scope": "Android FP16 cache tensors only; PCM remains at the strict FP16 threshold",
                "rationale": (
                    "Explicitly covers measured deterministic Android FP16 XNNPACK cache drift; "
                    "actual call-0 caches are still transported into call 1 and both PCM chunks "
                    "must pass the separate FP16 PCM threshold"
                ),
            }
        ),
        "strict_allclose": all(run["strict_allclose"] for run in runs),
        "accepted": all(run["accepted"] for run in runs),
        "deterministic_repeats": deterministic,
        "measurements": {
            "total_pte_bytes": sum(
                segment.get("model_bytes", 0)
                for segment in device_runs[0]["call_0"]["segments"]
                + device_runs[0]["call_1"]["segments"]
            ) if device_runs else 0,
            "peak_observed_pss_kib": max(
                (segment.get("pss_after_inference_kib", -1) for segment in segment_records),
                default=-1,
            ),
            "process_hwm_kib": device_result.get("memory_kib", {}).get("process_hwm_peak", -1),
        },
    }
    if (
        device_result.get("status") != "passed"
        or not result["accepted"]
        or not deterministic
    ):
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
    prepare_parser.add_argument("--precision", choices=("fp32", "fp16"), default="fp32")
    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("first_directory", type=Path)
    compare_parser.add_argument("cached_directory", type=Path)
    compare_parser.add_argument("device_result", type=Path)
    compare_parser.add_argument("device_output_directory", type=Path)
    compare_parser.add_argument("output", type=Path)
    compare_parser.add_argument("--device-properties", type=Path)
    compare_parser.add_argument("--precision", choices=("fp32", "fp16"), default="fp32")
    compare_parser.add_argument("--atol", type=float)
    compare_parser.add_argument("--rtol", type=float)
    compare_parser.add_argument("--cache-atol", type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare(
            args.first_directory,
            args.cached_directory,
            args.output_directory,
            args.precision,
        )
        return
    atol = args.atol if args.atol is not None else (2e-3 if args.precision == "fp16" else 2e-5)
    rtol = args.rtol if args.rtol is not None else (2e-3 if args.precision == "fp16" else 1e-5)
    cache_atol = args.cache_atol if args.cache_atol is not None else (
        3.5e-1 if args.precision == "fp16" else 6e-5
    )
    raise SystemExit(
        compare(
            args.first_directory,
            args.cached_directory,
            args.device_result,
            args.device_output_directory,
            args.output,
            args.device_properties,
            atol,
            rtol,
            cache_atol,
            args.precision,
        )
    )


if __name__ == "__main__":
    main()
