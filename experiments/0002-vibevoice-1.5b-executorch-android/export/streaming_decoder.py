#!/usr/bin/env python3
"""Tensor-only functional streaming adapter for the VibeVoice acoustic decoder."""

from __future__ import annotations

from typing import Sequence

import torch


def cache_module_names(fixture: dict[str, object], section: str) -> list[str]:
    """Return the fixture's stable alphabetical cache ABI ordering."""
    cache = fixture[section]
    if not isinstance(cache, dict):
        raise TypeError(f"Expected {section} to be a dictionary")
    suffix = "/sample_0"
    names = []
    for key in cache:
        if not key.endswith(suffix):
            raise ValueError(f"Unsupported cache key: {key}")
        names.append(key.removesuffix(suffix))
    return sorted(names)


class StaticTensorCache:
    """Trace-time cache facade backed only by an ordered tensor tuple.

    Layer IDs are used only for static Python lookup while torch.export traces the
    graph. They do not cross the exported ABI. Runtime inputs and outputs are the
    ordered tensor tuple described by the committed fixture manifest.
    """

    def __init__(
        self,
        layer_to_index: dict[str, int],
        inputs: tuple[torch.Tensor, ...] | None,
    ) -> None:
        self.layer_to_index = layer_to_index
        self.inputs = inputs
        self.outputs: list[torch.Tensor | None] = [None] * len(layer_to_index)

    def get(self, layer_id: str, sample_indices: torch.Tensor) -> torch.Tensor | None:
        del sample_indices
        if self.inputs is None:
            return None
        return self.inputs[self.layer_to_index[layer_id]]

    def set(
        self, layer_id: str, sample_indices: torch.Tensor, states: torch.Tensor
    ) -> None:
        del sample_indices
        # Materialize cache outputs so they do not alias intermediate tensors.
        # Alias outputs can create dependency cycles during XNNPACK partitioning.
        self.outputs[self.layer_to_index[layer_id]] = states.clone()

    def result(self) -> tuple[torch.Tensor, ...]:
        if any(value is None for value in self.outputs):
            raise RuntimeError("Decoder did not populate every cache output")
        return tuple(value for value in self.outputs if value is not None)


def _safe_streaming_sconv1d_class():
    from vibevoice.modular.modular_vibevoice_tokenizer import SConv1d

    class SafeStreamingSConv1d(SConv1d):
        """SConv1d streaming semantics without rank-3 pad/cat before Conv1d."""

        def __init__(self, original: SConv1d):
            torch.nn.Module.__init__(self)
            if not original.causal or original.pad_mode != "constant":
                raise ValueError("Only causal constant-zero SConv1d is supported")
            if original.stride != 1 or original.dilation != 1:
                raise ValueError("Streaming adapter currently requires stride=dilation=1")
            self.conv = original.conv
            self.causal = original.causal
            self.pad_mode = original.pad_mode
            self.kernel_size = original.kernel_size
            self.dilation = original.dilation
            self.stride = original.stride
            self.in_channels = original.in_channels
            self.out_channels = original.out_channels
            self.context_size = original.context_size
            self.padding_total = original.padding_total
            self._layer_id = original.layer_id
            inner = getattr(self.conv, "conv", self.conv)
            if tuple(inner.padding) != (0,):
                raise ValueError("Expected zero internal Conv1d padding")
            if inner.kernel_size[0] != self.context_size + 1:
                raise ValueError("Expected context size to equal kernel size minus one")
            inner.padding = (self.context_size,)
            if inner.groups == 1:
                for position in range(self.context_size):
                    self.register_buffer(
                        f"cache_kernel_{position}",
                        inner.weight[..., : self.context_size - position]
                        .detach()
                        .clone()
                        .contiguous(),
                        persistent=True,
                    )
            for width in range(1, self.context_size):
                shift = torch.zeros(self.context_size, self.context_size)
                for output_position in range(self.context_size - width):
                    shift[output_position + width, output_position] = 1
                insert = torch.zeros(width, self.context_size)
                for input_position in range(width):
                    insert[input_position, self.context_size - width + input_position] = 1
                self.register_buffer(f"cache_shift_{width}", shift, persistent=True)
                self.register_buffer(f"cache_insert_{width}", insert, persistent=True)

        def forward(
            self,
            value: torch.Tensor,
            cache: StaticTensorCache | None = None,
            sample_indices: torch.Tensor | None = None,
            use_cache: bool = False,
            debug: bool = False,
        ) -> torch.Tensor:
            if not use_cache or cache is None or sample_indices is None or debug:
                raise ValueError("SafeStreamingSConv1d requires explicit streaming cache")
            cached = cache.get(self.layer_id, sample_indices)
            has_history = cached is not None
            if cached is None:
                cached = value.new_zeros(
                    (value.shape[0], value.shape[1], self.context_size)
                )

            # Internal symmetric padding gives the zero-history causal result in
            # the first T positions. Add only the contribution from real cache
            # values to those positions, avoiding a rank-3 cat before Conv1d.
            base = self.conv(value)[..., : value.shape[-1]]
            inner = getattr(self.conv, "conv", self.conv)
            weight = inner.weight
            prefix = min(self.context_size, value.shape[-1])
            if has_history:
                corrected: list[torch.Tensor] = []
                for position in range(prefix):
                    cache_width = self.context_size - position
                    if inner.groups == 1:
                        contribution = torch.nn.functional.conv1d(
                            cached[..., position:],
                            getattr(self, f"cache_kernel_{position}"),
                            bias=None,
                        )[..., 0]
                    elif inner.groups == inner.in_channels == inner.out_channels:
                        contribution = (
                            cached[..., position:]
                            * weight[:, 0, :cache_width].unsqueeze(0)
                        ).sum(dim=-1)
                    else:
                        raise ValueError("Unsupported grouped Conv1d layout")
                    corrected.append(base[..., position] + contribution)
                if prefix:
                    output = torch.stack(corrected, dim=-1)
                    if value.shape[-1] > prefix:
                        output = torch.cat((output, base[..., prefix:]), dim=-1)
                else:
                    output = base
            else:
                output = base

            if value.shape[-1] >= self.context_size:
                next_cache = value[..., -self.context_size :]
            else:
                # Fixed matrix updates avoid rank-3 cat/select layout ambiguity
                # at singleton-time XNNPACK boundaries.
                width = value.shape[-1]
                shift = getattr(self, f"cache_shift_{width}")
                insert = getattr(self, f"cache_insert_{width}")
                next_cache = torch.matmul(cached, shift) + torch.matmul(value, insert)
            cache.set(self.layer_id, sample_indices, next_cache.contiguous())
            return output.contiguous()

    return SafeStreamingSConv1d


def replace_streaming_sconv1d(module: torch.nn.Module) -> list[str]:
    """Replace all SConv1d instances while retaining upstream isinstance checks."""
    from vibevoice.modular.modular_vibevoice_tokenizer import SConv1d

    replacement_class = _safe_streaming_sconv1d_class()
    replaced: list[str] = []
    for name, child in list(module.named_children()):
        if isinstance(child, SConv1d):
            setattr(module, name, replacement_class(child))
            replaced.append(name)
            continue
        for nested in replace_streaming_sconv1d(child):
            replaced.append(f"{name}.{nested}")
    return replaced


class FunctionalStreamingDecoder(torch.nn.Module):
    """Fixed-shape decoder with explicit stable cache tensor inputs/outputs."""

    def __init__(
        self,
        decoder: torch.nn.Module,
        cache_names: Sequence[str],
        cached: bool,
    ) -> None:
        super().__init__()
        self.decoder = decoder
        self.cache_names = tuple(cache_names)
        self.cached = cached
        module_by_name = dict(decoder.named_modules())
        layer_to_index: dict[str, int] = {}
        for index, name in enumerate(self.cache_names):
            if name not in module_by_name:
                raise KeyError(f"Cache module not found in decoder: {name}")
            layer_id = module_by_name[name].layer_id
            layer_to_index[layer_id] = index
        if len(layer_to_index) != len(self.cache_names):
            raise ValueError("Cache layer IDs are not unique")
        self.layer_to_index = layer_to_index

    def forward(
        self, latent_b64t: torch.Tensor, *cache_inputs: torch.Tensor
    ) -> tuple[torch.Tensor, ...]:
        if self.cached:
            if len(cache_inputs) != len(self.cache_names):
                raise ValueError("Cached entry point requires every cache tensor")
            inputs: tuple[torch.Tensor, ...] | None = tuple(cache_inputs)
        else:
            if cache_inputs:
                raise ValueError("First-chunk entry point has no cache inputs")
            inputs = None
        cache = StaticTensorCache(self.layer_to_index, inputs)
        sample_indices = torch.zeros(
            (latent_b64t.shape[0],), dtype=torch.int64, device=latent_b64t.device
        )
        pcm = self.decoder(
            latent_b64t,
            cache=cache,
            sample_indices=sample_indices,
            use_cache=True,
            debug=False,
        )
        return (pcm, *cache.result())


class FunctionalStreamingSegment(torch.nn.Module):
    """One decoder pipeline segment with explicit local cache tensors."""

    def __init__(
        self,
        decoder: torch.nn.Module,
        segment: int,
        cache_names: Sequence[str],
        cached: bool,
    ) -> None:
        super().__init__()
        if segment not in range(8):
            raise ValueError("segment must be 0..7 (seven stages plus head)")
        self.segment = segment
        self.cached = cached
        self.cache_names = tuple(cache_names)
        if segment < 7:
            self.upsample = decoder.upsample_layers[segment]
            self.stage = decoder.stages[segment]
            self.norm = None
            self.head = None
        else:
            self.upsample = None
            self.stage = None
            self.norm = decoder.norm
            self.head = decoder.head
        module_by_name = dict(decoder.named_modules())
        self.layer_to_index = {
            module_by_name[name].layer_id: index
            for index, name in enumerate(self.cache_names)
        }

    def forward(
        self, value: torch.Tensor, *cache_inputs: torch.Tensor
    ) -> tuple[torch.Tensor, ...]:
        if self.cached:
            if len(cache_inputs) != len(self.cache_names):
                raise ValueError("Segment requires every local cache tensor")
            inputs: tuple[torch.Tensor, ...] | None = tuple(cache_inputs)
        else:
            if cache_inputs:
                raise ValueError("First segment entry has no cache inputs")
            inputs = None
        cache = StaticTensorCache(self.layer_to_index, inputs)
        sample_indices = torch.zeros(
            (value.shape[0],), dtype=torch.int64, device=value.device
        )
        if self.segment < 7:
            for layer in self.upsample:
                value = layer(
                    value,
                    cache=cache,
                    sample_indices=sample_indices,
                    use_cache=True,
                    debug=False,
                )
            for block in self.stage:
                residual = value
                value = block.norm(value)
                value = block.mixer.conv(
                    value,
                    cache=cache,
                    sample_indices=sample_indices,
                    use_cache=True,
                    debug=False,
                )
                if block.gamma is not None:
                    value = value * block.gamma.unsqueeze(-1)
                value = residual + value
                residual = value
                value = block.ffn_norm(value)
                value = value.permute(0, 2, 1)
                value = block.ffn(value)
                value = value.permute(0, 2, 1)
                if block.ffn_gamma is not None:
                    value = value * block.ffn_gamma.unsqueeze(-1)
                value = residual + value
        else:
            value = self.norm(value)
            value = self.head(
                value,
                cache=cache,
                sample_indices=sample_indices,
                use_cache=True,
                debug=False,
            )
        return (value.contiguous(), *cache.result())


def segment_cache_names(cache_names: Sequence[str], segment: int) -> list[str]:
    if segment < 7:
        prefixes = (f"upsample_layers.{segment}.", f"stages.{segment}.")
        return [name for name in cache_names if name.startswith(prefixes)]
    return [name for name in cache_names if name == "head"]


def fixture_inputs(
    fixture: dict[str, object], cache_names: Sequence[str], cached: bool
) -> tuple[torch.Tensor, ...]:
    latent = fixture["latent_b64t"].to(dtype=torch.float32).contiguous()
    if not cached:
        return (latent,)
    cache = fixture["pre_cache"]
    return (
        latent,
        *(cache[f"{name}/sample_0"].unsqueeze(0).contiguous() for name in cache_names),
    )


def fixture_outputs(
    fixture: dict[str, object], cache_names: Sequence[str]
) -> tuple[torch.Tensor, ...]:
    cache = fixture["post_cache"]
    return (
        fixture["pcm"].to(dtype=torch.float32).contiguous(),
        *(cache[f"{name}/sample_0"].unsqueeze(0).contiguous() for name in cache_names),
    )
