#!/usr/bin/env python3
"""Lower one-token LFM2 RotaryEmbedding/GQA nodes to standard ONNX HTP ops.

The QNN EP 2.5 HTP translator does not claim the Microsoft RotaryEmbedding and
GroupQueryAttention nodes even though QAIRT has native op definitions. This
rewrite preserves explicit model state and emits only standard tensor ops. It
returns the newly computed K/V slices; the caller writes them into the fixed
left-aligned cache at the current position before the next token.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

ATTENTION_MASK = "attention_mask"


def set_shape(value_info: onnx.ValueInfoProto, dimensions: list[int]) -> None:
    shape = value_info.type.tensor_type.shape
    if len(shape.dim) != len(dimensions):
        raise ValueError(f"rank mismatch for {value_info.name}")
    for dim, value in zip(shape.dim, dimensions, strict=True):
        dim.ClearField("dim_param")
        dim.dim_value = value


def lower(source: Path, destination: Path, capacity: int) -> dict[str, object]:
    model = onnx.load(str(source), load_external_data=False)
    cache_length = capacity - 1
    producers = {output: node for node in model.graph.node for output in node.output}
    remove_ids: set[int] = set()
    replacement_by_gqa: dict[int, list[onnx.NodeProto]] = {}

    constants = {
        "__attn_shape_q": np.asarray([1, 1, 32, 64], dtype=np.int64),
        "__attn_shape_kv": np.asarray([1, 1, 8, 64], dtype=np.int64),
        "__attn_shape_q_3d": np.asarray([1, 1, 2048], dtype=np.int64),
        "__attn_shape_kv_3d": np.asarray([1, 1, 512], dtype=np.int64),
        "__attn_shape_key_repeat": np.asarray([1, 32, 64, capacity], dtype=np.int64),
        "__attn_shape_value_repeat": np.asarray([1, 32, capacity, 64], dtype=np.int64),
        "__attn_shape_output": np.asarray([1, 1, 2048], dtype=np.int64),
        "__attn_unsqueeze_head_axis": np.asarray([2], dtype=np.int64),
        "__attn_tile_heads": np.asarray([1, 1, 4, 1, 1], dtype=np.int64),
        "__rope_split": np.asarray([32, 32], dtype=np.int64),
        "__rope_unsqueeze_head_axis": np.asarray([2], dtype=np.int64),
        "__attn_scale": np.asarray(0.125, dtype=np.float32),
    }
    model.graph.initializer.extend(
        numpy_helper.from_array(value, name) for name, value in constants.items()
    )

    def rotary(input_name: str, output_name: str, heads: int, prefix: str) -> list[onnx.NodeProto]:
        shape_name = "__attn_shape_q" if heads == 32 else "__attn_shape_kv"
        output_shape_name = "__attn_shape_q_3d" if heads == 32 else "__attn_shape_kv_3d"
        shaped = f"{prefix}/reshape"
        cos_half = f"{prefix}/cos_half"
        sin_half = f"{prefix}/sin_half"
        cos_full = f"{prefix}/cos_full"
        sin_full = f"{prefix}/sin_full"
        cos = f"{prefix}/cos"
        sin = f"{prefix}/sin"
        first = f"{prefix}/first_half"
        second = f"{prefix}/second_half"
        negative_second = f"{prefix}/negative_second_half"
        rotated = f"{prefix}/rotated_half"
        scaled = f"{prefix}/scaled"
        rotated_scaled = f"{prefix}/rotated_scaled"
        result4 = f"{prefix}/result4"
        return [
            helper.make_node("Reshape", [input_name, shape_name], [shaped], name=shaped),
            helper.make_node("Gather", ["cos_cache", "position_ids"], [cos_half], name=cos_half, axis=0),
            helper.make_node("Gather", ["sin_cache", "position_ids"], [sin_half], name=sin_half, axis=0),
            helper.make_node("Concat", [cos_half, cos_half], [cos_full], name=cos_full, axis=-1),
            helper.make_node("Concat", [sin_half, sin_half], [sin_full], name=sin_full, axis=-1),
            helper.make_node("Unsqueeze", [cos_full, "__rope_unsqueeze_head_axis"], [cos], name=cos),
            helper.make_node("Unsqueeze", [sin_full, "__rope_unsqueeze_head_axis"], [sin], name=sin),
            helper.make_node("Split", [shaped, "__rope_split"], [first, second], name=f"{prefix}/split", axis=3),
            helper.make_node("Neg", [second], [negative_second], name=negative_second),
            helper.make_node("Concat", [negative_second, first], [rotated], name=rotated, axis=3),
            helper.make_node("Mul", [shaped, cos], [scaled], name=scaled),
            helper.make_node("Mul", [rotated, sin], [rotated_scaled], name=rotated_scaled),
            helper.make_node("Add", [scaled, rotated_scaled], [result4], name=result4),
            helper.make_node("Reshape", [result4, output_shape_name], [output_name], name=prefix),
        ]

    gqa_count = 0
    rotary_count = 0
    for node in model.graph.node:
        if node.op_type != "GroupQueryAttention" or node.domain != "com.microsoft":
            continue
        gqa_count += 1
        q_rotary = producers[node.input[0]]
        k_rotary = producers[node.input[1]]
        if q_rotary.op_type != "RotaryEmbedding" or k_rotary.op_type != "RotaryEmbedding":
            raise ValueError(f"unexpected rotary producers for {node.name}")
        remove_ids.update((id(q_rotary), id(k_rotary)))
        rotary_count += 2

        prefix = f"{node.name}/htp_standard"
        q_shape = f"{prefix}/q_shape"
        query = f"{prefix}/query"
        k_shape = f"{prefix}/k_shape"
        key_new = node.output[1]
        v_shape = f"{prefix}/v_shape"
        value_new = node.output[2]
        all_key = f"{prefix}/all_key"
        all_value = f"{prefix}/all_value"
        key_unsqueezed = f"{prefix}/key_unsqueezed"
        value_unsqueezed = f"{prefix}/value_unsqueezed"
        key_tiled = f"{prefix}/key_tiled"
        value_tiled = f"{prefix}/value_tiled"
        key_repeated = f"{prefix}/key_repeated"
        value_repeated = f"{prefix}/value_repeated"
        scores = f"{prefix}/scores"
        scaled_scores = f"{prefix}/scaled_scores"
        masked_scores = f"{prefix}/masked_scores"
        probabilities = f"{prefix}/probabilities"
        attended = f"{prefix}/attended"
        attended_bsnh = f"{prefix}/attended_bsnh"

        nodes = []
        nodes.extend(rotary(q_rotary.input[0], q_rotary.output[0], 32, f"{prefix}/q_rotary"))
        nodes.extend(rotary(k_rotary.input[0], k_rotary.output[0], 8, f"{prefix}/k_rotary"))
        nodes.extend(
            [
                helper.make_node("Reshape", [q_rotary.output[0], "__attn_shape_q"], [q_shape], name=q_shape),
                helper.make_node("Transpose", [q_shape], [query], name=query, perm=[0, 2, 1, 3]),
                helper.make_node("Reshape", [k_rotary.output[0], "__attn_shape_kv"], [k_shape], name=k_shape),
                helper.make_node("Transpose", [k_shape], [key_new], name=f"{prefix}/key_new", perm=[0, 2, 3, 1]),
                helper.make_node("Reshape", [node.input[2], "__attn_shape_kv"], [v_shape], name=v_shape),
                helper.make_node("Transpose", [v_shape], [value_new], name=f"{prefix}/value_new", perm=[0, 2, 1, 3]),
                helper.make_node("Concat", [node.input[3], key_new], [all_key], name=all_key, axis=3),
                helper.make_node("Concat", [node.input[4], value_new], [all_value], name=all_value, axis=2),
                helper.make_node("Unsqueeze", [all_key, "__attn_unsqueeze_head_axis"], [key_unsqueezed], name=key_unsqueezed),
                helper.make_node("Unsqueeze", [all_value, "__attn_unsqueeze_head_axis"], [value_unsqueezed], name=value_unsqueezed),
                helper.make_node("Tile", [key_unsqueezed, "__attn_tile_heads"], [key_tiled], name=key_tiled),
                helper.make_node("Tile", [value_unsqueezed, "__attn_tile_heads"], [value_tiled], name=value_tiled),
                helper.make_node("Reshape", [key_tiled, "__attn_shape_key_repeat"], [key_repeated], name=key_repeated),
                helper.make_node("Reshape", [value_tiled, "__attn_shape_value_repeat"], [value_repeated], name=value_repeated),
                helper.make_node("MatMul", [query, key_repeated], [scores], name=scores),
                helper.make_node("Mul", [scores, "__attn_scale"], [scaled_scores], name=scaled_scores),
                helper.make_node("Add", [scaled_scores, ATTENTION_MASK], [masked_scores], name=masked_scores),
                helper.make_node("Softmax", [masked_scores], [probabilities], name=probabilities, axis=-1),
                helper.make_node("MatMul", [probabilities, value_repeated], [attended], name=attended),
                helper.make_node("Transpose", [attended], [attended_bsnh], name=attended_bsnh, perm=[0, 2, 1, 3]),
                helper.make_node("Reshape", [attended_bsnh, "__attn_shape_output"], [node.output[0]], name=node.name),
            ]
        )
        replacement_by_gqa[id(node)] = nodes

    rewritten: list[onnx.NodeProto] = []
    for node in model.graph.node:
        if id(node) in remove_ids:
            continue
        if id(node) in replacement_by_gqa:
            rewritten.extend(replacement_by_gqa[id(node)])
        else:
            rewritten.append(node)
    del model.graph.node[:]
    model.graph.node.extend(rewritten)

    inputs = [value for value in model.graph.input if value.name != "seqlens_k"]
    del model.graph.input[:]
    model.graph.input.extend(inputs)
    model.graph.input.append(
        helper.make_tensor_value_info(ATTENTION_MASK, TensorProto.FLOAT, [1, 1, 1, capacity])
    )
    for value in model.graph.input:
        if value.name.endswith(".key") and value.name.startswith("past_key_values."):
            set_shape(value, [1, 8, 64, cache_length])
        elif value.name.endswith(".value") and value.name.startswith("past_key_values."):
            set_shape(value, [1, 8, cache_length, 64])
    for value in model.graph.output:
        if value.name.startswith("present.") and value.name.endswith(".key"):
            set_shape(value, [1, 8, 64, 1])
        elif value.name.startswith("present.") and value.name.endswith(".value"):
            set_shape(value, [1, 8, 1, 64])

    # Remove the now-unused fixed GQA scalar. Other unused constants are safely
    # eliminated by ORT's graph optimizer.
    initializers = [x for x in model.graph.initializer if x.name != "__max_sequence_length_i32"]
    del model.graph.initializer[:]
    model.graph.initializer.extend(initializers)

    destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(destination))
    onnx.checker.check_model(str(destination), full_check=False)
    return {
        "source": str(source),
        "destination": str(destination),
        "capacity": capacity,
        "attention_cache_length": cache_length,
        "gqa_nodes_lowered": gqa_count,
        "rotary_nodes_lowered": rotary_count,
        "cache_outputs": "new K/V slices only; caller writes each slice at the current left-aligned cache position",
        "mask": "[1,1,1,capacity], zero for valid past positions and current final slot, finite-negative elsewhere",
        "onnx_checker": "passed",
        "external_tensor_data_loaded_or_copied": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--capacity", type=int, default=4096)
    args = parser.parse_args()
    print(json.dumps(lower(args.source, args.destination, args.capacity), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
