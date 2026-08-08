#!/usr/bin/env python3
"""Decoder-only checkpoint loader and fixed-shape operator-coverage wrapper."""

from __future__ import annotations

import copy
import json
import math
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


class CausalPaddedSConv1d(torch.nn.Module):
    """Non-streaming SConv1d variant avoiding ExecuTorch constant_pad_nd.

    A symmetric padding value on Conv1d produces the causal outputs first; the
    right-padding-only outputs are then sliced away. This preserves the original
    causal zero-padding numerics without materializing a rank-3 pad/cat tensor,
    both of which fail ExecuTorch 1.0-1.2 dim-order checks for this decoder.
    """

    def __init__(self, original: torch.nn.Module):
        super().__init__()
        if not original.causal or original.pad_mode != "constant":
            raise ValueError("Rewrite only supports causal constant-zero SConv1d")
        self.conv = original.conv
        self.stride = original.stride
        self.padding_total = original.padding_total
        inner_conv = getattr(self.conv, "conv", self.conv)
        if tuple(inner_conv.padding) != (0,):
            raise ValueError("Expected the upstream Conv1d to have zero internal padding")
        inner_conv.padding = (self.padding_total,)

    def forward(
        self,
        value: torch.Tensor,
        cache: object | None = None,
        sample_indices: torch.Tensor | None = None,
        use_cache: bool = False,
        debug: bool = False,
    ) -> torch.Tensor:
        if use_cache or cache is not None or sample_indices is not None or debug:
            raise ValueError("CausalPaddedSConv1d is a non-streaming export wrapper")
        output_length = math.ceil(value.shape[-1] / self.stride)
        return self.conv(value)[..., :output_length].contiguous()


def replace_constant_pad_modules(module: torch.nn.Module) -> list[str]:
    """Replace decoder SConv1d modules with the export-safe equivalent."""
    replaced: list[str] = []
    for name, child in list(module.named_children()):
        if child.__class__.__name__ == "SConv1d":
            setattr(module, name, CausalPaddedSConv1d(child))
            replaced.append(name)
            continue
        for nested in replace_constant_pad_modules(child):
            replaced.append(f"{name}.{nested}")
    return replaced


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
