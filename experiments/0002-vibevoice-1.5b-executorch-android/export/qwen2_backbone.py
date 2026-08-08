#!/usr/bin/env python3
"""Tensor-only, fixed-capacity Qwen2 backbone ABI for VibeVoice."""

from __future__ import annotations

from collections.abc import Sequence

import torch
from transformers.cache_utils import Cache, StaticCache


CACHE_TENSORS_PER_LAYER = 2


def cache_tensor_names(num_hidden_layers: int) -> list[str]:
    """Return the normative flat cache order used by every entry point."""
    return [
        f"layer_{layer:02d}_{kind}"
        for layer in range(num_hidden_layers)
        for kind in ("key", "value")
    ]


def flatten_cache(cache: Cache, num_hidden_layers: int) -> tuple[torch.Tensor, ...]:
    """Flatten a Transformers cache as layer-ascending key/value pairs."""
    values: list[torch.Tensor] = []
    for layer in range(num_hidden_layers):
        values.extend((cache.key_cache[layer], cache.value_cache[layer]))
    return tuple(values)


def validate_cache_tensors(
    tensors: Sequence[torch.Tensor], num_hidden_layers: int
) -> None:
    expected = num_hidden_layers * CACHE_TENSORS_PER_LAYER
    if len(tensors) != expected:
        raise ValueError(f"Expected {expected} cache tensors, got {len(tensors)}")
    if not tensors:
        return
    shape = tensors[0].shape
    if len(shape) != 4:
        raise ValueError(f"Cache tensors must be rank 4, got {tuple(shape)}")
    for name, tensor in zip(cache_tensor_names(num_hidden_layers), tensors):
        if tensor.shape != shape:
            raise ValueError(
                f"{name} has shape {tuple(tensor.shape)}, expected {tuple(shape)}"
            )
        if tensor.dtype != tensors[0].dtype:
            raise ValueError(
                f"{name} has dtype {tensor.dtype}, expected {tensors[0].dtype}"
            )


class ExplicitStaticCache(StaticCache):
    """StaticCache facade whose storage is supplied by ordered ABI tensors.

    Construction deliberately bypasses ``StaticCache.__init__`` so a graph does
    not allocate or hide mutable cache state. Qwen2 updates each supplied tensor
    at ``cache_position`` and the wrapper returns every updated tensor.
    """

    def __init__(self, tensors: Sequence[torch.Tensor], num_hidden_layers: int):
        Cache.__init__(self)
        validate_cache_tensors(tensors, num_hidden_layers)
        # Clone so Hugging Face's in-place ``index_copy_`` updates graph-local
        # storage rather than mutating runtime inputs (which Edge rejects for
        # leaf tensors and would make controller ownership ambiguous).
        self.key_cache = [tensor.clone() for tensor in tensors[0::2]]
        self.value_cache = [tensor.clone() for tensor in tensors[1::2]]
        self.max_batch_size = tensors[0].shape[0]
        self.max_cache_len = tensors[0].shape[2]
        self._dtype = tensors[0].dtype


class SpeakerConditioning(torch.nn.Module):
    """Scatter dense speaker features into token embeddings before prefill.

    Audio encoding and the acoustic connector remain outside this boundary.
    ``speaker_embeddings`` is a dense, zero-filled ``[B,S,H]`` tensor and
    ``speaker_input_mask`` selects positions that replace token embeddings.
    """

    def forward(
        self,
        token_embeddings: torch.Tensor,
        speaker_embeddings: torch.Tensor,
        speaker_input_mask: torch.Tensor,
    ) -> torch.Tensor:
        return torch.where(
            speaker_input_mask.unsqueeze(-1), speaker_embeddings, token_embeddings
        )


class _Qwen2FixedCacheBase(torch.nn.Module):
    def __init__(
        self,
        backbone: torch.nn.Module,
        lm_head: torch.nn.Module,
        *,
        num_hidden_layers: int,
        num_key_value_heads: int,
        head_dim: int,
        cache_capacity: int,
    ):
        super().__init__()
        self.backbone = backbone
        self.lm_head = lm_head
        self.num_hidden_layers = num_hidden_layers
        self.num_key_value_heads = num_key_value_heads
        self.head_dim = head_dim
        self.cache_capacity = cache_capacity

    def _run(
        self,
        inputs_embeds: torch.Tensor,
        attention_mask: torch.Tensor,
        position_ids: torch.Tensor,
        cache_position: torch.Tensor,
        cache: ExplicitStaticCache,
    ) -> tuple[torch.Tensor, ...]:
        outputs = self.backbone(
            inputs_embeds=inputs_embeds,
            attention_mask=attention_mask,
            position_ids=position_ids,
            past_key_values=cache,
            cache_position=cache_position,
            use_cache=True,
            output_attentions=False,
            output_hidden_states=False,
            return_dict=True,
        )
        last_hidden_state = outputs.last_hidden_state[:, -1:, :]
        # Token selection is deliberately outside the exported graph. FP32 logits
        # keep native masking/sampling behavior independent of model precision.
        next_token_logits = self.lm_head(last_hidden_state[:, 0, :]).float()
        return (
            last_hidden_state,
            next_token_logits,
            *flatten_cache(outputs.past_key_values, self.num_hidden_layers),
        )


class Qwen2PrefillPrepare(torch.nn.Module):
    """Small first stage: build the fixed causal mask and shared RoPE tensors."""

    def __init__(self, backbone: torch.nn.Module, *, num_hidden_layers: int,
                 num_key_value_heads: int, head_dim: int, cache_capacity: int):
        super().__init__()
        self.backbone = backbone
        self.num_hidden_layers = num_hidden_layers
        self.num_key_value_heads = num_key_value_heads
        self.head_dim = head_dim
        self.cache_capacity = cache_capacity

    def forward(self, inputs_embeds: torch.Tensor, attention_mask: torch.Tensor,
                position_ids: torch.Tensor, cache_position: torch.Tensor
                ) -> tuple[torch.Tensor, ...]:
        shape = (inputs_embeds.shape[0], self.num_key_value_heads,
                 self.cache_capacity, self.head_dim)
        cache = ExplicitStaticCache(
            tuple(inputs_embeds.new_zeros(shape)
                  for _ in range(self.num_hidden_layers * CACHE_TENSORS_PER_LAYER)),
            self.num_hidden_layers,
        )
        causal_mask = self.backbone._update_causal_mask(
            attention_mask, inputs_embeds, cache_position, cache, False
        )
        cos, sin = self.backbone.rotary_emb(inputs_embeds, position_ids)
        return inputs_embeds, causal_mask, cos, sin


class _SingleLayerCache(StaticCache):
    """Cache facade mapping an original decoder layer index to one KV pair."""

    def __init__(self, key: torch.Tensor, value: torch.Tensor, layer_index: int):
        Cache.__init__(self)
        # Qwen2 indexes these lists with the layer's original layer_idx. Reusing
        # the selected clone in earlier, unreachable slots avoids allocating 28
        # full caches while retaining the checkpoint module unchanged.
        selected_key = key.clone()
        selected_value = value.clone()
        self.key_cache = [selected_key] * (layer_index + 1)
        self.value_cache = [selected_value] * (layer_index + 1)
        self.max_batch_size = key.shape[0]
        self.max_cache_len = key.shape[2]
        self._dtype = key.dtype


class Qwen2PrefillLayer(torch.nn.Module):
    """One decoder-layer stage with exactly one explicit key/value cache pair."""

    def __init__(self, layer: torch.nn.Module, layer_index: int):
        super().__init__()
        self.layer = layer
        self.layer_index = layer_index

    def forward(self, hidden_states: torch.Tensor, causal_mask: torch.Tensor,
                cache_position: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor,
                key_cache: torch.Tensor, value_cache: torch.Tensor
                ) -> tuple[torch.Tensor, ...]:
        cache = _SingleLayerCache(key_cache, value_cache, self.layer_index)
        output = self.layer(
            hidden_states,
            attention_mask=causal_mask,
            past_key_value=cache,
            output_attentions=False,
            use_cache=True,
            cache_position=cache_position,
            position_embeddings=(cos, sin),
        )[0]
        return output, cache.key_cache[self.layer_index], cache.value_cache[self.layer_index]


class Qwen2PrefillFinal(torch.nn.Module):
    """Final norm and tied LM head stage."""

    def __init__(self, norm: torch.nn.Module, lm_head: torch.nn.Module):
        super().__init__()
        self.norm = norm
        self.lm_head = lm_head

    def forward(self, hidden_states: torch.Tensor) -> tuple[torch.Tensor, ...]:
        hidden_states = self.norm(hidden_states)[:, -1:, :]
        return hidden_states, self.lm_head(hidden_states[:, 0, :]).float()


class Qwen2Prefill(_Qwen2FixedCacheBase):
    """Prefill entry: conditioned embeddings -> hidden/logits/full KV cache."""

    def forward(
        self,
        inputs_embeds: torch.Tensor,
        attention_mask: torch.Tensor,
        position_ids: torch.Tensor,
        cache_position: torch.Tensor,
    ) -> tuple[torch.Tensor, ...]:
        batch = inputs_embeds.shape[0]
        cache_shape = (
            batch,
            self.num_key_value_heads,
            self.cache_capacity,
            self.head_dim,
        )
        tensors = tuple(
            inputs_embeds.new_zeros(cache_shape)
            for _ in range(self.num_hidden_layers * CACHE_TENSORS_PER_LAYER)
        )
        cache = ExplicitStaticCache(tensors, self.num_hidden_layers)
        return self._run(
            inputs_embeds, attention_mask, position_ids, cache_position, cache
        )


class Qwen2Decode(_Qwen2FixedCacheBase):
    """One-token entry with explicit, ordered, fixed-capacity KV cache I/O."""

    def forward(
        self,
        inputs_embeds: torch.Tensor,
        attention_mask: torch.Tensor,
        position_ids: torch.Tensor,
        cache_position: torch.Tensor,
        *cache_tensors: torch.Tensor,
    ) -> tuple[torch.Tensor, ...]:
        cache = ExplicitStaticCache(cache_tensors, self.num_hidden_layers)
        return self._run(
            inputs_embeds, attention_mask, position_ids, cache_position, cache
        )
