#!/usr/bin/env python3
"""Serialize diffusion inputs and compare one-step/loop Android outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from android_io import file_sha256, read_float32_le, write_float32_le
from fixture_utils import tensor_metadata


INPUT_FILES = (
    "latent.f32le",
    "positive-condition.f32le",
    "negative-condition.f32le",
    "timesteps.f32le",
    "sigmas.f32le",
)


def prepare(reference_path: Path, loop_reference_path: Path, output: Path) -> None:
    reference = torch.load(reference_path, map_location="cpu", weights_only=True)
    loop = torch.load(loop_reference_path, map_location="cpu", weights_only=True)
    initial, _, positive, negative = reference["inputs"]
    values = (
        initial,
        positive,
        negative,
        loop["timesteps"].float(),
        loop["sigmas"].float(),
    )
    output.mkdir(parents=True, exist_ok=True)
    metadata = {}
    for name, value in zip(INPUT_FILES, values):
        write_float32_le(output / name, value)
        metadata[name] = tensor_metadata(value.float())
    (output / "input-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


def compare(
    reference_path: Path,
    loop_reference_path: Path,
    device_result_path: Path,
    one_step_output_path: Path,
    loop_output_path: Path,
    output_path: Path,
    device_properties_path: Path | None,
    atol: float,
    rtol: float,
) -> int:
    reference = torch.load(reference_path, map_location="cpu", weights_only=True)
    loop = torch.load(loop_reference_path, map_location="cpu", weights_only=True)
    expected_step = reference["output"].float().contiguous()
    expected_loop = loop["output"].float().contiguous()
    actual_step = read_float32_le(one_step_output_path, tuple(expected_step.shape))
    actual_loop = read_float32_le(loop_output_path, tuple(expected_loop.shape))

    def comparison(expected: torch.Tensor, actual: torch.Tensor, path: Path) -> dict:
        difference = (actual - expected).abs()
        return {
            "reference_output": tensor_metadata(expected),
            "android_output": tensor_metadata(actual),
            "raw_output_sha256": file_sha256(path),
            "max_abs_error": difference.max().item(),
            "mean_abs_error": difference.float().mean().item(),
            "atol": atol,
            "rtol": rtol,
            "allclose": bool(torch.allclose(actual, expected, atol=atol, rtol=rtol)),
        }

    device_result = json.loads(device_result_path.read_text())
    step_comparison = comparison(expected_step, actual_step, one_step_output_path)
    loop_comparison = comparison(expected_loop, actual_loop, loop_output_path)
    passed = (
        device_result.get("status") == "passed"
        and step_comparison["allclose"]
        and loop_comparison["allclose"]
    )
    result = {
        "schema_version": 1,
        "status": "passed" if passed else "failed",
        "scope": "FP32 XNNPACK diffusion head plus native Android ten-step DPM scheduler",
        "runtime": {"executorch": "1.2.0", "backend": "xnnpack"},
        "device": json.loads(device_properties_path.read_text())
        if device_properties_path
        else {},
        "device_result": device_result,
        "one_step_comparison": step_comparison,
        "loop_comparison": loop_comparison,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if passed else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("reference", type=Path)
    prepare_parser.add_argument("loop_reference", type=Path)
    prepare_parser.add_argument("output", type=Path)
    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("reference", type=Path)
    compare_parser.add_argument("loop_reference", type=Path)
    compare_parser.add_argument("device_result", type=Path)
    compare_parser.add_argument("one_step_output", type=Path)
    compare_parser.add_argument("loop_output", type=Path)
    compare_parser.add_argument("output", type=Path)
    compare_parser.add_argument("--device-properties", type=Path)
    compare_parser.add_argument("--atol", type=float, default=2e-5)
    compare_parser.add_argument("--rtol", type=float, default=1e-4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare(args.reference, args.loop_reference, args.output)
        return
    raise SystemExit(
        compare(
            args.reference,
            args.loop_reference,
            args.device_result,
            args.one_step_output,
            args.loop_output,
            args.output,
            args.device_properties,
            args.atol,
            args.rtol,
        )
    )


if __name__ == "__main__":
    main()
