#!/usr/bin/env python3
"""Decompose one-row Q4 embedding lookup into standard HTP-owned ONNX ops.

Only the selected token row is unpacked at runtime. This exactly follows the
LiquidONNX nibble layout: low nibble first, 32 values per asymmetric block,
with one scale and zero point per block.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import helper, numpy_helper


def lower(source: Path, destination: Path) -> dict[str, object]:
    model = onnx.load(str(source), load_external_data=False)
    targets = [
        node
        for node in model.graph.node
        if node.op_type == "GatherBlockQuantized" and node.domain == "com.microsoft"
    ]
    if len(targets) != 1:
        raise ValueError(f"expected one GatherBlockQuantized node, found {len(targets)}")
    target = targets[0]
    quant, indices, scales, zero_points = target.input
    output = target.output[0]
    prefix = f"{target.name}/htp_standard"

    constants = {
        "__embedding_sixteen": np.asarray(16.0, dtype=np.float32),
        "__embedding_pair_axis": np.asarray([3], dtype=np.int64),
        "__embedding_block_axis": np.asarray([3], dtype=np.int64),
        "__embedding_pair_shape": np.asarray([1, 1, 2048], dtype=np.int64),
        "__embedding_block_shape": np.asarray([1, 1, 2048], dtype=np.int64),
        "__embedding_tile_block32": np.asarray([1, 1, 1, 32], dtype=np.int64),
    }
    model.graph.initializer.extend(
        numpy_helper.from_array(value, name) for name, value in constants.items()
    )

    def unpack(packed: str, stem: str, unpacked_blocks: int) -> tuple[list[onnx.NodeProto], str]:
        gathered = f"{prefix}/{stem}_gather"
        as_float = f"{prefix}/{stem}_float"
        low = f"{prefix}/{stem}_low"
        divided = f"{prefix}/{stem}_divided"
        high = f"{prefix}/{stem}_high"
        low_u = f"{prefix}/{stem}_low_unsqueezed"
        high_u = f"{prefix}/{stem}_high_unsqueezed"
        paired = f"{prefix}/{stem}_paired"
        unpacked = f"{prefix}/{stem}_unpacked"
        return [
            helper.make_node("Gather", [packed, indices], [gathered], name=gathered, axis=0),
            helper.make_node("Cast", [gathered], [as_float], name=as_float, to=onnx.TensorProto.FLOAT),
            helper.make_node("Mod", [as_float, "__embedding_sixteen"], [low], name=low, fmod=1),
            helper.make_node("Div", [as_float, "__embedding_sixteen"], [divided], name=divided),
            helper.make_node("Floor", [divided], [high], name=high),
            helper.make_node("Unsqueeze", [low, "__embedding_pair_axis"], [low_u], name=low_u),
            helper.make_node("Unsqueeze", [high, "__embedding_pair_axis"], [high_u], name=high_u),
            helper.make_node("Concat", [low_u, high_u], [paired], name=paired, axis=3),
            helper.make_node(
                "Reshape",
                [paired, "__embedding_pair_shape" if unpacked_blocks == 2048 else "__embedding_zp_shape"],
                [unpacked],
                name=unpacked,
            ),
        ], unpacked

    # Packed weights hold 2,048 q4 values. Packed zero points hold 64 q4
    # values, one for every 32-value block.
    model.graph.initializer.append(
        numpy_helper.from_array(np.asarray([1, 1, 64], dtype=np.int64), "__embedding_zp_shape")
    )
    weight_nodes, weight_values = unpack(quant, "weight", 2048)
    zp_nodes, zp_values = unpack(zero_points, "zero_point", 64)

    scale_gather = f"{prefix}/scale_gather"
    scale_u = f"{prefix}/scale_unsqueezed"
    scale_tiled = f"{prefix}/scale_tiled"
    scale_full = f"{prefix}/scale_full"
    zp_u = f"{prefix}/zero_point_block_unsqueezed"
    zp_tiled = f"{prefix}/zero_point_block_tiled"
    zp_full = f"{prefix}/zero_point_full"
    centered = f"{prefix}/centered"
    replacement = [
        *weight_nodes,
        *zp_nodes,
        helper.make_node("Gather", [scales, indices], [scale_gather], name=scale_gather, axis=0),
        helper.make_node("Unsqueeze", [scale_gather, "__embedding_block_axis"], [scale_u], name=scale_u),
        helper.make_node("Tile", [scale_u, "__embedding_tile_block32"], [scale_tiled], name=scale_tiled),
        helper.make_node("Reshape", [scale_tiled, "__embedding_block_shape"], [scale_full], name=scale_full),
        helper.make_node("Unsqueeze", [zp_values, "__embedding_block_axis"], [zp_u], name=zp_u),
        helper.make_node("Tile", [zp_u, "__embedding_tile_block32"], [zp_tiled], name=zp_tiled),
        helper.make_node("Reshape", [zp_tiled, "__embedding_block_shape"], [zp_full], name=zp_full),
        helper.make_node("Sub", [weight_values, zp_full], [centered], name=centered),
        helper.make_node("Mul", [centered, scale_full], [output], name=target.name),
    ]

    rewritten: list[onnx.NodeProto] = []
    for node in model.graph.node:
        if node is target or node.name == target.name:
            rewritten.extend(replacement)
        else:
            rewritten.append(node)
    del model.graph.node[:]
    model.graph.node.extend(rewritten)

    destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(destination))
    onnx.checker.check_model(str(destination), full_check=False)
    return {
        "source": str(source),
        "destination": str(destination),
        "embedding_nodes_lowered": 1,
        "weight_bits": 4,
        "block_size": 32,
        "selected_rows_per_call": 1,
        "formula": "(unpack_low_nibble_first(weight_row) - repeated_zero_points) * repeated_scales",
        "onnx_checker": "passed",
        "external_tensor_data_loaded_or_copied": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(lower(args.source, args.destination), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
