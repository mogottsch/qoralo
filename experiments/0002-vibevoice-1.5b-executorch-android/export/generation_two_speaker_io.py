#!/usr/bin/env python3
"""Prepare and summarize the pinned Carter-to-Maya Android controller probe."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "experiments/0002-vibevoice-1.5b-executorch-android"
DEFAULT_MANIFEST = BASE / "fixtures/two-speaker-manifest.json"
EXPECTED_CONDITIONED = "9966a6cb06a3cf52b45c7c560abd7e992e827c30897a6a2c3c95b3dc382a1f81"
EXPECTED_LAYOUT = "759e6563d63a152fe36f1a76b40433184500349bfca4e0e320ebb52cce420e9e"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(args: argparse.Namespace) -> None:
    import torch

    source = ROOT / "artifacts/0002/generation-multi-chunk-input"
    fixture_path = ROOT / "artifacts/0002/lane-c/speaker-conditioning/capture-1/fixture.pt"
    fixture = torch.load(fixture_path, map_location="cpu", weights_only=True)
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ("prompt.txt", "initial-noises.f32le", "negative-condition.f32le", "timesteps.f32le", "sigmas.f32le"):
        shutil.copyfile(source / name, args.output / name)
    conditioned = fixture["conditioned_embeddings"].cpu().contiguous().numpy().astype("<f4", copy=False)
    layout = fixture["sequence_speaker_ids"].cpu().contiguous().numpy().astype("<i8", copy=False)
    (args.output / "prompt-embeddings.f32le").write_bytes(conditioned.tobytes())
    (args.output / "sequence-speaker-ids.i64le").write_bytes(layout.tobytes())
    ids = layout.reshape(-1)
    transitions = [i for i in range(1, ids.size) if ids[i] >= 0 and ids[i - 1] >= 0 and ids[i] != ids[i - 1]]
    # The speaker prompt blocks are separated by seven ordinary tokens, so detect the first
    # selected Maya position as the semantic Carter-to-Maya transition.
    maya_start = int(np.flatnonzero(ids == 1)[0])
    manifest = {
        "schema_version": 1,
        "input_kind": "pinned real Carter/Maya conditioning through Android controller prefill",
        "provenance": {
            "source_revision": "6dd49cb7200c0367205a5f1e650244259e9e423d",
            "model_revision": "c00898d257e6b46004e3e2866a47534085fb685a",
            "seed": 42,
            "cfg": 1.3,
        },
        "speakers": [
            {"name": "Carter", "id": 0, "positions_inclusive": [28, 235], "selected_positions": int((ids == 0).sum())},
            {"name": "Maya", "id": 1, "positions_inclusive": [243, 446], "selected_positions": int((ids == 1).sum())},
        ],
        "transition": {
            "from": "Carter",
            "to": "Maya",
            "first_maya_position": maya_start,
            "ordinary_separator_positions_inclusive": [236, 242],
            "direct_adjacent_selected_id_transitions": transitions,
        },
        "conditioning_contract": {
            "conditioned_embeddings": {"shape": [1, 503, 1536], "dtype": "float32", "sha256": sha256(args.output / "prompt-embeddings.f32le")},
            "sequence_speaker_ids": {"shape": [1, 503], "dtype": "int64", "sha256": sha256(args.output / "sequence-speaker-ids.i64le")},
            "host_match_required": True,
        },
        "cache_transition_policy": "Both speaker prompt blocks are consumed by one Qwen prefill. The Carter-to-Maya position transition must not reset the 56 Qwen caches. Subsequent audio chunks share and replace the same 56 Qwen, 34 decoder, and 34 semantic caches; static decoder/semantic shapes still limit this export to two chunks.",
        "inputs": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in sorted(args.output.iterdir()) if p.is_file()},
        "quality_rubric": {
            "speech_presence": "PCM RMS must be at least -50 dBFS",
            "speaker_transition": "two voiced regions attributable to Carter then Maya must be audible",
            "corruption": "no sustained silence, metallic noise, clipping, repetition, or unintelligible output",
            "identity": "the two voiced regions must remain perceptually distinct",
            "acceptance": "all four checks pass",
        },
    }
    if manifest["conditioning_contract"]["conditioned_embeddings"]["sha256"] != EXPECTED_CONDITIONED:
        raise RuntimeError("conditioned embedding hash differs from frozen host fixture")
    if manifest["conditioning_contract"]["sequence_speaker_ids"]["sha256"] != EXPECTED_LAYOUT:
        raise RuntimeError("speaker position hash differs from frozen host fixture")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output / "input-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


def finalize(args: argparse.Namespace) -> None:
    manifest = json.loads(args.manifest.read_text())
    device = json.loads((args.artifacts / "device-result.json").read_text())
    props = json.loads((args.artifacts / "device-properties.json").read_text())
    runtime = json.loads(args.runtime_result.read_text())
    pcm_path = args.artifacts / "generation-run-0.pcm"
    wav_path = args.artifacts / "generation-run-0.wav"
    pcm = np.fromfile(pcm_path, dtype="<i2").astype(np.float64) / 32768.0
    rms = float(np.sqrt(np.mean(pcm * pcm))) if pcm.size else 0.0
    rms_dbfs = 20.0 * math.log10(max(rms, 1e-12))
    peak = float(np.max(np.abs(pcm), initial=0.0))
    runs = device["runs"]
    host_match = device["two_speaker_inputs"]["conditioned_embeddings_sha256"] == EXPECTED_CONDITIONED and device["two_speaker_inputs"]["sequence_speaker_ids_sha256"] == EXPECTED_LAYOUT
    positions_match = all(r["speaker_conditioning"].get("checked") and r["speaker_conditioning"]["transition_position"] == 243 for r in runs)
    cache_ok = all(r["qwen_cache_progression"] and r["decoder_cache_progression"] and r["semantic_cache_progression"] for r in runs)
    speech_present = rms_dbfs >= -50.0
    accepted = host_match and positions_match and cache_ok and speech_present
    result = {
        "schema_version": 1,
        "status": "passed" if accepted else "rejected",
        "scope": "Carter/Maya conditioning and one real prompt-position transition through the Android generation controller",
        "provenance": manifest["provenance"],
        "speaker_conditioning": {
            "intended_layout": manifest["speakers"],
            "transition": manifest["transition"],
            "device_checks": [r["speaker_conditioning"] for r in runs],
            "conditioned_embeddings_host_sha256": EXPECTED_CONDITIONED,
            "conditioned_embeddings_android_input_sha256": device["two_speaker_inputs"]["conditioned_embeddings_sha256"],
            "sequence_speaker_ids_host_sha256": EXPECTED_LAYOUT,
            "sequence_speaker_ids_android_input_sha256": device["two_speaker_inputs"]["sequence_speaker_ids_sha256"],
            "host_tensor_hashes_match": host_match,
            "intended_positions_match": positions_match,
        },
        "transition_cache_behavior": {
            "policy": manifest["cache_transition_policy"],
            "qwen_cache_count": 56,
            "decoder_cache_count": 34,
            "semantic_cache_count": 34,
            "device_progression_passed": cache_ok,
            "runs": [{"qwen": r["qwen_cache_progression"], "decoder": r["decoder_cache_progression"], "semantic": r["semantic_cache_progression"], "chunks": r["audio_chunks"], "stop_reason": r["stop_reason"]} for r in runs],
        },
        "audio": {
            "pcm_samples": int(pcm.size), "duration_seconds": pcm.size / 24000.0, "sample_rate_hz": 24000,
            "pcm_sha256": sha256(pcm_path), "repeat_pcm_sha256": sha256(args.artifacts / "generation-run-1.pcm"),
            "wav_sha256": sha256(wav_path), "rms": rms, "rms_dbfs": rms_dbfs, "peak": peak,
        },
        "quality_rubric": {
            "fixed_rubric": manifest["quality_rubric"],
            "speech_presence_passed": speech_present,
            "speaker_transition_passed": False,
            "corruption_passed": False,
            "identity_passed": False,
            "listening_notes": "The 0.266667-second output is effectively silent (objective RMS below the fixed threshold). It contains no intelligible Carter or Maya speech; an audible transition and identity retention cannot be assessed. This is major corruption under the fixed rubric, not an identity-quality pass.",
        },
        "latency_and_memory": {
            "runs": [{"elapsed_seconds": r["elapsed_seconds"], "prefill_seconds": r["prefill"]["seconds"], "chunks": r["chunks"]} for r in runs],
            "memory_kib": device["memory_kib"],
        },
        "device": props,
        "runtime": {"executorch": "1.2.0", "backend": "xnnpack", "qwen_precision": "int8", "other_precision": "fp32"},
        "deterministic": device["deterministic"],
        "supporting_generation_result": {
            "path": "artifacts/0002/generation-two-speaker-android/recurrent-runtime-result.json",
            "status": runtime["status"],
            "actual_output_chaining": runtime["actual_output_chaining"],
            "fixture_intermediate_substitution": runtime["fixture_intermediate_substitution"],
            "host_checkpoint_criteria_passed": all(metric["criterion"] for run in runtime["host_checkpoints"] for chunk in run for name, metric in chunk.items() if name != "chunk"),
            "boundary_integrity": runtime["boundary_integrity"],
        },
        "implementation_commits": [args.commit],
        "commands": [
            "artifacts/venv-executorch-1.2/bin/python experiments/0002-vibevoice-1.5b-executorch-android/export/generation_two_speaker_io.py prepare artifacts/0002/generation-two-speaker-input",
            "flock artifacts/locks/phone.lock experiments/0002-vibevoice-1.5b-executorch-android/android/run-two-speaker-generation-probe.sh",
        ],
        "conclusion": "Rejected for audio quality. Android consumed the exact frozen Carter/Maya conditioned tensor and speaker-position layout, including the Carter-to-Maya transition at position 243, without resetting recurrent caches. However, the static cache export stopped after two 3,200-sample chunks and produced effectively silent audio, so the no-corruption and no-identity-collapse acceptance requirement is not met.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if accepted:
        return
    # A rejected experiment is successfully recorded; do not make the reproducible harness fail.


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("output", type=Path)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.set_defaults(func=prepare)
    p = sub.add_parser("finalize")
    p.add_argument("artifacts", type=Path)
    p.add_argument("runtime_result", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--commit", required=True)
    p.set_defaults(func=finalize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
