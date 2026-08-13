#!/usr/bin/env python3
"""Shared, dependency-light helpers for the Kokoro INT8 quality gate."""
from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import unicodedata
import wave
from pathlib import Path
from typing import Any, Iterable, Sequence

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]


def find_project_root(start: Path = EXPERIMENT_ROOT) -> Path:
    for path in (start, *start.parents):
        if (path / ".git").exists():
            return path
    raise RuntimeError("could not find project root")


PROJECT_ROOT = find_project_root()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def experiment_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(EXPERIMENT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def project_path(value: str) -> Path:
    return PROJECT_ROOT / value


def verify_file(path: Path, expected: dict[str, Any], label: str | None = None) -> dict[str, Any]:
    name = label or str(path)
    if not path.is_file():
        raise RuntimeError(f"missing pinned file: {name}: {path}")
    size = path.stat().st_size
    if "bytes" in expected and size != expected["bytes"]:
        raise RuntimeError(f"size mismatch for {name}: {size} != {expected['bytes']}")
    digest = sha256_file(path)
    if digest != expected["sha256"]:
        raise RuntimeError(f"SHA-256 mismatch for {name}: {digest} != {expected['sha256']}")
    return {"bytes": size, "sha256": digest}


def validate_source(source_root: Path, source_manifest_path: Path, verify_archive: bool = True) -> dict[str, Any]:
    manifest = load_json(source_manifest_path)
    evidence: dict[str, Any] = {
        "deployment_variant": manifest["deployment_variant"],
        "required_files": {},
        "experiment_0008_evidence": {},
    }
    if source_root.name != manifest["archive"]["expected_root"]:
        raise RuntimeError(
            f"source root must be named {manifest['archive']['expected_root']}, got {source_root.name}"
        )
    if not source_root.is_dir() or source_root.is_symlink():
        raise RuntimeError("exact source root must be a real directory, not a symlink")
    if verify_archive:
        archive = project_path(manifest["archive"]["project_path"])
        evidence["archive"] = verify_file(archive, manifest["archive"], "exact experiment 0008 archive")
    for relative, pin in manifest["required_files"].items():
        evidence["required_files"][relative] = verify_file(source_root / relative, pin, relative)

    # Pin the experiment 0008 provenance documents themselves, then use its deployed
    # inventory to verify every extracted frontend/model byte rather than spot-checking
    # only model.onnx and a few English files.
    for name, pin in manifest["experiment_0008_evidence"].items():
        evidence_path = project_path(pin["project_path"])
        evidence["experiment_0008_evidence"][name] = verify_file(
            evidence_path, pin, f"experiment 0008 {name}"
        )
    inventory_pin = manifest["experiment_0008_evidence"]["deployed_inventory"]
    inventory = load_json(project_path(inventory_pin["project_path"]))
    entries = inventory.get("files")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("pinned experiment 0008 deployed inventory is empty")
    expected: dict[str, dict[str, Any]] = {}
    for entry in entries:
        relative = entry.get("path")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or relative in expected
        ):
            raise RuntimeError(f"unsafe or duplicate deployed inventory path: {relative!r}")
        expected[relative] = entry
    actual: set[str] = set()
    for path in source_root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"source tree contains a symlink: {path}")
        if path.is_file():
            actual.add(path.relative_to(source_root).as_posix())
    if actual != set(expected):
        raise RuntimeError(
            f"source tree differs from pinned inventory; missing={sorted(set(expected) - actual)}, "
            f"unexpected={sorted(actual - set(expected))}"
        )
    for relative, pin in expected.items():
        verify_file(source_root / relative, pin, f"deployed source {relative}")
    evidence["full_source_inventory"] = {
        "inventory_sha256": evidence["experiment_0008_evidence"]["deployed_inventory"]["sha256"],
        "file_count": len(expected),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "every_file_size_and_sha256_verified": True,
        "unexpected_files_rejected": True,
        "symlinks_rejected": True,
    }
    return evidence


def load_corpus(path: Path) -> dict[str, Any]:
    corpus = load_json(path)
    if corpus.get("schema_version") != 1 or corpus.get("language") != "en-US":
        raise RuntimeError("unsupported corpus schema or language")
    seen: set[str] = set()
    for partition in ("calibration", "evaluation"):
        values = corpus.get(partition)
        if not isinstance(values, list) or len(values) < 2:
            raise RuntimeError(f"{partition} must contain multiple complete utterances")
        for value in values:
            utterance_id, text = value.get("id"), value.get("text")
            if not isinstance(utterance_id, str) or not re.fullmatch(r"[a-z0-9-]+", utterance_id):
                raise RuntimeError(f"invalid utterance id: {utterance_id!r}")
            if utterance_id in seen:
                raise RuntimeError(f"duplicate utterance id: {utterance_id}")
            seen.add(utterance_id)
            if not isinstance(text, str) or not text.strip() or text != text.strip():
                raise RuntimeError(f"invalid complete utterance: {utterance_id}")
            if "\n" in text or "\r" in text:
                raise RuntimeError(f"utterance must be passed whole, not line-split: {utterance_id}")
    return corpus


def read_pcm16_wav(path: Path) -> tuple[int, "Any"]:
    # Imported lazily so manifest and blind-package tests do not require NumPy.
    import numpy as np

    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        sample_rate = source.getframerate()
        frames = source.getnframes()
        compression = source.getcomptype()
        payload = source.readframes(frames)
        trailing = source.readframes(1)
    if channels != 1 or width != 2 or compression != "NONE":
        raise RuntimeError(f"expected mono PCM16 WAV: {path}")
    if sample_rate != 24000 or frames <= 0 or len(payload) != frames * 2 or trailing:
        raise RuntimeError(f"invalid WAV frame declaration or sample rate: {path}")
    samples = np.frombuffer(payload, dtype="<i2").astype(np.float64) / 32768.0
    if not np.all(np.isfinite(samples)):
        raise RuntimeError(f"non-finite decoded samples: {path}")
    return sample_rate, samples


def write_pcm16_wav(path: Path, samples: Sequence[float], sample_rate: int) -> dict[str, Any]:
    import numpy as np

    values = np.asarray(samples, dtype=np.float64)
    if sample_rate != 24000 or values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise RuntimeError("source samples must be finite, non-empty, mono, and 24 kHz")
    source_clip_count = int(np.count_nonzero(np.abs(values) > 1.0))
    pcm = np.rint(np.clip(values, -1.0, 1.0) * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with wave.open(str(temporary), "wb") as output:
        output.setparams((1, 2, sample_rate, values.size, "NONE", "not compressed"))
        output.writeframes(pcm.tobytes())
    temporary.replace(path)
    return {
        "source_sample_count": int(values.size),
        "source_peak": float(np.max(np.abs(values))),
        "source_clip_count": source_clip_count,
    }


def _percentile(values: "Any", percentile: float) -> float | None:
    import numpy as np

    return None if values.size == 0 else float(np.percentile(values, percentile))


def analyze_wav(path: Path) -> dict[str, Any]:
    """Decode the whole WAV and return integrity plus aggregate acoustic behavior.

    Pair decisions deliberately use no raw waveform/sample MSE. Kokoro contains random
    operators, and sample alignment is neither stable nor a perceptual quality metric.
    """
    import numpy as np

    sample_rate, samples = read_pcm16_wav(path)
    frame_size = round(sample_rate * 0.025)
    hop = round(sample_rate * 0.010)
    if samples.size < frame_size:
        padded = np.pad(samples, (0, frame_size - samples.size))
        frames = padded.reshape(1, -1)
    else:
        starts = np.arange(0, samples.size - frame_size + 1, hop)
        frames = np.stack([samples[start : start + frame_size] for start in starts])
    frame_rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-20)
    silence_threshold = 10 ** (-50.0 / 20.0)
    silent = frame_rms < silence_threshold
    active = ~silent
    leading = 0
    while leading < silent.size and silent[leading]:
        leading += 1
    trailing = 0
    while trailing < silent.size and silent[silent.size - trailing - 1]:
        trailing += 1

    window = np.hanning(frame_size)
    spectra = np.abs(np.fft.rfft(frames * window, n=1024, axis=1)) ** 2
    frequencies = np.fft.rfftfreq(1024, 1.0 / sample_rate)
    active_spectra = spectra[active]
    if active_spectra.size:
        power_sum = np.sum(active_spectra, axis=1) + 1e-20
        centroids = np.sum(active_spectra * frequencies, axis=1) / power_sum
        cumulative = np.cumsum(active_spectra, axis=1)
        rolloff_indexes = np.argmax(cumulative >= (0.85 * cumulative[:, -1:]), axis=1)
        rolloffs = frequencies[rolloff_indexes]
        mel_min = 2595.0 * math.log10(1.0 + 80.0 / 700.0)
        mel_max = 2595.0 * math.log10(1.0 + 8000.0 / 700.0)
        mel_edges = np.linspace(mel_min, mel_max, 33)
        hz_edges = 700.0 * (10 ** (mel_edges / 2595.0) - 1.0)
        envelope = []
        mean_power = np.mean(active_spectra, axis=0)
        for low, high in zip(hz_edges[:-1], hz_edges[1:]):
            mask = (frequencies >= low) & (frequencies < high)
            envelope.append(float(np.sum(mean_power[mask])) if np.any(mask) else 0.0)
        envelope_array = np.asarray(envelope, dtype=np.float64)
        envelope_array /= float(np.sum(envelope_array) + 1e-20)
    else:
        centroids = np.asarray([], dtype=np.float64)
        rolloffs = np.asarray([], dtype=np.float64)
        envelope_array = np.zeros(32, dtype=np.float64)

    pitch_size = round(sample_rate * 0.040)
    if samples.size >= pitch_size:
        pitch_starts = np.arange(0, samples.size - pitch_size + 1, hop)
        pitch_frames = np.stack([samples[start : start + pitch_size] for start in pitch_starts])
        pitch_frames -= np.mean(pitch_frames, axis=1, keepdims=True)
        pitch_energy = np.sqrt(np.mean(pitch_frames * pitch_frames, axis=1) + 1e-20)
        pitch_frames *= np.hanning(pitch_size)
        fft = np.fft.rfft(pitch_frames, n=2048, axis=1)
        autocorrelation = np.fft.irfft(fft * np.conj(fft), n=2048, axis=1)[:, :pitch_size]
        autocorrelation /= np.maximum(autocorrelation[:, :1], 1e-20)
        min_lag = sample_rate // 400
        max_lag = sample_rate // 60
        candidates = autocorrelation[:, min_lag : max_lag + 1]
        offsets = np.argmax(candidates, axis=1)
        strengths = candidates[np.arange(candidates.shape[0]), offsets]
        voiced = (strengths >= 0.30) & (pitch_energy >= silence_threshold)
        pitches = sample_rate / (offsets[voiced] + min_lag)
        voiced_fraction = float(np.count_nonzero(voiced) / voiced.size)
    else:
        pitches = np.asarray([], dtype=np.float64)
        voiced_fraction = 0.0

    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(samples * samples)))
    pcm_clip_count = int(np.count_nonzero(np.abs(samples) >= (32767.0 / 32768.0)))
    return {
        "path": experiment_relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "format": {
            "decoder": "python_stdlib_wave_full_decode",
            "channels": 1,
            "sample_width_bytes": 2,
            "sample_rate_hz": sample_rate,
            "frames": int(samples.size),
            "duration_seconds": float(samples.size / sample_rate),
        },
        "integrity": {
            "finite": True,
            "non_silent": bool(rms >= 1e-5 and peak > 0.0),
            "pcm_peak": peak,
            "pcm_rms": rms,
            "pcm_clip_count": pcm_clip_count,
            "pcm_clip_fraction": float(pcm_clip_count / samples.size),
            "silent_frame_fraction_below_minus_50_dbfs": float(np.mean(silent)),
            "leading_silence_seconds": float(leading * hop / sample_rate),
            "trailing_silence_seconds": float(trailing * hop / sample_rate),
        },
        "acoustic_behavior": {
            "method": "aggregate voiced-frame autocorrelation pitch and FFT power distribution; not speaker verification",
            "active_frame_count": int(np.count_nonzero(active)),
            "spectral_centroid_hz_median": _percentile(centroids, 50),
            "spectral_centroid_hz_iqr": (
                None if centroids.size == 0 else float(np.percentile(centroids, 75) - np.percentile(centroids, 25))
            ),
            "spectral_rolloff_85_hz_median": _percentile(rolloffs, 50),
            "pitch_hz_median": _percentile(pitches, 50),
            "pitch_hz_iqr": (
                None if pitches.size == 0 else float(np.percentile(pitches, 75) - np.percentile(pitches, 25))
            ),
            "voiced_frame_fraction": voiced_fraction,
            "normalized_32_band_power": [float(value) for value in envelope_array],
        },
    }


def _relative_difference(first: float | None, second: float | None) -> float | None:
    if first is None or second is None:
        return None
    denominator = max(abs(first), 1e-12)
    return float(abs(second - first) / denominator)


def compare_acoustic_behavior(fp32: dict[str, Any], int8: dict[str, Any]) -> dict[str, Any]:
    import numpy as np

    f_format, q_format = fp32["format"], int8["format"]
    f_audio, q_audio = fp32["acoustic_behavior"], int8["acoustic_behavior"]
    duration_ratio = q_format["duration_seconds"] / f_format["duration_seconds"]
    f_envelope = np.asarray(f_audio["normalized_32_band_power"], dtype=np.float64)
    q_envelope = np.asarray(q_audio["normalized_32_band_power"], dtype=np.float64)
    denominator = float(np.linalg.norm(f_envelope) * np.linalg.norm(q_envelope))
    envelope_cosine = float(np.dot(f_envelope, q_envelope) / denominator) if denominator else 0.0
    metrics = {
        "duration_ratio_int8_over_fp32": float(duration_ratio),
        "pitch_median_relative_difference": _relative_difference(
            f_audio["pitch_hz_median"], q_audio["pitch_hz_median"]
        ),
        "voiced_fraction_absolute_difference": float(
            abs(q_audio["voiced_frame_fraction"] - f_audio["voiced_frame_fraction"])
        ),
        "spectral_centroid_relative_difference": _relative_difference(
            f_audio["spectral_centroid_hz_median"], q_audio["spectral_centroid_hz_median"]
        ),
        "normalized_32_band_power_cosine": envelope_cosine,
    }
    checks = {
        "duration_ratio_between_0_80_and_1_25": 0.80 <= duration_ratio <= 1.25,
        "pitch_median_relative_difference_at_most_0_20": (
            metrics["pitch_median_relative_difference"] is not None
            and metrics["pitch_median_relative_difference"] <= 0.20
        ),
        "voiced_fraction_absolute_difference_at_most_0_20": (
            metrics["voiced_fraction_absolute_difference"] <= 0.20
        ),
        "spectral_centroid_relative_difference_at_most_0_20": (
            metrics["spectral_centroid_relative_difference"] is not None
            and metrics["spectral_centroid_relative_difference"] <= 0.20
        ),
        "normalized_32_band_power_cosine_at_least_0_90": envelope_cosine >= 0.90,
    }
    return {
        "method_note": "Aggregate distributions only; no raw sample MSE or sample-aligned quality decision is used.",
        "metrics": metrics,
        "checks": checks,
        "passed": all(checks.values()),
    }


def normalize_asr_text(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    normalized = re.sub(r"[^\w']+", " ", normalized, flags=re.UNICODE)
    return normalized.split()


def word_errors(reference: str, hypothesis: str) -> tuple[int, int]:
    expected, actual = normalize_asr_text(reference), normalize_asr_text(hypothesis)
    previous = list(range(len(actual) + 1))
    for row, expected_word in enumerate(expected, start=1):
        current = [row]
        for column, actual_word in enumerate(actual, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected_word != actual_word),
                )
            )
        previous = current
    return previous[-1], len(expected)


def contains_forbidden_mse_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any("mse" in str(key).casefold() or contains_forbidden_mse_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_mse_key(item) for item in value)
    return False
