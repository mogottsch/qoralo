#!/usr/bin/env python3
"""Deterministic derivation and analysis for protocol-v1 preview WAVs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import wave
from pathlib import Path
from typing import Any

import numpy as np
from scipy import signal

RATE = 24_000
SAMPLES = 360_000
FADE_SAMPLES = 240
ZERO_SEARCH = 240
TARGET_LUFS = -20.0
PEAK_DBFS = -1.0


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def preserve_raw(source: str | Path, destination: str | Path) -> str:
    """Copy once, refusing to overwrite, and verify the preserved byte hash."""
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    before, after = sha256_file(source), sha256_file(destination)
    if before != after:
        destination.unlink(missing_ok=True)
        raise IOError("raw preservation hash mismatch")
    return after


def _decode_pcm(data: bytes, width: int) -> np.ndarray:
    if width == 1:
        return (np.frombuffer(data, np.uint8).astype(np.float64) - 128.0) / 128.0
    if width == 2:
        return np.frombuffer(data, "<i2").astype(np.float64) / 32768.0
    if width == 3:
        b = np.frombuffer(data, np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v & 0x800000, v - 0x1000000, v)
        return v.astype(np.float64) / 8388608.0
    if width == 4:
        return np.frombuffer(data, "<i4").astype(np.float64) / 2147483648.0
    raise ValueError(f"unsupported PCM sample width: {width}")


def read_pcm_wav(path: str | Path) -> tuple[np.ndarray, int]:
    try:
        with wave.open(str(path), "rb") as w:
            if w.getcomptype() != "NONE":
                raise ValueError("compressed WAV is not supported")
            channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            if channels < 1 or rate < 1 or frames < 1:
                raise ValueError("WAV has invalid or empty format")
            data = w.readframes(frames)
    except (wave.Error, EOFError) as e:
        raise ValueError(f"malformed WAV: {e}") from e
    values = _decode_pcm(data, width)
    if values.size != frames * channels:
        raise ValueError("truncated WAV payload")
    return values.reshape(frames, channels).mean(axis=1, dtype=np.float64), rate


def resample_mono(samples: np.ndarray, source_rate: int) -> np.ndarray:
    if source_rate <= 0 or samples.ndim != 1 or samples.size == 0:
        raise ValueError("resampling requires non-empty mono input and a positive rate")
    if not np.all(np.isfinite(samples)):
        raise ValueError("input contains non-finite samples")
    if source_rate == RATE:
        return samples.astype(np.float64, copy=True)
    divisor = math.gcd(source_rate, RATE)
    return signal.resample_poly(
        samples.astype(np.float64), RATE // divisor, source_rate // divisor,
        window=("kaiser", 5.0), padtype="constant",
    ).astype(np.float64)


def choose_trim_end(samples: np.ndarray, target: int = SAMPLES, search: int = ZERO_SEARCH) -> int:
    if samples.size < target:
        raise ValueError(f"input is too short: {samples.size} samples; need at least {target}")
    lo, hi = max(target, target - search), min(samples.size, target + search)
    candidates: list[tuple[float, int, int]] = []
    for end in range(lo, hi + 1):
        if end == samples.size:
            amplitude = abs(float(samples[end - 1]))
        else:
            a, b = float(samples[end - 1]), float(samples[end])
            # Interpolated distance to zero when the boundary brackets a crossing.
            amplitude = 0.0 if (a == 0 or b == 0 or np.signbit(a) != np.signbit(b)) else min(abs(a), abs(b))
        candidates.append((amplitude, abs(end - target), end))
    return min(candidates)[2]


def exact_window(samples: np.ndarray) -> tuple[np.ndarray, int, int]:
    end = choose_trim_end(samples)
    start = end - SAMPLES
    return samples[start:end].copy(), start, end


def apply_fades(samples: np.ndarray, count: int = FADE_SAMPLES) -> np.ndarray:
    if count < 2 or samples.size < count * 2:
        raise ValueError("fade is too long for the input")
    out = samples.astype(np.float64, copy=True)
    ramp = np.sin(np.linspace(0.0, math.pi / 2.0, count, dtype=np.float64)) ** 2
    out[:count] *= ramp
    out[-count:] *= ramp[::-1]
    return out


def _biquad(samples: np.ndarray, kind: str, frequency: float, q: float, gain_db: float = 0.0) -> np.ndarray:
    # RBJ cookbook filters, frozen at the protocol output rate.
    w0 = 2 * math.pi * frequency / RATE
    alpha, cw = math.sin(w0) / (2 * q), math.cos(w0)
    if kind == "high_shelf":
        a = 10 ** (gain_db / 40); root = 2 * math.sqrt(a) * alpha
        b = np.array([a*((a+1)+(a-1)*cw+root), -2*a*((a-1)+(a+1)*cw), a*((a+1)+(a-1)*cw-root)])
        d = np.array([(a+1)-(a-1)*cw+root, 2*((a-1)-(a+1)*cw), (a+1)-(a-1)*cw-root])
    elif kind == "high_pass":
        b = np.array([(1+cw)/2, -(1+cw), (1+cw)/2]); d = np.array([1+alpha, -2*cw, 1-alpha])
    else:
        raise ValueError(kind)
    return signal.lfilter(b / d[0], d / d[0], samples)


def integrated_loudness(samples: np.ndarray) -> float:
    if samples.ndim != 1 or samples.size < int(0.4 * RATE):
        raise ValueError("loudness requires at least 400 ms of mono 24 kHz audio")
    weighted = _biquad(samples, "high_shelf", 1681.974450955533, 0.7071752369554196, 3.99984385397)
    weighted = _biquad(weighted, "high_pass", 38.13547087602444, 0.5003270373238773)
    block, hop = int(0.4 * RATE), int(0.1 * RATE)
    powers = np.array([np.mean(weighted[i:i+block] ** 2) for i in range(0, len(weighted)-block+1, hop)])
    loudness = -0.691 + 10 * np.log10(np.maximum(powers, np.finfo(float).tiny))
    absolute = powers[loudness >= -70.0]
    if absolute.size == 0:
        return -math.inf
    relative_gate = -0.691 + 10 * math.log10(float(np.mean(absolute))) - 10.0
    gated = powers[(loudness >= -70.0) & (loudness >= relative_gate)]
    return -math.inf if gated.size == 0 else -0.691 + 10 * math.log10(float(np.mean(gated)))


def normalize_gain(samples: np.ndarray) -> tuple[np.ndarray, float, float]:
    loudness = integrated_loudness(samples)
    peak = float(np.max(np.abs(samples)))
    if not math.isfinite(loudness) or peak == 0:
        return samples.copy(), 0.0, loudness
    loudness_gain = TARGET_LUFS - loudness
    peak_gain = PEAK_DBFS - 20 * math.log10(peak)
    gain_db = min(loudness_gain, peak_gain)
    return samples * (10 ** (gain_db / 20)), gain_db, loudness


def quantize_s16(samples: np.ndarray) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(0))
    tpdf = (rng.random(samples.size) - rng.random(samples.size)) / 32768.0
    ceiling = math.floor(32768.0 * 10 ** (PEAK_DBFS / 20.0))
    return np.clip(np.rint((samples + tpdf) * 32768.0), -ceiling, ceiling).astype("<i2")


def write_s16_wav(path: str | Path, pcm: np.ndarray) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(np.asarray(pcm, dtype="<i2").tobytes())


def validate_preview(path: str | Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as w:
        got = {"channels": w.getnchannels(), "sample_width_bytes": w.getsampwidth(), "sample_rate_hz": w.getframerate(), "sample_count": w.getnframes(), "compression": w.getcomptype()}
    expected = {"channels": 1, "sample_width_bytes": 2, "sample_rate_hz": RATE, "sample_count": SAMPLES, "compression": "NONE"}
    if got != expected:
        raise ValueError(f"preview format mismatch: {got}; expected {expected}")
    got["duration_seconds"] = SAMPLES / RATE
    got["sha256"] = sha256_file(path)
    return got


def audio_statistics(samples: np.ndarray) -> dict[str, float | None]:
    rms, peak = float(np.sqrt(np.mean(samples ** 2))), float(np.max(np.abs(samples)))
    db = lambda v: None if v == 0 else 20 * math.log10(v)
    return {"rms": rms, "rms_dbfs": db(rms), "peak": peak, "peak_dbfs": db(peak), "integrated_loudness_lufs": None if rms == 0 else integrated_loudness(samples)}


def real_time_factor(wall_seconds: float, raw_audio_seconds: float) -> float:
    if wall_seconds < 0 or raw_audio_seconds <= 0:
        raise ValueError("wall time must be nonnegative and raw audio duration positive")
    return wall_seconds / raw_audio_seconds


def derive(source: str | Path, output: str | Path) -> dict[str, Any]:
    mono, source_rate = read_pcm_wav(source)
    resampled = resample_mono(mono, source_rate)
    window, start, end = exact_window(resampled)
    faded = apply_fades(window)
    normalized, gain_db, input_lufs = normalize_gain(faded)
    pcm = quantize_s16(normalized)
    write_s16_wav(output, pcm)
    validation = validate_preview(output)
    floats = pcm.astype(np.float64) / 32768.0
    return {"source_sha256": sha256_file(source), "source_rate_hz": source_rate, "resampled_samples": int(resampled.size), "trim_start": start, "trim_end": end, "gain_db": gain_db, "pre_gain_loudness_lufs": input_lufs if math.isfinite(input_lufs) else None, "output": validation, "statistics": audio_statistics(floats)}


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("derive"); d.add_argument("source"); d.add_argument("output"); d.add_argument("--metadata")
    v = sub.add_parser("validate"); v.add_argument("path")
    args = p.parse_args()
    result = derive(args.source, args.output) if args.command == "derive" else validate_preview(args.path)
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if getattr(args, "metadata", None): Path(args.metadata).write_text(text, encoding="utf-8")
    else: print(text, end="")

if __name__ == "__main__":
    main()
