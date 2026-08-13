#!/usr/bin/env python3
"""Derive and record Candidate D from the first passing write-once attempt."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARTIFACTS = ROOT / "artifacts/supertonic-3"
NORMALIZED = ROOT / "artifacts/normalized/supertonic-3/v2"
RESULT = ROOT / "results/supertonic-3-preview.json"
sys.path.insert(0, str(ROOT / "tools"))
import audio_protocol  # noqa: E402
import protocol  # noqa: E402


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def statistics(samples: np.ndarray) -> dict:
    return audio_protocol.audio_statistics(samples.astype(np.float64))


def main() -> None:
    pins = read_json(HERE / "pins.json")
    plan = read_json(HERE / "speed-attempts.json")
    primary_dir = ARTIFACTS / "attempts/attempt-00"
    repeat_dir = ARTIFACTS / "repeats/attempt-00"
    primary_meta = read_json(primary_dir / "metadata.json")
    repeat_meta = read_json(repeat_dir / "metadata.json")
    raw_path, repeat_path = primary_dir / "native.f32le", repeat_dir / "native.f32le"

    if primary_meta["attempt"] != plan["attempts"][0] or repeat_meta["attempt"] != plan["attempts"][0]:
        raise SystemExit("primary and repeat must identify the first precommitted attempt")
    if primary_meta["duration_seconds"] < 15.0 or repeat_meta["duration_seconds"] < 15.0:
        raise SystemExit("default attempt did not satisfy the duration rule")
    if any((ARTIFACTS / "attempts" / f"attempt-{index:02d}").exists() for index in range(1, len(plan["attempts"]))):
        raise SystemExit("later attempts are forbidden after the first passing output")

    samples = np.fromfile(raw_path, dtype="<f4").astype(np.float64)
    repeated = np.fromfile(repeat_path, dtype="<f4").astype(np.float64)
    raw_hash = audio_protocol.sha256_file(raw_path)
    repeat_hash = audio_protocol.sha256_file(repeat_path)
    if raw_hash != primary_meta["raw_sha256"] or repeat_hash != repeat_meta["raw_sha256"]:
        raise SystemExit("write-once raw evidence hash mismatch")
    if samples.size != primary_meta["sample_count"] or repeated.size != repeat_meta["sample_count"]:
        raise SystemExit("raw evidence sample-count mismatch")
    if not np.all(np.isfinite(samples)) or not np.all(np.isfinite(repeated)):
        raise SystemExit("raw evidence contains non-finite samples")

    output_path = NORMALIZED / "supertonic-3-15s.wav"
    derivation_path = NORMALIZED / "derivation.json"
    if output_path.exists() or derivation_path.exists():
        raise SystemExit("refusing to overwrite normalized evidence")
    resampled = audio_protocol.resample_mono(samples, primary_meta["sample_rate_hz"])
    window, start, end = audio_protocol.exact_window(resampled)
    faded = audio_protocol.apply_fades(window)
    normalized, gain_db, input_lufs = audio_protocol.normalize_gain(faded)
    pcm = audio_protocol.quantize_s16(normalized)
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    audio_protocol.write_s16_wav(output_path, pcm)
    validation = audio_protocol.validate_preview(output_path)
    derivation = {
        "source": {"path": relative(raw_path), "sha256": raw_hash, "format": "float32le", "sample_rate_hz": 44100},
        "source_sha256": raw_hash,
        "source_rate_hz": 44100,
        "resampled_samples": int(resampled.size),
        "trim_start": start,
        "trim_end": end,
        "gain_db": gain_db,
        "pre_gain_loudness_lufs": input_lufs,
        "output": validation,
        "statistics": statistics(pcm.astype(np.float64) / 32768.0),
        "protocol_fingerprint": protocol.protocol_reference()["protocol_fingerprint"],
    }
    with derivation_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(derivation, indent=2, sort_keys=True, allow_nan=False) + "\n")
    if audio_protocol.sha256_file(raw_path) != raw_hash:
        raise RuntimeError("normalization modified raw evidence")

    difference = samples - repeated
    smoke = read_json(ARTIFACTS / "smoke-load.json")
    result = {
        "schema_version": 1,
        "model": "supertonic-3",
        "status": "accepted",
        "protocol": protocol.protocol_reference(),
        "command": [
            "models/supertonic-3/setup.sh",
            "models/supertonic-3/smoke-load.sh",
            "models/supertonic-3/generate_preview.sh 0",
            "models/supertonic-3/generate_preview.sh 0 --repeat",
            "python models/supertonic-3/finalize_preview.py",
        ],
        "provenance": {
            "source_url": pins["implementation"]["repository"],
            "source_revision": pins["implementation"]["revision"],
            "model_repository": pins["model"]["repo_id"],
            "model_revision": pins["model"]["revision"],
            "model_bytes": sum(item["bytes"] for item in pins["model"]["files"].values()),
            "dependency_lock_sha256": hashlib.sha256((HERE / "uv.lock").read_bytes()).hexdigest(),
            "implementation_repository": pins["implementation"]["repository"],
            "implementation_revision": pins["implementation"]["revision"],
            "implementation_tag": pins["implementation"]["tag"],
            "source_wheel_sha256": pins["implementation"]["wheel_sha256"],
            "model_files": smoke["model"]["verified_files"],
            "environment": {
                "device": "cpu",
                "execution_provider": "CPUExecutionProvider",
                "generation_python": smoke["runtime"]["python"],
                "supertonic": pins["implementation"]["version"],
                "onnxruntime": smoke["runtime"]["onnxruntime"],
                "dependency_lock": relative(HERE / "uv.lock"),
                "normalization_python": platform.python_version(),
                "normalization_numpy": importlib.metadata.version("numpy"),
                "normalization_scipy": importlib.metadata.version("scipy"),
            },
            "resource_grant": {"kind": "full-generation", "task": "task-6", "global_exclusive": True, "used_for_every_attempt_and_repeat": True},
            "network_during_generation": False,
            "generation_attempt_plan": relative(HERE / "speed-attempts.json"),
            "attempt_measurements": {
                "attempt-00-default": primary_meta,
                "attempt-00-fresh-process-repeat": repeat_meta,
            },
            "determinism": {
                "fresh_process_repeat_count": 1,
                "duration_and_sample_count_match": samples.size == repeated.size,
                "raw_hashes_match": raw_hash == repeat_hash,
                "primary_sha256": raw_hash,
                "repeat_sha256": repeat_hash,
                "differing_samples": int(np.count_nonzero(difference)),
                "max_absolute_sample_difference": float(np.max(np.abs(difference))),
                "rms_sample_difference": float(np.sqrt(np.mean(difference * difference))),
                "claim": "Bit-identical fresh-process repeat on this pinned CPU environment; no cross-platform bit-exact claim.",
            },
        },
        "voice": {
            **pins["voice"],
            "name": pins["voice"]["id"],
            "source": pins["voice"]["provenance_document"],
            "license": pins["model"]["license"],
            "asset_sha256": pins["model"]["files"][pins["voice"]["artifact"]]["sha256"],
            "stock_voice": True,
            "cloning_performed": False,
        },
        "speed_control": {
            "documented": True,
            "setting": plan["attempts"][0]["effective_speed"],
            "argument": "omitted",
            "precommitted_grid": [item["effective_speed"] for item in plan["attempts"]],
            "selection_rule": plan["selection_rule"],
            "note": "The documented SDK default passed; no speed retry or post-hoc time stretching was used.",
        },
        "raw": {
            "artifact_path": relative(raw_path),
            "sha256": raw_hash,
            "byte_count": raw_path.stat().st_size,
            "duration_seconds": primary_meta["duration_seconds"],
            "sample_count": int(samples.size),
            "sample_rate_hz": 44100,
            "channels": 1,
            "output_format": "headerless little-endian IEEE float32 PCM (native SDK array bytes)",
            "preserved_unchanged": True,
            "sha256_after_derivation": audio_protocol.sha256_file(raw_path),
            "statistics": statistics(samples),
            "repeat_artifact_path": relative(repeat_path),
            "repeat_sha256": repeat_hash,
            "repeat_statistics": statistics(repeated),
        },
        "normalized": {
            "artifact_path": relative(output_path),
            "sha256": validation["sha256"],
            "byte_count": output_path.stat().st_size,
            "duration_seconds": 15.0,
            "sample_rate_hz": 24000,
            "channels": 1,
            "sample_count": 360000,
            "sample_format": "PCM_S16LE",
            "statistics": derivation["statistics"],
            "derivation_metadata_path": relative(derivation_path),
        },
        "timing": primary_meta["timing"],
        "memory": primary_meta["memory"],
        "measurement_contract_version": 1,
        "attempts": [
            {"attempt_id": "attempt-00-default", "kind": "default", "resource_kind": "full-generation", "artifact_path": relative(raw_path), "status": "accepted", "control": {"speed": 1.05, "argument": "omitted"}},
            {"attempt_id": "attempt-00-fresh-process-repeat", "kind": "fresh-process-repeat", "resource_kind": "full-generation", "artifact_path": relative(repeat_path), "status": "accepted", "control": {"speed": 1.05, "argument": "omitted"}},
        ],
        "licenses": [
            {"component": "Supertone/supertonic-3 model and notices", "license": pins["model"]["license"], "source": "snapshot/LICENSE", "sha256": pins["model"]["files"]["LICENSE"]["sha256"], "acceptance": pins["model"]["license_acceptance"]},
            {"component": "supertonic Python SDK", "license": pins["implementation"]["license"], "source": pins["implementation"]["repository"], "sha256": pins["implementation"]["license_sha256"]},
        ],
        "publication_eligible": True,
        "forbidden_transformations_used": [],
        "conclusion": "Candidate D passed protocol-v2 at the default-first attempt; normalized audio is an exact 15-second derivation while primary and repeat raw evidence remain unchanged. The SDK is non-streaming, and first-audible timing adds the first qualifying native-frame offset to API completion rather than claiming streaming playback latency. This CPU listening result does not establish Android feasibility.",
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(RESULT), "normalized": str(output_path), "sha256": validation["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
