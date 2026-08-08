#!/usr/bin/env python3
"""Capture paired connector inputs from one locked VibeVoice generation iteration."""

from __future__ import annotations

import argparse
import hashlib
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

SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"
ABI_ORDER = ["acoustic_features", "semantic_features"]


class CaptureComplete(Exception):
    """Stop generation once both calls at the join boundary have completed."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "artifacts/source/microsoft-vibevoice")
    parser.add_argument("--model", type=Path, default=root / "artifacts/models/microsoft-VibeVoice-1.5B")
    parser.add_argument("--transcript", type=Path, default=root / "experiments/0001-vibevoice-1.5b-local-reference/transcript.txt")
    parser.add_argument("--output", type=Path, default=root / "artifacts/0002/lane-b/connectors/capture-1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cfg-scale", type=float, default=1.3)
    parser.add_argument("--repeat-of", type=Path, help="A prior fixture.pt; require byte-identical tensors")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    source, model = args.source.resolve(), args.model.resolve()
    demo = source / "demo/inference_from_file.py"
    index = model / "model.safetensors.index.json"
    if not demo.exists() or not index.exists():
        raise SystemExit("Pinned source or model checkpoint is missing")
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != SOURCE_REVISION:
        raise SystemExit(f"Expected VibeVoice source {SOURCE_REVISION}, got {revision}")
    if '"--seed"' not in demo.read_text():
        raise SystemExit("Prepare the historical demo with experiment 0001 before capture")

    sys.path.insert(0, str(source))
    from vibevoice.modular.modeling_vibevoice import SpeechConnector  # noqa: PLC0415

    original_forward = SpeechConnector.forward
    captured: dict[str, Any] = {}
    pending: dict[str, Any] | None = None
    call_index = 0

    def capture_forward(self: SpeechConnector, features: torch.Tensor) -> torch.Tensor:
        nonlocal pending, call_index
        output = original_forward(self, features)
        call_index += 1
        width = int(features.shape[-1])
        if width == 64:
            pending = {
                "acoustic_features": features.detach().cpu().float().contiguous(),
                "acoustic_output": output.detach().cpu().float().contiguous(),
                "acoustic_call_index": call_index,
            }
        elif width == 128 and pending is not None:
            captured.update(pending)
            captured.update(
                {
                    "semantic_features": features.detach().cpu().float().contiguous(),
                    "semantic_output": output.detach().cpu().float().contiguous(),
                    "joined_output": (pending["acoustic_output"] + output.detach().cpu().float()).contiguous(),
                    "semantic_call_index": call_index,
                }
            )
            raise CaptureComplete
        return output

    args.output.mkdir(parents=True, exist_ok=True)
    SpeechConnector.forward = capture_forward
    old_argv = sys.argv
    sys.argv = [
        str(demo), "--model_path", str(model), "--txt_path", str(args.transcript.resolve()),
        "--speaker_names", "Carter", "Maya", "--output_dir", str(args.output / "unused-audio"),
        "--device", "cpu", "--cfg_scale", str(args.cfg_scale), "--seed", str(args.seed),
    ]
    try:
        runpy.run_path(str(demo), run_name="__main__")
    except CaptureComplete:
        pass
    finally:
        sys.argv = old_argv
        SpeechConnector.forward = original_forward
    if not captured:
        raise SystemExit("Generation ended without a paired acoustic/semantic connector call")

    tensors = {name: captured[name] for name in (*ABI_ORDER, "acoustic_output", "semantic_output", "joined_output")}
    deterministic = None
    if args.repeat_of:
        prior = torch.load(args.repeat_of, map_location="cpu", weights_only=True)
        deterministic = all(torch.equal(tensors[name], prior[name]) for name in tensors)
        if not deterministic:
            differing = [name for name in tensors if not torch.equal(tensors[name], prior[name])]
            raise SystemExit(f"Repeat capture differs: {differing}")
    fixture_path = args.output / "fixture.pt"
    torch.save(tensors, fixture_path)
    manifest = {
        "schema_version": 1,
        "component": "speech_connector_join",
        "provenance": {
            "description": "paired calls in one diffusion-token generation iteration",
            "source_revision": SOURCE_REVISION,
            "model_revision": MODEL_REVISION,
            "model_index_sha256": file_sha256(index),
            "transcript_sha256": file_sha256(args.transcript.resolve()),
            "seed": args.seed,
            "cfg_scale": args.cfg_scale,
            "device": "cpu",
            "acoustic_call_index": captured["acoustic_call_index"],
            "semantic_call_index": captured["semantic_call_index"],
            "same_generation_state": captured["semantic_call_index"] == captured["acoustic_call_index"] + 1,
        },
        "fixture": "fixture.pt",
        "abi_order": ABI_ORDER,
        "output_order": ["joined_output"],
        "tensors": {name: tensor_metadata(value) for name, value in tensors.items()},
        "repeat": {"compared_to": str(args.repeat_of) if args.repeat_of else None, "all_tensor_hashes_match": deterministic},
        "capture": {"wall_seconds": time.perf_counter() - started, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
