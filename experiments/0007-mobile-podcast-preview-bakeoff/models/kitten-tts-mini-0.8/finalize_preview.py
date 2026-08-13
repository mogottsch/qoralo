#!/usr/bin/env python3
"""Normalize the first accepted Kitten attempt and publish complete task-8 evidence."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GENERATION = ROOT / "artifacts/kitten-tts-mini-0.8/generation"
NORMALIZED = ROOT / "artifacts/normalized/kitten-mini-0.8/v2"
RESULT_PATH = ROOT / "results/kitten-mini-0.8-preview.json"
sys.path.insert(0, str(ROOT / "tools"))
import audio_protocol  # noqa: E402
import protocol  # noqa: E402


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def stats(samples: np.ndarray) -> dict:
    return audio_protocol.audio_statistics(samples.astype(np.float64))


def main() -> None:
    pins = read_json(HERE / "pins.json")
    plan = read_json(HERE / "attempt-plan.json")
    accepted_dir = GENERATION / "attempt-03-speed-0.90/primary"
    repeat_dir = GENERATION / "attempt-03-speed-0.90/repeat-1"
    accepted_report = read_json(accepted_dir / "report.json")
    repeat_report = read_json(repeat_dir / "report.json")
    raw_path, repeat_path = accepted_dir / "native.f32le", repeat_dir / "native.f32le"
    if accepted_report.get("accepted_by_duration") is not True or repeat_report.get("accepted_by_duration") is not True:
        raise SystemExit("accepted primary and repeat evidence are required")
    if accepted_report["attempt"] != plan["attempts"][2] or repeat_report["attempt"] != plan["attempts"][2]:
        raise SystemExit("reports do not identify the selected precommitted attempt")
    raw_hash_before = audio_protocol.sha256_file(raw_path)
    repeat_hash = audio_protocol.sha256_file(repeat_path)
    if raw_hash_before != accepted_report["raw"]["sha256"] or repeat_hash != repeat_report["raw"]["sha256"]:
        raise SystemExit("write-once raw evidence hash mismatch")

    samples = np.fromfile(raw_path, dtype="<f4").astype(np.float64)
    repeated = np.fromfile(repeat_path, dtype="<f4").astype(np.float64)
    if samples.size != accepted_report["raw"]["sample_count"] or repeated.size != repeat_report["raw"]["sample_count"]:
        raise SystemExit("raw sample count mismatch")
    if samples.size < audio_protocol.SAMPLES or not np.all(np.isfinite(samples)):
        raise SystemExit("accepted raw waveform is invalid or too short")

    normalized_path = NORMALIZED / "kitten-mini-0.8-15s.wav"
    derivation_path = NORMALIZED / "derivation.json"
    if normalized_path.exists() or derivation_path.exists():
        raise SystemExit("refusing to overwrite normalized evidence")
    window, start, end = audio_protocol.exact_window(samples)
    faded = audio_protocol.apply_fades(window)
    normalized, gain_db, input_lufs = audio_protocol.normalize_gain(faded)
    pcm = audio_protocol.quantize_s16(normalized)
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    audio_protocol.write_s16_wav(normalized_path, pcm)
    validation = audio_protocol.validate_preview(normalized_path)
    derivation = {
        "source": {"path": relative(raw_path), "sha256": raw_hash_before, "format": "float32le", "sample_rate_hz": 24000},
        "source_sha256": raw_hash_before, "source_rate_hz": 24000, "resampled_samples": int(samples.size),
        "trim_start": start, "trim_end": end, "gain_db": gain_db,
        "pre_gain_loudness_lufs": input_lufs, "output": validation,
        "statistics": stats(pcm.astype(np.float64) / 32768.0),
        "protocol_fingerprint": protocol.protocol_reference()["protocol_fingerprint"],
    }
    with derivation_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(derivation, indent=2, sort_keys=True, allow_nan=False) + "\n")
    if audio_protocol.sha256_file(raw_path) != raw_hash_before:
        raise RuntimeError("normalization modified raw evidence")

    difference = samples - repeated
    old = read_json(RESULT_PATH)
    provenance = old["provenance"]
    provenance["determinism"] = {
        "fresh_process_repeat_count": 1,
        "duration_and_sample_count_match": samples.size == repeated.size,
        "raw_hashes_match": raw_hash_before == repeat_hash,
        "primary_sha256": raw_hash_before, "repeat_sha256": repeat_hash,
        "differing_samples": int(np.count_nonzero(difference)),
        "max_absolute_sample_difference": float(np.max(np.abs(difference))),
        "rms_sample_difference": float(np.sqrt(np.mean(difference * difference))),
        "claim": "Fresh-process repeat matched duration and sample count but not waveform bytes; no bit-exact determinism claim is made.",
    }
    provenance["resource_grant"] = {
        "kind": "full-generation", "task": "task-8", "global_exclusive": True,
        "used_for_every_attempt_and_repeat": True,
    }
    provenance["generation_attempt_plan"] = relative(HERE / "attempt-plan.json")
    provenance["network_during_generation"] = False
    report_sources = [
        ("attempt-01-default-primary", GENERATION / "attempt-01-default-primary.f32le.json"),
        ("attempt-01-default-repeat-1", GENERATION / "attempt-01-default-repeat-1.f32le.json"),
        ("attempt-02-speed-0.95-primary", GENERATION / "attempt-02-speed-0.95/primary/report.json"),
        ("attempt-03-speed-0.90-primary", accepted_dir / "report.json"),
        ("attempt-03-speed-0.90-repeat-1", repeat_dir / "report.json"),
    ]
    provenance["attempt_measurements"] = {
        name: {
            "speed": report["attempt"]["speed"], "accepted_by_duration": report["accepted_by_duration"],
            "raw_sha256": report["raw"]["sha256"], "sample_count": report["raw"]["sample_count"],
            "duration_seconds": report["raw"]["duration_seconds"], "timing": report["timing"],
            "memory": report["memory"],
        }
        for name, path in report_sources for report in [read_json(path)]
    }

    attempts = [
        ("attempt-01-default-primary", "default", "artifacts/kitten-tts-mini-0.8/generation/attempt-01-default-primary.f32le", "rejected", 1.0),
        ("attempt-01-default-repeat-1", "fresh-process-repeat", "artifacts/kitten-tts-mini-0.8/generation/attempt-01-default-repeat-1.f32le", "rejected", 1.0),
        ("attempt-02-speed-0.95-primary", "speed-retry", relative(GENERATION / "attempt-02-speed-0.95/primary/native.f32le"), "rejected", 0.95),
        ("attempt-03-speed-0.90-primary", "speed-retry", relative(raw_path), "accepted", 0.9),
        ("attempt-03-speed-0.90-repeat-1", "fresh-process-repeat", relative(repeat_path), "accepted", 0.9),
    ]
    result = {
        "schema_version": 1, "model": "kitten-tts-mini-0.8", "status": "accepted",
        "protocol": protocol.protocol_reference(), "provenance": provenance,
        "voice": old["voice"],
        "command": [
            "models/kitten-tts-mini-0.8/generate-preview.sh speed-0.95 primary",
            "models/kitten-tts-mini-0.8/generate-preview.sh speed-0.90 primary",
            "models/kitten-tts-mini-0.8/generate-preview.sh speed-0.90 repeat-1",
            "python models/kitten-tts-mini-0.8/finalize_preview.py",
        ],
        "speed_control": {
            "documented": True, "setting": 0.9, "default": 1.0,
            "precommitted_grid": [1.0, 0.95, 0.9], "selection_rule": plan["selection_rule"],
            "note": "Lower speed is slower synthesis through the official inference API, not post-hoc time stretching.",
        },
        "raw": {
            "artifact_path": relative(raw_path), "sha256": raw_hash_before,
            "byte_count": raw_path.stat().st_size, "duration_seconds": samples.size / 24000,
            "sample_count": int(samples.size), "sample_rate_hz": 24000, "channels": 1,
            "output_format": "headerless little-endian IEEE float32 PCM (native library array bytes)",
            "preserved_unchanged": True, "sha256_after_derivation": audio_protocol.sha256_file(raw_path),
            "statistics": stats(samples), "repeat_artifact_path": relative(repeat_path),
            "repeat_sha256": repeat_hash, "repeat_statistics": stats(repeated),
        },
        "normalized": {
            "artifact_path": relative(normalized_path), "sha256": validation["sha256"],
            "bytes": normalized_path.stat().st_size, "duration_seconds": 15.0,
            "sample_rate_hz": 24000, "channels": 1, "sample_count": 360000,
            "sample_format": "PCM_S16LE", "statistics": derivation["statistics"],
            "derivation_metadata_path": relative(derivation_path),
        },
        "timing": {
            **accepted_report["timing"], "api_first_output_unavailable_reason": None,
            "first_audible_output_unavailable_reason": None,
        },
        "memory": accepted_report["memory"], "measurement_contract_version": 1,
        "attempts": [
            {"attempt_id": item_id, "kind": kind, "resource_kind": "full-generation",
             "artifact_path": path, "status": status, "control": {"speed": speed}}
            for item_id, kind, path, status, speed in attempts
        ],
        "licenses": old["licenses"], "publication_eligible": True,
        "forbidden_transformations_used": [],
        "conclusion": "Candidate F passed protocol-v2 at the first eligible duration, speed=0.90; normalized audio is an exact 15-second derivation while every raw attempt remains unchanged.",
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(RESULT_PATH), "normalized": str(normalized_path), "sha256": validation["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
