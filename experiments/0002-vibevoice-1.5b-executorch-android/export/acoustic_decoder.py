#!/usr/bin/env python3
"""Decoder-only checkpoint loader and fixed-shape operator-coverage wrapper."""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path

import torch
from safetensors import safe_open


DECODER_PREFIX = "model.acoustic_tokenizer.decoder."


def build_decoder_config(acoustic_config: object) -> object:
    """Derive TokenizerDecoder's config without constructing the encoder."""
    if isinstance(acoustic_config.encoder_depths, str):
        encoder_depths = [int(value) for value in acoustic_config.encoder_depths.split("-")]
    else:
        encoder_depths = list(acoustic_config.encoder_depths)
    if acoustic_config.decoder_depths is None:
        decoder_depths = list(reversed(encoder_depths))
    elif isinstance(acoustic_config.decoder_depths, str):
        decoder_depths = [int(value) for value in acoustic_config.decoder_depths.split("-")]
    else:
        decoder_depths = list(acoustic_config.decoder_depths)

    result = copy.deepcopy(acoustic_config)
    result.dimension = acoustic_config.vae_dim
    result.n_filters = acoustic_config.decoder_n_filters
    result.ratios = acoustic_config.decoder_ratios
    result.depths = decoder_depths
    result.norm = acoustic_config.conv_norm
    result.pad_mode = acoustic_config.pad_mode
    result.bias = acoustic_config.conv_bias
    result.layernorm_eps = acoustic_config.layernorm_eps
    result.layernorm_elementwise_affine = acoustic_config.layernorm_elementwise_affine
    result.mixer_layer = acoustic_config.mixer_layer
    result.layer_scale_init_value = acoustic_config.layer_scale_init_value
    result.disable_last_norm = acoustic_config.disable_last_norm
    return result


def load_acoustic_decoder(model_path: Path, dtype: torch.dtype = torch.float32) -> torch.nn.Module:
    """Load only decoder tensors referenced by the sharded checkpoint index."""
    from vibevoice.modular.configuration_vibevoice import VibeVoiceConfig
    from vibevoice.modular.modular_vibevoice_tokenizer import TokenizerDecoder

    model_path = Path(model_path)
    config = VibeVoiceConfig.from_pretrained(model_path)
    decoder = TokenizerDecoder(build_decoder_config(config.acoustic_tokenizer_config))

    index = json.loads((model_path / "model.safetensors.index.json").read_text())
    by_shard: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for checkpoint_name, shard in index["weight_map"].items():
        if checkpoint_name.startswith(DECODER_PREFIX):
            by_shard[shard].append(
                (checkpoint_name, checkpoint_name.removeprefix(DECODER_PREFIX))
            )
    if not by_shard:
        raise RuntimeError(f"No weights with prefix {DECODER_PREFIX!r} in checkpoint")

    state: dict[str, torch.Tensor] = {}
    for shard, names in sorted(by_shard.items()):
        with safe_open(model_path / shard, framework="pt", device="cpu") as handle:
            for checkpoint_name, decoder_name in names:
                state[decoder_name] = handle.get_tensor(checkpoint_name).to(dtype=dtype)

    incompatible = decoder.load_state_dict(state, strict=True)
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise RuntimeError(f"Decoder state mismatch: {incompatible}")
    return decoder.to(dtype=dtype).eval()


class NonStreamingDecoderProbe(torch.nn.Module):
    """Fixed-layout probe for decoder operator coverage, without Python cache state.

    Input is `[batch, 64, latent_steps]`. This is deliberately not the final
    streaming ABI: the production wrapper must consume and return all cache
    tensors explicitly. It establishes export and backend operator coverage first.
    """

    def __init__(self, decoder: torch.nn.Module):
        super().__init__()
        self.decoder = decoder

    def forward(self, latent_b64t: torch.Tensor) -> torch.Tensor:
        return self.decoder(
            latent_b64t,
            cache=None,
            sample_indices=None,
            use_cache=False,
            debug=False,
        )
