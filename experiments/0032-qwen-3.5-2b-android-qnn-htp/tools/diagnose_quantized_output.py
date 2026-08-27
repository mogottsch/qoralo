#!/usr/bin/env python3
"""Compare pre-PTQ and converted W4A16 host outputs in separate processes."""
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


def summarize(logits: torch.Tensor) -> dict:
    values = logits.float().reshape(-1)
    top_values, top_ids = torch.topk(values, 10)
    return {
        "finite": bool(torch.isfinite(values).all()),
        "argmax": int(top_ids[0]),
        "top_ids": [int(value) for value in top_ids],
        "top_logits": [float(value) for value in top_values],
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "zero_count": int((values == 0).sum()),
        "numel": values.numel(),
    }


def make_state_templates(config, context: int) -> list[torch.Tensor]:
    state_a: list[torch.Tensor] = []
    state_b: list[torch.Tensor] = []
    for layer_type in config.layer_types:
        if layer_type == "linear_attention":
            state_a.append(
                torch.zeros(
                    1,
                    config.linear_num_value_heads,
                    config.linear_key_head_dim,
                    config.linear_value_head_dim,
                )
            )
            state_b.append(
                torch.zeros(
                    1,
                    2 * config.linear_num_key_heads * config.linear_key_head_dim
                    + config.linear_num_value_heads * config.linear_value_head_dim,
                    1,
                    config.linear_conv_kernel_dim,
                )
            )
        else:
            state_a.append(
                torch.zeros(1, config.n_kv_heads, config.head_dim, context - 1)
            )
            state_b.append(
                torch.zeros(1, config.n_kv_heads, context - 1, config.head_dim)
            )
    return state_a + state_b


def update_state(
    n_layers: int,
    layer_types: list[str],
    states: list[torch.Tensor],
    outputs,
    position: int,
) -> list[torch.Tensor]:
    next_a = list(outputs[1 : 1 + n_layers])
    next_b = list(outputs[1 + n_layers :])
    for index, layer_type in enumerate(layer_types):
        if layer_type == "linear_attention":
            states[index] = next_a[index].detach()
            states[n_layers + index] = next_b[index].detach()
        else:
            states[index][..., position] = next_a[index][..., 0]
            states[n_layers + index][:, :, position, :] = next_b[index][:, :, 0, :]
    return states


def rss_kib() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return -1


def write_checkpoint(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run_prompt(
    state_templates: list[torch.Tensor],
    n_layers: int,
    layer_types: list[str],
    graph_module,
    token_ids: list[int],
    context: int,
    label: str,
):
    states = [tensor.clone() for tensor in state_templates]
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
            states = update_state(n_layers, layer_types, states, outputs, position)
            if position == 0 or (position + 1) % 10 == 0 or position + 1 == len(token_ids):
                print(
                    f"{label}: token {position + 1}/{len(token_ids)}, "
                    f"argmax={int(last_logits.argmax())}, rss_kib={rss_kib()}",
                    flush=True,
                )
    assert last_logits is not None
    return last_logits, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("prepare", "run"), required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--params", type=Path, required=True)
    parser.add_argument("--token-ids", type=Path, required=True)
    parser.add_argument("--qdq-file", type=Path, required=True)
    parser.add_argument("--pre-logits", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context", type=int, default=4096)
    args = parser.parse_args()

    experiment = Path(__file__).resolve().parents[1]
    # Importing registers qwen35::softplus, which the saved QDQ graph references.
    adapter = load_module("qwen35_qnn_model", experiment / "tools/qwen35_qnn_model.py")
    from executorch.examples.models.llama.model_args import ModelArgs

    params = json.loads(args.params.read_text())
    config = ModelArgs(
        max_seq_len=args.context,
        max_context_len=args.context,
        max_batch_size=1,
        use_kv_cache=True,
        **params,
    )
    raw_ids = args.token_ids.read_bytes()
    token_ids = np.frombuffer(raw_ids, dtype="<i4").astype(np.int64).tolist()
    state_templates = make_state_templates(config, args.context)
    n_layers = config.n_layers
    layer_types = list(config.layer_types)

    if args.phase == "prepare":
        if args.checkpoint is None:
            raise ValueError("--checkpoint is required for the prepare phase")
        from executorch.backends.qualcomm.quantizer.quant_recipe import (
            QuantGranularity,
            QuantRecipe,
        )
        from executorch.backends.qualcomm.quantizer.quantizer import (
            QuantDtype,
            QnnQuantizer,
        )
        from torchao.quantization.pt2e import MinMaxObserver
        from torchao.quantization.pt2e.quantize_pt2e import convert_pt2e, prepare_pt2e

        print(f"phase=model_load_start rss_kib={rss_kib()}", flush=True)
        model = adapter.Qwen35QnnModel(config, context_len=args.context).eval()
        state_dict = adapter.adapt_converted_state_dict(
            torch.load(args.checkpoint, map_location="cpu", mmap=True)
        )
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        unexpected = [
            name
            for name in unexpected
            if not name.endswith((".conv_state", ".recurrent_state"))
        ]
        if missing or unexpected:
            raise RuntimeError(
                f"checkpoint mismatch: missing={missing}, unexpected={unexpected}"
            )
        model = model.float().eval()
        inputs = model.get_example_inputs()
        print(f"phase=export_start rss_kib={rss_kib()}", flush=True)
        exported = torch.export.export(model, inputs, strict=True).module()
        print(f"phase=export_done rss_kib={rss_kib()}", flush=True)

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
        print(f"phase=prepare_pt2e_start rss_kib={rss_kib()}", flush=True)
        prepared = prepare_pt2e(exported, quantizer)
        print(f"phase=prepare_pt2e_done rss_kib={rss_kib()}", flush=True)
        pre_logits, calibration_seconds = run_prompt(
            state_templates,
            n_layers,
            layer_types,
            prepared,
            token_ids,
            args.context,
            "pre_ptq",
        )
        args.pre_logits.parent.mkdir(parents=True, exist_ok=True)
        torch.save(pre_logits.cpu(), args.pre_logits)
        partial = {
            "schema_version": 1,
            "status": "pre_ptq_checkpoint",
            "prompt_tokens": len(token_ids),
            "pre_ptq": summarize(pre_logits),
            "calibration_seconds": calibration_seconds,
            "rss_kib": rss_kib(),
        }
        write_checkpoint(args.output, partial)
        print(f"phase=convert_pt2e_start rss_kib={rss_kib()}", flush=True)
        converted = convert_pt2e(prepared)
        print(f"phase=convert_pt2e_done rss_kib={rss_kib()}", flush=True)
        print(f"phase=qdq_export_start rss_kib={rss_kib()}", flush=True)
        qdq_export = torch.export.export(converted, inputs, strict=True)
        args.qdq_file.parent.mkdir(parents=True, exist_ok=True)
        torch.export.save(qdq_export, args.qdq_file)
        partial.update(
            {
                "status": "qdq_saved_checkpoint",
                "rss_kib_after_qdq_export": rss_kib(),
                "qdq_file_bytes": args.qdq_file.stat().st_size,
            }
        )
        write_checkpoint(args.output, partial)
        print(f"phase=prepare_complete rss_kib={rss_kib()}", flush=True)
        return

    # Register quantized_decomposed Q/DQ schemas before deserializing the saved graph.
    import torchao.quantization.pt2e.quantize_pt2e  # noqa: F401

    print(f"phase=qdq_load_start rss_kib={rss_kib()}", flush=True)
    converted = torch.export.load(args.qdq_file).module()
    print(f"phase=qdq_load_done rss_kib={rss_kib()}", flush=True)
    post_logits, converted_seconds = run_prompt(
        state_templates,
        n_layers,
        layer_types,
        converted,
        token_ids,
        args.context,
        "post_ptq_qdq",
    )
    pre_logits = torch.load(args.pre_logits, map_location="cpu", weights_only=True)
    difference = (pre_logits.float() - post_logits.float()).reshape(-1)
    prior = json.loads(args.output.read_text())
    result = {
        "schema_version": 1,
        "experiment": "0032-qwen-3.5-2b-android-qnn-htp",
        "evidence_class": "host_w4a16_qdq_output_diagnosis",
        "prompt_tokens": len(token_ids),
        "context_tokens": args.context,
        "quantization": "same QNN W4A16 PTQ recipe used by compile_exact_qnn.py",
        "pre_ptq": summarize(pre_logits),
        "post_ptq_qdq": summarize(post_logits),
        "difference": {
            "max_abs": float(difference.abs().max()),
            "mean_abs": float(difference.abs().mean()),
        },
        "timing_seconds": {
            "calibration": prior["calibration_seconds"],
            "converted_qdq_execution": converted_seconds,
        },
        "separate_process_boundary": True,
        "run_phase_peak_rss_kib": rss_kib(),
        "physical_observation": {"argmax": 0, "decoded": "!"},
        "claim_limits": [
            "Host PT2E QDQ execution only; this does not execute QNN or Android.",
            "The result diagnoses only whether the chosen PTQ recipe reproduces the physical argmax mismatch.",
        ],
    }
    write_checkpoint(args.output, result)
    print(args.output)


if __name__ == "__main__":
    main()
