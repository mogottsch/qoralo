#!/usr/bin/env python3
"""Capture the first real prediction-head call from the locked CPU reference."""

from __future__ import annotations

import argparse
import json
import resource
import runpy
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import torch

from fixture_utils import repo_root, tensor_metadata

EXPECTED_SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
EXPECTED_MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"


class CaptureComplete(Exception):
    """Stop the expensive reference run after the first prediction-head call."""


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
        default=root / "artifacts/0002/lane-b/diffusion-head",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cfg-scale", type=float, default=1.3)
    return parser.parse_args()


def main() -> None:
    started = time.perf_counter()
    args = parse_args()
    source = args.source.resolve()
    model = args.model.resolve()
    transcript = args.transcript.resolve()
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
    if '"--seed"' not in demo.read_text():
        raise SystemExit(
            "The historical demo is not prepared. Run experiment 0001's "
            "prepare_official_source.py first."
        )

    args.output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(source))
    from vibevoice.modular.modular_vibevoice_diffusion_head import (  # noqa: PLC0415
        VibeVoiceDiffusionHead,
    )

    original_forward = VibeVoiceDiffusionHead.forward
    captured: dict[str, Any] = {}

    def capture_forward(
        self: VibeVoiceDiffusionHead,
        noisy_images: torch.Tensor,
        timesteps: torch.Tensor,
        condition: torch.Tensor,
    ) -> torch.Tensor:
        output = original_forward(self, noisy_images, timesteps, condition)
        if captured:
            return output
        if noisy_images.shape[0] % 2:
            raise RuntimeError("Expected positive/negative CFG pairs")
        batch = noisy_images.shape[0] // 2
        noisy_latent = noisy_images[:batch]
        if not torch.equal(noisy_latent, noisy_images[batch:]):
            raise RuntimeError("CFG prediction call did not duplicate its noisy latent")
        timestep = timesteps[:batch]
        if not torch.equal(timestep, timesteps[batch:]):
            raise RuntimeError("CFG prediction call did not duplicate its timestep")
        positive_condition = condition[:batch]
        negative_condition = condition[batch:]
        positive_prediction, negative_prediction = output.chunk(2, dim=0)
        guided_prediction = negative_prediction + args.cfg_scale * (
            positive_prediction - negative_prediction
        )
        captured.update(
            {
                "noisy_latent": noisy_latent.detach().cpu().float().contiguous(),
                "timestep": timestep.detach().cpu().float().contiguous(),
                "positive_condition": positive_condition.detach()
                .cpu()
                .float()
                .contiguous(),
                "negative_condition": negative_condition.detach()
                .cpu()
                .float()
                .contiguous(),
                "guided_prediction": guided_prediction.detach()
                .cpu()
                .float()
                .contiguous(),
            }
        )
        raise CaptureComplete

    VibeVoiceDiffusionHead.forward = capture_forward
    old_argv = sys.argv
    sys.argv = [
        str(demo),
        "--model_path",
        str(model),
        "--txt_path",
        str(transcript),
        "--speaker_names",
        "Carter",
        "Maya",
        "--output_dir",
        str(args.output / "unused-audio"),
        "--device",
        "cpu",
        "--cfg_scale",
        str(args.cfg_scale),
        "--seed",
        str(args.seed),
    ]
    try:
        runpy.run_path(str(demo), run_name="__main__")
    except CaptureComplete:
        pass
    finally:
        sys.argv = old_argv
        VibeVoiceDiffusionHead.forward = original_forward

    if not captured:
        raise SystemExit("Generation ended without a prediction-head call")
    fixture_path = args.output / "fixture.pt"
    torch.save(captured, fixture_path)
    manifest = {
        "schema_version": 1,
        "component": "diffusion_head_cfg_prediction",
        "provenance": "first real diffusion-head invocation from locked CPU reference",
        "source_revision": EXPECTED_SOURCE_REVISION,
        "model_revision": EXPECTED_MODEL_REVISION,
        "seed": args.seed,
        "cfg_scale": args.cfg_scale,
        "diffusion_inference_steps": 10,
        "prediction_type": "v_prediction",
        "device": "cpu",
        "dtype": "float32",
        "fixture": "fixture.pt",
        "abi_order": [
            "noisy_latent",
            "timestep",
            "positive_condition",
            "negative_condition",
        ],
        "tensors": {name: tensor_metadata(value) for name, value in captured.items()},
        "capture": {
            "wall_seconds": time.perf_counter() - started,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "scope": {
            "included": "prediction head plus classifier-free guidance combine",
            "excluded": "DPM scheduler update and ten-step loop",
        },
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
