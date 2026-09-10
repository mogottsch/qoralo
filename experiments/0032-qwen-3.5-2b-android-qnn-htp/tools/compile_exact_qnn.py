#!/usr/bin/env python3
"""Convert and compile the exact pinned Qwen3.5-2B text route for QNN HTP."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
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
    parser.add_argument("--diagnostic-hidden-states", action="store_true")
    parser.add_argument("--diagnostic-layer0-components", action="store_true")
    parser.add_argument("--diagnostic-layer0-attention-components", action="store_true")
    parser.add_argument("--matmul-recurrence-reductions", action="store_true")
    parser.add_argument("--float-recurrence", action="store_true")
    parser.add_argument("--fp16-recurrence-island", action="store_true")
    parser.add_argument("--symmetric-activations", action="store_true")
    parser.add_argument("--histogram-activations", action="store_true")
    args = parser.parse_args()

    experiment = Path(__file__).resolve().parents[1]
    adapter = load_module("qwen35_qnn_model", experiment / "tools/qwen35_qnn_model.py")
    if args.fp16_recurrence_island:
        def fp16_recurrence_forward(
            self, query, key, value, a, b, recurrent_state
        ):
            query16 = query.half()
            key16 = key.half()
            query16 = query16 * torch.rsqrt(
                (query16 * query16).sum(-1, keepdim=True) + 1e-6
            )
            key16 = key16 * torch.rsqrt(
                (key16 * key16).sum(-1, keepdim=True) + 1e-6
            )
            query16 = query16[:, 0] * (1.0 / math.sqrt(self.key_head_dim))
            key16 = key16[:, 0]
            value16 = value.half()[:, 0]
            beta = torch.sigmoid(b.half())[:, 0]
            decay_log = (
                -torch.exp(self._a_log.half())
                * adapter.softplus(a.half() + self._dt_bias.half())[:, 0]
            )
            decay = torch.exp(decay_log).unsqueeze(-1).unsqueeze(-1)
            decay = decay.expand_as(recurrent_state)
            state = recurrent_state.half() * decay
            key_matrix = key16.unsqueeze(-1).expand_as(state)
            remembered = (state * key_matrix).sum(dim=-2)
            beta_matrix = beta.unsqueeze(-1).expand_as(value16)
            delta = (value16 - remembered) * beta_matrix
            key_outer = key16.unsqueeze(-1).expand(
                key16.shape[0],
                key16.shape[1],
                key16.shape[2],
                value16.shape[2],
            )
            delta_outer = delta.unsqueeze(-2).expand_as(key_outer)
            state = state + key_outer * delta_outer
            query_matrix = query16.unsqueeze(-1).expand_as(state)
            core = (state * query_matrix).sum(dim=-2).unsqueeze(1)
            return core, state.to(recurrent_state.dtype)

        def fp16_gated_norm_forward(self, hidden, gate):
            output_dtype = gate.dtype
            hidden16 = hidden.half()
            hidden16 = hidden16 * torch.rsqrt(
                (hidden16 * hidden16).mean(-1, keepdim=True) + self.eps
            )
            hidden16 = hidden16 * self.weight.half()
            hidden16 = hidden16 * torch.nn.functional.silu(gate.half())
            return hidden16.to(output_dtype)

        adapter.GatedDeltaRecurrence.forward = fp16_recurrence_forward
        adapter.RMSNormGated.forward = fp16_gated_norm_forward
    if args.matmul_recurrence_reductions:
        def matmul_recurrence_forward(
            self, query, key, value, a, b, recurrent_state
        ):
            query32 = query.float()
            key32 = key.float()
            query32 = query32 * torch.rsqrt(
                (query32 * query32).sum(-1, keepdim=True) + 1e-6
            )
            key32 = key32 * torch.rsqrt(
                (key32 * key32).sum(-1, keepdim=True) + 1e-6
            )
            query32 = query32[:, 0] * (1.0 / math.sqrt(self.key_head_dim))
            key32 = key32[:, 0]
            value32 = value.float()[:, 0]
            beta = torch.sigmoid(b.float())[:, 0]
            decay_log = (
                -torch.exp(self._a_log.float())
                * adapter.softplus(a.float() + self._dt_bias.float())[:, 0]
            )
            decay = torch.exp(decay_log).unsqueeze(-1).unsqueeze(-1)
            decay = decay.expand_as(recurrent_state)
            state = recurrent_state.float() * decay
            remembered = torch.matmul(key32.unsqueeze(-2), state).squeeze(-2)
            beta_matrix = beta.unsqueeze(-1).expand_as(value32)
            delta = (value32 - remembered) * beta_matrix
            key_outer = key32.unsqueeze(-1).expand(
                key32.shape[0],
                key32.shape[1],
                key32.shape[2],
                value32.shape[2],
            )
            delta_outer = delta.unsqueeze(-2).expand_as(key_outer)
            state = state + key_outer * delta_outer
            core = torch.matmul(query32.unsqueeze(-2), state).squeeze(-2).unsqueeze(1)
            return core, state.to(recurrent_state.dtype)

        adapter.GatedDeltaRecurrence.forward = matmul_recurrence_forward
    register_softplus_visitor()
    if args.fp16_recurrence_island:
        import executorch.backends.qualcomm.python.PyQnnManagerAdaptor as PyQnnManager
        from executorch.backends.qualcomm.builders import node_visitor

        node_visitor.QNN_TENSOR_TYPE_MAP[torch.float16] = (
            PyQnnManager.Qnn_DataType_t.QNN_DATATYPE_FLOAT_16
        )

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
    from torchao.quantization.pt2e import HistogramObserver, MinMaxObserver
    from torchao.quantization.pt2e.quantize_pt2e import convert_pt2e, prepare_pt2e

    params = json.loads(args.params.read_text())
    config = ModelArgs(
        max_seq_len=args.context,
        max_context_len=args.context,
        max_batch_size=1,
        use_kv_cache=True,
        **params,
    )
    diagnostic_component_names = [
        "embedded_hidden",
        "attention_normalized",
        "attention_output",
        "post_attention_hidden",
        "ffn_normalized",
        "ffn_w1",
        "ffn_silu_w1",
        "ffn_w3",
        "ffn_product",
        "ffn_output",
        "hidden_after_layer0",
    ]
    diagnostic_attention_component_names = [
        "attention_qkv_projection",
        "attention_conv_pre_silu",
        "attention_conv_activated",
        "attention_query",
        "attention_key",
        "attention_value",
        "attention_a_projection",
        "attention_b_projection",
        "attention_recurrent_core",
        "attention_z_projection",
        "attention_gated_norm_core",
    ]
    if (
        args.diagnostic_hidden_states
        or args.diagnostic_layer0_components
        or args.diagnostic_layer0_attention_components
    ):
        class ExactDiagnosticModel(adapter.Qwen35QnnModel):
            def forward(self, tokens, attention_mask, input_pos, *states):
                state_a = states[: self.n_layers]
                state_b = states[self.n_layers :]
                cos = self.freqs_cos[input_pos][0]
                sin = self.freqs_sin[input_pos][0]
                hidden = self.tok_embeddings(tokens)
                out_a = []
                out_b = []
                hidden_states = []
                components = []
                for index, layer in enumerate(self.layers):
                    if index == 0 and (
                        args.diagnostic_layer0_components
                        or args.diagnostic_layer0_attention_components
                    ):
                        embedded_hidden = hidden
                        normalized = layer.attention_norm(hidden)
                        attention_components = []
                        if args.diagnostic_layer0_attention_components:
                            attention_module = layer.attention
                            batch, seq, _ = normalized.shape
                            qkv_projection = attention_module.in_proj_qkv(normalized)
                            mixed = qkv_projection.transpose(1, 2).unsqueeze(2)
                            conv_input = torch.cat((state_b[index], mixed), dim=-1)
                            next_b = conv_input[:, :, :, -attention_module.kernel :]
                            conv_pre_silu = attention_module.conv1d(conv_input)[:, :, :, -1:]
                            conv_activated = torch.nn.functional.silu(conv_pre_silu)
                            mixed = conv_activated.squeeze(2).transpose(1, 2)
                            query, key, value = torch.split(
                                mixed,
                                (
                                    attention_module.key_dim,
                                    attention_module.key_dim,
                                    attention_module.value_dim,
                                ),
                                dim=-1,
                            )
                            query = query.view(
                                batch,
                                seq,
                                attention_module.num_key_heads,
                                attention_module.key_head_dim,
                            )
                            key = key.view(
                                batch,
                                seq,
                                attention_module.num_key_heads,
                                attention_module.key_head_dim,
                            )
                            value = value.view(
                                batch,
                                seq,
                                attention_module.num_value_heads,
                                attention_module.value_head_dim,
                            )
                            if attention_module.head_repeat > 1:
                                query = query.repeat_interleave(
                                    attention_module.head_repeat, dim=2
                                )
                                key = key.repeat_interleave(
                                    attention_module.head_repeat, dim=2
                                )
                            a_projection = attention_module.in_proj_a(normalized)
                            b_projection = attention_module.in_proj_b(normalized)
                            recurrent_core, next_a = attention_module.recurrence(
                                query,
                                key,
                                value,
                                a_projection,
                                b_projection,
                                state_a[index],
                            )
                            z_projection = attention_module.in_proj_z(normalized).view(
                                batch,
                                seq,
                                attention_module.num_value_heads,
                                attention_module.value_head_dim,
                            )
                            gated_norm_core = attention_module.norm(
                                recurrent_core.reshape(-1, attention_module.value_head_dim),
                                z_projection.reshape(-1, attention_module.value_head_dim),
                            )
                            attention = attention_module.out_proj(
                                gated_norm_core.view(batch, seq, attention_module.value_dim)
                            )
                            attention_components.extend(
                                (
                                    qkv_projection,
                                    conv_pre_silu,
                                    conv_activated,
                                    query,
                                    key,
                                    value,
                                    a_projection,
                                    b_projection,
                                    recurrent_core,
                                    z_projection,
                                    gated_norm_core,
                                )
                            )
                        else:
                            attention, next_a, next_b = layer.attention(
                                normalized, state_a[index], state_b[index]
                            )
                        post_attention = hidden + attention
                        ffn_normalized = layer.ffn_norm(post_attention)
                        ffn_w1 = layer.feed_forward.w1(ffn_normalized)
                        ffn_silu_w1 = torch.nn.functional.silu(ffn_w1)
                        ffn_w3 = layer.feed_forward.w3(ffn_normalized)
                        ffn_product = ffn_silu_w1 * ffn_w3
                        ffn_output = layer.feed_forward.w2(ffn_product)
                        hidden = post_attention + ffn_output
                        if args.diagnostic_layer0_components:
                            components.extend(
                                (
                                    embedded_hidden,
                                    normalized,
                                    attention,
                                    post_attention,
                                    ffn_normalized,
                                    ffn_w1,
                                    ffn_silu_w1,
                                    ffn_w3,
                                    ffn_product,
                                    ffn_output,
                                    hidden,
                                )
                            )
                        components.extend(attention_components)
                    else:
                        hidden, next_a, next_b = layer(
                            hidden,
                            cos,
                            sin,
                            attention_mask,
                            state_a[index],
                            state_b[index],
                        )
                    out_a.append(next_a)
                    out_b.append(next_b)
                    if args.diagnostic_hidden_states:
                        hidden_states.append(hidden)
                return (
                    self.output(self.norm(hidden)),
                    *out_a,
                    *out_b,
                    *hidden_states,
                    *components,
                )

        model = ExactDiagnosticModel(config, context_len=args.context).eval()
    else:
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

    activation_observer = (
        HistogramObserver if args.histogram_activations else MinMaxObserver
    )
    recipe = QuantRecipe(
        QuantDtype.use_16a4w,
        False,
        act_observer=activation_observer,
        granularity=QuantGranularity.PER_TENSOR,
        act_symmetric=args.symmetric_activations,
        verbose=False,
    ).add_node_target(
        {torch.ops.aten.linear.default, torch.ops.aten.conv2d.default},
        QuantDtype.use_16a4w,
        False,
        act_observer=activation_observer,
        granularity=QuantGranularity.PER_CHANNEL,
        act_symmetric=args.symmetric_activations,
    )
    float_recurrence_node_names = []
    if args.float_recurrence or args.fp16_recurrence_island:
        class FloatRecurrenceQuantizer(QnnQuantizer):
            def annotate(self, graph_module):
                for node in graph_module.graph.nodes:
                    module_stack = str(node.meta.get("nn_module_stack", {}))
                    if (
                        ".attention.recurrence" in module_stack
                        or ".attention.norm" in module_stack
                    ):
                        self.discard_nodes.add(node.name)
                        float_recurrence_node_names.append(node.name)
                return super().annotate(graph_module)

        quantizer = FloatRecurrenceQuantizer()
        quantizer.set_default_quant_config(
            QuantDtype.use_16a4w,
            False,
            is_conv_per_channel=True,
            is_linear_per_channel=True,
            act_observer=activation_observer,
            act_symmetric=args.symmetric_activations,
        )
    else:
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
    if args.float_recurrence or args.fp16_recurrence_island:
        for pass_type, setting in passes_job.items():
            if pass_type.__name__ == "RecomposeRmsNorm":
                setting["activate"] = False
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
            use_fp16=(args.float_recurrence or args.fp16_recurrence_island),
            use_multi_contexts=args.shards > 1,
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
        "diagnostic_hidden_states": args.diagnostic_hidden_states,
        "matmul_recurrence_reductions": args.matmul_recurrence_reductions,
        "float_recurrence": args.float_recurrence,
        "fp16_recurrence_island": args.fp16_recurrence_island,
        "symmetric_activations": args.symmetric_activations,
        "activation_observer": activation_observer.__name__,
        "float_recurrence_annotation_nodes": len(set(float_recurrence_node_names)),
        "diagnostic_layer0_components": args.diagnostic_layer0_components,
        "diagnostic_layer0_attention_components": (
            args.diagnostic_layer0_attention_components
        ),
        "diagnostic_component_names": (
            (diagnostic_component_names if args.diagnostic_layer0_components else [])
            + (
                diagnostic_attention_component_names
                if args.diagnostic_layer0_attention_components
                else []
            )
        ),
        "forward_outputs": (
            1
            + 2 * model.n_layers
            + (model.n_layers if args.diagnostic_hidden_states else 0)
            + (len(diagnostic_component_names) if args.diagnostic_layer0_components else 0)
            + (
                len(diagnostic_attention_component_names)
                if args.diagnostic_layer0_attention_components
                else 0
            )
        ),
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
