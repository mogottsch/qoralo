#!/usr/bin/env python3
"""Replace LiquidONNX RMSNorm contrib nodes with equivalent standard ONNX ops.

LiquidONNX commit 9a23ddd emits SimplifiedLayerNormalization nodes in the
standard ONNX domain. ONNX Runtime 1.26 rejects that graph because the op is a
Microsoft contrib op. This rewrite deliberately uses only standard ONNX ops so
both the CPU viability gate and QNN graph importer see the same formula.
Large external tensor data is not loaded or copied.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import helper, numpy_helper


def rewrite(source: Path, destination: Path) -> dict[str, object]:
    model = onnx.load(str(source), load_external_data=False)
    replacements = {"SimplifiedLayerNormalization": 0, "SkipSimplifiedLayerNormalization": 0}
    rewritten: list[onnx.NodeProto] = []

    model.graph.initializer.extend(
        [
            numpy_helper.from_array(np.asarray(2.0, dtype=np.float32), "__rms_pow2"),
            numpy_helper.from_array(np.asarray(1e-5, dtype=np.float32), "__rms_epsilon"),
            numpy_helper.from_array(np.asarray([-1], dtype=np.int64), "__rms_axes"),
        ]
    )

    for node in model.graph.node:
        if node.op_type not in replacements:
            rewritten.append(node)
            continue

        replacements[node.op_type] += 1
        epsilon = next((attr.f for attr in node.attribute if attr.name == "epsilon"), 1e-5)
        if abs(epsilon - 1e-5) > 1e-9:
            raise ValueError(f"unsupported epsilon on {node.name}: {epsilon}")

        prefix = f"{node.name}/qnn_rms_decomposition"
        value = node.input[0]
        if node.op_type == "SkipSimplifiedLayerNormalization":
            skip_sum = f"{prefix}/skip_add"
            rewritten.append(helper.make_node("Add", node.input[:2], [skip_sum], name=skip_sum))
            value = skip_sum
            scale = node.input[2]
        else:
            scale = node.input[1]

        square = f"{prefix}/square"
        mean = f"{prefix}/mean"
        mean_epsilon = f"{prefix}/epsilon"
        root = f"{prefix}/sqrt"
        normalized = f"{prefix}/divide"
        rewritten.extend(
            [
                helper.make_node("Pow", [value, "__rms_pow2"], [square], name=square),
                helper.make_node(
                    "ReduceMean", [square, "__rms_axes"], [mean], name=mean, keepdims=1
                ),
                helper.make_node(
                    "Add", [mean, "__rms_epsilon"], [mean_epsilon], name=mean_epsilon
                ),
                helper.make_node("Sqrt", [mean_epsilon], [root], name=root),
                helper.make_node("Div", [value, root], [normalized], name=normalized),
                helper.make_node("Mul", [normalized, scale], list(node.output), name=node.name),
            ]
        )

    del model.graph.node[:]
    model.graph.node.extend(rewritten)
    destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(destination))
    onnx.checker.check_model(str(destination), full_check=False)

    return {
        "source": str(source),
        "destination": str(destination),
        "replacements": replacements,
        "output_nodes": len(model.graph.node),
        "onnx_checker": "passed",
        "external_tensor_data_loaded_or_copied": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(rewrite(args.source, args.destination), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
