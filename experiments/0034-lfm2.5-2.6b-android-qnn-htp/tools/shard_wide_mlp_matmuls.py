#!/usr/bin/env python3
"""Shard LFM2's 10,752-wide Q4 MLP matrices into two HTP-sized halves."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import StringStringEntryProto, TensorProto, helper, numpy_helper

WIDE = 10_752
PARTS = (6_144, 4_608)
BLOCK_SIZE = 32
PART_BLOCKS = tuple(value // BLOCK_SIZE for value in PARTS)


def attrs(node: onnx.NodeProto, *, k: int, n: int) -> dict[str, object]:
    result = {item.name: helper.get_attribute_value(item) for item in node.attribute}
    result["K"] = k
    result["N"] = n
    return result


def external_fields(tensor: TensorProto) -> tuple[str, int, int]:
    fields = {item.key: item.value for item in tensor.external_data}
    return fields["location"], int(fields.get("offset", "0")), int(fields["length"])


def external_tensor(
    source: TensorProto, name: str, dimensions: list[int], location: str, offset: int, length: int
) -> TensorProto:
    tensor = TensorProto()
    tensor.name = name
    tensor.data_type = source.data_type
    tensor.dims.extend(dimensions)
    tensor.data_location = TensorProto.EXTERNAL
    tensor.external_data.extend(
        [
            StringStringEntryProto(key="location", value=location),
            StringStringEntryProto(key="offset", value=str(offset)),
            StringStringEntryProto(key="length", value=str(length)),
        ]
    )
    return tensor


def shard(source: Path, destination: Path, shard_data: Path) -> dict[str, object]:
    model = onnx.load(str(source), load_external_data=False)
    initializers = {item.name: item for item in model.graph.initializer}
    replaced_initializers: set[str] = set()
    added_initializers: list[TensorProto] = []
    rewritten: list[onnx.NodeProto] = []
    gate_or_up = 0
    down = 0
    shard_offset = 0
    shard_data.parent.mkdir(parents=True, exist_ok=True)

    split_sizes_name = "__mlp_wide_split_sizes"
    added_initializers.extend(
        [
            numpy_helper.from_array(np.asarray(PARTS, dtype=np.int64), split_sizes_name),
            numpy_helper.from_array(
                np.zeros((1, 1, PARTS[0] - PARTS[1]), dtype=np.float32),
                "__mlp_part1_input_padding",
            ),
        ]
    )

    with shard_data.open("wb") as shard_stream:
        for node in model.graph.node:
            if node.op_type != "MatMulNBits" or node.domain != "com.microsoft":
                rewritten.append(node)
                continue
            node_attrs = {item.name: helper.get_attribute_value(item) for item in node.attribute}
            k = int(node_attrs["K"])
            n = int(node_attrs["N"])
            if (k, n) not in ((2048, WIDE), (WIDE, 2048)):
                rewritten.append(node)
                continue
            if len(node.input) != 3:
                raise ValueError(f"expected symmetric MatMulNBits on {node.name}")
            weight = initializers[node.input[1]]
            scales = initializers[node.input[2]]
            weight_location, weight_offset, weight_length = external_fields(weight)
            scale_location, scale_offset, scale_length = external_fields(scales)
            if weight_location != "model_q4.onnx_data" or scale_location != weight_location:
                raise ValueError(f"unexpected external data on {node.name}")
            data_path = source.parent / weight_location
            prefix = f"{node.name}/htp_shard"

            if (k, n) == (2048, WIDE):
                gate_or_up += 1
                # Output-channel halves are contiguous in [N, K/block, block/2].
                outputs = []
                weight_cursor = weight_offset
                scale_cursor = scale_offset
                for index, part_size in enumerate(PARTS):
                    w_part_bytes = part_size * (2048 // BLOCK_SIZE) * (BLOCK_SIZE // 2)
                    s_part_bytes = part_size * (2048 // BLOCK_SIZE) * 4
                    w_name = f"{node.input[1]}_part{index}"
                    s_name = f"{node.input[2]}_part{index}"
                    added_initializers.extend(
                        [
                            external_tensor(
                                weight,
                                w_name,
                                [part_size, 2048 // BLOCK_SIZE, BLOCK_SIZE // 2],
                                weight_location,
                                weight_cursor,
                                w_part_bytes,
                            ),
                            external_tensor(
                                scales,
                                s_name,
                                [part_size, 2048 // BLOCK_SIZE],
                                scale_location,
                                scale_cursor,
                                s_part_bytes,
                            ),
                        ]
                    )
                    weight_cursor += w_part_bytes
                    scale_cursor += s_part_bytes
                    part_output = f"{prefix}/part{index}"
                    outputs.append(part_output)
                    rewritten.append(
                        helper.make_node(
                            "MatMulNBits",
                            [node.input[0], w_name, s_name],
                            [part_output],
                            name=f"{prefix}/matmul{index}",
                            domain="com.microsoft",
                            **attrs(node, k=2048, n=part_size),
                        )
                    )
                rewritten.append(
                    helper.make_node("Concat", outputs, list(node.output), name=node.name, axis=-1)
                )
            else:
                down += 1
                # Input-channel halves are strided across N, so materialize two
                # compact external tensors in a separate ignored data file.
                input_parts = [f"{prefix}/input0", f"{prefix}/input1"]
                rewritten.append(
                    helper.make_node(
                        "Split",
                        [node.input[0], split_sizes_name],
                        input_parts,
                        name=f"{prefix}/split_input",
                        axis=-1,
                    )
                )
                weight_map = np.memmap(
                    data_path,
                    mode="r",
                    dtype=np.uint8,
                    offset=weight_offset,
                    shape=tuple(weight.dims),
                )
                scale_map = np.memmap(
                    data_path,
                    mode="r",
                    dtype=np.float32,
                    offset=scale_offset,
                    shape=tuple(scales.dims),
                )
                outputs = []
                block_start = 0
                for index, (part_size, block_count) in enumerate(zip(PARTS, PART_BLOCKS, strict=True)):
                    block_slice = slice(block_start, block_start + block_count)
                    block_start += block_count
                    weight_part = np.ascontiguousarray(weight_map[:, block_slice, :])
                    scale_part = np.ascontiguousarray(scale_map[:, block_slice])
                    matmul_input = input_parts[index]
                    matmul_k = part_size
                    if index == 1:
                        # v73 accepts the 6,144-wide block matmul but rejects
                        # K=4,608 during graph finalization. Zero-pad both the
                        # activation and quantized weight blocks to 6,144; the
                        # extra dot-product contribution is exactly zero.
                        pad_blocks = PART_BLOCKS[0] - block_count
                        weight_part = np.concatenate(
                            [weight_part, np.zeros((2048, pad_blocks, BLOCK_SIZE // 2), dtype=np.uint8)],
                            axis=1,
                        )
                        scale_part = np.concatenate(
                            [scale_part, np.ones((2048, pad_blocks), dtype=np.float32)], axis=1
                        )
                        padded_input = f"{prefix}/input{index}_padded"
                        rewritten.append(
                            helper.make_node(
                                "Concat",
                                [matmul_input, "__mlp_part1_input_padding"],
                                [padded_input],
                                name=padded_input,
                                axis=-1,
                            )
                        )
                        matmul_input = padded_input
                        matmul_k = PARTS[0]
                    w_bytes = weight_part.tobytes()
                    s_bytes = scale_part.tobytes()
                    stored_blocks = weight_part.shape[1]
                    w_name = f"{node.input[1]}_part{index}"
                    s_name = f"{node.input[2]}_part{index}"
                    w_at = shard_offset
                    shard_stream.write(w_bytes)
                    shard_offset += len(w_bytes)
                    s_at = shard_offset
                    shard_stream.write(s_bytes)
                    shard_offset += len(s_bytes)
                    added_initializers.extend(
                        [
                            external_tensor(
                                weight,
                                w_name,
                                [2048, stored_blocks, BLOCK_SIZE // 2],
                                shard_data.name,
                                w_at,
                                len(w_bytes),
                            ),
                            external_tensor(
                                scales,
                                s_name,
                                [2048, stored_blocks],
                                shard_data.name,
                                s_at,
                                len(s_bytes),
                            ),
                        ]
                    )
                    part_output = f"{prefix}/part{index}"
                    outputs.append(part_output)
                    rewritten.append(
                        helper.make_node(
                            "MatMulNBits",
                            [matmul_input, w_name, s_name],
                            [part_output],
                            name=f"{prefix}/matmul{index}",
                            domain="com.microsoft",
                            **attrs(node, k=matmul_k, n=2048),
                        )
                    )
                rewritten.append(helper.make_node("Add", outputs, list(node.output), name=node.name))
            replaced_initializers.update(node.input[1:])

    kept_initializers = [
        item for item in model.graph.initializer if item.name not in replaced_initializers
    ]
    del model.graph.initializer[:]
    model.graph.initializer.extend(kept_initializers)
    model.graph.initializer.extend(added_initializers)
    del model.graph.node[:]
    model.graph.node.extend(rewritten)
    destination.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(destination))
    onnx.checker.check_model(str(destination), full_check=False)
    return {
        "source": str(source),
        "destination": str(destination),
        "shard_data": str(shard_data),
        "gate_or_up_nodes_sharded": gate_or_up,
        "down_nodes_sharded": down,
        "wide_dimension": WIDE,
        "part_dimensions": list(PARTS),
        "block_size": BLOCK_SIZE,
        "shard_data_bytes": shard_offset,
        "onnx_checker": "passed",
        "equivalence": "output-channel concatenation for gate/up; block-aligned input split plus partial-output addition for down",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("shard_data", type=Path)
    args = parser.parse_args()
    print(json.dumps(shard(args.source, args.destination, args.shard_data), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
