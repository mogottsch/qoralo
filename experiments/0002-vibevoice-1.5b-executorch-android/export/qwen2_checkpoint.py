#!/usr/bin/env python3
"""Load only the locked checkpoint's Qwen2 backbone in FP32."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import torch
import torch.nn.functional as F
from safetensors import safe_open
from transformers import Qwen2Config
from transformers.models.qwen2.modeling_qwen2 import Qwen2Model

LANGUAGE_MODEL_PREFIX = "model.language_model."


class TiedLMHead(torch.nn.Module):
    """Apply the checkpoint's tied token embedding as an output projection."""

    def __init__(self, weight: torch.nn.Parameter):
        super().__init__()
        self.weight = weight

    def forward(self, hidden_state: torch.Tensor) -> torch.Tensor:
        return F.linear(hidden_state, self.weight)


def load_qwen2_backbone(
    model_path: Path, dtype: torch.dtype = torch.float32
) -> tuple[Qwen2Model, TiedLMHead]:
    """Construct Qwen2 and copy only language-model tensors from the shards.

    Tensors are copied one at a time into the initialized module so loading FP32
    does not retain a second full state dictionary in RAM.
    """
    model_path = Path(model_path)
    root_config = json.loads((model_path / "config.json").read_text())
    decoder_config = dict(root_config["decoder_config"])
    decoder_config["torch_dtype"] = dtype
    config = Qwen2Config(**decoder_config)
    config._attn_implementation = "eager"
    backbone = Qwen2Model(config).to(dtype=dtype).eval()

    index = json.loads((model_path / "model.safetensors.index.json").read_text())
    by_shard: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for checkpoint_name, shard in index["weight_map"].items():
        if checkpoint_name.startswith(LANGUAGE_MODEL_PREFIX):
            by_shard[shard].append(
                (
                    checkpoint_name,
                    checkpoint_name.removeprefix(LANGUAGE_MODEL_PREFIX),
                )
            )
    if not by_shard:
        raise RuntimeError(
            f"No weights with prefix {LANGUAGE_MODEL_PREFIX!r} in checkpoint"
        )

    destinations = backbone.state_dict()
    loaded: set[str] = set()
    with torch.no_grad():
        for shard, names in sorted(by_shard.items()):
            with safe_open(model_path / shard, framework="pt", device="cpu") as handle:
                for checkpoint_name, backbone_name in names:
                    if backbone_name not in destinations:
                        raise RuntimeError(
                            f"Unexpected Qwen2 tensor: {checkpoint_name}"
                        )
                    source = handle.get_tensor(checkpoint_name)
                    destination = destinations[backbone_name]
                    if source.shape != destination.shape:
                        raise RuntimeError(
                            f"{checkpoint_name} shape {tuple(source.shape)} does not match "
                            f"{tuple(destination.shape)}"
                        )
                    destination.copy_(source)
                    loaded.add(backbone_name)

    missing = sorted(set(destinations) - loaded)
    if missing:
        raise RuntimeError(f"Missing Qwen2 checkpoint tensors: {missing}")
    return backbone, TiedLMHead(backbone.embed_tokens.weight).eval()
