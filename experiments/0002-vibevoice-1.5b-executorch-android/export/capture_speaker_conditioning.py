#!/usr/bin/env python3
"""Capture Carter/Maya prompt conditioning from the pinned VibeVoice model."""

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
from speaker_conditioning import SpeakerConditioner, sequence_speaker_ids_from_masks

SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"
SPEAKERS = ("Carter", "Maya")


class CaptureComplete(Exception):
    pass


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
    parser.add_argument("--output", type=Path, default=root / "artifacts/0002/lane-c/speaker-conditioning/capture-1")
    parser.add_argument("--repeat-of", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cfg-scale", type=float, default=1.3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    source, model = args.source.resolve(), args.model.resolve()
    demo = source / "demo/inference_from_file.py"
    index = model / "model.safetensors.index.json"
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != SOURCE_REVISION:
        raise SystemExit(f"Expected source {SOURCE_REVISION}, got {revision}")
    if not demo.exists() or not index.exists():
        raise SystemExit("Pinned source or model checkpoint is missing")

    sys.path.insert(0, str(source))
    from vibevoice.modular.modeling_vibevoice_inference import (  # noqa: PLC0415
        VibeVoiceForConditionalGenerationInference,
    )

    captured: dict[str, torch.Tensor] = {}
    original_process = VibeVoiceForConditionalGenerationInference._process_speech_inputs
    original_forward = VibeVoiceForConditionalGenerationInference.forward
    pending: dict[str, torch.Tensor] = {}

    def process(self: Any, speech_tensors: torch.Tensor, speech_masks: torch.Tensor, speech_type: str = "audio"):
        acoustic_features, flattened_outputs = original_process(self, speech_tensors, speech_masks, speech_type)
        # Re-run only the small pinned connector so the ABI retains speaker rows.
        connector_outputs = self.model.acoustic_connector(acoustic_features).detach().cpu().float().contiguous()
        pending.update({
            "prompt_features": acoustic_features.detach().cpu().float().contiguous(),
            "connector_outputs": connector_outputs,
            "prompt_mask": speech_masks.detach().cpu().bool().contiguous(),
        })
        expected_flat = connector_outputs[pending["prompt_mask"]]
        torch.testing.assert_close(expected_flat, flattened_outputs.detach().cpu().float(), rtol=0, atol=0)
        return acoustic_features, flattened_outputs

    def forward(self: Any, *positional: Any, **kwargs: Any):
        if "speech_tensors" not in kwargs or kwargs.get("speech_tensors") is None:
            return original_forward(self, *positional, **kwargs)
        input_ids = kwargs.get("input_ids")
        sequence_mask = kwargs.get("speech_input_mask")
        # Populate prompt-derived tensors using the exact pinned path.
        self._process_speech_inputs(kwargs["speech_tensors"].to(self.dtype), kwargs["speech_masks"])
        if input_ids is None or sequence_mask is None or not pending:
            raise RuntimeError("Expected token IDs and speaker masks at conditioning boundary")
        token_embeddings = self.model.get_input_embeddings()(input_ids).detach().cpu().float().contiguous()
        speaker_ids = torch.arange(len(SPEAKERS), dtype=torch.int64)
        sequence_ids = sequence_speaker_ids_from_masks(
            sequence_mask.detach().cpu().bool().contiguous(), pending["prompt_mask"], speaker_ids
        )
        conditioned = SpeakerConditioner()(
            token_embeddings, pending["connector_outputs"], pending["prompt_mask"], speaker_ids, sequence_ids
        )
        captured.update(pending)
        captured.update({
            "speaker_ids": speaker_ids,
            "sequence_speaker_ids": sequence_ids,
            "token_embeddings": token_embeddings,
            "conditioned_embeddings": conditioned.detach().cpu().contiguous(),
        })
        raise CaptureComplete

    args.output.mkdir(parents=True, exist_ok=True)
    VibeVoiceForConditionalGenerationInference._process_speech_inputs = process
    VibeVoiceForConditionalGenerationInference.forward = forward
    old_argv = sys.argv
    sys.argv = [
        str(demo), "--model_path", str(model), "--txt_path", str(args.transcript.resolve()),
        "--speaker_names", *SPEAKERS, "--output_dir", str(args.output / "unused-audio"),
        "--device", "cpu", "--cfg_scale", str(args.cfg_scale), "--seed", str(args.seed),
    ]
    try:
        runpy.run_path(str(demo), run_name="__main__")
    except CaptureComplete:
        pass
    finally:
        sys.argv = old_argv
        VibeVoiceForConditionalGenerationInference.forward = original_forward
        VibeVoiceForConditionalGenerationInference._process_speech_inputs = original_process
    if not captured:
        raise SystemExit("Generation did not reach the speaker-conditioning boundary")

    deterministic: bool | None = None
    if args.repeat_of:
        prior = torch.load(args.repeat_of, map_location="cpu", weights_only=True)
        differing = [name for name, value in captured.items() if name not in prior or not torch.equal(value, prior[name])]
        deterministic = not differing and set(prior) == set(captured)
        if not deterministic:
            raise SystemExit(f"Repeat capture differs: {differing}")
    fixture = args.output / "fixture.pt"
    torch.save(captured, fixture)
    manifest = {
        "schema_version": 1,
        "component": "speaker_conditioning",
        "provenance": {
            "source_revision": SOURCE_REVISION,
            "model_revision": MODEL_REVISION,
            "model_index_sha256": file_sha256(index),
            "transcript_sha256": file_sha256(args.transcript.resolve()),
            "speakers": list(SPEAKERS),
            "seed": args.seed,
            "cfg_scale": args.cfg_scale,
            "device": "cpu_fp32",
        },
        "fixture": "fixture.pt",
        "abi_order": ["token_embeddings", "connector_outputs", "prompt_mask", "speaker_ids", "sequence_speaker_ids"],
        "output_order": ["conditioned_embeddings"],
        "tensors": {name: tensor_metadata(value) for name, value in captured.items()},
        "speaker_hashes": {
            name: {
                "prompt_features": tensor_metadata(captured["prompt_features"][row]),
                "connector_outputs": tensor_metadata(captured["connector_outputs"][row][captured["prompt_mask"][row]]),
            }
            for row, name in enumerate(SPEAKERS)
        },
        "raw_audio_policy": "voice WAV bytes and waveform tensors are inputs to capture only and are never saved, hashed, or committed",
        "repeat": {"compared_to": str(args.repeat_of) if args.repeat_of else None, "all_tensor_hashes_match": deterministic},
        "capture": {"wall_seconds": time.perf_counter() - started, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
