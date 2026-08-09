#!/usr/bin/env python3
"""Derive and validate task 6's normalized comparison copy with protocol-pinned tools."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audio_protocol
import protocol


def main() -> None:
    raw_dir = ROOT / "artifacts/raw/realtime"
    normalized_dir = ROOT / "artifacts/normalized/realtime"
    capture_path = raw_dir / "capture.json"
    raw_wav = raw_dir / "assembled-native.wav"
    normalized_wav = normalized_dir / "realtime-15s.wav"
    derivation_path = normalized_dir / "derivation.json"
    result_path = ROOT / "results/realtime-preview.json"
    if not capture_path.is_file() or not raw_wav.is_file():
        raise SystemExit("run generate-preview.sh first")
    for output in (normalized_wav, derivation_path, result_path):
        if output.exists():
            raise SystemExit(f"refusing to overwrite existing evidence: {output}")

    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    raw_hash_before = audio_protocol.sha256_file(raw_wav)
    if raw_hash_before != capture["primary"]["assembled_wav"]["sha256"]:
        raise RuntimeError("assembled raw WAV changed after capture")
    raw_samples, raw_rate = audio_protocol.read_pcm_wav(raw_wav)
    if raw_rate != 24_000 or raw_samples.size < audio_protocol.SAMPLES:
        raise RuntimeError("native output is too short or has the wrong rate")

    normalized_dir.mkdir(parents=True, exist_ok=True)
    derivation = audio_protocol.derive(raw_wav, normalized_wav)
    derivation_path.write_text(json.dumps(derivation, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    raw_hash_after = audio_protocol.sha256_file(raw_wav)
    if raw_hash_after != raw_hash_before:
        raise RuntimeError("normalization modified raw evidence")

    raw_stats = audio_protocol.audio_statistics(raw_samples)
    normalized_samples, _ = audio_protocol.read_pcm_wav(normalized_wav)
    normalized_stats = audio_protocol.audio_statistics(normalized_samples)
    primary = capture["primary"]
    raw_duration = raw_samples.size / raw_rate
    pins = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
    provenance = json.loads((HERE / "provenance.json").read_text(encoding="utf-8"))
    result = {
        "schema_version": 1,
        "model": "realtime",
        "status": "accepted",
        "protocol": protocol.protocol_reference(),
        "provenance": {
            "source_revision": pins["source"]["revision"],
            "model_revision": pins["model"]["revision"],
            "tokenizer_revision": pins["tokenizer"]["revision"],
            "source_url": pins["source"]["repository"],
            "model_url": pins["model"]["repository"],
            "model_bytes": pins["model"]["files"]["model.safetensors"]["bytes"],
            "model_sha256": pins["model"]["files"]["model.safetensors"]["sha256"],
            "lazy_download_bytes_during_generation": 0,
            "device": capture["device"],
            "dtype": "bfloat16",
            "attention": "sdpa",
            "diffusion_steps": 5,
            "cfg_scale": 1.5,
            "token_sampling": False,
            "seed": capture["seed"],
            "seed_support": capture["seed_support"],
            "determinism": capture["determinism"],
            "streaming_chunk_count": len(primary["chunks"]),
            "streaming_chunks": primary["chunks"],
            "raw_capture_metadata_path": str(capture_path.relative_to(ROOT)),
            "generation_command": ["models/vibevoice-realtime/generate-preview.sh"],
            "derivation_command": ["python3", "models/vibevoice-realtime/finalize_preview.py"],
            "anomalies": [
                "No generation exception, empty chunk, non-finite sample, clipping, or hash drift was observed.",
                "Subjective audible anomaly review is pending_user_review; no listening claim was invented.",
            ],
        },
        "voice": {
            "name": "en-Grace_woman.pt",
            "source": provenance["voice_conditioning"]["provenance"],
            "sha256": capture["voice_sha256"],
            "stock_voice": True,
        },
        "command": ["models/vibevoice-realtime/generate-preview.sh"],
        "speed_control": {"documented": False, "setting": None, "regeneration_needed": False},
        "raw": {
            "artifact_path": str(raw_wav.relative_to(ROOT)),
            "sha256": raw_hash_before,
            "bytes": raw_wav.stat().st_size,
            "duration_seconds": raw_duration,
            "sample_rate_hz": raw_rate,
            "channels": 1,
            "sample_count": int(raw_samples.size),
            "output_format": "WAV PCM_S16LE",
            "statistics": raw_stats,
            "streaming_chunk_count": len(primary["chunks"]),
            "preserved_unchanged": True,
            "sha256_after_derivation": raw_hash_after,
        },
        "normalized": {
            "artifact_path": str(normalized_wav.relative_to(ROOT)),
            "sha256": derivation["output"]["sha256"],
            "bytes": normalized_wav.stat().st_size,
            "duration_seconds": 15.0,
            "sample_rate_hz": 24_000,
            "channels": 1,
            "sample_count": 360_000,
            "sample_format": "PCM_S16LE",
            "statistics": normalized_stats,
            "derivation_metadata_path": str(derivation_path.relative_to(ROOT)),
        },
        "timing": {
            "generation_wall_seconds": primary["wall_seconds"],
            "api_first_output_seconds": primary["api_first_output_seconds"],
            "first_audible_output_seconds": primary["first_audible_output_seconds"],
            "rtf": audio_protocol.real_time_factor(primary["wall_seconds"], raw_duration),
        },
        "memory": {
            "baseline_rss_bytes": capture["baseline_rss_bytes"],
            "peak_process_tree_rss_bytes": capture["rss"]["peak_process_tree_rss_bytes"],
            "sample_interval_ms": round(capture["rss"]["sampling_interval_seconds"] * 1000),
        },
        "forbidden_transformations_used": [],
        "conclusion": "Host-preview-only listening and reproducibility evidence; this result makes no Android or mobile-feasibility claim.",
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(result_path), "normalized": str(normalized_wav), "sha256": result["normalized"]["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
