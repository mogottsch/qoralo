#!/usr/bin/env python3
"""Specialize the exact LFM2 export to a one-token, fixed-capacity stateful profile.

The canonical prompts are submitted token-by-token through this single loaded
route. Attention KV and convolution state remain explicit graph I/O. A caller
resets a logical request by zeroing every state tensor and setting position 0.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

MASK_PREFIX = "/model/attn_mask_reformat/attn_mask_subgraph/"
SEQLENS_INPUT = "seqlens_k"
MAX_SEQUENCE_INITIALIZER = "__max_sequence_length_i32"


def set_shape(value_info: onnx.ValueInfoProto, dimensions: list[int]) -> None:
    shape = value_info.type.tensor_type.shape
    if len(shape.dim) != len(dimensions):
        raise ValueError(f"rank mismatch for {value_info.name}: {len(shape.dim)} != {dimensions}")
    for dim, value in zip(shape.dim, dimensions, strict=True):
        dim.ClearField("dim_param")
        dim.dim_value = value


def specialize(source: Path, destination: Path, capacity: int) -> dict[str, object]:
    model = onnx.load(str(source), load_external_data=False)
    if capacity < 3970:
        raise ValueError("capacity must fit the 1,922-token long prompt plus 2,048-token ceiling")

    # Replace the mask-derived dynamic GQA controls with explicit position and a
    # fixed maximum capacity. seqlens_k is total valid sequence length minus 1.
    gqa_count = 0
    for node in model.graph.node:
        if node.op_type == "GroupQueryAttention" and node.domain == "com.microsoft":
            if len(node.input) < 7:
                raise ValueError(f"unexpected GQA inputs on {node.name}")
            node.input[5] = SEQLENS_INPUT
            node.input[6] = MAX_SEQUENCE_INITIALIZER
            gqa_count += 1
    if gqa_count != 8:
        raise ValueError(f"expected 8 GQA nodes, found {gqa_count}")

    kept_nodes = [node for node in model.graph.node if not node.name.startswith(MASK_PREFIX)]
    removed_mask_nodes = len(model.graph.node) - len(kept_nodes)
    del model.graph.node[:]
    model.graph.node.extend(kept_nodes)

    kept_inputs = [value for value in model.graph.input if value.name != "attention_mask"]
    del model.graph.input[:]
    model.graph.input.extend(kept_inputs)
    model.graph.input.append(
        helper.make_tensor_value_info(SEQLENS_INPUT, TensorProto.INT32, [1])
    )
    model.graph.initializer.append(
        numpy_helper.from_array(np.asarray(capacity, dtype=np.int32), MAX_SEQUENCE_INITIALIZER)
    )

    for value in model.graph.input:
        if value.name == "input_ids":
            value.type.tensor_type.elem_type = TensorProto.INT32
            set_shape(value, [1, 1])
        elif value.name == "position_ids":
            set_shape(value, [1, 1])
        elif value.name == SEQLENS_INPUT:
            set_shape(value, [1])
        elif value.name.startswith("past_key_values."):
            set_shape(value, [1, 8, capacity, 64])
        elif value.name.startswith("past_conv."):
            set_shape(value, [1, 2048, 3])

    for value in model.graph.output:
        if value.name == "logits":
            set_shape(value, [1, 1, 128000])
        elif value.name.startswith("present."):
            set_shape(value, [1, 8, capacity, 64])
        elif value.name.startswith("present_conv."):
            set_shape(value, [1, 2048, 3])

    replacements = {
        "batch_size": 1,
        "sequence_length": 1,
        "past_sequence_length": capacity,
        "total_sequence_length": capacity,
    }
    for value in model.graph.value_info:
        for dim in value.type.tensor_type.shape.dim:
            if dim.dim_param in replacements:
                replacement = replacements[dim.dim_param]
                dim.ClearField("dim_param")
                dim.dim_value = replacement

    destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(destination))
    onnx.checker.check_model(str(destination), full_check=False)
    return {
        "source": str(source),
        "destination": str(destination),
        "capacity": capacity,
        "autoregressive_tokens_per_call": 1,
        "gqa_nodes_rewired": gqa_count,
        "mask_nodes_removed": removed_mask_nodes,
        "state_reset": "zero 16 attention KV inputs and 22 convolution inputs before each request",
        "onnx_checker": "passed",
        "external_tensor_data_loaded_or_copied": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--capacity", type=int, default=4096)
    args = parser.parse_args()
    print(json.dumps(specialize(args.source, args.destination, args.capacity), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
