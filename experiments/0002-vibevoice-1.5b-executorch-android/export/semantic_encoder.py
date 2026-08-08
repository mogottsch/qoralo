#!/usr/bin/env python3
"""Semantic-tokenizer encoder loader and explicit streaming-cache ABI."""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path
from typing import Sequence

import torch
from safetensors import safe_open

SEMANTIC_ENCODER_PREFIX = "model.semantic_tokenizer.encoder."
AUDIO_SHAPE = (1, 1, 3200)
OUTPUT_SHAPE = (1, 1, 128)


def build_encoder_config(config: object) -> object:
    """Derive TokenizerEncoder's construction config without the full model."""
    result = copy.deepcopy(config)
    result.dimension = config.vae_dim
    result.n_filters = config.encoder_n_filters
    result.ratios = list(config.encoder_ratios)
    result.depths = (
        [int(value) for value in config.encoder_depths.split("-")]
        if isinstance(config.encoder_depths, str)
        else list(config.encoder_depths)
    )
    result.norm = config.conv_norm
    result.pad_mode = config.pad_mode
    result.bias = config.conv_bias
    result.layernorm_eps = config.layernorm_eps
    result.layernorm_elementwise_affine = config.layernorm_elementwise_affine
    result.mixer_layer = config.mixer_layer
    result.layer_scale_init_value = config.layer_scale_init_value
    result.disable_last_norm = config.disable_last_norm
    return result


def load_semantic_encoder(model_path: Path, dtype: torch.dtype = torch.float32) -> torch.nn.Module:
    """Load only semantic encoder tensors named in the checkpoint index."""
    from vibevoice.modular.configuration_vibevoice import VibeVoiceConfig
    from vibevoice.modular.modular_vibevoice_tokenizer import TokenizerEncoder

    model_path = Path(model_path)
    config = VibeVoiceConfig.from_pretrained(model_path)
    encoder = TokenizerEncoder(build_encoder_config(config.semantic_tokenizer_config))
    index = json.loads((model_path / "model.safetensors.index.json").read_text())
    by_shard: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for checkpoint_name, shard in index["weight_map"].items():
        if checkpoint_name.startswith(SEMANTIC_ENCODER_PREFIX):
            by_shard[shard].append(
                (checkpoint_name, checkpoint_name.removeprefix(SEMANTIC_ENCODER_PREFIX))
            )
    if not by_shard:
        raise RuntimeError(f"No weights with prefix {SEMANTIC_ENCODER_PREFIX!r}")
    state: dict[str, torch.Tensor] = {}
    for shard, names in sorted(by_shard.items()):
        with safe_open(model_path / shard, framework="pt", device="cpu") as handle:
            for checkpoint_name, encoder_name in names:
                state[encoder_name] = handle.get_tensor(checkpoint_name).to(dtype=dtype)
    encoder.load_state_dict(state, strict=True)
    return encoder.to(dtype=dtype).eval()


def semantic_cache_names(encoder: torch.nn.Module) -> tuple[str, ...]:
    """Return the stable lexical ABI order of all stateful causal convolutions."""
    from vibevoice.modular.modular_vibevoice_tokenizer import SConv1d

    names = tuple(sorted(name for name, module in encoder.named_modules() if isinstance(module, SConv1d)))
    if len(names) != 34:
        raise ValueError(f"Expected 34 semantic cache tensors, found {len(names)}")
    return names


def cache_shapes(encoder: torch.nn.Module, names: Sequence[str]) -> tuple[tuple[int, ...], ...]:
    modules = dict(encoder.named_modules())
    return tuple((1, int(modules[name].in_channels), int(modules[name].context_size)) for name in names)


class ExplicitTensorCache:
    """Upstream cache facade backed by ordered, non-aliased ABI tensors."""

    def __init__(self, layer_to_index: dict[str, int], inputs: tuple[torch.Tensor, ...] | None):
        self.layer_to_index = layer_to_index
        self.inputs = inputs
        self.outputs: list[torch.Tensor | None] = [None] * len(layer_to_index)

    def get(self, layer_id: str, sample_indices: torch.Tensor) -> torch.Tensor | None:
        del sample_indices
        return None if self.inputs is None else self.inputs[self.layer_to_index[layer_id]]

    def set(self, layer_id: str, sample_indices: torch.Tensor, states: torch.Tensor) -> None:
        del sample_indices
        self.outputs[self.layer_to_index[layer_id]] = states.clone().contiguous()

    def result(self) -> tuple[torch.Tensor, ...]:
        if any(value is None for value in self.outputs):
            raise RuntimeError("Encoder did not populate every cache output")
        return tuple(value for value in self.outputs if value is not None)


class FunctionalSemanticEncoder(torch.nn.Module):
    """One 3200-sample call with explicit 34-tensor input/output cache state.

    First-call and cached-call modules are exported as separate PTE methods because
    an absent cache is not a tensor. Output order is semantic_features followed by
    cache tensors in ``cache_names`` order.
    """

    def __init__(self, encoder: torch.nn.Module, cache_names: Sequence[str], cached: bool):
        super().__init__()
        self.encoder = encoder
        self.cache_names = tuple(cache_names)
        self.cached = cached
        modules = dict(encoder.named_modules())
        self.layer_to_index = {
            modules[name].layer_id: index for index, name in enumerate(self.cache_names)
        }
        if len(self.layer_to_index) != len(self.cache_names):
            raise ValueError("Semantic cache layer IDs are not unique")

    def forward(self, audio: torch.Tensor, *cache_inputs: torch.Tensor) -> tuple[torch.Tensor, ...]:
        if self.cached:
            if len(cache_inputs) != len(self.cache_names):
                raise ValueError("Cached call requires all 34 cache tensors")
            inputs: tuple[torch.Tensor, ...] | None = tuple(cache_inputs)
        else:
            if cache_inputs:
                raise ValueError("Reset/first call accepts no cache tensors")
            inputs = None
        cache = ExplicitTensorCache(self.layer_to_index, inputs)
        sample_indices = torch.zeros((audio.shape[0],), dtype=torch.int64, device=audio.device)
        features = self.encoder(
            audio, cache=cache, sample_indices=sample_indices, use_cache=True, debug=False
        ).permute(0, 2, 1).contiguous()
        return (features, *cache.result())


def validate_call_inputs(
    audio: torch.Tensor,
    caches: Sequence[torch.Tensor],
    expected_shapes: Sequence[Sequence[int]],
    *,
    cached: bool,
) -> tuple[torch.Tensor, ...]:
    """Strict ABI validation used before export and by tests/tooling."""
    if tuple(audio.shape) != AUDIO_SHAPE or audio.dtype != torch.float32:
        raise ValueError(f"audio must be float32 {AUDIO_SHAPE}, got {audio.dtype} {tuple(audio.shape)}")
    if not audio.is_contiguous() or not torch.isfinite(audio).all():
        raise ValueError("audio must be contiguous and finite")
    expected_count = len(expected_shapes) if cached else 0
    if len(caches) != expected_count:
        raise ValueError(f"Expected {expected_count} cache tensors, got {len(caches)}")
    shapes_to_check = expected_shapes if cached else ()
    for index, (value, shape) in enumerate(zip(caches, shapes_to_check, strict=True)):
        if tuple(value.shape) != tuple(shape) or value.dtype != torch.float32:
            raise ValueError(f"cache[{index}] must be float32 {tuple(shape)}, got {value.dtype} {tuple(value.shape)}")
        if not value.is_contiguous() or not torch.isfinite(value).all():
            raise ValueError(f"cache[{index}] must be contiguous and finite")
    return (audio, *caches)
