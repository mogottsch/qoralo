#!/usr/bin/env python3
"""Frozen four-call cache ABI adapters and transactional host controller.

The exported methods are deliberately pure: all recurrent state crosses the method
boundary as fixed-capacity tensors.  Validation and atomic commit live in the host
controller rather than relying on mutable model/runtime state.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import torch

CACHE_COUNT = 34


def load_contract(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text())
    if value.get("status") != "frozen_pre_export":
        raise ValueError("four-call ABI is not frozen_pre_export")
    return value


def tensor_sha256(value: torch.Tensor) -> str:
    return hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def canonical_cache(value: torch.Tensor, capacity_shape: Sequence[int]) -> torch.Tensor:
    """Left-align a variable trace cache in a zero-filled ABI capacity tensor."""
    shape = tuple(int(item) for item in capacity_shape)
    if value.dtype != torch.float32 or tuple(value.shape[:-1]) != shape[:-1]:
        raise ValueError(f"cache metadata mismatch: {value.dtype} {tuple(value.shape)} vs {shape}")
    if value.shape[-1] > shape[-1]:
        raise ValueError("cache exceeds frozen capacity")
    result = torch.zeros(shape, dtype=torch.float32)
    result[..., : value.shape[-1]].copy_(value)
    return result.contiguous()


def trace_state(call: dict[str, object], method: dict[str, object], side: str) -> tuple[torch.Tensor, ...]:
    domain = "decoder" if method["method_order"] == 0 else "semantic"
    values = call[domain][f"{side}_cache"]
    return tuple(
        canonical_cache(values[item["source_name"]], item["capacity_shape"])
        for item in method["caches"]
    )


def _padding_is_zero(value: torch.Tensor, valid: int) -> bool:
    return valid == value.shape[-1] or bool(torch.count_nonzero(value[..., valid:]) == 0)


def validate_state(
    contract: dict[str, object], domain: str, phase: int, lengths: torch.Tensor,
    caches: Sequence[torch.Tensor], *, post: bool = False,
) -> None:
    if phase not in range(4):
        raise ValueError(f"phase {phase} is outside the four-call boundary")
    method = contract["methods"]["acoustic_decode" if domain == "decoder" else "semantic_encode"]
    transition = contract["call_transitions"][phase]
    key = f"{domain}_{'post' if post else 'pre'}_valid_lengths"
    expected = torch.tensor(transition[key], dtype=torch.int32)
    if lengths.dtype != torch.int32 or tuple(lengths.shape) != (CACHE_COUNT,) or not torch.equal(lengths.cpu(), expected):
        raise ValueError(f"{domain} valid lengths do not match frozen phase {phase} {key}")
    if len(caches) != CACHE_COUNT:
        raise ValueError(f"{domain} requires {CACHE_COUNT} caches, got {len(caches)}")
    for index, (value, spec, valid) in enumerate(zip(caches, method["caches"], expected.tolist(), strict=True)):
        shape = tuple(spec["capacity_shape"])
        if value.dtype != torch.float32 or tuple(value.shape) != shape or not value.is_contiguous():
            raise ValueError(f"{domain} cache {index} must be contiguous float32 {shape}")
        if not bool(torch.isfinite(value).all()):
            raise ValueError(f"{domain} cache {index} contains non-finite values")
        if not _padding_is_zero(value, valid):
            raise ValueError(f"{domain} cache {index} has non-zero padding")


class FixedTensorCache:
    """Upstream cache facade backed by fixed ABI tensors and valid lengths."""

    def __init__(self, layer_to_index: dict[str, int], inputs: Sequence[torch.Tensor], lengths: torch.Tensor):
        self.layer_to_index = layer_to_index
        self.inputs = tuple(inputs)
        self.lengths = lengths
        self.outputs: list[torch.Tensor | None] = [None] * len(inputs)

    def get(self, layer_id: str, sample_indices: torch.Tensor) -> torch.Tensor:
        del sample_indices
        return self.inputs[self.layer_to_index[layer_id]].unsqueeze(0)

    def valid_length(self, layer_id: str) -> torch.Tensor:
        return self.lengths[self.layer_to_index[layer_id]]

    def set(self, layer_id: str, sample_indices: torch.Tensor, states: torch.Tensor) -> None:
        del sample_indices
        index = self.layer_to_index[layer_id]
        capacity = self.inputs[index].shape[-1]
        if states.shape[-1] != capacity:
            raise RuntimeError(f"adapter produced {states.shape[-1]} values for capacity {capacity}")
        self.outputs[index] = states.squeeze(0).clone().contiguous()

    def result(self) -> tuple[torch.Tensor, ...]:
        if any(value is None for value in self.outputs):
            raise RuntimeError("method did not populate every cache output")
        return tuple(value for value in self.outputs if value is not None)


class FixedSConvTranspose1d(torch.nn.Module):
    """SConvTranspose1d with tensor-selected, left-aligned fixed cache state.

    Every possible history length is represented by a static candidate. Selection
    happens with tensor equality, so no data-dependent Python slicing enters the
    exported graph. One convolution is evaluated after selection.
    """

    def __init__(self, original: torch.nn.Module):
        super().__init__()
        self.convtr = original.convtr
        self.causal = original.causal
        self.trim_right_ratio = original.trim_right_ratio
        self.padding_total = original.padding_total
        self.context_size = original.context_size
        self.stride = original.stride
        self._layer_id = original.layer_id

    @property
    def layer_id(self) -> str:
        return self._layer_id

    def forward(self, x: torch.Tensor, cache: FixedTensorCache | None = None,
                sample_indices: torch.Tensor | None = None, use_cache: bool = False,
                debug: bool = False) -> torch.Tensor:
        if not use_cache or cache is None or sample_indices is None or debug:
            raise ValueError("fixed transpose adapter requires explicit streaming state")
        stored = cache.get(self.layer_id, sample_indices)
        valid = cache.valid_length(self.layer_id)
        capacity = stored.shape[-1]
        candidates = []
        for width in range(capacity + 1):
            candidates.append(torch.cat((stored[..., :width], x, x.new_zeros((*x.shape[:-1], capacity - width))), dim=-1))
        packed = torch.zeros_like(candidates[0])
        for width, candidate in enumerate(candidates):
            packed = packed + candidate * (valid == width).to(dtype=x.dtype)
        full = self.convtr(packed)
        padding_right = int(math.ceil(self.padding_total * self.trim_right_ratio)) if self.causal else self.padding_total // 2
        padding_left = self.padding_total - padding_right
        if padding_left + padding_right:
            full = full[..., padding_left : full.shape[-1] - padding_right]
        expected = x.shape[-1] * self.stride
        outputs = []
        next_states = []
        for width in range(capacity + 1):
            start = width * self.stride
            outputs.append(full[..., start : start + expected])
            history = torch.cat((stored[..., :width], x), dim=-1)
            history = history[..., -capacity:]
            next_states.append(torch.cat((history, x.new_zeros((*x.shape[:-1], capacity - history.shape[-1]))), dim=-1))
        output = torch.zeros_like(outputs[0])
        next_cache = torch.zeros_like(stored)
        for width, (candidate_output, candidate_cache) in enumerate(zip(outputs, next_states, strict=True)):
            selected = (valid == width).to(dtype=x.dtype)
            output = output + candidate_output * selected
            next_cache = next_cache + candidate_cache * selected
        cache.set(self.layer_id, sample_indices, next_cache)
        return output.contiguous()


def _fixed_transpose_class():
    """Retain upstream isinstance dispatch while replacing its implementation."""
    from vibevoice.modular.modular_vibevoice_tokenizer import SConvTranspose1d

    class FixedTranspose(SConvTranspose1d):
        def __init__(self, original: SConvTranspose1d):
            torch.nn.Module.__init__(self)
            self.convtr = original.convtr
            self.causal = original.causal
            self.trim_right_ratio = original.trim_right_ratio
            self.padding_total = original.padding_total
            self.context_size = original.context_size
            self.stride = original.stride
            self._layer_id = original.layer_id

        forward = FixedSConvTranspose1d.forward

    return FixedTranspose


def replace_transpose(module: torch.nn.Module) -> list[str]:
    from vibevoice.modular.modular_vibevoice_tokenizer import SConvTranspose1d
    replacement = _fixed_transpose_class()
    replaced: list[str] = []
    for name, child in list(module.named_children()):
        if isinstance(child, SConvTranspose1d):
            setattr(module, name, replacement(child))
            replaced.append(name)
        else:
            replaced.extend(f"{name}.{nested}" for nested in replace_transpose(child))
    return replaced


class FourCallAudioMethod(torch.nn.Module):
    """One frozen acoustic or semantic method with the normative tensor order."""

    def __init__(self, component: torch.nn.Module, domain: str, cache_specs: Sequence[dict[str, object]], transitions: Sequence[dict[str, object]]):
        super().__init__()
        if domain not in ("decoder", "semantic"):
            raise ValueError(domain)
        self.component = component
        self.domain = domain
        self.cache_names = tuple(item["source_name"].removesuffix("/sample_0") for item in cache_specs)
        modules = dict(component.named_modules())
        self.layer_to_index = {modules[name].layer_id: index for index, name in enumerate(self.cache_names)}
        table = [item[f"{domain}_post_valid_lengths"] for item in transitions]
        self.register_buffer("next_lengths", torch.tensor(table, dtype=torch.int32), persistent=False)

    def forward(self, primary: torch.Tensor, phase: torch.Tensor, valid_lengths: torch.Tensor,
                *cache_inputs: torch.Tensor) -> tuple[torch.Tensor, ...]:
        cache = FixedTensorCache(self.layer_to_index, cache_inputs, valid_lengths)
        sample_indices = torch.zeros((1,), dtype=torch.int64, device=primary.device)
        if self.domain == "decoder":
            value = self.component(primary.permute(0, 2, 1).contiguous(), cache=cache,
                                   sample_indices=sample_indices, use_cache=True, debug=False)
        else:
            value = self.component(primary, cache=cache, sample_indices=sample_indices,
                                   use_cache=True, debug=False).permute(0, 2, 1).contiguous()
        next_lengths = torch.index_select(self.next_lengths, 0, phase.to(torch.int64).reshape(1)).squeeze(0)
        return (value, next_lengths, *cache.result())


@dataclass
class DomainState:
    lengths: torch.Tensor
    caches: tuple[torch.Tensor, ...]


class AtomicFourCallController:
    """Validate both methods and commit their outputs together or not at all."""

    def __init__(self, contract: dict[str, object]):
        self.contract = contract
        self.reset()

    def reset(self) -> None:
        self.phase = 0
        states = {}
        for domain, name in (("decoder", "acoustic_decode"), ("semantic", "semantic_encode")):
            specs = self.contract["methods"][name]["caches"]
            states[domain] = DomainState(torch.zeros(CACHE_COUNT, dtype=torch.int32), tuple(torch.zeros(tuple(item["capacity_shape"]), dtype=torch.float32) for item in specs))
        self.decoder, self.semantic = states["decoder"], states["semantic"]

    def execute(self, decoder_latent: torch.Tensor,
                decoder_method: Callable[..., Sequence[torch.Tensor]],
                semantic_method: Callable[..., Sequence[torch.Tensor]]) -> tuple[torch.Tensor, torch.Tensor]:
        if self.phase >= 4:
            raise ValueError("phase 4 is the validation boundary, not a steady-state entry")
        validate_state(self.contract, "decoder", self.phase, self.decoder.lengths, self.decoder.caches)
        validate_state(self.contract, "semantic", self.phase, self.semantic.lengths, self.semantic.caches)
        before = [tensor_sha256(value) for value in (*self.decoder.caches, *self.semantic.caches)]
        phase = torch.tensor(self.phase, dtype=torch.int32)
        decoder_outputs = tuple(decoder_method(decoder_latent, phase, self.decoder.lengths, *self.decoder.caches))
        if len(decoder_outputs) != 36:
            raise ValueError("acoustic_decode returned the wrong tensor count")
        pcm, decoder_lengths, *decoder_caches = decoder_outputs
        semantic_outputs = tuple(semantic_method(pcm, phase, self.semantic.lengths, *self.semantic.caches))
        if len(semantic_outputs) != 36:
            raise ValueError("semantic_encode returned the wrong tensor count")
        semantic, semantic_lengths, *semantic_caches = semantic_outputs
        after = [tensor_sha256(value) for value in (*self.decoder.caches, *self.semantic.caches)]
        if before != after:
            raise ValueError("method mutated input cache storage")
        for label, value, shape in (("pcm", pcm, (1, 1, 3200)), ("semantic", semantic, (1, 1, 128))):
            if value.dtype != torch.float32 or tuple(value.shape) != shape or not bool(torch.isfinite(value).all()):
                raise ValueError(f"invalid {label} output")
        validate_state(self.contract, "decoder", self.phase, decoder_lengths, decoder_caches, post=True)
        validate_state(self.contract, "semantic", self.phase, semantic_lengths, semantic_caches, post=True)
        self.decoder = DomainState(decoder_lengths.clone(), tuple(value.clone() for value in decoder_caches))
        self.semantic = DomainState(semantic_lengths.clone(), tuple(value.clone() for value in semantic_caches))
        self.phase += 1
        return pcm, semantic
