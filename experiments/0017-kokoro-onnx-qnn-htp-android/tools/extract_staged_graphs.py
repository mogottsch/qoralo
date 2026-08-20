#!/usr/bin/env python3
"""Split the fixed-contract Kokoro QNN-compatible graph at module boundaries.

The source graph is not retraced or optimized. Each stage is a backward slice of
exact source nodes and initializer payloads, with named intermediate tensors
promoted to graph inputs/outputs. Models and runtime tensors stay under ignored
``work/``; the emitted manifest locks every stage interface and byte hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import onnx
from onnx import TensorProto, helper, numpy_helper

EXPECTED_SOURCE_SHA256 = "7278ed2f0dbe8307a42904434b81116f252dd996bb6a2c064f81ad44269f21cb"
QUANTIZED_OPS = {
    "QuantizeLinear",
    "DequantizeLinear",
    "DynamicQuantizeLinear",
    "MatMulInteger",
    "QLinearConv",
    "QLinearMatMul",
}


@dataclass(frozen=True)
class StageSpec:
    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    role: str


BERT = "/bert_encoder/Add_output_0"
DURATION_CONTEXT = "/text_encoder/Where_13"
TEXT_CONTEXT = "/text_encoder_1/Where_7_output_0"
PROSODY_CONTEXT = "/MatMul_output_0"
ASR_CONTEXT = "/MatMul_1_output_0"
F0 = "/If_output_0"
NOISE = "/If_1_output_0"
GENERATOR_INPUT = "/decoder/decode.3/Mul_output_0"
HARMONIC = "/decoder/generator/Concat_1_output_0"
G0_BASE = "/decoder/generator/Add_2_output_0"
G0_BRANCHES = tuple(
    f"/decoder/generator/resblocks.{index}/Add_8_output_0" for index in range(3)
)
G0_MERGED = "/decoder/generator/Div_1_output_0"
G1_BASE = "/decoder/generator/Add_5_output_0"
G1_BRANCHES = tuple(
    f"/decoder/generator/resblocks.{index}/Add_8_output_0" for index in range(3, 6)
)
G1_MERGED = "/decoder/generator/Div_2_output_0"

STAGES = (
    StageSpec(
        "bert",
        ("tokens",),
        (BERT,),
        "ALBERT text representation and learned projection",
    ),
    StageSpec(
        "duration_encoder",
        (BERT, "style"),
        (DURATION_CONTEXT,),
        "style-conditioned duration encoder",
    ),
    StageSpec(
        "text_encoder",
        ("tokens",),
        (TEXT_CONTEXT,),
        "convolutional/recurrent acoustic text encoder",
    ),
    StageSpec(
        "duration_alignment",
        (DURATION_CONTEXT, TEXT_CONTEXT, "speed"),
        (PROSODY_CONTEXT, ASR_CONTEXT, "pred_dur"),
        "duration LSTM/head plus fixed-contract runtime alignment",
    ),
    StageSpec(
        "prosody",
        (PROSODY_CONTEXT, "style"),
        (F0, NOISE),
        "shared recurrent prosody network and F0/noise heads",
    ),
    StageSpec(
        "decoder",
        (ASR_CONTEXT, F0, NOISE, "style"),
        (GENERATOR_INPUT,),
        "style-conditioned acoustic decoder before waveform generator",
    ),
    StageSpec(
        "harmonic_source",
        (F0,),
        (HARMONIC,),
        "fixed-phase harmonic source, learned merge, and source STFT",
    ),
    StageSpec(
        "generator_0_base",
        (GENERATOR_INPUT, HARMONIC, "style"),
        (G0_BASE,),
        "first upsample and style-conditioned source residual branch",
    ),
    StageSpec(
        "generator_0_resblock_0",
        (G0_BASE, "style"),
        (G0_BRANCHES[0],),
        "first-resolution residual block 0",
    ),
    StageSpec(
        "generator_0_resblock_1",
        (G0_BASE, "style"),
        (G0_BRANCHES[1],),
        "first-resolution residual block 1",
    ),
    StageSpec(
        "generator_0_resblock_2",
        (G0_BASE, "style"),
        (G0_BRANCHES[2],),
        "first-resolution residual block 2",
    ),
    StageSpec(
        "generator_0_merge",
        G0_BRANCHES,
        (G0_MERGED,),
        "ordered residual sum and divide by three",
    ),
    StageSpec(
        "generator_1_base",
        (G0_MERGED, HARMONIC, "style"),
        (G1_BASE,),
        "second upsample and style-conditioned source residual branch",
    ),
    StageSpec(
        "generator_1_resblock_3",
        (G1_BASE, "style"),
        (G1_BRANCHES[0],),
        "second-resolution residual block 3",
    ),
    StageSpec(
        "generator_1_resblock_4",
        (G1_BASE, "style"),
        (G1_BRANCHES[1],),
        "second-resolution residual block 4",
    ),
    StageSpec(
        "generator_1_resblock_5",
        (G1_BASE, "style"),
        (G1_BRANCHES[2],),
        "second-resolution residual block 5",
    ),
    StageSpec(
        "generator_1_merge",
        G1_BRANCHES,
        (G1_MERGED,),
        "ordered residual sum and divide by three",
    ),
    StageSpec(
        "waveform_istft",
        (G1_MERGED,),
        ("audio",),
        "spectral head and exact exported inverse STFT",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_payload_sha256(tensor: onnx.TensorProto) -> str:
    return hashlib.sha256(numpy_helper.to_array(tensor).tobytes()).hexdigest()


def dtype_name(dtype: int) -> str:
    names = {
        TensorProto.FLOAT: "float32",
        TensorProto.INT64: "int64",
        TensorProto.BOOL: "bool",
        TensorProto.INT32: "int32",
    }
    if dtype not in names:
        raise RuntimeError(f"unsupported stage-interface dtype: {dtype}")
    return names[dtype]


def value_contract(value: onnx.ValueInfoProto) -> dict[str, object]:
    tensor_type = value.type.tensor_type
    if not tensor_type.HasField("shape"):
        raise RuntimeError(f"missing tensor shape: {value.name}")
    shape: list[int] = []
    for dim in tensor_type.shape.dim:
        if not dim.HasField("dim_value") or dim.dim_value <= 0:
            raise RuntimeError(f"non-fixed tensor dimension: {value.name}")
        shape.append(dim.dim_value)
    return {
        "name": value.name,
        "dtype": dtype_name(tensor_type.elem_type),
        "shape": shape,
        "elements": int(__import__("math").prod(shape)),
    }


def make_stage_model(
    source: onnx.ModelProto,
    spec: StageSpec,
    values: dict[str, onnx.ValueInfoProto],
    initializer_by_name: dict[str, onnx.TensorProto],
    producer: dict[str, onnx.NodeProto],
) -> tuple[onnx.ModelProto, list[onnx.NodeProto], list[onnx.TensorProto]]:
    boundary = set(spec.inputs)
    needed_values = list(spec.outputs)
    kept_node_ids: set[int] = set()
    while needed_values:
        name = needed_values.pop()
        if name in boundary or name in initializer_by_name:
            continue
        node = producer.get(name)
        if node is None:
            raise RuntimeError(f"{spec.name}: unresolved value {name!r}")
        if id(node) in kept_node_ids:
            continue
        kept_node_ids.add(id(node))
        needed_values.extend(item for item in node.input if item)

    # Source order is already topological; filtering preserves it.
    nodes = [node for node in source.graph.node if id(node) in kept_node_ids]
    produced = {name for node in nodes for name in node.output if name}
    used = {name for node in nodes for name in node.input if name}
    unresolved = sorted(used - produced - boundary - set(initializer_by_name))
    if unresolved:
        raise RuntimeError(f"{spec.name}: undeclared stage inputs: {unresolved}")
    unused_boundaries = sorted(boundary - used - set(spec.outputs))
    if unused_boundaries:
        raise RuntimeError(f"{spec.name}: unused declared inputs: {unused_boundaries}")

    initializers = [
        tensor for tensor in source.graph.initializer if tensor.name in used
    ]
    live_values = boundary | produced | used | set(spec.outputs)
    stage_value_info = [
        value
        for value in source.graph.value_info
        if value.name in live_values
        and value.name not in boundary
        and value.name not in spec.outputs
    ]
    inputs = [values[name] for name in spec.inputs]
    outputs = [values[name] for name in spec.outputs]
    graph = helper.make_graph(
        nodes,
        f"kokoro_0017_{spec.name}",
        inputs,
        outputs,
        initializer=initializers,
        value_info=stage_value_info,
        doc_string=(
            "Exact backward slice of the fixed-contract QNN-compatible Kokoro "
            f"graph: {spec.role}."
        ),
    )
    model = helper.make_model(
        graph,
        producer_name="experiment-0017-stage-extractor",
        producer_version="1",
        domain=source.domain,
        model_version=source.model_version,
        doc_string=source.doc_string,
        opset_imports=source.opset_import,
        ir_version=source.ir_version,
    )
    model.metadata_props.extend(source.metadata_props)
    model.functions.extend(source.functions)
    onnx.checker.check_model(model, full_check=True)
    return model, nodes, initializers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    source_sha = sha256(args.source)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"source hash mismatch: expected {EXPECTED_SOURCE_SHA256}, got {source_sha}"
        )
    source = onnx.load(str(args.source), load_external_data=False)
    if any(node.op_type in QUANTIZED_OPS for node in source.graph.node):
        raise RuntimeError("source unexpectedly contains quantized operators")

    all_values = [
        *source.graph.input,
        *source.graph.output,
        *source.graph.value_info,
    ]
    values = {value.name: value for value in all_values}
    if len(values) != len(all_values):
        # Duplicates between graph input/output/value_info are legal, but the
        # compatibility graph intentionally has unique metadata records.
        duplicates = [
            name
            for name, count in Counter(value.name for value in all_values).items()
            if count > 1
        ]
        raise RuntimeError(f"duplicate value metadata: {duplicates}")
    initializer_by_name = {item.name: item for item in source.graph.initializer}
    producer = {
        output: node for node in source.graph.node for output in node.output if output
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stage_records = []
    coverage: defaultdict[str, list[str]] = defaultdict(list)
    initializer_payloads = {
        item.name: tensor_payload_sha256(item) for item in source.graph.initializer
    }
    for index, spec in enumerate(STAGES, start=1):
        model, nodes, initializers = make_stage_model(
            source, spec, values, initializer_by_name, producer
        )
        model_path = args.output_dir / f"{index:02d}-{spec.name}.onnx"
        onnx.save(model, str(model_path))
        for node in nodes:
            coverage[node.name].append(spec.name)
        for item in initializers:
            if tensor_payload_sha256(item) != initializer_payloads[item.name]:
                raise RuntimeError(f"initializer payload changed: {item.name}")
        stage_records.append(
            {
                "index": index,
                "name": spec.name,
                "role": spec.role,
                "model": {
                    "path": str(model_path),
                    "bytes": model_path.stat().st_size,
                    "sha256": sha256(model_path),
                },
                "inputs": [value_contract(values[name]) for name in spec.inputs],
                "outputs": [value_contract(values[name]) for name in spec.outputs],
                "structure": {
                    "nodes": len(nodes),
                    "initializers": len(initializers),
                    "initializer_payload_bytes": sum(
                        numpy_helper.to_array(item).nbytes for item in initializers
                    ),
                    "operators": dict(
                        sorted(Counter(node.op_type for node in nodes).items())
                    ),
                    "quantized_operator_count": sum(
                        node.op_type in QUANTIZED_OPS for node in nodes
                    ),
                },
            }
        )

    source_names = {node.name for node in source.graph.node}
    covered_names = set(coverage)
    missing = sorted(source_names - covered_names)
    if missing:
        raise RuntimeError(f"stage decomposition omitted source nodes: {missing}")
    extras = sorted(covered_names - source_names)
    if extras:
        raise RuntimeError(f"stage decomposition introduced nodes: {extras}")

    original_inputs = {value.name for value in source.graph.input}
    available = set(original_inputs)
    for record in stage_records:
        required = {item["name"] for item in record["inputs"]}
        if not required <= available:
            raise RuntimeError(
                f"pipeline order error at {record['name']}: {sorted(required - available)}"
            )
        available.update(item["name"] for item in record["outputs"])
    original_outputs = {value.name for value in source.graph.output}
    if not original_outputs <= available:
        raise RuntimeError(f"pipeline does not produce: {sorted(original_outputs - available)}")

    manifest = {
        "schema_version": 1,
        "source": {
            "path": str(args.source),
            "bytes": args.source.stat().st_size,
            "sha256": source_sha,
            "nodes": len(source.graph.node),
            "initializers": len(source.graph.initializer),
        },
        "policy": {
            "fixed_contract_only": True,
            "quantization": False,
            "learned_initializer_payload_changes": 0,
            "stage_models_are_exact_backward_slices": True,
            "stage_execution_order": "sequential host processes for eligibility; explicit CPU tensor orchestration",
        },
        "pipeline_inputs": [value_contract(value) for value in source.graph.input],
        "pipeline_outputs": [value_contract(value) for value in source.graph.output],
        "stages": stage_records,
        "coverage": {
            "source_nodes": len(source_names),
            "covered_unique_nodes": len(covered_names),
            "duplicated_boundary_support_nodes": {
                name: stages
                for name, stages in sorted(coverage.items())
                if len(stages) > 1
            },
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "manifest": str(args.manifest),
                "stages": len(stage_records),
                "source_nodes": len(source_names),
                "covered_unique_nodes": len(covered_names),
                "duplicated_nodes": len(
                    manifest["coverage"]["duplicated_boundary_support_nodes"]
                ),
                "total_stage_model_bytes": sum(
                    record["model"]["bytes"] for record in stage_records
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
