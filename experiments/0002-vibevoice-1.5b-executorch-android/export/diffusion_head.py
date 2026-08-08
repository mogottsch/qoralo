#!/usr/bin/env python3
"""Diffusion-head-only loader and stable one-step tensor ABI."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import torch
from safetensors import safe_open


PREDICTION_HEAD_PREFIX = "model.prediction_head."


def load_prediction_head(
    model_path: Path, dtype: torch.dtype = torch.float32
) -> torch.nn.Module:
    """Construct and load only the prediction head from a sharded checkpoint."""
    from vibevoice.modular.configuration_vibevoice import VibeVoiceConfig
    from vibevoice.modular.modular_vibevoice_diffusion_head import (
        VibeVoiceDiffusionHead,
    )

    model_path = Path(model_path)
    config = VibeVoiceConfig.from_pretrained(model_path)
    head = VibeVoiceDiffusionHead(config.diffusion_head_config)

    index = json.loads((model_path / "model.safetensors.index.json").read_text())
    by_shard: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for checkpoint_name, shard in index["weight_map"].items():
        if checkpoint_name.startswith(PREDICTION_HEAD_PREFIX):
            by_shard[shard].append(
                (
                    checkpoint_name,
                    checkpoint_name.removeprefix(PREDICTION_HEAD_PREFIX),
                )
            )
    if not by_shard:
        raise RuntimeError(
            f"No weights with prefix {PREDICTION_HEAD_PREFIX!r} in checkpoint"
        )

    state: dict[str, torch.Tensor] = {}
    for shard, names in sorted(by_shard.items()):
        with safe_open(model_path / shard, framework="pt", device="cpu") as handle:
            for checkpoint_name, head_name in names:
                state[head_name] = handle.get_tensor(checkpoint_name).to(dtype=dtype)

    incompatible = head.load_state_dict(state, strict=True)
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise RuntimeError(f"Prediction-head state mismatch: {incompatible}")
    return head.to(dtype=dtype).eval()


class DiffusionHeadStep(torch.nn.Module):
    """One CFG prediction-head call, excluding scheduler state and iteration.

    Stable FP32 ABI:
      noisy_latent:       [batch, 64]
      timestep:           [batch]
      positive_condition: [batch, 1536]
      negative_condition: [batch, 1536]
      return:             [batch, 64] CFG-guided v-prediction

    The locked reference uses a fixed CFG scale of 1.3. The native controller is
    responsible for applying the scheduler update and invoking this graph again.
    """

    def __init__(self, prediction_head: torch.nn.Module, cfg_scale: float = 1.3):
        super().__init__()
        self.prediction_head = prediction_head
        self.cfg_scale = float(cfg_scale)

    def forward(
        self,
        noisy_latent: torch.Tensor,
        timestep: torch.Tensor,
        positive_condition: torch.Tensor,
        negative_condition: torch.Tensor,
    ) -> torch.Tensor:
        duplicated_latent = torch.cat((noisy_latent, noisy_latent), dim=0)
        duplicated_timestep = torch.cat((timestep, timestep), dim=0)
        condition = torch.cat((positive_condition, negative_condition), dim=0)
        prediction = self.prediction_head(
            duplicated_latent, duplicated_timestep, condition
        )
        positive_prediction, negative_prediction = prediction.chunk(2, dim=0)
        return negative_prediction + self.cfg_scale * (
            positive_prediction - negative_prediction
        )
