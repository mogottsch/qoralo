from __future__ import annotations

import importlib.util
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).parents[1] / "export/compare_generation_audio.py"
SPEC = importlib.util.spec_from_file_location("compare_generation_audio", MODULE_PATH)
assert SPEC and SPEC.loader
comparison = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = comparison
SPEC.loader.exec_module(comparison)


def write_wav(path: Path, samples: np.ndarray, *, rate: int = 24_000, channels: int = 1, width: int = 2) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(np.asarray(samples, dtype="<i2").tobytes())


def test_read_and_verify_pcm_s16le(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    samples = np.array([-32768, -100, 0, 100, 32767], dtype=np.int16)
    write_wav(path, samples)

    audio = comparison.read_pcm_s16le_mono(path)
    record = comparison.verify_audio(
        audio, expected_sha256=comparison.file_sha256(path), expected_samples=5
    )

    assert record["verified"] is True
    assert record["encoding"] == "PCM_S16LE"
    assert record["duration_seconds"] == pytest.approx(5 / 24_000)
    assert audio.samples_i16.tolist() == samples.tolist()


def test_reader_rejects_non_mono_wav(tmp_path: Path) -> None:
    path = tmp_path / "stereo.wav"
    write_wav(path, np.zeros(20, dtype=np.int16), channels=2)
    with pytest.raises(ValueError, match="expected mono"):
        comparison.read_pcm_s16le_mono(path)


def test_alignment_recovers_candidate_offset() -> None:
    rng = np.random.default_rng(42)
    candidate = rng.normal(size=1000)
    reference = np.concatenate((np.zeros(321), candidate, np.zeros(100)))

    result = comparison.alignment(reference, candidate, 24_000)

    assert result["status"] == "measured"
    assert result["lag_samples"] == 321
    assert result["overlap_samples"] == 1000
    assert result["normalized_cross_correlation"] == pytest.approx(1.0, abs=1e-12)


def test_silence_makes_alignment_and_spectrum_unavailable() -> None:
    tone = np.sin(2 * np.pi * 440 * np.arange(2400) / 24_000)
    silence = np.zeros(640)

    aligned = comparison.alignment(tone, silence, 24_000)
    spectrum = comparison.spectral_stats(silence, 24_000)

    assert aligned == {
        "status": "insufficient_energy",
        "lag_samples": None,
        "lag_seconds": None,
        "normalized_cross_correlation": None,
        "overlap_samples": 0,
    }
    assert spectrum["status"] == "insufficient_energy"
    assert spectrum["centroid_hz"] is None


def test_spectral_stats_locate_tone() -> None:
    samples = np.sin(2 * np.pi * 1000 * np.arange(24_000) / 24_000)
    result = comparison.spectral_stats(samples, 24_000)

    assert result["status"] == "measured"
    assert result["centroid_hz"] == pytest.approx(1000.0, abs=1.0)
    assert result["rolloff_95_hz"] == pytest.approx(1000.0, abs=1.0)
    assert result["band_energy_fraction"]["1000-4000_hz"] > 0.49


def test_waveform_stats_reports_silence_without_nonfinite_json_values() -> None:
    stats = comparison.waveform_stats(np.zeros(10))
    assert stats["rms"] == 0.0
    assert stats["rms_dbfs"] is None
    assert stats["peak"] == 0.0
    assert stats["clipped_samples"] == 0
