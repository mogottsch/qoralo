#!/usr/bin/env python3
"""Capture the first two real streaming acoustic-decoder calls from experiment 0001."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch

from fixture_utils import repo_root, snapshot_cache, tensor_metadata

EXPECTED_SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
EXPECTED_MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=root / "artifacts/source/microsoft-vibevoice",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=root / "artifacts/models/microsoft-VibeVoice-1.5B",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        default=root / "experiments/0001-vibevoice-1.5b-local-reference/transcript.txt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "artifacts/0002/acoustic-decoder-fixtures",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cfg-scale", type=float, default=1.3)
    return parser.parse_args()


def save_call(
    output_dir: Path,
    call_index: int,
    latent: torch.Tensor,
    sample_indices: torch.Tensor | None,
    pcm: torch.Tensor,
    pre_tensors: dict[str, torch.Tensor],
    pre_entries: list[dict[str, Any]],
    post_tensors: dict[str, torch.Tensor],
    post_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    latent_b64t = latent.detach().cpu()
    if latent_b64t.shape[-1] == 64:
        latent_b64t = latent_b64t.permute(0, 2, 1).contiguous()
    indices = (
        sample_indices.detach().cpu().clone()
        if sample_indices is not None
        else torch.arange(latent_b64t.shape[0], dtype=torch.int64)
    )
    payload = {
        "latent_b64t": latent_b64t,
        "sample_indices": indices,
        "pcm": pcm.detach().cpu().clone(),
        "pre_cache": pre_tensors,
        "post_cache": post_tensors,
    }
    fixture_name = f"call_{call_index:03d}.pt"
    torch.save(payload, output_dir / fixture_name)
    return {
        "call_index": call_index,
        "fixture": fixture_name,
        "latent_b64t": tensor_metadata(payload["latent_b64t"]),
        "sample_indices": tensor_metadata(payload["sample_indices"]),
        "pcm": tensor_metadata(payload["pcm"]),
        "pre_cache": pre_entries,
        "post_cache": post_entries,
    }


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    model = args.model.resolve()
    demo = source / "demo/inference_from_file.py"
    if not demo.exists() or not (model / "model.safetensors.index.json").exists():
        raise SystemExit("Pinned source or model checkpoint is missing")
    source_revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if source_revision != EXPECTED_SOURCE_REVISION:
        raise SystemExit(
            f"Expected VibeVoice source {EXPECTED_SOURCE_REVISION}, got {source_revision}"
        )
    demo_text = demo.read_text()
    if '"--seed"' not in demo_text:
        raise SystemExit(
            "The historical demo is not prepared. Run experiment 0001's "
            "prepare_official_source.py first."
        )

    args.output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(source))
    from vibevoice.modular.modular_vibevoice_tokenizer import (  # noqa: PLC0415
        VibeVoiceAcousticTokenizerModel,
    )

    original_decode = VibeVoiceAcousticTokenizerModel.decode
    calls: list[dict[str, Any]] = []

    def capture_decode(
        self: VibeVoiceAcousticTokenizerModel,
        latents: torch.Tensor,
        cache: Any = None,
        sample_indices: torch.Tensor | None = None,
        use_cache: bool = False,
        debug: bool = False,
    ) -> torch.Tensor:
        call_index = len(calls)
        should_capture = call_index < 2 and use_cache and cache is not None
        if should_capture:
            pre_tensors, pre_entries = snapshot_cache(self.decoder, cache)
        pcm = original_decode(
            self,
            latents,
            cache=cache,
            sample_indices=sample_indices,
            use_cache=use_cache,
            debug=debug,
        )
        if should_capture:
            post_tensors, post_entries = snapshot_cache(self.decoder, cache)
            calls.append(
                save_call(
                    args.output,
                    call_index,
                    latents,
                    sample_indices,
                    pcm,
                    pre_tensors,
                    pre_entries,
                    post_tensors,
                    post_entries,
                )
            )
        return pcm

    VibeVoiceAcousticTokenizerModel.decode = capture_decode
    old_argv = sys.argv
    output_audio = args.output / "generated-audio"
    sys.argv = [
        str(demo),
        "--model_path",
        str(model),
        "--txt_path",
        str(args.transcript.resolve()),
        "--speaker_names",
        "Carter",
        "Maya",
        "--output_dir",
        str(output_audio),
        "--device",
        "cpu",
        "--cfg_scale",
        str(args.cfg_scale),
        "--seed",
        str(args.seed),
    ]
    try:
        runpy.run_path(str(demo), run_name="__main__")
    finally:
        sys.argv = old_argv
        VibeVoiceAcousticTokenizerModel.decode = original_decode

    if len(calls) != 2:
        raise SystemExit(f"Expected two decoder calls, captured {len(calls)}")
    manifest = {
        "schema_version": 1,
        "source_revision": EXPECTED_SOURCE_REVISION,
        "model_revision": EXPECTED_MODEL_REVISION,
        "seed": args.seed,
        "cfg_scale": args.cfg_scale,
        "transcript": str(args.transcript.resolve()),
        "device": "cpu",
        "dtype": "float32",
        "calls": calls,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Captured {len(calls)} calls in {args.output}")


if __name__ == "__main__":
    main()
