#!/usr/bin/env python3
"""ONNX STFT + real-valued iSTFT decomposition for faithful Kokoro export.

Eager execution uses PyTorch's own FFT for the analysis transform. During the
legacy ONNX export only, the custom autograd symbolic emits the standard ONNX
STFT operator (opset >= 17). The inverse remains the mathematically equivalent
real-valued overlap-add from exact_stft.py because ONNX has no inverse-STFT op.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from exact_stft import ExactRealSTFT


class _OnnxSTFT(torch.autograd.Function):
    @staticmethod
    def forward(
        ctx: object,
        padded_waveform: torch.Tensor,
        window: torch.Tensor,
        frame_length: int,
        frame_step: int,
    ) -> torch.Tensor:
        del ctx
        value = torch.stft(
            padded_waveform,
            n_fft=frame_length,
            hop_length=frame_step,
            win_length=frame_length,
            window=window,
            center=False,
            return_complex=True,
        )
        return torch.view_as_real(value)

    @staticmethod
    def symbolic(
        graph: object,
        padded_waveform: object,
        window: object,
        frame_length: int,
        frame_step: int,
    ) -> object:
        axes = graph.op(
            "Constant", value_t=torch.tensor([2], dtype=torch.int64)
        )
        signal = graph.op("Unsqueeze", padded_waveform, axes)
        step = graph.op(
            "Constant",
            value_t=torch.tensor(frame_step, dtype=torch.int64),
        )
        length = graph.op(
            "Constant",
            value_t=torch.tensor(frame_length, dtype=torch.int64),
        )
        # ONNX STFT: [batch, frames, frequency, real_or_imag].
        value = graph.op(
            "STFT", signal, step, window, length, onesided_i=1
        )
        # Match torch.stft/view_as_real: [batch, frequency, frames, 2].
        return graph.op("Transpose", value, perm_i=[0, 2, 1, 3])


class OnnxExactSTFT(ExactRealSTFT):
    """Drop-in replacement for Kokoro's TorchSTFT with an ONNX symbolic."""

    def __init__(self, filter_length: int = 20, hop_length: int = 5, win_length: int = 20):
        super().__init__(filter_length, hop_length, win_length)
        window = torch.hann_window(win_length, periodic=True, dtype=torch.float32)
        self.register_buffer("analysis_window", window)

    def transform(self, waveform: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if waveform.dim() != 2:
            raise ValueError("expected waveform shape [batch, time]")
        pad = self.filter_length // 2
        padded = F.pad(waveform, (pad, pad), mode="reflect")
        complex_parts = _OnnxSTFT.apply(
            padded, self.analysis_window, self.filter_length, self.hop_length
        )
        real = complex_parts[..., 0]
        imag = complex_parts[..., 1]
        magnitude = torch.sqrt(real.square() + imag.square())
        phase = torch.atan2(imag, real)
        return magnitude, phase
