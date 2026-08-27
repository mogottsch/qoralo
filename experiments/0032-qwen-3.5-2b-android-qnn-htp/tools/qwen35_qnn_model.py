#!/usr/bin/env python3
"""Qwen3.5 decode graph with explicit state for QNN/HTP lowering.

This model adapter is intentionally runtime-agnostic. It keeps full-attention KV
cache and Gated DeltaNet recurrent/causal-convolution state in graph I/O rather
than mutable PyTorch buffers, so every tensor computation can be delegated and
a caller can reset a logical request by zeroing the state inputs.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


# Keep Softplus as one edge op. The experiment's QNN visitor maps this to
# qti.aisw:ElementWiseNeuron(operation=SOFTPLUS), which QAIRT 2.49 documents for
# FP16/FP32 and fixed-point HTP tensors.
try:
    @torch.library.custom_op("qwen35::softplus", mutates_args=())
    def qwen35_softplus(x: torch.Tensor) -> torch.Tensor:
        return F.softplus(x)

    @qwen35_softplus.register_fake
    def _(x: torch.Tensor) -> torch.Tensor:
        return torch.empty_like(x)
except RuntimeError as error:
    # Importing twice in one interpreter is harmless when the schema already
    # belongs to this module.
    if "already" not in str(error).lower():
        raise


def softplus(x: torch.Tensor) -> torch.Tensor:
    return torch.ops.qwen35.softplus.default(x)


class RMSNormUnitOffset(nn.Module):
    """Qwen3.5 RMSNorm: normalize in FP32 and scale by ``1 + weight``."""

    def __init__(self, dim: int, eps: float) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.zeros(dim))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_dtype = x.dtype
        x32 = x.float()
        normalized = x32 * torch.rsqrt((x32 * x32).mean(-1, keepdim=True) + self.eps)
        return (normalized * (1.0 + self.weight.float())).to(input_dtype)


class RMSNormGated(nn.Module):
    def __init__(self, dim: int, eps: float) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.zeros(dim))
        self.eps = eps

    def forward(self, hidden: torch.Tensor, gate: torch.Tensor) -> torch.Tensor:
        input_dtype = hidden.dtype
        hidden32 = hidden.float()
        hidden32 = hidden32 * torch.rsqrt(
            (hidden32 * hidden32).mean(-1, keepdim=True) + self.eps
        )
        hidden32 = hidden32 * self.weight.float()
        hidden32 = hidden32 * F.silu(gate.float())
        return hidden32.to(input_dtype)


def _apply_rope(
    x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor, rotary_dim: int
) -> torch.Tensor:
    # x: [B, H, S, D], cos/sin: [S, rotary_dim/2]
    x_rot, x_pass = x[..., :rotary_dim], x[..., rotary_dim:]
    x1 = x_rot[..., 0::2]
    x2 = x_rot[..., 1::2]
    cos = cos.view(1, 1, cos.shape[0], -1)
    sin = sin.view(1, 1, sin.shape[0], -1)
    rotated = torch.stack((x1 * cos - x2 * sin, x1 * sin + x2 * cos), dim=-1)
    rotated = rotated.flatten(-2)
    return torch.cat((rotated, x_pass), dim=-1)


def _repeat_kv(x: torch.Tensor, repeats: int) -> torch.Tensor:
    if repeats == 1:
        return x
    batch, heads, seq, dim = x.shape
    return (
        x[:, :, None, :, :]
        .expand(batch, heads, repeats, seq, dim)
        .reshape(batch, heads * repeats, seq, dim)
    )


class Qwen35FullAttention(nn.Module):
    def __init__(self, config, output_new_cache_only: bool = True) -> None:
        super().__init__()
        self.n_heads = config.n_heads
        self.n_kv_heads = config.n_kv_heads
        self.head_dim = config.head_dim
        self.dim = config.dim
        self.rotary_dim = int(config.head_dim * config.partial_rotary_factor)
        self.output_new_cache_only = output_new_cache_only
        self.q_norm_fn = RMSNormUnitOffset(self.head_dim, config.norm_eps)
        self.k_norm_fn = RMSNormUnitOffset(self.head_dim, config.norm_eps)
        self.wq = nn.Linear(self.dim, 2 * self.n_heads * self.head_dim, bias=False)
        self.wk = nn.Linear(self.dim, self.n_kv_heads * self.head_dim, bias=False)
        self.wv = nn.Linear(self.dim, self.n_kv_heads * self.head_dim, bias=False)
        self.wo = nn.Linear(self.n_heads * self.head_dim, self.dim, bias=False)

    def forward(
        self,
        hidden: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        attention_mask: torch.Tensor,
        key_cache: torch.Tensor,
        value_cache: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        batch, seq, _ = hidden.shape
        q_and_gate = self.wq(hidden).view(batch, seq, self.n_heads, 2 * self.head_dim)
        query, gate = torch.chunk(q_and_gate, 2, dim=-1)
        key = self.wk(hidden).view(batch, seq, self.n_kv_heads, self.head_dim)
        value = self.wv(hidden).view(batch, seq, self.n_kv_heads, self.head_dim)
        query = self.q_norm_fn(query).transpose(1, 2)
        key = self.k_norm_fn(key).transpose(1, 2)
        value = value.transpose(1, 2)
        query = _apply_rope(query, cos, sin, self.rotary_dim)
        key = _apply_rope(key, cos, sin, self.rotary_dim)
        key_t = key.transpose(2, 3)
        all_key = torch.cat((key_cache, key_t), dim=-1)
        all_value = torch.cat((value_cache, value), dim=2)
        repeated_key = _repeat_kv(all_key, self.n_heads // self.n_kv_heads)
        repeated_value = _repeat_kv(all_value, self.n_heads // self.n_kv_heads)
        scores = torch.matmul(query, repeated_key) / math.sqrt(self.head_dim)
        scores = scores + attention_mask
        probs = F.softmax(scores.float(), dim=-1).to(query.dtype)
        output = torch.matmul(probs, repeated_value)
        output = output.transpose(1, 2).reshape(batch, seq, -1)
        output = output * torch.sigmoid(gate.reshape(batch, seq, -1))
        output = self.wo(output)
        if self.output_new_cache_only:
            return output, key_t, value
        return output, all_key, all_value


class Qwen35GatedDeltaNet(nn.Module):
    def __init__(self, config) -> None:
        super().__init__()
        self.dim = config.dim
        self.num_key_heads = config.linear_num_key_heads
        self.num_value_heads = config.linear_num_value_heads
        self.key_head_dim = config.linear_key_head_dim
        self.value_head_dim = config.linear_value_head_dim
        self.key_dim = self.num_key_heads * self.key_head_dim
        self.value_dim = self.num_value_heads * self.value_head_dim
        self.head_repeat = self.num_value_heads // self.num_key_heads
        self.kernel = config.linear_conv_kernel_dim
        self.conv_dim = 2 * self.key_dim + self.value_dim
        self.in_proj_qkv = nn.Linear(self.dim, self.conv_dim, bias=False)
        self.in_proj_z = nn.Linear(self.dim, self.value_dim, bias=False)
        self.in_proj_b = nn.Linear(self.dim, self.num_value_heads, bias=False)
        self.in_proj_a = nn.Linear(self.dim, self.num_value_heads, bias=False)
        self.conv1d = nn.Conv2d(
            self.conv_dim,
            self.conv_dim,
            kernel_size=(1, self.kernel),
            groups=self.conv_dim,
            bias=False,
        )
        self.dt_bias = nn.Parameter(torch.ones(self.num_value_heads))
        self.A_log = nn.Parameter(torch.zeros(self.num_value_heads))
        self.norm = RMSNormGated(self.value_head_dim, config.norm_eps)
        self.out_proj = nn.Linear(self.value_dim, self.dim, bias=False)

    def forward(
        self,
        hidden: torch.Tensor,
        recurrent_state: torch.Tensor,
        conv_state: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        batch, seq, _ = hidden.shape
        # Canonical campaign uses a one-token decode graph. Prompt prefill calls
        # the same loaded graph sequentially, preserving exact token order.
        torch._check(seq == 1)
        mixed = self.in_proj_qkv(hidden).transpose(1, 2).unsqueeze(2)
        conv_input = torch.cat((conv_state, mixed), dim=-1)
        new_conv_state = conv_input[:, :, :, -self.kernel :]
        mixed = F.silu(self.conv1d(conv_input)[:, :, :, -1:])
        mixed = mixed.squeeze(2).transpose(1, 2)
        query, key, value = torch.split(
            mixed, (self.key_dim, self.key_dim, self.value_dim), dim=-1
        )
        query = query.view(batch, 1, self.num_key_heads, self.key_head_dim)
        key = key.view(batch, 1, self.num_key_heads, self.key_head_dim)
        value = value.view(batch, 1, self.num_value_heads, self.value_head_dim)
        if self.head_repeat > 1:
            query = query.repeat_interleave(self.head_repeat, dim=2)
            key = key.repeat_interleave(self.head_repeat, dim=2)
        query32 = query.float()
        key32 = key.float()
        query32 = query32 * torch.rsqrt(
            (query32 * query32).sum(-1, keepdim=True) + 1e-6
        )
        key32 = key32 * torch.rsqrt((key32 * key32).sum(-1, keepdim=True) + 1e-6)
        query32 = query32[:, 0] * (1.0 / math.sqrt(self.key_head_dim))
        key32 = key32[:, 0]
        value32 = value.float()[:, 0]
        beta = torch.sigmoid(self.in_proj_b(hidden).float())[:, 0]
        decay_log = (
            -torch.exp(self.A_log.float())
            * softplus(self.in_proj_a(hidden).float() + self.dt_bias.float())[:, 0]
        )
        state = recurrent_state.float() * torch.exp(decay_log).unsqueeze(-1).unsqueeze(-1)
        remembered = (state * key32.unsqueeze(-1)).sum(dim=-2)
        delta = (value32 - remembered) * beta.unsqueeze(-1)
        state = state + key32.unsqueeze(-1) * delta.unsqueeze(-2)
        core = (state * query32.unsqueeze(-1)).sum(dim=-2).unsqueeze(1)
        gate = self.in_proj_z(hidden).view(batch, 1, self.num_value_heads, self.value_head_dim)
        core = self.norm(core.reshape(-1, self.value_head_dim), gate.reshape(-1, self.value_head_dim))
        output = self.out_proj(core.view(batch, 1, self.value_dim))
        return output, state.to(recurrent_state.dtype), new_conv_state


class Qwen35DecoderLayer(nn.Module):
    def __init__(self, layer_index: int, config, output_new_cache_only: bool) -> None:
        super().__init__()
        self.is_linear = config.layer_types[layer_index] == "linear_attention"
        self.attention = (
            Qwen35GatedDeltaNet(config)
            if self.is_linear
            else Qwen35FullAttention(config, output_new_cache_only)
        )
        self.attention_norm = RMSNormUnitOffset(config.dim, config.norm_eps)
        self.ffn_norm = RMSNormUnitOffset(config.dim, config.norm_eps)
        self.feed_forward = nn.Module()
        self.feed_forward.w1 = nn.Linear(config.dim, config.hidden_dim, bias=False)
        self.feed_forward.w2 = nn.Linear(config.hidden_dim, config.dim, bias=False)
        self.feed_forward.w3 = nn.Linear(config.dim, config.hidden_dim, bias=False)

        def feed_forward(x: torch.Tensor) -> torch.Tensor:
            return self.feed_forward.w2(F.silu(self.feed_forward.w1(x)) * self.feed_forward.w3(x))

        self._feed_forward = feed_forward

    def forward(self, hidden, cos, sin, mask, state_a, state_b):
        normalized = self.attention_norm(hidden)
        if self.is_linear:
            attention, out_a, out_b = self.attention(normalized, state_a, state_b)
        else:
            attention, out_a, out_b = self.attention(normalized, cos, sin, mask, state_a, state_b)
        hidden = hidden + attention
        hidden = hidden + self._feed_forward(self.ffn_norm(hidden))
        return hidden, out_a, out_b


class Qwen35QnnModel(nn.Module):
    """One-token Qwen3.5 graph whose state is explicit in inputs/outputs."""

    def __init__(self, config, ar_len: int = 1, context_len: int = 4096) -> None:
        super().__init__()
        if ar_len != 1:
            raise ValueError("Only the one-token QNN graph is implemented")
        self.config = config
        self.ar_len = ar_len
        self.context_len = context_len
        self.dim = config.dim
        self.n_layers = config.n_layers
        self.n_heads = config.n_heads
        self.n_kv_heads = config.n_kv_heads
        self.head_dim = config.head_dim
        self.vocab_size = config.vocab_size
        self.layer_types = list(config.layer_types)
        self.tok_embeddings = nn.Embedding(config.vocab_size, config.dim)
        self.layers = nn.ModuleList(
            [Qwen35DecoderLayer(i, config, True) for i in range(config.n_layers)]
        )
        self.norm = RMSNormUnitOffset(config.dim, config.norm_eps)
        self.output = nn.Linear(config.dim, config.vocab_size, bias=False)
        rotary_dim = int(config.head_dim * config.partial_rotary_factor)
        inv_freq = 1.0 / (
            config.rope_freq_base
            ** (torch.arange(0, rotary_dim, 2, dtype=torch.float32) / rotary_dim)
        )
        positions = torch.arange(context_len, dtype=torch.float32)
        freqs = torch.outer(positions, inv_freq)
        self.register_buffer("freqs_cos", freqs.cos(), persistent=False)
        self.register_buffer("freqs_sin", freqs.sin(), persistent=False)

    def forward(
        self,
        tokens: torch.Tensor,
        attention_mask: torch.Tensor,
        input_pos: torch.Tensor,
        *states: torch.Tensor,
    ):
        state_a = states[: self.n_layers]
        state_b = states[self.n_layers :]
        cos = self.freqs_cos[input_pos][0]
        sin = self.freqs_sin[input_pos][0]
        hidden = self.tok_embeddings(tokens)
        out_a: List[torch.Tensor] = []
        out_b: List[torch.Tensor] = []
        for index, layer in enumerate(self.layers):
            hidden, next_a, next_b = layer(
                hidden, cos, sin, attention_mask, state_a[index], state_b[index]
            )
            out_a.append(next_a)
            out_b.append(next_b)
        return (self.output(self.norm(hidden)), *out_a, *out_b)

    def get_example_inputs(self):
        tokens = torch.ones((1, 1), dtype=torch.int32)
        mask = torch.full((1, 1, 1, self.context_len), -65504.0)
        mask[..., -1:] = 0.0
        pos = torch.zeros((1, 1), dtype=torch.int32)
        state_a: List[torch.Tensor] = []
        state_b: List[torch.Tensor] = []
        for layer_type in self.layer_types:
            if layer_type == "linear_attention":
                state_a.append(
                    torch.zeros(
                        1,
                        self.config.linear_num_value_heads,
                        self.config.linear_key_head_dim,
                        self.config.linear_value_head_dim,
                    )
                )
                state_b.append(
                    torch.zeros(1, 2 * self.config.linear_num_key_heads * self.config.linear_key_head_dim + self.config.linear_num_value_heads * self.config.linear_value_head_dim, 1, self.config.linear_conv_kernel_dim)
                )
            else:
                state_a.append(
                    torch.zeros(1, self.n_kv_heads, self.head_dim, self.context_len - 1)
                )
                state_b.append(
                    torch.zeros(1, self.n_kv_heads, self.context_len - 1, self.head_dim)
                )
        return (tokens, mask, pos, *state_a, *state_b)

    def get_metadata(self):
        return {
            "get_ar_len": 1,
            "get_bos_id": 248045,
            "get_eos_id": 248046,
            "get_dim": self.dim,
            "get_head_dim": self.head_dim,
            "get_max_batch_size": 1,
            "get_max_seq_len": self.context_len,
            "get_max_context_len": self.context_len,
            "get_n_bos": 1,
            "get_n_eos": 2,
            "get_n_kv_heads": self.n_kv_heads,
            "get_n_layers": self.n_layers,
            "get_vocab_size": self.vocab_size,
            "get_use_kv_cache": True,
            "get_qwen35_state_abi": 1,
        }


def adapt_converted_state_dict(state_dict: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    """Adapt ExecuTorch's pinned HF→Meta mapping to this QNN adapter."""
    adapted = dict(state_dict)
    for name in list(adapted):
        if name.endswith(".attention.conv1d.weight") and adapted[name].dim() == 3:
            adapted[name] = adapted[name].unsqueeze(2)
    return adapted
