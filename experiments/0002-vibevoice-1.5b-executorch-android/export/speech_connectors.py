#!/usr/bin/env python3
"""Connector-only checkpoint loader and tensor ABI for the semantic/audio join."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import torch
from safetensors import safe_open


CONNECTOR_PREFIXES = {
    "acoustic": "model.acoustic_connector.",
    "semantic": "model.semantic_connector.",
}


class ConnectorRMSNorm(torch.nn.Module):
    """The LlamaRMSNorm calculation used by the pinned SpeechConnector."""

    def __init__(self, hidden_size: int, eps: float = 1e-6):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.ones(hidden_size))
        self.eps = eps

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        input_dtype = value.dtype
        normalized = value.float()
        variance = normalized.pow(2).mean(-1, keepdim=True)
        normalized = normalized * torch.rsqrt(variance + self.eps)
        return self.weight * normalized.to(input_dtype)


class SpeechConnector(torch.nn.Module):
    """Checkpoint-compatible copy of the pinned two-linear-layer connector."""

    def __init__(self, input_dim: int, output_dim: int):
        super().__init__()
        self.fc1 = torch.nn.Linear(input_dim, output_dim)
        self.norm = ConnectorRMSNorm(output_dim)
        self.fc2 = torch.nn.Linear(output_dim, output_dim)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.fc2(self.norm(self.fc1(features)))


def load_speech_connectors(
    model_path: Path, dtype: torch.dtype = torch.float32
) -> tuple[torch.nn.Module, torch.nn.Module]:
    """Load acoustic and semantic connectors without constructing other components."""
    model_path = Path(model_path)
    config = json.loads((model_path / "config.json").read_text())
    output_dim = int(config["decoder_config"]["hidden_size"])
    modules = {
        "acoustic": SpeechConnector(int(config["acoustic_vae_dim"]), output_dim),
        "semantic": SpeechConnector(int(config["semantic_vae_dim"]), output_dim),
    }

    index = json.loads((model_path / "model.safetensors.index.json").read_text())
    by_shard: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for checkpoint_name, shard in index["weight_map"].items():
        for kind, prefix in CONNECTOR_PREFIXES.items():
            if checkpoint_name.startswith(prefix):
                by_shard[shard].append(
                    (kind, checkpoint_name, checkpoint_name.removeprefix(prefix))
                )
                break
    states: dict[str, dict[str, torch.Tensor]] = {kind: {} for kind in modules}
    for shard, entries in sorted(by_shard.items()):
        with safe_open(model_path / shard, framework="pt", device="cpu") as handle:
            for kind, checkpoint_name, module_name in entries:
                states[kind][module_name] = handle.get_tensor(checkpoint_name).to(
                    dtype=dtype
                )

    for kind, module in modules.items():
        if not states[kind]:
            raise RuntimeError(f"No {kind} connector weights found")
        incompatible = module.load_state_dict(states[kind], strict=True)
        if incompatible.missing_keys or incompatible.unexpected_keys:
            raise RuntimeError(f"{kind} connector state mismatch: {incompatible}")
        module.to(dtype=dtype).eval()
    return modules["acoustic"], modules["semantic"]


class SpeechConnectorJoin(torch.nn.Module):
    """Stable tensor-only join used to construct the next LM input embedding.

    ABI: `(acoustic [batch,64], semantic [batch,128]) -> [batch,1536]`.
    """

    def __init__(
        self, acoustic_connector: torch.nn.Module, semantic_connector: torch.nn.Module
    ):
        super().__init__()
        self.acoustic_connector = acoustic_connector
        self.semantic_connector = semantic_connector

    def forward(
        self, acoustic_features: torch.Tensor, semantic_features: torch.Tensor
    ) -> torch.Tensor:
        return self.acoustic_connector(acoustic_features) + self.semantic_connector(
            semantic_features
        )
