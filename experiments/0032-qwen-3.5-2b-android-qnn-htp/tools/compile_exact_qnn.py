#!/usr/bin/env python3
"""Convert and compile the exact pinned Qwen3.5-2B text route for QNN HTP."""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import torch


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def register_softplus_visitor() -> None:
    import executorch.backends.qualcomm.python.PyQnnManagerAdaptor as PyQnnManager
    from executorch.backends.qualcomm.builders.node_visitor import NodeVisitor
    from executorch.backends.qualcomm.builders.node_visitor_manager import register_node_visitor
    from executorch.backends.qualcomm.builders.qnn_constants import (
        OpElementWiseNeuron,
        QNN_OP_PACKAGE_NAME_QTI_AISW,
    )
    from executorch.backends.qualcomm.utils.constants import QCOM_DATA

    @register_node_visitor
    class Softplus(NodeVisitor):
        target = ["qwen35.softplus.default"]

        def define_node(self, node, nodes_to_wrappers):
            input_node = self.get_node(node.args[0])
            inp = self.define_tensor(
                input_node,
                node,
                self.get_tensor(input_node, node),
                PyQnnManager.Qnn_TensorType_t.QNN_TENSOR_TYPE_NATIVE,
                nodes_to_wrappers,
            )
            out = self.define_tensor(
                node,
                node,
                self.get_tensor(node, node),
                PyQnnManager.Qnn_TensorType_t.QNN_TENSOR_TYPE_NATIVE,
                nodes_to_wrappers,
            )
            op = PyQnnManager.PyQnnOpWrapper(
                node.name, QNN_OP_PACKAGE_NAME_QTI_AISW, OpElementWiseNeuron.op_name
            )
            op.AddInputTensors([inp])
            op.AddOutputTensors([out])
            op.AddScalarParam(
                OpElementWiseNeuron.param_operation,
                PyQnnManager.Qnn_DataType_t.QNN_DATATYPE_UINT_32,
                {QCOM_DATA: np.uint32(7)},
            )
            op.AddScalarParam(
                OpElementWiseNeuron.param_beta,
                PyQnnManager.Qnn_DataType_t.QNN_DATATYPE_FLOAT_32,
                {QCOM_DATA: np.float32(1.0)},
            )
            return op


def update_state(model, states: list[torch.Tensor], outputs, position: int) -> list[torch.Tensor]:
    next_a = list(outputs[1 : 1 + model.n_layers])
    next_b = list(outputs[1 + model.n_layers :])
    for index, layer_type in enumerate(model.layer_types):
        if layer_type == "linear_attention":
            states[index] = next_a[index].detach()
            states[model.n_layers + index] = next_b[index].detach()
        else:
            states[index][..., position] = next_a[index][..., 0]
            states[model.n_layers + index][:, :, position, :] = next_b[index][:, :, 0, :]
    return states


def calibrate(model, graph_module, token_ids: list[int], context: int) -> dict:
    states = [tensor.clone() for tensor in model.get_example_inputs()[3:]]
    started = time.perf_counter()
    last_logits = None
    with torch.no_grad():
        for position, token in enumerate(token_ids):
            mask = torch.full((1, 1, 1, context), -65504.0)
            if position:
                mask[..., :position] = 0.0
            mask[..., -1] = 0.0
            outputs = graph_module(
                torch.tensor([[token]], dtype=torch.int32),
                mask,
                torch.tensor([[position]], dtype=torch.int32),
                *states,
            )
            last_logits = outputs[0].detach()
            states = update_state(model, states, outputs, position)
    return {
        "tokens": len(token_ids),
        "seconds": time.perf_counter() - started,
        "last_logits_finite": bool(torch.isfinite(last_logits).all()),
        "last_argmax": int(last_logits.argmax()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--params", type=Path, required=True)
    parser.add_argument("--token-ids", type=Path, required=True)
    parser.add_argument("--context", type=int, default=4096)
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--qdq-output", type=Path)
    args = parser.parse_args()

    experiment = Path(__file__).resolve().parents[1]
    adapter = load_module("qwen35_qnn_model", experiment / "tools/qwen35_qnn_model.py")
    register_softplus_visitor()

    from executorch.backends.qualcomm._passes import FoldQDQ, TagQuantIO
    from executorch.backends.qualcomm._passes.qnn_pass_manager import (
        get_capture_program_passes,
        get_passes_dependency_for_capture_program,
    )
    from executorch.backends.qualcomm.quantizer.quant_recipe import (
        QuantGranularity,
        QuantRecipe,
    )
    from executorch.backends.qualcomm.quantizer.quantizer import QuantDtype, QnnQuantizer
    from executorch.backends.qualcomm.utils.constants import QCOM_PASS_ACTIVATE_KEY
    from executorch.backends.qualcomm.utils.utils import (
        generate_htp_compiler_spec,
        generate_qnn_executorch_compiler_spec,
        get_soc_to_chipset_map,
        to_edge_transform_and_lower_to_qnn,
    )
    from executorch.devtools.backend_debug import get_delegation_info
    from executorch.examples.models.llama.model_args import ModelArgs
    from executorch.exir import ExecutorchBackendConfig
    from executorch.exir.passes.memory_planning_pass import MemoryPlanningPass
    from executorch.extension.llm.custom_ops import model_sharding
    from torchao.quantization.pt2e import MinMaxObserver
    from torchao.quantization.pt2e.quantize_pt2e import convert_pt2e, prepare_pt2e

    params = json.loads(args.params.read_text())
    config = ModelArgs(
        max_seq_len=args.context,
        max_context_len=args.context,
        max_batch_size=1,
        use_kv_cache=True,
        **params,
    )
    model = adapter.Qwen35QnnModel(config, context_len=args.context).eval()
    state = adapter.adapt_converted_state_dict(
        torch.load(args.checkpoint, map_location="cpu", mmap=True)
    )
    missing, unexpected = model.load_state_dict(state, strict=False)
    unexpected = [
        name
        for name in unexpected
        if not name.endswith((".conv_state", ".recurrent_state"))
    ]
    if missing or unexpected:
        raise RuntimeError(f"checkpoint mismatch: missing={missing}, unexpected={unexpected}")
    model = model.float().eval()

    export_inputs = model.get_example_inputs()
    phase = {"export_start_unix_ns": time.time_ns()}
    exported = torch.export.export(model, export_inputs, strict=True).module()
    phase["export_end_unix_ns"] = time.time_ns()

    recipe = QuantRecipe(
        QuantDtype.use_16a4w,
        False,
        act_observer=MinMaxObserver,
        granularity=QuantGranularity.PER_TENSOR,
        verbose=False,
    ).add_node_target(
        {torch.ops.aten.linear.default, torch.ops.aten.conv2d.default},
        QuantDtype.use_16a4w,
        False,
        act_observer=MinMaxObserver,
        granularity=QuantGranularity.PER_CHANNEL,
    )
    quantizer = QnnQuantizer()
    quantizer.set_recipe(recipe)
    prepared = prepare_pt2e(exported, quantizer)

    raw_ids = args.token_ids.read_bytes()
    if len(raw_ids) % 4:
        raise ValueError("token ID file is not int32le")
    token_ids = np.frombuffer(raw_ids, dtype="<i4").astype(np.int64).tolist()
    if len(token_ids) + 2048 > args.context:
        raise ValueError("canonical short prompt plus output ceiling exceeds compile context")
    calibration = calibrate(model, prepared, token_ids, args.context)
    phase["calibration_end_unix_ns"] = time.time_ns()
    qdq = convert_pt2e(prepared)
    phase["convert_end_unix_ns"] = time.time_ns()

    if args.qdq_output:
        args.qdq_output.parent.mkdir(parents=True, exist_ok=True)
        torch.export.save(torch.export.export(qdq, export_inputs, strict=True), args.qdq_output)

    passes_job = get_capture_program_passes()
    dep_table = get_passes_dependency_for_capture_program()
    if args.shards > 1:
        SplitGraph, setting = model_sharding.get_split_graph_pass(
            model.n_layers, shares=args.shards
        )
        passes_job[SplitGraph] = setting
        dep_table[SplitGraph] = [FoldQDQ]
        dep_table[TagQuantIO] = [SplitGraph]
    passes_job[TagQuantIO][QCOM_PASS_ACTIVATE_KEY] = False

    compile_spec = generate_qnn_executorch_compiler_spec(
        soc_model=get_soc_to_chipset_map()["SM8550"],
        backend_options=generate_htp_compiler_spec(
            use_fp16=False, use_multi_contexts=args.shards > 1
        ),
        debug=True,
        saver=False,
    )
    phase["qnn_compile_start_unix_ns"] = time.time_ns()
    edge = to_edge_transform_and_lower_to_qnn(
        qdq,
        export_inputs,
        compile_spec,
        constant_methods=model.get_metadata(),
        dep_table=dep_table,
        passes_job=passes_job,
        skip_node_id_set=set(),
        skip_node_op_set={"llama.fallback.default"},
        convert_linear_to_conv2d=True,
    )
    phase["qnn_compile_end_unix_ns"] = time.time_ns()

    delegation = get_delegation_info(edge.exported_program().graph_module)
    breakdown = {
        name: {"delegated": item.delegated, "non_delegated": item.non_delegated}
        for name, item in delegation.delegation_by_operator.items()
    }
    allowed_plumbing = {"getitem", "llama_fallback_default"}
    non_delegate_compute = {
        name: counts["non_delegated"]
        for name, counts in breakdown.items()
        if counts["non_delegated"] and name not in allowed_plumbing
    }
    result = {
        "schema_version": 1,
        "experiment": "0032-qwen-3.5-2b-android-qnn-htp",
        "status": "compiled" if not non_delegate_compute else "rejected_fallback",
        "model": "Qwen/Qwen3.5-2B",
        "context_tokens": args.context,
        "quantization": "W4A16 PTQ with per-channel Linear/Conv weights and 16-bit activations, including Gated DeltaNet recurrence",
        "shards": args.shards,
        "calibration": calibration,
        "delegated_subgraphs": delegation.num_delegated_subgraphs,
        "delegated_nodes": delegation.num_delegated_nodes,
        "non_delegated_nodes": delegation.num_non_delegated_nodes,
        "delegation_by_operator": breakdown,
        "non_delegated_tensor_compute": non_delegate_compute,
        "phase_timestamps": phase,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if non_delegate_compute:
        raise RuntimeError(f"QNN tensor-compute fallback remains: {non_delegate_compute}")

    program = edge.to_executorch(
        config=ExecutorchBackendConfig(
            memory_planning_pass=MemoryPlanningPass(alloc_graph_input=False)
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as destination:
        program.write_to_file(destination)
    print(args.output)


if __name__ == "__main__":
    main()
