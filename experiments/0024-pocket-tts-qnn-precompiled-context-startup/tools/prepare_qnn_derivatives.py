#!/usr/bin/env python3
"""Create the eight canonical fixed-Alba QNN-compatible graph derivatives."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import helper, numpy_helper

EXPECTED = {
    "text_conditioner.onnx": "c4212aa0deb4d16b4b9340484489c03b4566929a0d23e3ccd115bbcbd6263f18",
    "flow_prefill_text64.onnx": "3f070985ae719479a4ad8623938991010921b3bfdf654fb4060ae8d252bb08f3",
    "flow_ar_bos1.onnx": "f60eacce2f90703495eb3d05314aff77b4a9baefc614b5a5727ca3bee9d4c8b0",
    "flow_ar_latent1.onnx": "784f960a480c302f124df0ca8e40ea9e324e77cc86dbb29b4ee1e88567fdbad9",
    "flow.onnx": "fa74e3777dc661135807d964d47f177bc93159392a0a484718ba0343130f7a60",
    "mimi_decoder12.onnx": "6c3e398ef7a12a6798a67de4abeb606390b1710f45007640d789171ae814da56",
    "mimi_decoder6.onnx": "9cb6d327f67344b0f1ac7ed7109b34502822bbd25271f16612021c42520ecd90",
    "mimi_decoder1.onnx": "c9361ac87eedf60ada38638039c55a093d9cbb7ae7959703ff1837636f98a46c",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setshape(value: onnx.ValueInfoProto, shape: list[int]) -> None:
    dims = value.type.tensor_type.shape.dim
    if len(dims) != len(shape):
        raise ValueError((value.name, len(dims), shape))
    for dim, size in zip(dims, shape):
        dim.ClearField("dim_param")
        dim.dim_value = size


def constants(model: onnx.ModelProto) -> dict[str, np.ndarray]:
    result = {item.name: numpy_helper.to_array(item) for item in model.graph.initializer}
    for node in model.graph.node:
        if node.op_type == "Constant" and len(node.output) == 1:
            attrs = [item for item in node.attribute if item.name == "value"]
            if len(attrs) == 1:
                result[node.output[0]] = numpy_helper.to_array(attrs[0].t)
    return result


def consumers(model: onnx.ModelProto) -> dict[str, list[onnx.NodeProto]]:
    result: dict[str, list[onnx.NodeProto]] = {}
    for node in model.graph.node:
        for name in node.input:
            result.setdefault(name, []).append(node)
    return result


def replace_inputs(model: onnx.ModelProto, mapping: dict[str, str]) -> None:
    for node in model.graph.node:
        for index, name in enumerate(node.input):
            while name in mapping:
                name = mapping[name]
            node.input[index] = name
    for output in model.graph.output:
        name = output.name
        while name in mapping:
            name = mapping[name]
        output.name = name


def rewrite_decoder(model: onnx.ModelProto) -> dict[str, int]:
    con = consumers(model)
    mapping: dict[str, str] = {}
    remove: set[str] = set()
    for node in [item for item in model.graph.node if item.op_type == "IsNaN"]:
        users = con.get(node.output[0], [])
        if len(users) != 1 or users[0].op_type != "Where" or users[0].input[2] != node.input[0]:
            raise ValueError(f"unexpected NaN cleanup around {node.name}")
        where = users[0]
        mapping[where.output[0]] = node.input[0]
        remove.update((node.name, where.name))
    replace_inputs(model, mapping)

    outputs = {item.name: item for item in model.graph.output}
    identities = 0
    for node in [item for item in model.graph.node if item.op_type == "Identity"]:
        if len(node.input) == 1 and len(node.output) == 1 and node.output[0] in outputs:
            outputs[node.output[0]].name = node.input[0]
            remove.add(node.name)
            identities += 1
    if len({item.name for item in model.graph.output}) != len(model.graph.output):
        raise ValueError("duplicate decoder outputs after direct state aliases")
    kept = [node for node in model.graph.node if node.name not in remove]
    del model.graph.node[:]
    model.graph.node.extend(kept)
    return {"nan_cleanup_nodes_removed": len(remove) - identities,
            "output_identities_removed": identities}


def specialize_text(source: Path, output: Path) -> dict[str, object]:
    model = onnx.load(str(source))
    inputs = {item.name: item for item in model.graph.input}
    outputs = {item.name: item for item in model.graph.output}
    setshape(inputs["token_ids"], [1, 64])
    setshape(outputs["embeddings"], [1, 64, 1024])
    model = onnx.shape_inference.infer_shapes(model, strict_mode=True)
    onnx.checker.check_model(model, full_check=True)
    onnx.save(model, str(output))
    return {"transformation": "I/O shape specialization only", "tokens": 64}


def specialize_flow(source: Path, output: Path) -> dict[str, object]:
    model = onnx.load(str(source))
    shapes = {"c": [1, 1024], "s": [1, 1], "t": [1, 1], "x": [1, 32]}
    for value in model.graph.input:
        if value.name not in shapes:
            raise ValueError(f"unexpected flow input {value.name}")
        setshape(value, shapes[value.name])
    if len(model.graph.output) != 1:
        raise ValueError("unexpected flow output count")
    setshape(model.graph.output[0], [1, 32])
    model = onnx.shape_inference.infer_shapes(model, strict_mode=True)
    onnx.checker.check_model(model, full_check=True)
    onnx.save(model, str(output))
    return {"transformation": "I/O shape specialization only", "shapes": shapes}


def specialize_decoder(source: Path, output: Path, frames: int) -> dict[str, object]:
    model = onnx.load(str(source))
    inputs = {item.name: item for item in model.graph.input}
    if "latent" not in inputs or len(model.graph.output) != 57:
        raise ValueError("unexpected decoder ABI")
    setshape(inputs["latent"], [1, frames, 32])
    setshape(model.graph.output[0], [1, 1, frames * 1920])
    model = onnx.shape_inference.infer_shapes(model, strict_mode=True)
    rewrite = rewrite_decoder(model)
    model.doc_string = ((model.doc_string + "\n") if model.doc_string else "") + (
        "Derivative: fixed frame extent, finite-fixture NaN-cleanup bypass, and direct unchanged state outputs.")
    onnx.checker.check_model(model, full_check=True)
    onnx.save(model, str(output))
    return {"transformation": "QNN compatibility derivative", "frames": frames, **rewrite}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controlled", type=Path, required=True)
    parser.add_argument("--static-flow", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-documented-derivatives", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, object]] = {}

    destinations = {
        "text_conditioner.onnx": specialize_text(args.controlled / "text_conditioner.onnx",
                                                  args.output / "text_conditioner.onnx"),
        "flow.onnx": specialize_flow(args.controlled / "flow_lm_flow.onnx", args.output / "flow.onnx"),
    }
    for frames in (12, 6, 1):
        name = f"mimi_decoder{frames}.onnx"
        destinations[name] = specialize_decoder(args.controlled / "mimi_decoder.onnx",
                                                args.output / name, frames)
    for source_name, target_name in (("flow_lm_prefill_text64.onnx", "flow_prefill_text64.onnx"),
                                     ("flow_lm_ar_bos1.onnx", "flow_ar_bos1.onnx"),
                                     ("flow_lm_ar_latent1.onnx", "flow_ar_latent1.onnx")):
        source = args.static_flow / source_name
        target = args.output / target_name
        target.write_bytes(source.read_bytes())
        destinations[target_name] = {"transformation": "fixed cache512 canonical export"}

    for name, transformation in destinations.items():
        path = args.output / name
        onnx.checker.check_model(onnx.load(str(path)), full_check=True)
        actual = sha(path)
        records[name] = {"path": str(path), "bytes": path.stat().st_size, "sha256": actual,
                         "expected_0014_sha256": EXPECTED[name], "exact_0014_hash_match": actual == EXPECTED[name],
                         **transformation}
    exact = all(record["exact_0014_hash_match"] for record in records.values())
    report = {
        "schema_version": 1,
        "route": "pocket-fixed-alba-text64-cache512-canonical-v2-0024-reconstruction-derivative",
        "source_arm_and_context_arm_use_same_files": True,
        "exact_0014_hashes_reproduced": exact,
        "documented_derivatives_allowed": bool(args.allow_documented_derivatives),
        "graphs": records,
    }
    (args.output / "inventory.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not exact and not args.allow_documented_derivatives:
        raise SystemExit("graph hash drift from 0014; inspect and prove derivative equivalence before continuing")


if __name__ == "__main__":
    main()
