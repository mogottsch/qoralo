#!/usr/bin/env python3
"""Export and host-validate tiny synthetic Qwen2 prefill/decode XNNPACK PTEs."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path

import torch
from transformers import Qwen2Config
from transformers.models.qwen2.modeling_qwen2 import Qwen2Model

from fixture_utils import repo_root
from qwen2_backbone import Qwen2Decode, Qwen2Prefill, cache_tensor_names


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=root / "artifacts/0002/lane-c/tiny-xnnpack"
    )
    return parser.parse_args()


def version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def compare(actual: tuple[torch.Tensor, ...], expected: tuple[torch.Tensor, ...]) -> float:
    if len(actual) != len(expected):
        raise RuntimeError(f"Expected {len(expected)} outputs, got {len(actual)}")
    maximum = 0.0
    for actual_tensor, expected_tensor in zip(actual, expected):
        torch.testing.assert_close(actual_tensor, expected_tensor, atol=1e-5, rtol=1e-4)
        maximum = max(maximum, (actual_tensor - expected_tensor).abs().max().item())
    return maximum


def main() -> None:
    args = parse_args()
    try:
        from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
        from executorch.exir import to_edge_transform_and_lower
        from executorch.runtime import Runtime
    except ImportError as error:
        raise SystemExit(f"ExecuTorch 1.2 with XNNPACK is required: {error}") from error

    torch.manual_seed(7)
    config = Qwen2Config(
        vocab_size=32,
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        max_position_embeddings=32,
        sliding_window=None,
        use_sliding_window=False,
        _attn_implementation="eager",
    )
    backbone = Qwen2Model(config).eval()
    lm_head = torch.nn.Linear(16, 32, bias=False).eval()
    lm_head.weight = backbone.embed_tokens.weight
    options = {
        "num_hidden_layers": 2,
        "num_key_value_heads": 2,
        "head_dim": 4,
        "cache_capacity": 8,
    }
    prefill = Qwen2Prefill(backbone, lm_head, **options).eval()
    decode = Qwen2Decode(backbone, lm_head, **options).eval()
    prefill_inputs = (
        torch.randn(1, 3, 16),
        torch.tensor([[1, 1, 1, 0, 0, 0, 0, 0]]),
        torch.arange(3).unsqueeze(0),
        torch.arange(3),
    )
    with torch.no_grad():
        prefill_reference = prefill(*prefill_inputs)
    decode_inputs = (
        torch.randn(1, 1, 16),
        torch.tensor([[1, 1, 1, 1, 0, 0, 0, 0]]),
        torch.tensor([[3]]),
        torch.tensor([3]),
        *(value.clone() for value in prefill_reference[2:]),
    )
    with torch.no_grad():
        decode_reference = decode(*decode_inputs)

    args.output.mkdir(parents=True, exist_ok=True)
    specs = (
        ("prefill", prefill, prefill_inputs, prefill_reference),
        ("decode", decode, decode_inputs, decode_reference),
    )
    results: dict[str, object] = {}
    runtime = Runtime.get()
    for name, module, inputs, reference in specs:
        exported = torch.export.export(module, inputs, strict=True)
        edge = to_edge_transform_and_lower(
            exported, partitioner=[XnnpackPartitioner()]
        )
        delegate_count = sum(
            1
            for _, child in edge.exported_program().graph_module.named_modules()
            if getattr(child, "original_module", None) is not None
        )
        pte = args.output / f"qwen2-tiny-{name}-xnnpack.pte"
        with pte.open("wb") as handle:
            edge.to_executorch().write_to_file(handle)
        actual = tuple(runtime.load_program(str(pte)).load_method("forward").execute(inputs))
        results[name] = {
            "pte": str(pte),
            "bytes": pte.stat().st_size,
            "delegate_segments": delegate_count,
            "outputs": len(actual),
            "max_abs_error": compare(actual, reference),
        }

    metadata = {
        "schema_version": 1,
        "status": "passed",
        "synthetic_only": True,
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "transformers": version("transformers"),
            "executorch": version("executorch"),
        },
        "config": options,
        "cache_order": cache_tensor_names(2),
        "results": results,
        "limitations": [
            "This proves ABI/export/runtime mechanics, not real-checkpoint numerics.",
            "No quantization was applied.",
            "Android was not used.",
        ],
    }
    (args.output / "result.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
