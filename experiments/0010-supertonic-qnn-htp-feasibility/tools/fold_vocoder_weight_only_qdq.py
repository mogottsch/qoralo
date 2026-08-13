#!/usr/bin/env python3
"""Constant-fold only Supertonic vocoder's weight-only QDQ tails.

The released vocoder has eight weight-only per-channel DequantizeLinear nodes
feeding otherwise floating-point Conv operations. QAIRT's float-fallback path
rejects those Conv nodes because they have no quantized bias. Folding those
constant DQ nodes is mathematically equivalent at float32 precision and leaves
all activation-QDQ regions untouched. The result remains a labeled derivative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper

EXPECTED_INPUT_SHA256 = (
    "e923d60f53f95eb1ce235f1dc33ec56d9c057823c96fa6f8acf98f32b0da6152"
)
EXPECTED_FOLDED_NODES = 8


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


def dequantize(
    quantized: np.ndarray,
    scale: np.ndarray,
    zero_point: np.ndarray,
    axis: int,
) -> np.ndarray:
    q = quantized.astype(np.float32)
    s = scale.astype(np.float32)
    z = zero_point.astype(np.float32)
    if s.size == 1:
        return np.asarray(
            (q - float(z.reshape(-1)[0])) * float(s.reshape(-1)[0]), dtype=np.float32
        )
    shape = [1] * q.ndim
    shape[axis] = s.size
    return np.asarray((q - z.reshape(shape)) * s.reshape(shape), dtype=np.float32)


def run(args: argparse.Namespace) -> None:
    source = args.input.resolve()
    output = args.output.resolve()
    provenance = args.provenance.resolve()
    source_hash = sha256_file(source)
    if source_hash != EXPECTED_INPUT_SHA256:
        raise SystemExit(f"unexpected source hash: {source_hash}")

    model = onnx.load(str(source))
    graph = model.graph
    initializers = {
        initializer.name: numpy_helper.to_array(initializer).copy()
        for initializer in graph.initializer
    }
    producers = {name: node for node in graph.node for name in node.output}
    consumer_counts: dict[str, int] = {}
    for node in graph.node:
        for name in node.input:
            consumer_counts[name] = consumer_counts.get(name, 0) + 1

    fold_nodes: list[onnx.NodeProto] = []
    folded_inputs: set[str] = set()
    records: list[dict[str, object]] = []
    for conv in (node for node in graph.node if node.op_type == "Conv"):
        if len(conv.input) < 2:
            continue
        weight_dq = producers.get(conv.input[1])
        if weight_dq is None or weight_dq.op_type != "DequantizeLinear":
            continue
        if len(weight_dq.input) < 3 or any(
            name not in initializers for name in weight_dq.input[:3]
        ):
            continue

        # Keep QDQ weights when the Conv activation is itself dequantized. Those
        # are the intended fully quantized regions of the released model.
        activation_producer = producers.get(conv.input[0])
        if (
            activation_producer is not None
            and activation_producer.op_type == "DequantizeLinear"
        ):
            continue

        if consumer_counts.get(weight_dq.output[0], 0) != 1:
            raise SystemExit(
                f"weight DQ output is shared unexpectedly: {weight_dq.name}"
            )
        weight = dequantize(
            initializers[weight_dq.input[0]],
            initializers[weight_dq.input[1]],
            initializers[weight_dq.input[2]],
            axis_of(weight_dq),
        )
        graph.initializer.append(
            numpy_helper.from_array(weight, name=weight_dq.output[0])
        )
        fold_nodes.append(weight_dq)
        folded_inputs.update(weight_dq.input[:3])
        records.append(
            {
                "conv": conv.name,
                "dequantize_node": weight_dq.name,
                "output_initializer": weight_dq.output[0],
                "shape": list(weight.shape),
                "source_dtype": str(initializers[weight_dq.input[0]].dtype),
                "folded_dtype": str(weight.dtype),
                "scale_count": int(initializers[weight_dq.input[1]].size),
            }
        )

    if len(fold_nodes) != EXPECTED_FOLDED_NODES:
        raise SystemExit(
            f"expected {EXPECTED_FOLDED_NODES} weight-only DQ nodes, found {len(fold_nodes)}"
        )

    folded_node_ids = {id(node) for node in fold_nodes}
    kept_nodes = [node for node in graph.node if id(node) not in folded_node_ids]
    del graph.node[:]
    graph.node.extend(kept_nodes)

    # Each folded quantization initializer was private to its removed DQ node.
    remaining_uses = {name for node in graph.node for name in node.input}
    removable = folded_inputs - remaining_uses
    kept_initializers = [
        initializer
        for initializer in graph.initializer
        if initializer.name not in removable
    ]
    del graph.initializer[:]
    graph.initializer.extend(kept_initializers)

    onnx.checker.check_model(model)
    output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(model, str(output), save_as_external_data=False)
    report = {
        "schema_version": 1,
        "derivative_type": "constant-fold-weight-only-per-channel-dequantize",
        "claim_limit": "This derivative does not prove that the untouched released graph executes on QNN.",
        "source": {
            "path": str(source),
            "bytes": source.stat().st_size,
            "sha256": source_hash,
        },
        "output": {
            "path": str(output),
            "bytes": output.stat().st_size,
            "sha256": sha256_file(output),
        },
        "tool": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "onnx": onnx.__version__,
            "numpy": np.__version__,
        },
        "folded_nodes": records,
    }
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
