#!/usr/bin/env python3
"""Annotate the canonical-v2 ORT-optimized graph with observed tensor shapes.

Only graph/value metadata is changed. Nodes, attributes, initializers, and tensor
payloads remain byte-for-byte equal at protobuf-field level to the supplied
optimized model. Profile shapes are accepted only when every repeated event for
a named top-level node agrees.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import onnx
from onnx import TensorProto, helper

DTYPES = {
    "bool": TensorProto.BOOL,
    "float": TensorProto.FLOAT,
    "float16": TensorProto.FLOAT16,
    "double": TensorProto.DOUBLE,
    "int8": TensorProto.INT8,
    "int16": TensorProto.INT16,
    "int32": TensorProto.INT32,
    "int64": TensorProto.INT64,
    "uint8": TensorProto.UINT8,
    "uint16": TensorProto.UINT16,
    "uint32": TensorProto.UINT32,
    "uint64": TensorProto.UINT64,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def event_name(name: str) -> str:
    suffix = "_kernel_time"
    return name[: -len(suffix)] if name.endswith(suffix) else name


def tensor_spec(item: object) -> tuple[int, tuple[int, ...]] | None:
    if not isinstance(item, dict) or len(item) != 1:
        return None
    dtype_name, shape = next(iter(item.items()))
    if dtype_name not in DTYPES or not isinstance(shape, list):
        return None
    if not all(isinstance(value, int) and value >= 0 for value in shape):
        return None
    return DTYPES[dtype_name], tuple(shape)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()

    model = onnx.load(str(args.model), load_external_data=False)
    profile = json.loads(args.profile.read_text())
    top_nodes = {node.name: node for node in model.graph.node}
    if "" in top_nodes or len(top_nodes) != len(model.graph.node):
        raise RuntimeError("optimized top-level node names are empty or non-unique")

    observed: dict[str, list[tuple[tuple[int, tuple[int, ...]] | None, ...]]] = defaultdict(list)
    provider_counts: Counter[str] = Counter()
    for event in profile:
        if event.get("cat") != "Node":
            continue
        values = event.get("args", {})
        provider = values.get("provider")
        if provider:
            provider_counts[provider] += 1
        name = event_name(str(event.get("name", "")))
        if name not in top_nodes:
            continue
        shapes = values.get("output_type_shape")
        if not isinstance(shapes, list):
            continue
        observed[name].append(tuple(tensor_spec(item) for item in shapes))

    existing = {value.name for value in model.graph.value_info}
    existing.update(value.name for value in model.graph.input)
    existing.update(value.name for value in model.graph.output)
    annotated = 0
    skipped_non_tensor = 0
    missing = []
    mismatched = []
    for node in model.graph.node:
        candidates = observed.get(node.name, [])
        if not candidates:
            missing.append(node.name)
            continue
        unique = set(candidates)
        if len(unique) != 1:
            mismatched.append({"node": node.name, "observations": len(unique)})
            continue
        specs = next(iter(unique))
        if len(specs) == 0 and len(node.output) > 0:
            # ORT omits output_type_shape entries for sequence-valued outputs.
            skipped_non_tensor += len(node.output)
            continue
        if len(specs) != len(node.output):
            mismatched.append({"node": node.name, "graph_outputs": len(node.output), "profile_outputs": len(specs)})
            continue
        for name, spec in zip(node.output, specs):
            if not name or name in existing:
                continue
            if spec is None:
                skipped_non_tensor += 1
                continue
            dtype, shape = spec
            model.graph.value_info.append(helper.make_tensor_value_info(name, dtype, list(shape)))
            existing.add(name)
            annotated += 1

    if mismatched:
        raise RuntimeError(f"profile/output mismatch: {mismatched[:10]}")
    outputs = {value.name: value for value in model.graph.output}
    expected_outputs = {"audio": (TensorProto.FLOAT, [361200]), "pred_dur": (TensorProto.INT64, [235])}
    if set(outputs) != set(expected_outputs):
        raise RuntimeError(f"unexpected graph outputs: {sorted(outputs)}")
    for name, (dtype, shape) in expected_outputs.items():
        value = outputs[name]
        if value.type.tensor_type.elem_type != dtype:
            raise RuntimeError(f"output dtype drift: {name}")
        del value.type.tensor_type.shape.dim[:]
        for size in shape:
            value.type.tensor_type.shape.dim.add().dim_value = size

    args.output.parent.mkdir(parents=True, exist_ok=True)
    onnx.checker.check_model(model, full_check=True)
    onnx.save(model, str(args.output))
    record = {
        "schema_version": 1,
        "transformation": "metadata-only concrete tensor-shape annotation from one fixed-input CPU profile",
        "source": {"path": str(args.model), "bytes": args.model.stat().st_size, "sha256": sha256(args.model)},
        "profile": {"path": str(args.profile), "bytes": args.profile.stat().st_size, "sha256": sha256(args.profile), "provider_counts": dict(provider_counts)},
        "output": {"path": str(args.output), "bytes": args.output.stat().st_size, "sha256": sha256(args.output)},
        "top_level_nodes": len(model.graph.node),
        "initializers": len(model.graph.initializer),
        "profiled_top_level_nodes": len(observed),
        "annotated_tensor_values": annotated,
        "skipped_non_tensor_values": skipped_non_tensor,
        "missing_top_level_nodes": missing,
        "node_initializer_attribute_changes": 0,
        "fixed_graph_outputs": {"audio": [361200], "pred_dur": [235]},
    }
    args.provenance.parent.mkdir(parents=True, exist_ok=True)
    args.provenance.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
