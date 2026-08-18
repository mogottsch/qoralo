#!/usr/bin/env python3
"""Create a provenance-recorded ONNX derivative with concrete I/O shapes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import onnx


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_assignment(text: str) -> tuple[str, list[int]]:
    if "=" not in text:
        raise argparse.ArgumentTypeError("shape must use NAME=DIM,DIM,...")
    name, dimensions_text = text.split("=", 1)
    try:
        dimensions = [int(value) for value in dimensions_text.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid shape: {text}") from error
    if not name or not dimensions or any(value <= 0 for value in dimensions):
        raise argparse.ArgumentTypeError(f"invalid shape: {text}")
    return name, dimensions


def set_shape(value_info: onnx.ValueInfoProto, dimensions: list[int]) -> None:
    tensor_type = value_info.type.tensor_type
    if not tensor_type.HasField("shape"):
        raise ValueError(f"tensor has no shape: {value_info.name}")
    if len(tensor_type.shape.dim) != len(dimensions):
        raise ValueError(
            f"rank mismatch for {value_info.name}: model={len(tensor_type.shape.dim)}, requested={len(dimensions)}"
        )
    for dimension, value in zip(tensor_type.shape.dim, dimensions, strict=True):
        dimension.ClearField("dim_param")
        dimension.dim_value = value


def run(args: argparse.Namespace) -> None:
    source = args.input.resolve()
    output = args.output.resolve()
    provenance = args.provenance.resolve()
    requested_inputs = dict(args.input_shape)
    requested_outputs = dict(args.output_shape)

    model = onnx.load(str(source))
    graph_inputs = {item.name: item for item in model.graph.input}
    graph_outputs = {item.name: item for item in model.graph.output}
    if set(requested_inputs) != set(graph_inputs):
        raise SystemExit(
            f"all graph inputs must be fixed exactly once: model={sorted(graph_inputs)}, requested={sorted(requested_inputs)}"
        )
    if set(requested_outputs) != set(graph_outputs):
        raise SystemExit(
            f"all graph outputs must be fixed exactly once: model={sorted(graph_outputs)}, requested={sorted(requested_outputs)}"
        )
    for name, shape in requested_inputs.items():
        set_shape(graph_inputs[name], shape)
    for name, shape in requested_outputs.items():
        set_shape(graph_outputs[name], shape)

    try:
        model = onnx.shape_inference.infer_shapes(model, strict_mode=True)
    except Exception as error:
        raise SystemExit(f"ONNX strict shape inference failed: {error}") from error
    onnx.checker.check_model(model, full_check=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(model, str(output), save_as_external_data=False)
    report = {
        "schema_version": 1,
        "derivative_type": "concrete-onnx-io-shapes",
        "source": {
            "path": str(source),
            "bytes": source.stat().st_size,
            "sha256": sha256_file(source),
        },
        "output": {
            "path": str(output),
            "bytes": output.stat().st_size,
            "sha256": sha256_file(output),
        },
        "input_shapes": requested_inputs,
        "output_shapes": requested_outputs,
        "tool": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "onnx": onnx.__version__,
        },
    }
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument(
        "--input-shape", type=parse_assignment, action="append", required=True
    )
    parser.add_argument(
        "--output-shape", type=parse_assignment, action="append", required=True
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
