#!/usr/bin/env python3
"""Rewrite constant per-channel vocoder QDQ tensors to per-tensor QDQ.

QAIRT/QNN 2.22.6 rejects the exact released vocoder's per-channel ONNX
DequantizeLinear tensors during conversion. This creates a clearly labeled
compatibility derivative while preserving the released graph's activation-QDQ
placement. It is never evidence that the exact released graph worked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper

EXPECTED_INPUT_SHA256 = (
    "e923d60f53f95eb1ce235f1dc33ec56d9c057823c96fa6f8acf98f32b0da6152"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def axis_of(node: onnx.NodeProto) -> int:
    for attribute in node.attribute:
        if attribute.name == "axis":
            return int(attribute.i)
    return 1


def clear_axis(node: onnx.NodeProto) -> None:
    kept = [attribute for attribute in node.attribute if attribute.name != "axis"]
    del node.attribute[:]
    node.attribute.extend(kept)


def dequantize(
    q: np.ndarray, scale: np.ndarray, zero_point: np.ndarray, axis: int
) -> np.ndarray:
    qf = q.astype(np.float32)
    sf = scale.astype(np.float32)
    zf = zero_point.astype(np.float32)
    if sf.size == 1:
        return (qf - float(zf.reshape(-1)[0])) * float(sf.reshape(-1)[0])
    shape = [1] * q.ndim
    shape[axis] = sf.size
    return (qf - zf.reshape(shape)) * sf.reshape(shape)


def replace_initializer(graph: onnx.GraphProto, name: str, value: np.ndarray) -> None:
    for index, initializer in enumerate(graph.initializer):
        if initializer.name == name:
            graph.initializer[index].CopyFrom(
                numpy_helper.from_array(np.asarray(value), name=name)
            )
            return
    raise ValueError(f"initializer not found: {name}")


def quantize_symmetric_int8(
    value: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    maximum = float(np.max(np.abs(value))) if value.size else 0.0
    scale_value = max(maximum / 127.0, np.finfo(np.float32).tiny)
    quantized = np.clip(np.rint(value / scale_value), -127, 127).astype(np.int8)
    return (
        quantized,
        np.asarray(scale_value, dtype=np.float32),
        np.asarray(0, dtype=np.int8),
    )


def quantize_bias_int32(
    value: np.ndarray, scale_value: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not np.isfinite(scale_value) or scale_value <= 0:
        raise ValueError(f"invalid bias scale: {scale_value}")
    limits = np.iinfo(np.int32)
    quantized64 = np.rint(value.astype(np.float64) / scale_value)
    if np.any(quantized64 < limits.min) or np.any(quantized64 > limits.max):
        raise ValueError("bias would overflow int32 with activation*weight scale")
    return (
        quantized64.astype(np.int32),
        np.asarray(scale_value, dtype=np.float32),
        np.asarray(0, dtype=np.int32),
    )


def tensor_error(reference: np.ndarray, reconstructed: np.ndarray) -> dict[str, float]:
    delta = reconstructed.astype(np.float64) - reference.astype(np.float64)
    return {
        "max_abs": float(np.max(np.abs(delta))) if delta.size else 0.0,
        "mean_abs": float(np.mean(np.abs(delta))) if delta.size else 0.0,
        "rmse": float(np.sqrt(np.mean(np.square(delta)))) if delta.size else 0.0,
    }


def run(args: argparse.Namespace) -> None:
    source = args.input.resolve()
    output = args.output.resolve()
    provenance = args.provenance.resolve()
    source_hash = sha256_file(source)
    if source_hash != EXPECTED_INPUT_SHA256:
        raise SystemExit(
            f"input is not the exact experiment-0008 vocoder: {source_hash}"
        )

    model = onnx.load(str(source))
    graph = model.graph
    initializers = {
        initializer.name: numpy_helper.to_array(initializer).copy()
        for initializer in graph.initializer
    }
    producers = {name: node for node in graph.node for name in node.output}

    changes: list[dict[str, Any]] = []
    converted_dq_names: set[str] = set()
    for conv in (node for node in graph.node if node.op_type == "Conv"):
        if len(conv.input) < 2:
            continue
        weight_dq = producers.get(conv.input[1])
        if weight_dq is None or weight_dq.op_type != "DequantizeLinear":
            continue
        if any(name not in initializers for name in weight_dq.input[:3]):
            continue
        old_weight_q = initializers[weight_dq.input[0]]
        old_weight_scale = initializers[weight_dq.input[1]]
        old_weight_zero = initializers[weight_dq.input[2]]
        if old_weight_scale.size <= 1:
            continue
        if old_weight_q.dtype != np.int8:
            raise SystemExit(
                f"unexpected per-channel weight dtype for {weight_dq.name}: {old_weight_q.dtype}"
            )
        weight_float = dequantize(
            old_weight_q, old_weight_scale, old_weight_zero, axis_of(weight_dq)
        )
        weight_q, weight_scale, weight_zero = quantize_symmetric_int8(weight_float)
        replace_initializer(graph, weight_dq.input[0], weight_q)
        replace_initializer(graph, weight_dq.input[1], weight_scale)
        replace_initializer(graph, weight_dq.input[2], weight_zero)
        clear_axis(weight_dq)
        initializers[weight_dq.input[0]] = weight_q
        initializers[weight_dq.input[1]] = weight_scale
        initializers[weight_dq.input[2]] = weight_zero
        converted_dq_names.add(weight_dq.name)

        weight_reconstructed = dequantize(weight_q, weight_scale, weight_zero, 0)
        change: dict[str, Any] = {
            "conv": conv.name,
            "weight_dq": weight_dq.name,
            "weight_shape": list(weight_q.shape),
            "old_channels": int(old_weight_scale.size),
            "new_scale": float(weight_scale),
            "weight_error": tensor_error(weight_float, weight_reconstructed),
        }

        if len(conv.input) >= 3:
            bias_dq = producers.get(conv.input[2])
            if (
                bias_dq is not None
                and bias_dq.op_type == "DequantizeLinear"
                and all(name in initializers for name in bias_dq.input[:3])
                and initializers[bias_dq.input[1]].size > 1
            ):
                old_bias_q = initializers[bias_dq.input[0]]
                old_bias_scale = initializers[bias_dq.input[1]]
                old_bias_zero = initializers[bias_dq.input[2]]
                if old_bias_q.dtype != np.int32:
                    raise SystemExit(
                        f"unexpected bias dtype for {bias_dq.name}: {old_bias_q.dtype}"
                    )
                bias_float = dequantize(
                    old_bias_q, old_bias_scale, old_bias_zero, axis_of(bias_dq)
                )

                activation_dq = producers.get(conv.input[0])
                if (
                    activation_dq is None
                    or activation_dq.op_type != "DequantizeLinear"
                    or len(activation_dq.input) < 2
                    or activation_dq.input[1] not in initializers
                    or initializers[activation_dq.input[1]].size != 1
                ):
                    raise SystemExit(
                        f"cannot derive scalar activation encoding for bias {bias_dq.name}"
                    )
                activation_scale = float(
                    initializers[activation_dq.input[1]].reshape(-1)[0]
                )
                new_bias_scale_value = activation_scale * float(weight_scale)
                bias_q, bias_scale, bias_zero = quantize_bias_int32(
                    bias_float, new_bias_scale_value
                )
                replace_initializer(graph, bias_dq.input[0], bias_q)
                replace_initializer(graph, bias_dq.input[1], bias_scale)
                replace_initializer(graph, bias_dq.input[2], bias_zero)
                clear_axis(bias_dq)
                initializers[bias_dq.input[0]] = bias_q
                initializers[bias_dq.input[1]] = bias_scale
                initializers[bias_dq.input[2]] = bias_zero
                converted_dq_names.add(bias_dq.name)

                bias_reconstructed = dequantize(bias_q, bias_scale, bias_zero, 0)
                change.update(
                    bias_dq=bias_dq.name,
                    activation_scale=activation_scale,
                    new_bias_scale=float(bias_scale),
                    bias_error=tensor_error(bias_float, bias_reconstructed),
                )
        changes.append(change)

    remaining = []
    for node in graph.node:
        if node.op_type != "DequantizeLinear" or len(node.input) < 2:
            continue
        if node.input[1] in initializers and initializers[node.input[1]].size > 1:
            remaining.append(node.name)
    if remaining:
        raise SystemExit(f"unhandled per-channel DequantizeLinear nodes: {remaining}")

    onnx.checker.check_model(model)
    output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(model, str(output), save_as_external_data=False)
    output_hash = sha256_file(output)
    report = {
        "schema_version": 1,
        "derivative_type": "per-channel-to-per-tensor-constant-qdq-compatibility-rewrite",
        "claim_limit": "This derivative does not prove that the exact released ONNX graph converts or executes on QNN.",
        "source": {
            "path": str(source),
            "bytes": source.stat().st_size,
            "sha256": source_hash,
        },
        "output": {
            "path": str(output),
            "bytes": output.stat().st_size,
            "sha256": output_hash,
        },
        "tool": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "onnx": onnx.__version__,
            "numpy": np.__version__,
        },
        "converted_dequantize_nodes": len(converted_dq_names),
        "converted_convolutions": len(changes),
        "changes": changes,
    }
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "sha256": output_hash,
                "converted_dequantize_nodes": len(converted_dq_names),
                "converted_convolutions": len(changes),
                "provenance": str(provenance),
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
