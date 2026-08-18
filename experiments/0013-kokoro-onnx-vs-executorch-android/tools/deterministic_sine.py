#!/usr/bin/env python3
"""Seed-materialized Kokoro sine/noise source for a fixed deployment shape.

The official generator samples one [batch, harmonic] phase tensor and one
sine-shaped standard-normal tensor on every inference. ONNX Random* does not
expose a portable session seed. For the matched fixed-input experiment, this
narrow module materializes exactly those two *model random inputs* from a
recorded PyTorch CPU seed and checks their runtime shapes. They are stochastic
inputs, not neural intermediates or learned parameters.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class SeededSineGen(nn.Module):
    def __init__(
        self,
        *,
        f0_shape: tuple[int, int, int],
        seed: int,
        sampling_rate: int = 24_000,
        upsample_scale: int = 300,
        harmonic_num: int = 8,
        sine_amp: float = 0.1,
        noise_std: float = 0.003,
        voiced_threshold: float = 10.0,
    ) -> None:
        super().__init__()
        if f0_shape[0] != 1 or f0_shape[2] != 1:
            raise ValueError("the frozen Kokoro route requires f0 shape [1, time, 1]")
        self.sine_amp = sine_amp
        self.noise_std = noise_std
        self.harmonic_num = harmonic_num
        self.dim = harmonic_num + 1
        self.sampling_rate = sampling_rate
        self.voiced_threshold = voiced_threshold
        self.upsample_scale = upsample_scale
        generator = torch.Generator(device="cpu")
        generator.manual_seed(seed)
        phase = torch.rand(f0_shape[0], self.dim, generator=generator)
        phase[:, 0] = 0
        # The official interpolation returns a [B,T,H] view with H-major
        # storage, and randn_like preserves that memory format. Reproduce the
        # exact CPU RNG-to-logical-index mapping rather than generating a
        # contiguous tensor with the same shape.
        noise_shape = (f0_shape[0], f0_shape[1], self.dim)
        noise_stride = (f0_shape[1] * self.dim, 1, f0_shape[1])
        noise = torch.empty_strided(noise_shape, noise_stride).normal_(
            generator=generator
        )
        self.register_buffer("initial_phase", phase)
        self.register_buffer("standard_noise", noise)

    def _f02uv(self, f0: torch.Tensor) -> torch.Tensor:
        return (f0 > self.voiced_threshold).to(torch.float32)

    def _f02sine(self, f0_values: torch.Tensor) -> torch.Tensor:
        if (
            f0_values.shape[0] != self.standard_noise.shape[0]
            or f0_values.shape[1] != self.standard_noise.shape[1]
            or f0_values.shape[2] != self.standard_noise.shape[2]
        ):
            raise ValueError("runtime F0 shape differs from the frozen random-input shape")
        rad_values = (f0_values / self.sampling_rate) % 1
        rad_values[:, 0, :] = rad_values[:, 0, :] + self.initial_phase
        rad_values = F.interpolate(
            rad_values.transpose(1, 2),
            scale_factor=1 / self.upsample_scale,
            mode="linear",
        ).transpose(1, 2)
        phase = torch.cumsum(rad_values, dim=1) * 2 * torch.pi
        phase = F.interpolate(
            phase.transpose(1, 2) * self.upsample_scale,
            scale_factor=self.upsample_scale,
            mode="linear",
        ).transpose(1, 2)
        return torch.sin(phase)

    def forward(self, f0: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        multipliers = torch.arange(
            1, self.harmonic_num + 2, dtype=f0.dtype, device=f0.device
        ).reshape(1, 1, -1)
        f0_values = f0 * multipliers
        sine_waves = self._f02sine(f0_values) * self.sine_amp
        uv = self._f02uv(f0)
        noise_amp = uv * self.noise_std + (1 - uv) * self.sine_amp / 3
        noise = noise_amp * self.standard_noise
        sine_waves = sine_waves * uv + noise
        return sine_waves, uv, noise
