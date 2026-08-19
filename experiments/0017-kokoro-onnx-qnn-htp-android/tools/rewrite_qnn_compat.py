#!/usr/bin/env python3
"""Apply the bounded fixed-contract QNN compatibility rewrite for Kokoro.

The rewrite targets only the residual unsupported nodes identified after the
metadata-only shape pass:

* bypass finite-input attention NaN sanitizers;
* lower duration-driven repeat_interleave + scatter into a fixed-width,
  value-driven alignment matrix (the duration tensor remains computed);
* replace shape-derived zero/index tensors with equivalent constants;
* lower two shape-conditional squeezes to fixed Reshape operations.

No checkpoint/learned tensor is changed and no quantization is introduced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, deque
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

EXPECTED_SOURCE_SHA256 = "8f13f170a5b67459e0fb325682cd1ab1f2fa4ff0d62e988222dd38a4d95fe00f"
TOKENS = 125
FRAMES = 304


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tensor_bytes(value: onnx.TensorProto) -> bytes:
    return numpy_helper.to_array(value).tobytes()


def replace_all_inputs(nodes: list[onnx.NodeProto], old: str, new: str) -> int:
    changed = 0
    for node in nodes:
        for index, value in enumerate(node.input):
            if value == old:
                node.input[index] = new
                changed += 1
    return changed


def add_initializer(model: onnx.ModelProto, name: str, value: np.ndarray) -> None:
    if any(item.name == name for item in model.graph.initializer):
        raise RuntimeError(f"initializer already exists: {name}")
    model.graph.initializer.append(numpy_helper.from_array(np.ascontiguousarray(value), name=name))


def topological_sort(nodes: list[onnx.NodeProto], available: set[str]) -> list[onnx.NodeProto]:
    producer = {output: index for index, node in enumerate(nodes) for output in node.output if output}
    indegree = [0] * len(nodes)
    consumers: dict[int, list[int]] = {}
    for index, node in enumerate(nodes):
        dependencies = {producer[name] for name in node.input if name in producer and producer[name] != index}
        indegree[index] = len(dependencies)
        for dependency in dependencies:
            consumers.setdefault(dependency, []).append(index)
        for name in node.input:
            if name and name not in producer and name not in available:
                # Inputs captured by a retained subgraph are allowed; top-level
                # rewritten graphs are expected not to have any.
                raise RuntimeError(f"unresolved top-level input {name!r} for {node.name}")
    queue = deque(index for index, value in enumerate(indegree) if value == 0)
    result = []
    while queue:
        index = queue.popleft()
        result.append(nodes[index])
        for consumer in consumers.get(index, []):
            indegree[consumer] -= 1
            if indegree[consumer] == 0:
                queue.append(consumer)
    if len(result) != len(nodes):
        raise RuntimeError("rewritten graph is cyclic")
    return result


def live_top_level_nodes(model: onnx.ModelProto, nodes: list[onnx.NodeProto]) -> list[onnx.NodeProto]:
    producer = {output: node for node in nodes for output in node.output if output}
    needed_values = [value.name for value in model.graph.output]
    live_ids: set[int] = set()
    while needed_values:
        value = needed_values.pop()
        node = producer.get(value)
        if node is None or id(node) in live_ids:
            continue
        live_ids.add(id(node))
        needed_values.extend(name for name in node.input if name)
    return [node for node in nodes if id(node) in live_ids]


def op_counts(nodes: list[onnx.NodeProto]) -> dict[str, int]:
    counts = Counter((node.domain or "ai.onnx") + "::" + node.op_type for node in nodes)
    return dict(sorted(counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    actual_source_sha = sha256(args.source)
    if actual_source_sha != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(f"source hash mismatch: {actual_source_sha}")

    model = onnx.load(str(args.source), load_external_data=False)
    original_nodes = list(model.graph.node)
    original_initializers = {item.name: item for item in model.graph.initializer}
    nodes = list(model.graph.node)
    by_name = {node.name: node for node in nodes}
    if len(by_name) != len(nodes):
        raise RuntimeError("source nodes must have unique non-empty names")

    # 1. The fixed finite input has finite attention Softmax tensors. Bypass
    # torch.nan_to_num's IsNaN/Where pair, retaining the exact Softmax value.
    nan_rewrites = []
    remove_names: set[str] = set()
    for index in range(12):
        suffix = "" if index == 0 else f"_{index}"
        prefix = f"/bert/encoder/albert_layer_groups.0/albert_layers.0/attention{suffix}"
        isnan = by_name[f"{prefix}/IsNaN"]
        where = by_name[f"{prefix}/Where_1"]
        if isnan.op_type != "IsNaN" or where.op_type != "Where":
            raise RuntimeError(f"attention sanitizer structure drift: {prefix}")
        softmax = isnan.input[0]
        if list(where.input)[0] != isnan.output[0] or list(where.input)[2] != softmax:
            raise RuntimeError(f"attention sanitizer inputs drift: {prefix}")
        true_value = original_initializers.get(where.input[1])
        if true_value is None or np.any(numpy_helper.to_array(true_value) != 0):
            raise RuntimeError(f"attention sanitizer true branch is not constant zero: {prefix}")
        rewired = replace_all_inputs(nodes, where.output[0], softmax)
        if rewired != 1:
            raise RuntimeError(f"unexpected sanitizer consumer count {rewired}: {prefix}")
        remove_names.update((isnan.name, where.name))
        nan_rewrites.append({"isnan": isnan.name, "where": where.name, "replacement": softmax})

    # 2. Lower repeat_interleave + scatter to the same fixed [1,125,304]
    # one-hot alignment, driven by the runtime-computed pred_dur values.
    legacy_alignment_output = "/Unsqueeze_5_output_0"
    legacy_alignment = by_name["/Unsqueeze_5"]
    if legacy_alignment.output[0] != legacy_alignment_output:
        raise RuntimeError("legacy alignment output drift")
    remove_names.add(legacy_alignment.name)
    align_prefix = "/qnn_static_alignment"
    lower_name = align_prefix + "/lower_triangle"
    duration_shape_name = align_prefix + "/duration_shape"
    positions_name = align_prefix + "/positions"
    axis_name = align_prefix + "/axis0"
    add_initializer(model, lower_name, np.tril(np.ones((TOKENS, TOKENS), dtype=np.float32)))
    add_initializer(model, duration_shape_name, np.asarray([TOKENS, 1], dtype=np.int64))
    add_initializer(model, positions_name, np.arange(FRAMES, dtype=np.float32).reshape(1, FRAMES))
    add_initializer(model, axis_name, np.asarray([0], dtype=np.int64))
    alignment_nodes = [
        helper.make_node("Cast", ["pred_dur"], [align_prefix + "/dur_f32"], name=align_prefix + "/Cast", to=TensorProto.FLOAT),
        helper.make_node("Reshape", [align_prefix + "/dur_f32", duration_shape_name], [align_prefix + "/dur_col"], name=align_prefix + "/Reshape"),
        helper.make_node("MatMul", [lower_name, align_prefix + "/dur_col"], [align_prefix + "/end"], name=align_prefix + "/MatMul"),
        helper.make_node("Sub", [align_prefix + "/end", align_prefix + "/dur_col"], [align_prefix + "/start"], name=align_prefix + "/Sub"),
        helper.make_node("GreaterOrEqual", [positions_name, align_prefix + "/start"], [align_prefix + "/after_start"], name=align_prefix + "/GreaterOrEqual"),
        helper.make_node("Less", [positions_name, align_prefix + "/end"], [align_prefix + "/before_end"], name=align_prefix + "/Less"),
        helper.make_node("And", [align_prefix + "/after_start", align_prefix + "/before_end"], [align_prefix + "/mask"], name=align_prefix + "/And"),
        helper.make_node("Cast", [align_prefix + "/mask"], [align_prefix + "/alignment"], name=align_prefix + "/CastMask", to=TensorProto.FLOAT),
        helper.make_node("Unsqueeze", [align_prefix + "/alignment", axis_name], [legacy_alignment_output], name=align_prefix + "/Unsqueeze"),
    ]
    nodes.extend(alignment_nodes)

    # 3. Shape-derived tensors. These are zero initial states/envelopes or index
    # grids, not learned/neural intermediates.
    direct_constants = {
        "/shared/ConstantOfShape_output_0": np.zeros((2, 1, 256), dtype=np.float32),
        "/decoder/generator/m_source/l_sin_gen/Expand_1_output_0": np.zeros((1, 1, 9), dtype=np.int64),
        "/decoder/generator/m_source/l_sin_gen/Expand_2_output_0": np.zeros((1, 1, 9), dtype=np.int64),
        "/decoder/generator/m_source/l_sin_gen/Expand_3_output_0": np.arange(9, dtype=np.int64).reshape(1, 1, 9),
        "/decoder/generator/m_source/l_sin_gen/Concat_1_output_0": np.asarray([1, 1, 9], dtype=np.int64),
        "/decoder/generator/ConstantOfShape_1_output_0": np.ones((1, 1, 36_481), dtype=np.float32),
    }
    producer = {output: node for node in nodes for output in node.output if output}
    for name, value in direct_constants.items():
        old = producer.get(name)
        if old is None:
            raise RuntimeError(f"constant replacement output missing: {name}")
        remove_names.add(old.name)
        add_initializer(model, name, value)

    # This Expand is shape-preserving ([1,9] -> [1,9]), so it is an identity.
    sin_expand = by_name["/decoder/generator/m_source/l_sin_gen/Expand"]
    sin_add = sin_expand.input[0]
    rewired = replace_all_inputs(nodes, sin_expand.output[0], sin_add)
    if rewired != 1:
        raise RuntimeError(f"unexpected sine Expand consumer count: {rewired}")
    remove_names.add(sin_expand.name)

    # 4. The two source squeezes export as shape-dependent If nodes. Both fixed
    # tensors are [1,1,608], so the selected result is a [1,608] reshape.
    reshape_shape = "/qnn_static_squeeze/shape"
    add_initializer(model, reshape_shape, np.asarray([1, 608], dtype=np.int64))
    squeeze_specs = [
        ("/If", "/F0_proj/Conv_output_0", "/If_output_0", "/qnn_static_squeeze/F0"),
        ("/If_1", "/N_proj/Conv_output_0", "/If_1_output_0", "/qnn_static_squeeze/N"),
    ]
    for old_name, data, output, new_name in squeeze_specs:
        old = by_name[old_name]
        if old.op_type != "If" or old.output[0] != output:
            raise RuntimeError(f"fixed squeeze structure drift: {old_name}")
        remove_names.add(old_name)
        nodes.append(helper.make_node("Reshape", [data, reshape_shape], [output], name=new_name))

    nodes = [node for node in nodes if node.name not in remove_names]
    nodes = live_top_level_nodes(model, nodes)

    used_values = {name for node in nodes for name in node.input if name}
    used_values.update(value.name for value in model.graph.output)
    initializers_before_prune = {item.name: item for item in model.graph.initializer}
    retained_initializers = [item for item in model.graph.initializer if item.name in used_values]
    removed_initializers = [item for item in model.graph.initializer if item.name not in used_values]
    # A compatibility rewrite may prune only small exporter constants. Any
    # sizable removed tensor could be a learned parameter and fails closed.
    unexpectedly_large = [
        {"name": item.name, "bytes": len(tensor_bytes(item))}
        for item in removed_initializers
        if len(tensor_bytes(item)) > 4096
    ]
    if unexpectedly_large:
        raise RuntimeError(f"rewrite would prune sizable tensors: {unexpectedly_large}")

    available = {value.name for value in model.graph.input}
    available.update(item.name for item in retained_initializers)
    nodes = topological_sort(nodes, available)
    del model.graph.node[:]
    model.graph.node.extend(nodes)
    del model.graph.initializer[:]
    model.graph.initializer.extend(retained_initializers)

    live_values = available | {value.name for value in model.graph.output}
    live_values.update(output for node in nodes for output in node.output)
    value_info = [value for value in model.graph.value_info if value.name in live_values]
    del model.graph.value_info[:]
    model.graph.value_info.extend(value_info)
    # Add metadata for new intermediate values where absent.
    known = {value.name for value in [*model.graph.input, *model.graph.output, *model.graph.value_info]}
    new_specs = {
        align_prefix + "/dur_f32": (TensorProto.FLOAT, [TOKENS]),
        align_prefix + "/dur_col": (TensorProto.FLOAT, [TOKENS, 1]),
        align_prefix + "/end": (TensorProto.FLOAT, [TOKENS, 1]),
        align_prefix + "/start": (TensorProto.FLOAT, [TOKENS, 1]),
        align_prefix + "/after_start": (TensorProto.BOOL, [TOKENS, FRAMES]),
        align_prefix + "/before_end": (TensorProto.BOOL, [TOKENS, FRAMES]),
        align_prefix + "/mask": (TensorProto.BOOL, [TOKENS, FRAMES]),
        align_prefix + "/alignment": (TensorProto.FLOAT, [TOKENS, FRAMES]),
        legacy_alignment_output: (TensorProto.FLOAT, [1, TOKENS, FRAMES]),
        "/If_output_0": (TensorProto.FLOAT, [1, 608]),
        "/If_1_output_0": (TensorProto.FLOAT, [1, 608]),
    }
    for name, (dtype, shape) in new_specs.items():
        if name not in known:
            model.graph.value_info.append(helper.make_tensor_value_info(name, dtype, shape))
            known.add(name)

    # Preserve all retained initializer payloads exactly.
    changed_retained = []
    for item in model.graph.initializer:
        old = initializers_before_prune.get(item.name)
        if old is not None and item.SerializeToString() != old.SerializeToString():
            changed_retained.append(item.name)
    if changed_retained:
        raise RuntimeError(f"retained initializer mutation: {changed_retained}")

    onnx.checker.check_model(model, full_check=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(args.output))
    if any(node.op_type in {"QuantizeLinear", "DequantizeLinear", "DynamicQuantizeLinear", "MatMulInteger"} for node in model.graph.node):
        raise RuntimeError("quantized operator appeared")

    removed_node_names = sorted(set(node.name for node in original_nodes) - set(node.name for node in nodes))
    added_node_names = sorted(set(node.name for node in nodes) - set(node.name for node in original_nodes))
    record = {
        "schema_version": 1,
        "source": {"path": str(args.source), "bytes": args.source.stat().st_size, "sha256": actual_source_sha},
        "output": {"path": str(args.output), "bytes": args.output.stat().st_size, "sha256": sha256(args.output)},
        "fixed_contract": {"tokens": TOKENS, "duration_sum_and_alignment_width": FRAMES},
        "changes": {
            "attention_nan_sanitizers_bypassed": nan_rewrites,
            "alignment_lowering": "runtime pred_dur -> float32 lower-triangular prefix sums -> static [125,304] comparison mask",
            "shape_derived_constants": {name: {"dtype": str(value.dtype), "shape": list(value.shape), "sha256": hashlib.sha256(value.tobytes()).hexdigest()} for name, value in direct_constants.items()},
            "shape_conditional_squeezes_lowered": [item[0] for item in squeeze_specs],
            "removed_nodes": removed_node_names,
            "added_nodes": added_node_names,
            "removed_initializers": [{"name": item.name, "bytes": len(tensor_bytes(item)), "sha256": hashlib.sha256(tensor_bytes(item)).hexdigest()} for item in removed_initializers],
            "added_initializers": sorted(set(item.name for item in model.graph.initializer) - set(original_initializers)),
            "retained_initializer_payload_changes": changed_retained,
        },
        "structure": {
            "source_nodes": len(original_nodes),
            "output_nodes": len(nodes),
            "source_initializers": len(original_initializers),
            "output_initializers": len(model.graph.initializer),
            "source_operators": op_counts(original_nodes),
            "output_operators": op_counts(nodes),
            "quantized_operator_count": 0,
        },
        "claim_boundary": "Fixed-contract standard-operator compatibility lowering; no learned tensor change, quantization, or neural intermediate fixture.",
    }
    args.provenance.parent.mkdir(parents=True, exist_ok=True)
    args.provenance.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": record["output"], "structure": record["structure"], "removed_nodes": len(removed_node_names), "removed_initializers": len(removed_initializers)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
