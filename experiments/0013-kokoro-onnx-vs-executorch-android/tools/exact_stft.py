#!/usr/bin/env python3
"""Real-valued, exportable decomposition of Kokoro's torch.stft/torch.istft.

Kokoro's released source uses complex PyTorch STFT operations, which are not a
portable mobile graph interface. This module expresses the same one-sided DFT,
Hann window, centered reflection padding, overlap-add, and window-envelope
normalization with real Conv1d/ConvTranspose1d operations. It is deliberately
narrow: only the even-N, center=True, periodic-Hann configuration used by
Kokoro v1.0 is supported.
"""
from __future__ import annotations

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class ExactRealSTFT(nn.Module):
    def __init__(self, filter_length: int = 20, hop_length: int = 5, win_length: int = 20):
        super().__init__()
        if filter_length <= 0 or filter_length % 2:
            raise ValueError("only positive even FFT lengths are supported")
        if win_length != filter_length:
            raise ValueError("Kokoro requires win_length == filter_length")
        if hop_length <= 0:
            raise ValueError("hop_length must be positive")
        self.filter_length = filter_length
        self.hop_length = hop_length
        self.win_length = win_length
        self.freq_bins = filter_length // 2 + 1
        window = torch.hann_window(win_length, periodic=True, dtype=torch.float32)

        n = torch.arange(filter_length, dtype=torch.float64)
        k = torch.arange(self.freq_bins, dtype=torch.float64).unsqueeze(1)
        angle = 2.0 * math.pi * k * n / filter_length
        analysis_real = torch.cos(angle) * window.double()
        analysis_imag = -torch.sin(angle) * window.double()

        factors = torch.full((self.freq_bins, 1), 2.0, dtype=torch.float64)
        factors[0] = 1.0
        factors[-1] = 1.0
        synthesis_real = factors * torch.cos(angle) * window.double() / filter_length
        synthesis_imag = -factors * torch.sin(angle) * window.double() / filter_length

        self.register_buffer("analysis_real", analysis_real.float().unsqueeze(1))
        self.register_buffer("analysis_imag", analysis_imag.float().unsqueeze(1))
        self.register_buffer("synthesis_real", synthesis_real.float().unsqueeze(1))
        self.register_buffer("synthesis_imag", synthesis_imag.float().unsqueeze(1))
        self.register_buffer("window_square", window.square().reshape(1, 1, -1))

    def transform(self, waveform: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if waveform.dim() != 2:
            raise ValueError("expected waveform shape [batch, time]")
        pad = self.filter_length // 2
        x = F.pad(waveform, (pad, pad), mode="reflect").unsqueeze(1)
        real = F.conv1d(x, self.analysis_real, stride=self.hop_length)
        imag = F.conv1d(x, self.analysis_imag, stride=self.hop_length)
        magnitude = torch.sqrt(real.square() + imag.square())
        phase = torch.atan2(imag, real)
        return magnitude, phase

    def inverse(self, magnitude: torch.Tensor, phase: torch.Tensor) -> torch.Tensor:
        if magnitude.dim() != 3 or phase.shape != magnitude.shape:
            raise ValueError("expected matching [batch, frequency, frame] tensors")
        real = magnitude * torch.cos(phase)
        imag = magnitude * torch.sin(phase)
        numerator = F.conv_transpose1d(
            real, self.synthesis_real, stride=self.hop_length
        ) + F.conv_transpose1d(
            imag, self.synthesis_imag, stride=self.hop_length
        )
        envelope_input = torch.ones_like(magnitude[:, :1, :])
        denominator = F.conv_transpose1d(
            envelope_input, self.window_square, stride=self.hop_length
        )
        waveform = numerator / denominator.clamp_min(1.0e-11)
        pad = self.filter_length // 2
        waveform = waveform[..., pad:-pad]
        return waveform

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        magnitude, phase = self.transform(waveform)
        return self.inverse(magnitude, phase)
