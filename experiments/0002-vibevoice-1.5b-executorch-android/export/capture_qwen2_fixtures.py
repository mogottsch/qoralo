#!/usr/bin/env python3
"""Capture real Qwen2 prefill/decode calls (heavy-RAM; do not run concurrently)."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

from fixture_utils import repo_root, tensor_metadata
from qwen2_backbone import cache_tensor_names

EXPECTED_SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
EXPECTED_MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "artifacts/source/microsoft-vibevoice")
    parser.add_argument("--model", type=Path, default=root / "artifacts/models/microsoft-VibeVoice-1.5B")
    parser.add_argument(
        "--transcript",
        type=Path,
        default=root / "experiments/0001-vibevoice-1.5b-local-reference/transcript.txt",
    )
    parser.add_argument(
        "--output", type=Path, default=root / "artifacts/0002/lane-c/qwen2-fixtures"
    )
    parser.add_argument("--cache-capacity", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cfg-scale", type=float, default=1.3)
    return parser.parse_args()


def padded_cache(cache: Any, capacity: int, layers: int) -> tuple[torch.Tensor, ...]:
    result: list[torch.Tensor] = []
    for layer in range(layers):
        for source in (cache.key_cache[layer], cache.value_cache[layer]):
            if source.shape[2] > capacity:
                raise RuntimeError(
                    f"Occupied cache length {source.shape[2]} exceeds capacity {capacity}"
                )
            target = source.new_zeros(
                source.shape[0], source.shape[1], capacity, source.shape[3]
            )
            target[:, :, : source.shape[2], :] = source.detach()
            result.append(target.cpu())
    return tuple(result)


def padded_attention_mask(mask: torch.Tensor, capacity: int) -> torch.Tensor:
    if mask.shape[1] > capacity:
        raise RuntimeError(
            f"Attention-mask length {mask.shape[1]} exceeds capacity {capacity}"
        )
    result = mask.new_zeros(mask.shape[0], capacity)
    result[:, : mask.shape[1]] = mask
    return result.cpu()


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    model_path = args.model.resolve()
    source_revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if source_revision != EXPECTED_SOURCE_REVISION:
        raise SystemExit(
            f"Expected source {EXPECTED_SOURCE_REVISION}, got {source_revision}"
        )
    if args.cache_capacity <= 0:
        raise SystemExit("--cache-capacity must be positive")

    sys.path.insert(0, str(source))
    from transformers.models.qwen2.modeling_qwen2 import Qwen2Model  # noqa: PLC0415
    from vibevoice.modular.modeling_vibevoice_inference import (  # noqa: PLC0415
        VibeVoiceForConditionalGenerationInference,
    )

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    captures: list[dict[str, Any]] = []
    pending_speaker_mask: torch.Tensor | None = None
    prefill_end: int | None = None
    original_outer_forward = VibeVoiceForConditionalGenerationInference.forward
    original_qwen_forward = Qwen2Model.forward

    def outer_forward(self: Any, *positional: Any, **kwargs: Any) -> Any:
        nonlocal pending_speaker_mask
        previous = pending_speaker_mask
        mask = kwargs.get("speech_input_mask")
        pending_speaker_mask = mask.detach().cpu().clone() if mask is not None else None
        try:
            return original_outer_forward(self, *positional, **kwargs)
        finally:
            pending_speaker_mask = previous

    def qwen_forward(self: Any, *positional: Any, **kwargs: Any) -> Any:
        nonlocal prefill_end
        inputs_embeds = kwargs.get("inputs_embeds")
        cache_position = kwargs.get("cache_position")
        attention_mask = kwargs.get("attention_mask")
        position_ids = kwargs.get("position_ids")
        past = kwargs.get("past_key_values")
        candidate = inputs_embeds is not None and cache_position is not None
        position_start = int(cache_position[0].item()) if candidate else -1
        is_prefill = candidate and not captures and inputs_embeds.shape[1] > 1
        is_decode = (
            candidate
            and len(captures) == 1
            and inputs_embeds.shape[1] == 1
            and prefill_end is not None
            and position_start == prefill_end
        )
        should_capture = is_prefill or is_decode
        pre_cache = None
        if is_decode:
            pre_cache = padded_cache(past, args.cache_capacity, self.config.num_hidden_layers)

        result = original_qwen_forward(self, *positional, **kwargs)
        if not should_capture:
            return result

        if attention_mask is None:
            raise RuntimeError("Expected an explicit attention mask from generation")
        if position_ids is None:
            position_ids = cache_position.unsqueeze(0)
        end = int(cache_position[-1].item()) + 1
        if end > args.cache_capacity:
            raise RuntimeError(
                f"Cache position {end - 1} exceeds capacity {args.cache_capacity}"
            )
        if is_prefill:
            prefill_end = end

        post_cache = padded_cache(
            result.past_key_values, args.cache_capacity, self.config.num_hidden_layers
        )
        hidden = result.last_hidden_state[:, -1:, :].detach().cpu()
        # The locked checkpoint ties lm_head to embed_tokens (config=true and no
        # separate lm_head tensor), so this exactly reproduces the outer head.
        logits = F.linear(
            result.last_hidden_state[:, -1, :], self.embed_tokens.weight
        ).float().detach().cpu()
        payload: dict[str, Any] = {
            "inputs_embeds": inputs_embeds.detach().cpu().clone(),
            "attention_mask": padded_attention_mask(attention_mask, args.cache_capacity),
            "position_ids": position_ids.detach().cpu().clone(),
            "cache_position": cache_position.detach().cpu().clone(),
            "expected_last_hidden_state": hidden,
            "expected_next_token_logits": logits,
            "post_cache": post_cache,
        }
        if pre_cache is not None:
            payload["pre_cache"] = pre_cache
        if is_prefill:
            payload["speaker_input_mask"] = (
                pending_speaker_mask
                if pending_speaker_mask is not None
                else torch.zeros(inputs_embeds.shape[:2], dtype=torch.bool)
            )
        name = "prefill" if is_prefill else "decode"
        torch.save(payload, output_dir / f"{name}.pt")
        captures.append(
            {
                "entry": name,
                "fixture": f"{name}.pt",
                "cache_position": cache_position.detach().cpu().tolist(),
                "inputs_embeds": tensor_metadata(payload["inputs_embeds"]),
                "attention_mask": tensor_metadata(payload["attention_mask"]),
                "position_ids": tensor_metadata(payload["position_ids"]),
                "expected_last_hidden_state": tensor_metadata(hidden),
                "expected_next_token_logits": tensor_metadata(logits),
                "pre_cache": [tensor_metadata(value) for value in pre_cache or ()],
                "post_cache": [tensor_metadata(value) for value in post_cache],
            }
        )
        return result

    VibeVoiceForConditionalGenerationInference.forward = outer_forward
    Qwen2Model.forward = qwen_forward
    demo = source / "demo/inference_from_file.py"
    old_argv = sys.argv
    sys.argv = [
        str(demo),
        "--model_path", str(model_path),
        "--txt_path", str(args.transcript.resolve()),
        "--speaker_names", "Carter", "Maya",
        "--output_dir", str(output_dir / "generated-audio"),
        "--device", "cpu",
        "--cfg_scale", str(args.cfg_scale),
        "--seed", str(args.seed),
    ]
    try:
        runpy.run_path(str(demo), run_name="__main__")
    finally:
        sys.argv = old_argv
        Qwen2Model.forward = original_qwen_forward
        VibeVoiceForConditionalGenerationInference.forward = original_outer_forward

    if [item["entry"] for item in captures] != ["prefill", "decode"]:
        raise SystemExit(f"Expected prefill and decode captures, got {captures}")
    manifest = {
        "schema_version": 1,
        "source_revision": EXPECTED_SOURCE_REVISION,
        "model_revision": EXPECTED_MODEL_REVISION,
        "seed": args.seed,
        "cfg_scale": args.cfg_scale,
        "cache_capacity": args.cache_capacity,
        "cache_order": cache_tensor_names(28),
        "captures": captures,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Captured Qwen2 prefill and decode fixtures in {output_dir}")


if __name__ == "__main__":
    main()
