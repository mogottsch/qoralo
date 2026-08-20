#!/usr/bin/env python3
"""Run a deterministic canonical-v2 controlled-eager Kokoro CPU oracle."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch
from kokoro import KModel

PINS = {
    "model": (327212226, "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"),
    "config": (2351, "5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f"),
    "tokens": (1880, "9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280"),
    "style": (1024, "8acaca07623d98a1085f6b182fb997d715dd1d67862e350567e6d9b1bc8ec71b"),
    "speed": (4, "e00e5eb9444182f352323374ef4e08ebcb784725fdd4fd612d7730540b3e0c8c"),
}
SEED = 20260818
TOKEN_COUNT = 235


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, key: str) -> None:
    size, expected = PINS[key]
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"{key} is not a regular file")
    if path.stat().st_size != size or sha256(path) != expected:
        raise RuntimeError(f"{key} pin mismatch: {path}")


def predict_duration(
    model: KModel, input_ids: torch.Tensor, style: torch.Tensor, speed: torch.Tensor
) -> torch.Tensor:
    input_lengths = torch.full(
        (input_ids.shape[0],), input_ids.shape[-1], dtype=torch.long
    )
    text_mask = torch.arange(input_lengths.max()).unsqueeze(0).expand(
        input_lengths.shape[0], -1
    ).type_as(input_lengths)
    text_mask = torch.gt(text_mask + 1, input_lengths.unsqueeze(1))
    bert_dur = model.bert(input_ids, attention_mask=(~text_mask).int())
    d_en = model.bert_encoder(bert_dur).transpose(-1, -2)
    prosody_style = style[:, 128:]
    d = model.predictor.text_encoder(
        d_en, prosody_style, input_lengths, text_mask
    )
    x, _ = model.predictor.lstm(d)
    duration = model.predictor.duration_proj(x)
    duration = torch.sigmoid(duration).sum(axis=-1) / speed
    return torch.round(duration).clamp(min=1).long().squeeze()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--tokens", type=Path, required=True)
    parser.add_argument("--style", type=Path, required=True)
    parser.add_argument("--speed", type=Path, required=True)
    parser.add_argument("--experiment-0013-tools", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    for key in PINS:
        verify(getattr(args, key), key)
    if importlib.metadata.version("kokoro") != "0.9.4":
        raise RuntimeError("kokoro package version drift")

    sys.path.insert(0, str(args.experiment_0013_tools))
    from deterministic_sine import SeededSineGen
    from onnx_exact_stft import OnnxExactSTFT

    tool_paths = {
        name: args.experiment_0013_tools / name
        for name in (
            "deterministic_sine.py",
            "onnx_exact_stft.py",
            "exact_stft.py",
        )
    }
    if not all(path.is_file() for path in tool_paths.values()):
        raise RuntimeError("experiment-0013 exact-STFT tool set is incomplete")

    tokens_np = np.fromfile(args.tokens, dtype="<i8").reshape(1, TOKEN_COUNT)
    style_np = np.fromfile(args.style, dtype="<f4").reshape(1, 256)
    speed_np = np.fromfile(args.speed, dtype="<f4").reshape(1)
    if speed_np[0] != 1.0:
        raise RuntimeError("speed drift")
    tokens = torch.from_numpy(tokens_np.copy())
    style = torch.from_numpy(style_np.copy())
    speed = torch.from_numpy(speed_np.copy())

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    setup_start = time.perf_counter()
    model = KModel(
        repo_id="not-used",
        model=str(args.model),
        config=str(args.config),
        disable_complex=False,
    ).cpu().eval()
    model_load_seconds = time.perf_counter() - setup_start

    with torch.inference_mode():
        duration_start = time.perf_counter()
        preliminary_duration = predict_duration(model, tokens, style, speed)
        duration_probe_seconds = time.perf_counter() - duration_start
    if tuple(preliminary_duration.shape) != (TOKEN_COUNT,):
        raise RuntimeError("duration shape drift")
    duration_sum = int(preliminary_duration.sum().item())
    if duration_sum <= 0:
        raise RuntimeError("invalid duration sum")
    audio_samples = duration_sum * 600

    model.decoder.generator.stft = OnnxExactSTFT(20, 5, 20)
    model.decoder.generator.m_source.l_sin_gen = SeededSineGen(
        f0_shape=(1, audio_samples, 1), seed=SEED
    )
    with torch.inference_mode():
        inference_start = time.perf_counter()
        audio, duration = model.forward_with_tokens(tokens, style, speed)
        inference_seconds = time.perf_counter() - inference_start
    audio = audio.squeeze().cpu().contiguous()
    duration = duration.cpu().contiguous()
    if not torch.equal(duration, preliminary_duration):
        raise RuntimeError("full inference duration differs from duration probe")
    if tuple(audio.shape) != (audio_samples,):
        raise RuntimeError(
            f"audio shape drift: expected {(audio_samples,)}, got {tuple(audio.shape)}"
        )

    audio_np = np.ascontiguousarray(audio.numpy(), dtype="<f4")
    duration_np = np.ascontiguousarray(duration.numpy(), dtype="<i8")
    if not np.isfinite(audio_np).all():
        raise RuntimeError("non-finite controlled-eager audio")
    peak = float(np.max(np.abs(audio_np)))
    rms = float(np.sqrt(np.mean(audio_np.astype(np.float64) ** 2)))
    clipped = int(np.count_nonzero(np.abs(audio_np) >= 1.0))
    if not (0.0001 <= peak < 1.0 and rms >= 0.00001 and clipped == 0):
        raise RuntimeError("controlled-eager structural audio gate failed")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = args.output_dir / "audio.f32"
    duration_path = args.output_dir / "duration.i64"
    audio_path.write_bytes(audio_np.tobytes())
    duration_path.write_bytes(duration_np.tobytes())
    record = {
        "schema_version": 1,
        "status": "passed",
        "route": "canonical_v2_official_frontend_controlled_eager_cpu_oracle",
        "source": {
            "model": {
                "path": str(args.model),
                "bytes": args.model.stat().st_size,
                "sha256": sha256(args.model),
            },
            "config": {
                "path": str(args.config),
                "bytes": args.config.stat().st_size,
                "sha256": sha256(args.config),
            },
            "kokoro": importlib.metadata.version("kokoro"),
            "tools": {
                name: {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
                for name, path in tool_paths.items()
            },
        },
        "inputs": {
            "tokens": {
                "shape": [1, TOKEN_COUNT],
                "sha256": sha256(args.tokens),
            },
            "style": {"shape": [1, 256], "sha256": sha256(args.style)},
            "speed": {"value": 1.0, "sha256": sha256(args.speed)},
            "seed": SEED,
        },
        "outputs": {
            "duration": {
                "ignored_path": str(duration_path),
                "shape": [TOKEN_COUNT],
                "sum": duration_sum,
                "bytes": duration_path.stat().st_size,
                "sha256": sha256(duration_path),
            },
            "audio": {
                "ignored_path": str(audio_path),
                "shape": [audio_samples],
                "sample_rate_hz": 24000,
                "duration_seconds": audio_samples / 24000.0,
                "bytes": audio_path.stat().st_size,
                "sha256": sha256(audio_path),
                "all_finite": True,
                "absolute_peak": peak,
                "rms": rms,
                "clipped_float_samples": clipped,
            },
        },
        "timing": {
            "model_load_seconds": model_load_seconds,
            "duration_probe_seconds": duration_probe_seconds,
            "full_inference_seconds": inference_seconds,
        },
        "memory": {
            "ru_maxrss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "semantics": "process-lifetime resident-set high-water; includes Python, PyTorch, model load, duration probe, full inference, and outputs; not steady PSS or component-isolated",
        },
        "transformation": {
            "learned_weights_changed": False,
            "quantized": False,
            "stft": "experiment-0013 controlled exact-STFT representation",
            "random_inputs": "SeededSineGen fixed at seed 20260818 and runtime-derived fixed F0/audio shape",
        },
        "claim_boundary": "Controlled-eager CPU oracle for the new canonical-v2 official-frontend derivative; not ONNX export, QNN assignment, physical HTP proof, benchmark performance, or listening acceptance.",
    }
    args.provenance.parent.mkdir(parents=True, exist_ok=True)
    args.provenance.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
