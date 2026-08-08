#!/usr/bin/env python3
"""Shared helpers for acoustic-decoder fixtures."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import torch


def tensor_sha256(tensor: torch.Tensor) -> str:
    """Hash the exact contiguous CPU bytes of a tensor."""
    raw = (
        tensor.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
    )
    return hashlib.sha256(raw).hexdigest()


def tensor_metadata(tensor: torch.Tensor) -> dict[str, Any]:
    value = tensor.detach().cpu()
    result: dict[str, Any] = {
        "shape": list(value.shape),
        "dtype": str(value.dtype).removeprefix("torch."),
        "numel": value.numel(),
        "sha256": tensor_sha256(value),
    }
    if value.is_floating_point() and value.numel():
        result.update(
            {
                "finite": bool(torch.isfinite(value).all()),
                "min": value.min().item(),
                "max": value.max().item(),
                "mean": value.float().mean().item(),
            }
        )
    return result


def decoder_layer_ids(decoder: torch.nn.Module) -> dict[str, str]:
    """Map runtime cache IDs to stable decoder module names."""
    result: dict[str, str] = {}
    for name, module in decoder.named_modules():
        if module.__class__.__name__ not in {"SConv1d", "SConvTranspose1d"}:
            continue
        layer_id = module.layer_id
        if layer_id in result:
            raise ValueError(f"Duplicate cache layer ID: {layer_id}")
        result[layer_id] = name
    return result


def snapshot_cache(
    decoder: torch.nn.Module, cache: Any
) -> tuple[dict[str, torch.Tensor], list[dict[str, Any]]]:
    """Clone a VibeVoice cache using stable module-name/sample keys."""
    ids = decoder_layer_ids(decoder)
    tensors: dict[str, torch.Tensor] = {}
    entries: list[dict[str, Any]] = []
    for (layer_id, sample_index), state in sorted(
        cache.cache.items(), key=lambda item: (ids.get(item[0][0], item[0][0]), item[0][1])
    ):
        if layer_id not in ids:
            raise KeyError(f"Cache contains unknown decoder layer ID: {layer_id}")
        name = ids[layer_id]
        key = f"{name}/sample_{sample_index}"
        cloned = state.detach().cpu().clone()
        tensors[key] = cloned
        entries.append(
            {
                "key": key,
                "module": name,
                "sample_index": int(sample_index),
                **tensor_metadata(cloned),
            }
        )
    return tensors, entries


def repo_root(start: Path) -> Path:
    """Find this spike repository without relying on the process cwd."""
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / ".git").exists() and (candidate / "experiments").exists():
            return candidate
    raise RuntimeError(f"Could not find repository root from {start}")
