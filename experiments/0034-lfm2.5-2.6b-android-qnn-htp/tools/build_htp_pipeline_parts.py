#!/usr/bin/env python3
"""Build memory-bounded HTP pipeline parts from the lowered/sharded LFM2 graph."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

import numpy as np
import onnx
from onnx import StringStringEntryProto, TensorProto, helper
from onnx.utils import Extractor

ATTENTION_LAYERS = {2, 5, 9, 13, 17, 21, 24, 27}
PART_SIZES = (6144, 4608)
HEAD_CHUNK = 6144


def value(name: str, shape: list[int], dtype: int = TensorProto.FLOAT) -> onnx.ValueInfoProto:
    return helper.make_tensor_value_info(name, dtype, shape)


def external_fields(tensor: TensorProto) -> tuple[str, int, int]:
    fields = {entry.key: entry.value for entry in tensor.external_data}
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


def build(source: Path, output_dir: Path) -> dict[str, object]:
    model = onnx.load(str(source), load_external_data=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    locations = sorted(
        {
            entry.value
            for initializer in model.graph.initializer
            for entry in initializer.external_data
            if entry.key == "location"
        }
    )
    for location in locations:
        source_data = source.parent / location
        link = output_dir / location
        if not link.exists():
            os.link(source_data, link)

    # Expose every intended cut point to ONNX's dependency extractor.
    known = {item.name for item in model.graph.value_info}
    additions: dict[str, onnx.ValueInfoProto] = {}

    def expose(name: str, shape: list[int]) -> None:
        if name not in known and name not in additions:
            additions[name] = value(name, shape)

    for layer in range(30):
        expose(f"/model/layers.{layer}/Add_1/output_0", [1, 1, 2048])
        expose(f"/model/layers.{layer}/Add_2/output_0", [1, 1, 2048])
        expose(f"/model/layers.{layer}/ffn_layernorm/LayerNorm/output_0", [1, 1, 2048])
        for projection in ("gate_proj", "up_proj"):
            for part, size in enumerate(PART_SIZES):
                expose(
                    f"/model/layers.{layer}/mlp/{projection}/MatMul_Q4/htp_shard/part{part}",
                    [1, 1, size],
                )
        for part, size in enumerate(PART_SIZES):
            expose(
                f"/model/layers.{layer}/mlp/down_proj/MatMul_Q4/htp_shard/input{part}",
                [1, 1, size],
            )
            expose(
                f"/model/layers.{layer}/mlp/down_proj/MatMul_Q4/htp_shard/part{part}",
                [1, 1, 2048],
            )
    final_norm = "/model/layers.30/final_norm_layernorm/output_0"
    expose(final_norm, [1, 1, 2048])
    model.graph.value_info.extend(additions.values())

    parts: list[dict[str, object]] = []

    def save_part(name: str, part: onnx.ModelProto, kind: str, metadata: dict[str, object]) -> None:
        path = output_dir / f"{name}.onnx"
        onnx.save(part, str(path))
        onnx.checker.check_model(str(path), full_check=False)
        parts.append(
            {
                "name": name,
                "path": path.name,
                "kind": kind,
                "inputs": [item.name for item in part.graph.input],
                "outputs": [item.name for item in part.graph.output],
                "nodes": len(part.graph.node),
                "initializers": len(part.graph.initializer),
                **metadata,
            }
        )

    hidden = "/model/embed_tokens/GatherBlockQuantized/output_0"
    for layer in range(30):
        residual = f"/model/layers.{layer}/Add_1/output_0"
        next_hidden = f"/model/layers.{layer}/Add_2/output_0"
        norm = f"/model/layers.{layer}/ffn_layernorm/LayerNorm/output_0"
        if layer in ATTENTION_LAYERS:
            core_inputs = [
                hidden,
                "position_ids",
                "attention_mask",
                f"past_key_values.{layer}.key",
                f"past_key_values.{layer}.value",
            ]
            state_outputs = [f"present.{layer}.key", f"present.{layer}.value"]
        else:
            core_inputs = [hidden, f"past_conv.{layer}"]
            state_outputs = [f"present_conv.{layer}"]
        core = Extractor(model).extract_model(core_inputs, [residual, norm, *state_outputs])
        save_part(
            f"layer-{layer:02d}-core-norm",
            core,
            "attention_core_norm" if layer in ATTENTION_LAYERS else "convolution_core_norm",
            {"layer": layer},
        )

        products = []
        for half, size in enumerate(PART_SIZES):
            up = f"/model/layers.{layer}/mlp/up_proj/MatMul_Q4/htp_shard/part{half}"
            up_part = Extractor(model).extract_model([norm], [up])
            save_part(
                f"layer-{layer:02d}-up-{half}", up_part, "mlp_up_projection", {"layer": layer, "part": half, "width": size}
            )

            gate = f"/model/layers.{layer}/mlp/gate_proj/MatMul_Q4/htp_shard/part{half}"
            gate_part = Extractor(model).extract_model([norm], [gate])
            gate_part.graph.input.append(value(up, [1, 1, size]))
            del gate_part.graph.output[:]
            sigmoid = f"{gate}/pipeline_sigmoid"
            silu = f"{gate}/pipeline_silu"
            product = f"/model/layers.{layer}/mlp/pipeline_product_part{half}"
            gate_part.graph.node.extend(
                [
                    helper.make_node("Sigmoid", [gate], [sigmoid], name=sigmoid),
                    helper.make_node("Mul", [gate, sigmoid], [silu], name=silu),
                    helper.make_node("Mul", [silu, up], [product], name=product),
                ]
            )
            gate_part.graph.output.append(value(product, [1, 1, size]))
            save_part(
                f"layer-{layer:02d}-gate-activate-{half}",
                gate_part,
                "mlp_gate_and_activation",
                {"layer": layer, "part": half, "width": size},
            )
            products.append(product)

        down_outputs = []
        for half, size in enumerate(PART_SIZES):
            graph_input = f"/model/layers.{layer}/mlp/down_proj/MatMul_Q4/htp_shard/input{half}"
            graph_output = f"/model/layers.{layer}/mlp/down_proj/MatMul_Q4/htp_shard/part{half}"
            down_part = Extractor(model).extract_model([graph_input], [graph_output])
            # Give the pipeline's semantically identical product cut-point the
            # exact name expected by the extracted down-projection graph.
            down_part.graph.input[0].name = products[half]
            for node in down_part.graph.node:
                for index, item in enumerate(node.input):
                    if item == graph_input:
                        node.input[index] = products[half]
            down_outputs.append(graph_output)
            save_part(
                f"layer-{layer:02d}-down-{half}",
                down_part,
                "mlp_down_projection_partial",
                {"layer": layer, "part": half, "width": size},
            )
        summed = f"/model/layers.{layer}/mlp/pipeline_down_sum"
        residual_graph = helper.make_graph(
            [
                helper.make_node("Add", down_outputs, [summed], name=summed),
                helper.make_node("Add", [residual, summed], [next_hidden], name=f"/model/layers.{layer}/Add_2"),
            ],
            f"lfm2_layer_{layer}_residual",
            [value(down_outputs[0], [1, 1, 2048]), value(down_outputs[1], [1, 1, 2048]), value(residual, [1, 1, 2048])],
            [value(next_hidden, [1, 1, 2048])],
        )
        residual_part = helper.make_model(
            residual_graph,
            ir_version=model.ir_version,
            opset_imports=[copy.deepcopy(item) for item in model.opset_import],
        )
        save_part(
            f"layer-{layer:02d}-residual",
            residual_part,
            "mlp_partial_sum_and_residual",
            {"layer": layer},
        )
        hidden = next_hidden

    final_norm_model = Extractor(model).extract_model([hidden], [final_norm])
    save_part("final-norm", final_norm_model, "final_norm", {})

    # Split the vocabulary projection into independently prepared output-channel
    # chunks. The runner performs one global greedy argmax across chunk outputs.
    logits_node = next(
        node
        for node in model.graph.node
        if node.op_type == "MatMulNBits"
        and any(attr.name == "N" and helper.get_attribute_value(attr) == 128000 for attr in node.attribute)
    )
    initializer_map = {item.name: item for item in model.graph.initializer}
    weight = initializer_map[logits_node.input[1]]
    scales = initializer_map[logits_node.input[2]]
    w_location, w_offset, _ = external_fields(weight)
    s_location, s_offset, _ = external_fields(scales)
    cursor = 0
    chunk = 0
    while cursor < 128000:
        remaining = 128000 - cursor
        # The v73 HTP preparation path rejects the otherwise natural final
        # width 5,120. Use two smaller supported final chunks instead.
        width = 4096 if remaining == 5120 else min(HEAD_CHUNK, remaining)
        w_bytes = width * 64 * 16
        s_bytes = width * 64 * 4
        w_name = f"{weight.name}_vocab_{cursor}_{cursor + width}"
        s_name = f"{scales.name}_vocab_{cursor}_{cursor + width}"
        out = f"logits_vocab_{cursor}_{cursor + width}"
        node = helper.make_node(
            "MatMulNBits",
            [final_norm, w_name, s_name],
            [out],
            name=f"/lm_head/chunk_{chunk}",
            domain="com.microsoft",
            K=2048,
            N=width,
            bits=4,
            block_size=32,
            accuracy_level=4,
        )
        graph = helper.make_graph(
            [node],
            f"lfm2_head_chunk_{chunk}",
            [value(final_norm, [1, 1, 2048])],
            [value(out, [1, 1, width])],
            [
                external_tensor(weight, w_name, [width, 64, 16], w_location, w_offset, w_bytes),
                external_tensor(scales, s_name, [width, 64], s_location, s_offset, s_bytes),
            ],
        )
        part = helper.make_model(
            graph,
            ir_version=model.ir_version,
            opset_imports=[copy.deepcopy(item) for item in model.opset_import],
        )
        save_part(
            f"head-{chunk:02d}",
            part,
            "lm_head_chunk",
            {"chunk": chunk, "token_offset": cursor, "width": width},
        )
        cursor += width
        w_offset += w_bytes
        s_offset += s_bytes
        chunk += 1

    manifest = {
        "schema_version": 1,
        "source": str(source),
        "logical_route": "CPU exact Q4 embedding lookup, then all transformer/state/final-norm/lm-head tensor graphs through ordered HTP parts, then CPU greedy argmax/tokenizer",
        "explicit_cpu_frontend": {
            "operation": "one-row asymmetric Q4 embedding dequantization",
            "reason": "QNN EP 2.5 HTP does not claim GatherBlockQuantized; explicit frontend is not provider fallback",
        },
        "htp_part_count": len(parts),
        "loaded_route_requirement": "all part sessions/contexts are created once during setup and retained for the campaign",
        "reset": "zero all 22 convolution states and all 16 attention K/V states before every logical request",
        "head_reduction": "CPU compares all HTP head-chunk logits and applies one global greedy argmax",
        "parts": parts,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    manifest = build(args.source, args.output_dir)
    print(json.dumps({"manifest": str(args.output_dir / 'manifest.json'), "htp_part_count": manifest["htp_part_count"]}, indent=2))


if __name__ == "__main__":
    main()
