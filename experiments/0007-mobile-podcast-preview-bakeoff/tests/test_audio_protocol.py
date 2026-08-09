import math
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audio_protocol as ap


def wav(path, samples, rate=24000, channels=1):
    values = np.asarray(samples)
    if channels > 1 and values.ndim == 1:
        values = np.column_stack([values] * channels)
    pcm = np.clip(np.rint(values * 32768), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(channels); f.setsampwidth(2); f.setframerate(rate); f.writeframes(pcm.tobytes())


def tone(seconds, rate=24000, hz=220, amplitude=.2):
    t = np.arange(round(seconds * rate)) / rate
    return amplitude * np.sin(2 * np.pi * hz * t)


def test_read_mono_is_arithmetic_mean(tmp_path):
    path = tmp_path / "stereo.wav"
    left, right = tone(1), -tone(1) + .2
    wav(path, np.column_stack([left, right]), channels=2)
    mono, rate = ap.read_pcm_wav(path)
    assert rate == 24000
    assert np.mean(mono) == pytest.approx(.1, abs=2e-5)


def test_malformed_and_empty_input_rejected(tmp_path):
    path = tmp_path / "bad.wav"; path.write_bytes(b"not wave")
    with pytest.raises(ValueError, match="malformed WAV"): ap.read_pcm_wav(path)
    with pytest.raises(ValueError): ap.resample_mono(np.array([]), 24000)


def test_resample_is_deterministic_and_has_frozen_length():
    source = tone(16, 16000)
    one, two = ap.resample_mono(source, 16000), ap.resample_mono(source, 16000)
    assert len(one) == 384000
    np.testing.assert_array_equal(one, two)
    assert np.sqrt(np.mean(one**2)) == pytest.approx(np.sqrt(np.mean(source**2)), rel=.002)


def test_zero_crossing_selection_and_exact_window():
    samples = np.ones(ap.SAMPLES + 100)
    samples[ap.SAMPLES + 37] = -.5
    end = ap.choose_trim_end(samples)
    assert end in (ap.SAMPLES + 37, ap.SAMPLES + 38)
    output, start, chosen = ap.exact_window(samples)
    assert len(output) == ap.SAMPLES and chosen - start == ap.SAMPLES


def test_too_short_rejected():
    with pytest.raises(ValueError, match="too short"): ap.exact_window(np.zeros(ap.SAMPLES - 1))


def test_fades_have_zero_endpoints_and_preserve_middle():
    out = ap.apply_fades(np.ones(ap.SAMPLES))
    assert out[0] == 0 and out[-1] == 0
    assert out[ap.FADE_SAMPLES] == 1
    assert np.all(np.diff(out[:ap.FADE_SAMPLES]) >= 0)


def test_normalization_target_and_peak_ceiling():
    normalized, gain, before = ap.normalize_gain(tone(15, amplitude=.03))
    assert before < ap.TARGET_LUFS
    assert ap.integrated_loudness(normalized) == pytest.approx(ap.TARGET_LUFS, abs=.02)
    loud = tone(15, amplitude=.99)
    limited, gain, _ = ap.normalize_gain(loud)
    assert 20 * math.log10(np.max(np.abs(limited))) <= ap.PEAK_DBFS + 1e-9
    quantized = ap.quantize_s16(limited)
    assert 20 * math.log10(np.max(np.abs(quantized)) / 32768) <= ap.PEAK_DBFS


def test_dither_is_deterministic_and_statistics_and_rtf():
    a = ap.quantize_s16(np.zeros(10000)); b = ap.quantize_s16(np.zeros(10000))
    np.testing.assert_array_equal(a, b)
    assert np.any(a != 0)
    stats = ap.audio_statistics(tone(15, amplitude=.2))
    assert stats["rms_dbfs"] == pytest.approx(20 * math.log10(.2 / math.sqrt(2)), abs=.01)
    assert ap.real_time_factor(3, 15) == .2
    with pytest.raises(ValueError): ap.real_time_factor(1, 0)


def test_raw_preservation_refuses_overwrite_and_hashes(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "raw" / "native"
    source.write_bytes(b"native bytes")
    digest = ap.preserve_raw(source, destination)
    assert digest == ap.sha256_file(source) == ap.sha256_file(destination)
    with pytest.raises(FileExistsError): ap.preserve_raw(source, destination)


def test_full_derivation_and_exact_format(tmp_path):
    source, output = tmp_path / "source.wav", tmp_path / "preview.wav"
    wav(source, tone(15.1, rate=16000), rate=16000)
    result = ap.derive(source, output)
    assert result["output"]["sample_count"] == 360000
    assert result["output"]["duration_seconds"] == 15
    assert result["output"]["channels"] == 1
    assert result["output"]["sample_width_bytes"] == 2
    assert ap.validate_preview(output)["sample_rate_hz"] == 24000


def test_validation_rejects_wrong_format(tmp_path):
    path = tmp_path / "short.wav"; wav(path, tone(1))
    with pytest.raises(ValueError, match="format mismatch"): ap.validate_preview(path)
