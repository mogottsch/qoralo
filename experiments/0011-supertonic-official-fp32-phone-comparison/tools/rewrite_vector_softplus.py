#!/usr/bin/env python3
"""Replace the one locked vector-estimator Softplus with a stable primitive identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

SOURCE_SHA256 = "723316adfcff378c8ac72ee9db34cadf3b890e4167fa9a76f07398e0d4ff5b92"
TARGET_NAME = "/vector_estimator/vector_field/time_encoder/mlp/mlp.1/Softplus"
TARGET_INPUT = "/vector_estimator/vector_field/time_encoder/mlp/mlp.0/linear/Gemm_output_0"
TARGET_OUTPUT = "/vector_estimator/vector_field/time_encoder/mlp/mlp.1/Softplus_output_0"
EXPECTED_CONSUMER = "/vector_estimator/vector_field/time_encoder/mlp/mlp.1/Tanh"
PREFIX = TARGET_NAME + "/stable"
ONE_NAME = PREFIX + "/one"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def value_contract(model: onnx.ModelProto, name: str) -> tuple[int, list[int]]:
    for info in [*model.graph.input, *model.graph.output, *model.graph.value_info]:
        if info.name == name:
            tensor = info.type.tensor_type
            shape = [dimension.dim_value for dimension in tensor.shape.dim]
            return tensor.elem_type, shape
    raise ValueError(f"missing value_info for {name}")


def rewrite(model: onnx.ModelProto) -> tuple[onnx.ModelProto, dict]:
    default_opsets = [item.version for item in model.opset_import if item.domain in ("", "ai.onnx")]
    if default_opsets != [19]:
        raise ValueError(f"expected default ONNX opset 19, found {default_opsets}")
    matches = [(i, node) for i, node in enumerate(model.graph.node) if node.name == TARGET_NAME]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one target node, found {len(matches)}")
    index, selected = matches[0]
    if selected.op_type != "Softplus" or selected.domain not in ("", "ai.onnx"):
        raise ValueError("target is not a standard-domain Softplus")
    if list(selected.input) != [TARGET_INPUT] or list(selected.output) != [TARGET_OUTPUT] or selected.attribute:
        raise ValueError("target wiring or attributes differ from the locked contract")
    dtype, shape = value_contract(model, TARGET_INPUT)
    if dtype != TensorProto.FLOAT or shape != [2, 256]:
        raise ValueError(f"expected float32 [2,256] target input, found dtype={dtype} shape={shape}")
    consumers = [node for node in model.graph.node if TARGET_OUTPUT in node.input]
    if len(consumers) != 1 or consumers[0].name != EXPECTED_CONSUMER or consumers[0].op_type != "Tanh":
        raise ValueError("target output has an unexpected or unsafe consumer set")
    if TARGET_OUTPUT in {item.name for item in model.graph.output}:
        raise ValueError("target output is unexpectedly a graph output")
    occupied_values = {name for node in model.graph.node for name in [*node.input, *node.output]}
    occupied_values.update(item.name for item in model.graph.initializer)
    internal = [PREFIX + suffix for suffix in ("/relu", "/abs", "/neg_abs", "/exp", "/one_plus_exp", "/log")]
    if any(name in occupied_values for name in [*internal, ONE_NAME]):
        raise ValueError("replacement value name collision")

    relu, absolute, negative, exponent, one_plus, logarithm = internal
    nodes = [
        helper.make_node("Relu", [TARGET_INPUT], [relu], name=PREFIX + "/Relu"),
        helper.make_node("Abs", [TARGET_INPUT], [absolute], name=PREFIX + "/Abs"),
        helper.make_node("Neg", [absolute], [negative], name=PREFIX + "/Neg"),
        helper.make_node("Exp", [negative], [exponent], name=PREFIX + "/Exp"),
        helper.make_node("Add", [exponent, ONE_NAME], [one_plus], name=PREFIX + "/AddOne"),
        helper.make_node("Log", [one_plus], [logarithm], name=PREFIX + "/Log"),
        helper.make_node("Add", [relu, logarithm], [TARGET_OUTPUT], name=PREFIX + "/AddFinal"),
    ]
    original_node_hash = hashlib.sha256(selected.SerializeToString()).hexdigest()
    del model.graph.node[index]
    for offset, node in enumerate(nodes):
        model.graph.node.insert(index + offset, node)
    one = numpy_helper.from_array(np.asarray(1.0, dtype=np.float32), name=ONE_NAME)
    model.graph.initializer.append(one)
    onnx.checker.check_model(model, full_check=True)
    report = {
        "target_index": index,
        "removed": {"name": selected.name, "op_type": selected.op_type, "input": list(selected.input), "output": list(selected.output), "sha256": original_node_hash},
        "inserted_nodes": [{"name": n.name, "op_type": n.op_type, "input": list(n.input), "output": list(n.output), "sha256": hashlib.sha256(n.SerializeToString()).hexdigest()} for n in nodes],
        "inserted_initializers": [{"name": one.name, "dtype": "float32", "shape": [], "value": 1.0, "sha256": hashlib.sha256(one.SerializeToString()).hexdigest()}],
        "input_contract": {"name": TARGET_INPUT, "dtype": "float32", "shape": shape},
        "output_contract": {"name": TARGET_OUTPUT, "consumer": EXPECTED_CONSUMER},
        "identity": "Relu(x) + Log(1 + Exp(-Abs(x)))",
        "numerical_stability": "Exp receives -Abs(x), so its argument is never positive and cannot overflow.",
    }
    return model, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    source_hash = sha256_file(args.input)
    if source_hash != SOURCE_SHA256:
        raise SystemExit(f"source hash lock failed: expected {SOURCE_SHA256}, got {source_hash}")
    model = onnx.load(str(args.input), load_external_data=True)
    original_nodes = [node.SerializeToString() for node in model.graph.node]
    original_initializers = [item.SerializeToString() for item in model.graph.initializer]
    model, report = rewrite(model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(model, str(args.output), save_as_external_data=False)
    reloaded = onnx.load(str(args.output), load_external_data=True)
    index = report["target_index"]
    unchanged_nodes = [node.SerializeToString() for node in reloaded.graph.node[:index]] + [node.SerializeToString() for node in reloaded.graph.node[index + 7 :]]
    checks = {
        "all_non_target_original_nodes_byte_identical_and_ordered": unchanged_nodes == original_nodes[:index] + original_nodes[index + 1 :],
        "all_original_initializers_byte_identical_and_ordered": [item.SerializeToString() for item in reloaded.graph.initializer[:-1]] == original_initializers,
        "exactly_one_initializer_appended": len(reloaded.graph.initializer) == len(original_initializers) + 1,
        "node_count_delta_is_plus_six": len(reloaded.graph.node) == len(original_nodes) + 6,
        "deterministic_serialization": reloaded.SerializeToString() == model.SerializeToString(),
    }
    if not all(checks.values()):
        raise SystemExit(f"post-write proof failed: {checks}")
    provenance = {"schema_version": 1, "transformation": "single stable Softplus primitive expansion", "source": {"path": str(args.input.resolve()), "sha256": source_hash, "bytes": args.input.stat().st_size}, "output": {"path": str(args.output.resolve()), "sha256": sha256_file(args.output), "bytes": args.output.stat().st_size}, "opset": 19, "report": report, "proof": checks, "tool_sha256": sha256_file(Path(__file__).resolve()), "onnx": onnx.__version__}
    args.provenance.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    print(json.dumps(provenance, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
