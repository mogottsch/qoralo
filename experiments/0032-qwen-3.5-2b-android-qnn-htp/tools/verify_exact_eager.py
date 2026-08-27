#!/usr/bin/env python3
"""Compare the exact converted checkpoint against ExecuTorch's Qwen3.5 eager model."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import torch
import torch.nn.functional as F


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metrics(reference: torch.Tensor, actual: torch.Tensor) -> dict[str, float]:
    reference = reference.float().reshape(-1)
    actual = actual.float().reshape(-1)
    difference = (reference - actual).abs()
    return {
        "max_abs": float(difference.max()),
        "mean_abs": float(difference.mean()),
        "cosine": float(F.cosine_similarity(reference, actual, dim=0)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--params", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context", type=int, default=4096)
    parser.add_argument("--token", type=int, default=248045)
    args = parser.parse_args()

    experiment = Path(__file__).resolve().parents[1]
    adapter_module = load_module("qwen35_qnn_model", experiment / "tools/qwen35_qnn_model.py")
    from executorch.examples.models.llama.llama_transformer import construct_transformer
    from executorch.examples.models.llama.model_args import ModelArgs

    params = json.loads(args.params.read_text())
    config = ModelArgs(
        max_seq_len=args.context,
        max_context_len=args.context,
        max_batch_size=1,
        use_kv_cache=True,
        **params,
    )
    checkpoint = torch.load(args.checkpoint, map_location="cpu", mmap=True)

    reference = construct_transformer(config).eval()
    ref_missing, ref_unexpected = reference.load_state_dict(checkpoint, strict=False)
    reference = reference.float().eval()

    adapter = adapter_module.Qwen35QnnModel(config, context_len=args.context).eval()
    adapted = adapter_module.adapt_converted_state_dict(checkpoint)
    missing, unexpected = adapter.load_state_dict(adapted, strict=False)
    ignored_state = tuple((".conv_state", ".recurrent_state"))
    unexpected = [name for name in unexpected if not name.endswith(ignored_state)]
    if missing or unexpected:
        raise RuntimeError(f"adapter mismatch: missing={missing}, unexpected={unexpected}")

    adapter_inputs = adapter.get_example_inputs()
    token_i32 = torch.tensor([[args.token]], dtype=torch.int32)
    position_i32 = torch.tensor([[0]], dtype=torch.int32)
    with torch.no_grad():
        reference_logits = reference(token_i32.long(), input_pos=torch.tensor([0]))
        if isinstance(reference_logits, tuple):
            reference_logits = reference_logits[0]
        adapter_outputs = adapter(
            token_i32,
            adapter_inputs[1],
            position_i32,
            *adapter_inputs[3:],
        )

    reference_logits = reference_logits.reshape(1, -1)
    adapter_logits = adapter_outputs[0].reshape(1, -1)
    first_attention = reference.layers[0].attention
    result = {
        "schema_version": 1,
        "evidence_class": "exact_checkpoint_host_eager_equivalence",
        "model": "Qwen/Qwen3.5-2B",
        "token_id": args.token,
        "reference": "ExecuTorch v1.2.0 examples.models.llama Qwen3.5 implementation",
        "reference_shape": list(reference_logits.shape),
        "adapter_shape": list(adapter_logits.shape),
        "logits": metrics(reference_logits, adapter_logits),
        "recurrent_state_layer0": metrics(
            first_attention.recurrent_state, adapter_outputs[1]
        ),
        "conv_state_layer0": metrics(
            first_attention.conv_state.unsqueeze(2), adapter_outputs[1 + adapter.n_layers]
        ),
        "reference_argmax": int(reference_logits.argmax()),
        "adapter_argmax": int(adapter_logits.argmax()),
        "adapter_missing": list(missing),
        "adapter_unexpected_after_state_filter": unexpected,
        "reference_missing": list(ref_missing),
        "reference_unexpected": list(ref_unexpected),
        "claim_limits": [
            "Host eager comparison only; this is not quantized-output validation.",
            "This is not Android execution and is not physical QNN/HTP evidence."
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if result["logits"]["max_abs"] != 0.0:
        raise RuntimeError(f"non-exact eager logits: {result['logits']}")
    print(args.output)


if __name__ == "__main__":
    main()
