#!/usr/bin/env python3
"""Rewrite eight proven ConvNeXt GELU decompositions to com.microsoft.Gelu.

This is deliberately model- and hash-specific. It only accepts the fixed,
weight-folded Supertonic 3 INT8 vocoder derivative and only rewrites ConvNeXt
blocks 0 through 7. Every five-node chain and scalar constant is verified
before any graph mutation. ConvNeXt blocks 8 and 9 are intentionally untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import helper, numpy_helper

EXPECTED_INPUT_SHA256 = "ee6760340a128e6f1f397ccee84c1fdd50165524d4ac7de76d522dec679fff14"
EXPECTED_PREFIXES = tuple(f"/decoder/convnext.{index}/act" for index in range(8))
EXPECTED_CONSTANTS = {
    "sqrt_2": np.float32(np.sqrt(np.float32(2.0))),
    "one": np.float32(1.0),
    "half": np.float32(0.5),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scalar_constant(
    name: str,
    initializers: dict[str, np.ndarray],
    producers: dict[str, onnx.NodeProto],
) -> np.float32:
    array: np.ndarray | None = initializers.get(name)
    if array is None:
        producer = producers.get(name)
        if producer is None or producer.op_type != "Constant" or producer.domain:
            raise ValueError(f"{name!r} is not a standard Constant output")
        value_attributes = [attribute for attribute in producer.attribute if attribute.name == "value"]
        if len(value_attributes) != 1:
            raise ValueError(f"{producer.name!r} does not have exactly one tensor value")
        array = numpy_helper.to_array(value_attributes[0].t)
    if array.dtype != np.dtype("float32") or array.shape != ():
        raise ValueError(f"{name!r} must be a scalar float32, got {array.dtype} {array.shape}")
    return np.float32(array)


def exact_constant(actual: np.float32, expected: np.float32, label: str) -> None:
    if actual.tobytes() != expected.tobytes():
        raise ValueError(
            f"{label} constant mismatch: got {float(actual)!r} "
            f"(0x{actual.tobytes().hex()}), expected {float(expected)!r} "
            f"(0x{expected.tobytes().hex()})"
        )


def sole_consumer(
    value: str,
    consumers: dict[str, list[onnx.NodeProto]],
    op_type: str,
    expected_name: str,
) -> onnx.NodeProto:
    matches = consumers.get(value, [])
    if len(matches) != 1:
        raise ValueError(f"{value!r} has {len(matches)} consumers, expected exactly one")
    node = matches[0]
    if node.op_type != op_type or node.domain or node.name != expected_name:
        raise ValueError(
            f"consumer of {value!r} is {node.domain}:{node.op_type} {node.name!r}, "
            f"expected standard {op_type} {expected_name!r}"
        )
    return node


def other_input(node: onnx.NodeProto, known: str) -> str:
    if len(node.input) != 2 or list(node.input).count(known) != 1:
        raise ValueError(f"{node.name!r} must have two inputs containing {known!r} exactly once")
    return node.input[1] if node.input[0] == known else node.input[0]


def tensor_shape(model: onnx.ModelProto, name: str) -> list[int | str | None] | None:
    values = list(model.graph.input) + list(model.graph.output) + list(model.graph.value_info)
    for value in values:
        if value.name != name or not value.type.HasField("tensor_type"):
            continue
        result: list[int | str | None] = []
        for dimension in value.type.tensor_type.shape.dim:
            if dimension.HasField("dim_value"):
                result.append(int(dimension.dim_value))
            elif dimension.HasField("dim_param"):
                result.append(dimension.dim_param)
            else:
                result.append(None)
        return result
    return None


def analyze(model: onnx.ModelProto) -> list[dict[str, Any]]:
    graph = model.graph
    initializers = {item.name: numpy_helper.to_array(item) for item in graph.initializer}
    producers: dict[str, onnx.NodeProto] = {}
    consumers: dict[str, list[onnx.NodeProto]] = {}
    for node in graph.node:
        for output in node.output:
            if output in producers:
                raise ValueError(f"duplicate producer for {output!r}")
            producers[output] = node
        for input_name in node.input:
            consumers.setdefault(input_name, []).append(node)
    graph_outputs = {value.name for value in graph.output}

    records: list[dict[str, Any]] = []
    for prefix in EXPECTED_PREFIXES:
        names = {
            "div": f"{prefix}/Div",
            "erf": f"{prefix}/Erf",
            "add": f"{prefix}/Add",
            "mul_x": f"{prefix}/Mul",
            "mul_half": f"{prefix}/Mul_1",
        }
        by_name = {node.name: node for node in graph.node}
        try:
            div = by_name[names["div"]]
        except KeyError as error:
            raise ValueError(f"missing selected Div {names['div']!r}") from error
        if div.op_type != "Div" or div.domain or len(div.input) != 2 or len(div.output) != 1:
            raise ValueError(f"{div.name!r} is not a standard binary Div")

        constant_inputs = []
        for input_name in div.input:
            try:
                value = scalar_constant(input_name, initializers, producers)
            except ValueError:
                continue
            constant_inputs.append((input_name, value))
        if len(constant_inputs) != 1:
            raise ValueError(f"{div.name!r} must have exactly one scalar constant input")
        sqrt_name, sqrt_value = constant_inputs[0]
        exact_constant(sqrt_value, EXPECTED_CONSTANTS["sqrt_2"], "sqrt(2)")
        x = other_input(div, sqrt_name)

        erf = sole_consumer(div.output[0], consumers, "Erf", names["erf"])
        if len(erf.input) != 1 or len(erf.output) != 1:
            raise ValueError(f"{erf.name!r} is not unary")
        add = sole_consumer(erf.output[0], consumers, "Add", names["add"])
        one_name = other_input(add, erf.output[0])
        one_value = scalar_constant(one_name, initializers, producers)
        exact_constant(one_value, EXPECTED_CONSTANTS["one"], "one")

        mul_x = sole_consumer(add.output[0], consumers, "Mul", names["mul_x"])
        reused_x = other_input(mul_x, add.output[0])
        if reused_x != x:
            raise ValueError(f"{mul_x.name!r} uses {reused_x!r}, but Div uses x={x!r}")
        mul_half = sole_consumer(mul_x.output[0], consumers, "Mul", names["mul_half"])
        half_name = other_input(mul_half, mul_x.output[0])
        half_value = scalar_constant(half_name, initializers, producers)
        exact_constant(half_value, EXPECTED_CONSTANTS["half"], "half")
        if len(mul_half.output) != 1:
            raise ValueError(f"{mul_half.name!r} must have exactly one output")

        removed_outputs = {div.output[0], erf.output[0], add.output[0], mul_x.output[0]}
        unsafe_outputs = sorted(removed_outputs & graph_outputs)
        if unsafe_outputs:
            raise ValueError(f"intermediate values are graph outputs: {unsafe_outputs}")

        records.append(
            {
                "prefix": prefix,
                "x": x,
                "output": mul_half.output[0],
                "x_shape": tensor_shape(model, x),
                "output_shape": tensor_shape(model, mul_half.output[0]),
                "nodes": [div.name, erf.name, add.name, mul_x.name, mul_half.name],
                "constants": {
                    "sqrt_2": {"value_name": sqrt_name, "float32": float(sqrt_value), "little_endian_hex": sqrt_value.tobytes().hex()},
                    "one": {"value_name": one_name, "float32": float(one_value), "little_endian_hex": one_value.tobytes().hex()},
                    "half": {"value_name": half_name, "float32": float(half_value), "little_endian_hex": half_value.tobytes().hex()},
                },
                "safety": {
                    "reuses_identical_x": True,
                    "each_removed_intermediate_has_exactly_one_consumer": True,
                    "no_removed_intermediate_is_graph_output": True,
                },
            }
        )
    return records


def run(args: argparse.Namespace) -> None:
    source, output, provenance = args.input.resolve(), args.output.resolve(), args.provenance.resolve()
    source_hash = sha256_file(source)
    if source_hash != EXPECTED_INPUT_SHA256:
        raise SystemExit(f"unexpected source hash: {source_hash}")
    model = onnx.load(str(source))
    onnx.checker.check_model(model)
    before_nodes = len(model.graph.node)
    before_erf = sum(node.op_type == "Erf" and not node.domain for node in model.graph.node)
    before_gelu = sum(node.op_type == "Gelu" and node.domain == "com.microsoft" for node in model.graph.node)
    records = analyze(model)
    if len(records) != 8:
        raise SystemExit(f"expected eight verified chains, found {len(records)}")

    selected_names = {name for record in records for name in record["nodes"]}
    replacements = {
        record["nodes"][0]: helper.make_node(
            "Gelu", [record["x"]], [record["output"]],
            name=f"{record['prefix']}/Gelu_explicit", domain="com.microsoft"
        )
        for record in records
    }
    rewritten = []
    for node in model.graph.node:
        if node.name in replacements:
            rewritten.append(replacements[node.name])
        elif node.name not in selected_names:
            rewritten.append(node)
    del model.graph.node[:]
    model.graph.node.extend(rewritten)
    model.doc_string = (model.doc_string + "\n" if model.doc_string else "") + "Derivative: eight verified ConvNeXt 0-7 GELU decompositions rewritten as com.microsoft.Gelu."
    onnx.checker.check_model(model)

    output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(model, str(output), save_as_external_data=False)
    reloaded = onnx.load(str(output))
    onnx.checker.check_model(reloaded)
    after_nodes = len(reloaded.graph.node)
    after_erf = sum(node.op_type == "Erf" and not node.domain for node in reloaded.graph.node)
    after_gelu = sum(node.op_type == "Gelu" and node.domain == "com.microsoft" for node in reloaded.graph.node)
    validations = {
        "onnx_checker_before": True,
        "onnx_checker_after_reload": True,
        "replacement_count": len(records),
        "node_count_before": before_nodes,
        "node_count_after": after_nodes,
        "node_count_delta": after_nodes - before_nodes,
        "standard_erf_before": before_erf,
        "standard_erf_after": after_erf,
        "explicit_microsoft_gelu_before": before_gelu,
        "explicit_microsoft_gelu_after": after_gelu,
        "all_selected_node_names_removed": not any(node.name in selected_names for node in reloaded.graph.node),
        "convnext_8_and_9_erf_preserved": all(any(node.name == f"/decoder/convnext.{i}/act/Erf" for node in reloaded.graph.node) for i in (8, 9)),
    }
    expected_validation = {
        "replacement_count": 8, "node_count_delta": -32,
        "standard_erf_after": before_erf - 8,
        "explicit_microsoft_gelu_after": before_gelu + 8,
        "all_selected_node_names_removed": True,
        "convnext_8_and_9_erf_preserved": True,
    }
    for key, expected in expected_validation.items():
        if validations[key] != expected:
            raise SystemExit(f"post-save validation failed for {key}: {validations[key]!r} != {expected!r}")

    report = {
        "schema_version": 1,
        "derivative_type": "explicit-com.microsoft-gelu-convnext-0-through-7",
        "claim_limit": "Host graph rewriting and gates do not prove physical-device HTP execution.",
        "source": {"path": str(source), "bytes": source.stat().st_size, "sha256": source_hash},
        "output": {"path": str(output), "bytes": output.stat().st_size, "sha256": sha256_file(output)},
        "model_io": {
            "latent": tensor_shape(reloaded, "latent"),
            "wav_tts": tensor_shape(reloaded, "wav_tts"),
        },
        "replacement_policy": {
            "selected_prefixes": list(EXPECTED_PREFIXES),
            "unselected_standard_gelu_prefixes": ["/decoder/convnext.8/act", "/decoder/convnext.9/act"],
            "exact_float32_constants_little_endian_hex": {key: value.tobytes().hex() for key, value in EXPECTED_CONSTANTS.items()},
        },
        "replacements": records,
        "validations": validations,
        "tool": {
            "path": str(Path(__file__).resolve()), "sha256": sha256_file(Path(__file__).resolve()),
            "python_float32_pack_check": struct.pack("<f", float(EXPECTED_CONSTANTS["sqrt_2"])).hex(),
            "onnx": onnx.__version__, "numpy": np.__version__,
        },
    }
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
