#!/usr/bin/env python3
"""Lower a bounded Qwen3.5 structural model to QNN and report delegation."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import torch


def load_adapter(path: Path):
    spec = importlib.util.spec_from_file_location("qwen35_qnn_model", path)
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
            input_tensor = self.get_tensor(input_node, node)
            input_wrapper = self.define_tensor(
                input_node,
                node,
                input_tensor,
                PyQnnManager.Qnn_TensorType_t.QNN_TENSOR_TYPE_NATIVE,
                nodes_to_wrappers,
            )
            output_tensor = self.get_tensor(node, node)
            output_wrapper = self.define_tensor(
                node,
                node,
                output_tensor,
                PyQnnManager.Qnn_TensorType_t.QNN_TENSOR_TYPE_NATIVE,
                nodes_to_wrappers,
            )
            op = PyQnnManager.PyQnnOpWrapper(
                node.name, QNN_OP_PACKAGE_NAME_QTI_AISW, OpElementWiseNeuron.op_name
            )
            op.AddInputTensors([input_wrapper])
            op.AddOutputTensors([output_wrapper])
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--context", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()

    experiment = Path(__file__).resolve().parents[1]
    adapter = load_adapter(experiment / "tools/qwen35_qnn_model.py")
    register_softplus_visitor()

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

    params = json.loads(args.params.read_text())
    config = ModelArgs(
        max_seq_len=args.context,
        max_context_len=args.context,
        max_batch_size=1,
        use_kv_cache=True,
        **params,
    )
    model = adapter.Qwen35QnnModel(config, context_len=args.context).eval()
    if args.checkpoint:
        state = torch.load(args.checkpoint, map_location="cpu", mmap=True)
        state = adapter.adapt_converted_state_dict(state)
        missing, unexpected = model.load_state_dict(state, strict=False)
        unexpected = [
            name
            for name in unexpected
            if not name.endswith((".conv_state", ".recurrent_state"))
        ]
        if missing or unexpected:
            raise RuntimeError(f"checkpoint mismatch: missing={missing}, unexpected={unexpected}")

    inputs = model.get_example_inputs()
    compile_spec = generate_qnn_executorch_compiler_spec(
        soc_model=get_soc_to_chipset_map()["SM8550"],
        backend_options=generate_htp_compiler_spec(use_fp16=True),
        debug=True,
        saver=False,
    )
    with torch.no_grad():
        edge = to_edge_transform_and_lower_to_qnn(
            model,
            inputs,
            compile_spec,
            constant_methods=model.get_metadata(),
            skip_node_id_set=set(),
            skip_node_op_set=set(),
            convert_linear_to_conv2d=True,
        )

    graph_module = edge.exported_program().graph_module
    delegation = get_delegation_info(graph_module)
    breakdown = {
        name: {"delegated": item.delegated, "non_delegated": item.non_delegated}
        for name, item in delegation.delegation_by_operator.items()
    }
    non_delegate_compute = {
        name: counts["non_delegated"]
        for name, counts in breakdown.items()
        if counts["non_delegated"] and name != "getitem"
    }
    result = {
        "schema_version": 1,
        "experiment": "0032-qwen-3.5-2b-android-qnn-htp",
        "scope": "bounded structural Qwen3.5 QNN lowering probe; not model inference",
        "context_tokens": args.context,
        "layer_types": params["layer_types"],
        "delegated_subgraphs": delegation.num_delegated_subgraphs,
        "delegated_nodes": delegation.num_delegated_nodes,
        "non_delegated_nodes": delegation.num_non_delegated_nodes,
        "delegation_by_operator": breakdown,
        "non_delegated_tensor_compute": non_delegate_compute,
        "all_tensor_compute_delegated": not non_delegate_compute,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if non_delegate_compute:
        raise RuntimeError(f"QNN fallback remains: {non_delegate_compute}")

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
