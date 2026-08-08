#!/usr/bin/env python3
"""Prepare Android FP32 inputs and compare raw device output with PyTorch."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import torch

from fixture_utils import tensor_metadata


def write_float32_le(path: Path, tensor: torch.Tensor) -> None:
    values = tensor.detach().cpu().to(torch.float32).contiguous().flatten().tolist()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack(f"<{len(values)}f", *values))


def read_float32_le(path: Path, shape: tuple[int, ...]) -> torch.Tensor:
    raw = path.read_bytes()
    count = 1
    for dimension in shape:
        count *= dimension
    expected = count * 4
    if len(raw) != expected:
        raise ValueError(f"Expected {expected} bytes for shape {shape}, got {len(raw)}")
    return torch.tensor(struct.unpack(f"<{count}f", raw), dtype=torch.float32).reshape(shape)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(reference_path: Path, output_path: Path) -> None:
    reference = torch.load(reference_path, map_location="cpu", weights_only=True)
    value = reference["input"].to(torch.float32).contiguous()
    if tuple(value.shape) != (1, 64, 1):
        raise ValueError(f"Expected input [1,64,1], got {tuple(value.shape)}")
    write_float32_le(output_path, value)
    print(json.dumps({"path": str(output_path), **tensor_metadata(value)}, indent=2))


def compare(
    reference_path: Path,
    device_result_path: Path,
    device_output_path: Path,
    output_path: Path,
    device_properties_path: Path | None,
    atol: float,
    rtol: float,
) -> int:
    reference = torch.load(reference_path, map_location="cpu", weights_only=True)
    expected = reference["output"].to(torch.float32).contiguous()
    actual = read_float32_le(device_output_path, tuple(expected.shape))
    difference = (actual - expected).abs()
    device_result: dict[str, Any] = json.loads(device_result_path.read_text())
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "passed",
        "scope": "FP32 fixed-shape non-streaming acoustic-decoder Android probe",
        "runtime": {"executorch": "1.2.0", "backend": "xnnpack"},
        "device": (
            json.loads(device_properties_path.read_text())
            if device_properties_path is not None
            else {}
        ),
        "device_result": device_result,
        "comparison": {
            "reference_output": tensor_metadata(expected),
            "android_output": tensor_metadata(actual),
            "raw_output_sha256": file_sha256(device_output_path),
            "max_abs_error": difference.max().item(),
            "mean_abs_error": difference.float().mean().item(),
            "atol": atol,
            "rtol": rtol,
            "allclose": bool(torch.allclose(actual, expected, atol=atol, rtol=rtol)),
        },
    }
    if device_result.get("status") != "passed" or not result["comparison"]["allclose"]:
        result["status"] = "failed"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("reference", type=Path)
    prepare_parser.add_argument("output", type=Path)
    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("reference", type=Path)
    compare_parser.add_argument("device_result", type=Path)
    compare_parser.add_argument("device_output", type=Path)
    compare_parser.add_argument("output", type=Path)
    compare_parser.add_argument("--device-properties", type=Path)
    compare_parser.add_argument("--atol", type=float, default=1e-5)
    compare_parser.add_argument("--rtol", type=float, default=1e-4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare(args.reference, args.output)
        return
    raise SystemExit(
        compare(
            args.reference,
            args.device_result,
            args.device_output,
            args.output,
            args.device_properties,
            args.atol,
            args.rtol,
        )
    )


if __name__ == "__main__":
    main()
