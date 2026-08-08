#!/usr/bin/env python3
"""Small tensor-only reference for VibeVoice's native ten-step DPM loop."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import torch


def cosine_betas(num_train_timesteps: int = 1000, max_beta: float = 0.999) -> torch.Tensor:
    """Match the pinned scheduler's ``betas_for_alpha_bar(..., cosine)``."""
    def alpha_bar(value: float) -> float:
        return math.cos((value + 0.008) / 1.008 * math.pi / 2) ** 2

    return torch.tensor(
        [
            min(
                1
                - alpha_bar((index + 1) / num_train_timesteps)
                / alpha_bar(index / num_train_timesteps),
                max_beta,
            )
            for index in range(num_train_timesteps)
        ],
        dtype=torch.float32,
    )


def ten_step_schedule() -> tuple[torch.Tensor, torch.Tensor]:
    """Return the locked ten integer timesteps and eleven float32 sigmas."""
    alphas_cumprod = torch.cumprod(1.0 - cosine_betas(), dim=0)
    timesteps = np.linspace(0, 999, 11).round()[::-1][:-1].copy().astype(np.int64)
    training_sigmas = (
        ((1 - alphas_cumprod) / alphas_cumprod).sqrt().numpy().astype(np.float32)
    )
    sigmas = np.interp(timesteps, np.arange(1000), training_sigmas)
    sigmas = np.concatenate([sigmas, [0]]).astype(np.float32)
    return torch.from_numpy(timesteps), torch.from_numpy(sigmas)


def _alpha_sigma(sigma: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    alpha = 1 / torch.sqrt(sigma**2 + 1)
    return alpha, sigma * alpha


@dataclass
class DpmSolverState:
    """FP32 DPM-Solver++ order-two midpoint state used by VibeVoice."""

    sigmas: torch.Tensor
    step_index: int = 0
    previous_x0: torch.Tensor | None = None

    def step(self, prediction: torch.Tensor, sample: torch.Tensor) -> torch.Tensor:
        index = self.step_index
        sigma_s = self.sigmas[index]
        alpha_s, sigma_s_normalized = _alpha_sigma(sigma_s)
        current_x0 = alpha_s * sample - sigma_s_normalized * prediction

        sigma_t = self.sigmas[index + 1]
        alpha_t, sigma_t_normalized = _alpha_sigma(sigma_t)
        lambda_s = torch.log(alpha_s) - torch.log(sigma_s_normalized)
        lambda_t = torch.log(alpha_t) - torch.log(sigma_t_normalized)
        h = lambda_t - lambda_s
        coefficient = alpha_t * (torch.exp(-h) - 1.0)

        # The pinned scheduler uses first order for the first and final steps.
        if self.previous_x0 is None or index == len(self.sigmas) - 2:
            result = (sigma_t_normalized / sigma_s_normalized) * sample
            result = result - coefficient * current_x0
        else:
            previous_sigma = self.sigmas[index - 1]
            previous_alpha, previous_sigma_normalized = _alpha_sigma(previous_sigma)
            previous_lambda = torch.log(previous_alpha) - torch.log(
                previous_sigma_normalized
            )
            r0 = (lambda_s - previous_lambda) / h
            derivative = (current_x0 - self.previous_x0) / r0
            result = (sigma_t_normalized / sigma_s_normalized) * sample
            result = result - coefficient * current_x0 - 0.5 * coefficient * derivative

        self.previous_x0 = current_x0
        self.step_index += 1
        return result.to(dtype=prediction.dtype)
