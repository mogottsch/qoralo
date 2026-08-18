#!/usr/bin/env python3
"""Recompute prospective waveform and phase-tolerant Kokoro audio diagnostics."""
from __future__ import annotations

import argparse
import json
import math
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 24_000
N_FFT = 1024
HOP = 256


def load_audio(path: Path) -> np.ndarray:
    if path.suffix == ".f32":
        data = np.fromfile(path, dtype="<f4")
    elif path.suffix == ".wav":
        with wave.open(str(path), "rb") as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, SAMPLE_RATE):
                raise RuntimeError(f"WAV contract drift: {path}")
            raw = stream.readframes(stream.getnframes())
            if stream.readframes(1):
                raise RuntimeError("WAV has unread trailing frames")
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    else:
        data = np.load(path).reshape(-1)
    if data.size != 182_400 or not np.isfinite(data).all():
        raise RuntimeError(f"audio shape/finite contract drift: {path} {data.shape}")
    return np.asarray(data, dtype=np.float64)


def frames(values: np.ndarray) -> np.ndarray:
    padded = np.pad(values, (N_FFT // 2, N_FFT // 2), mode="reflect")
    return np.lib.stride_tricks.sliding_window_view(padded, N_FFT)[::HOP]


def magnitude(values: np.ndarray) -> np.ndarray:
    n = np.arange(N_FFT, dtype=np.float64)
    window = 0.5 - 0.5 * np.cos(2.0 * np.pi * n / N_FFT)  # periodic Hann
    return np.abs(np.fft.rfft(frames(values) * window, n=N_FFT, axis=1))


def mel_filterbank() -> np.ndarray:
    minimum, maximum, count = 20.0, 12_000.0, 80
    hz_to_mel = lambda hz: 2595.0 * np.log10(1.0 + hz / 700.0)
    mel_to_hz = lambda mel: 700.0 * (10.0 ** (mel / 2595.0) - 1.0)
    points = mel_to_hz(np.linspace(hz_to_mel(minimum), hz_to_mel(maximum), count + 2))
    frequencies = np.fft.rfftfreq(N_FFT, 1.0 / SAMPLE_RATE)
    bank = np.zeros((count, frequencies.size), dtype=np.float64)
    for index in range(count):
        left, center, right = points[index : index + 3]
        bank[index] = np.maximum(0.0, np.minimum((frequencies - left) / (center - left), (right - frequencies) / (right - center)))
    return bank


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a.reshape(-1), b.reshape(-1)) / (np.linalg.norm(a) * np.linalg.norm(b)))


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    x, y = a.reshape(-1), b.reshape(-1)
    x = x - x.mean(); y = y - y.mean()
    return float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y)))


def compare(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float | bool]:
    delta = candidate - reference
    ref_mag, got_mag = magnitude(reference), magnitude(candidate)
    log_ref = 20.0 * np.log10(np.maximum(ref_mag, 1.0e-7))
    log_got = 20.0 * np.log10(np.maximum(got_mag, 1.0e-7))
    bank = mel_filterbank()
    ref_mel = 10.0 * np.log10(np.maximum(np.square(ref_mag) @ bank.T, 1.0e-10))
    got_mel = 10.0 * np.log10(np.maximum(np.square(got_mag) @ bank.T, 1.0e-10))
    ref_env = np.sqrt(np.mean(np.square(frames(reference)), axis=1))
    got_env = np.sqrt(np.mean(np.square(frames(candidate)), axis=1))
    rmse = float(np.sqrt(np.mean(np.square(delta))))
    return {
        "same_shape": reference.shape == candidate.shape,
        "waveform_cosine_descriptive": cosine(reference, candidate),
        "waveform_rmse_descriptive": rmse,
        "waveform_nrmse_descriptive": rmse / float(np.sqrt(np.mean(np.square(reference)))),
        "waveform_snr_db_descriptive": float(20.0 * np.log10(np.linalg.norm(reference) / np.linalg.norm(delta))),
        "waveform_max_abs_descriptive": float(np.max(np.abs(delta))),
        "magnitude_spectral_convergence": float(np.linalg.norm(got_mag - ref_mag) / np.linalg.norm(ref_mag)),
        "flattened_log_magnitude_pearson": pearson(log_ref, log_got),
        "log_mel_cosine": cosine(ref_mel, got_mel),
        "mean_absolute_log_mel_db": float(np.mean(np.abs(got_mel - ref_mel))),
        "rms_envelope_pearson": pearson(ref_env, got_env),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text())
    thresholds = policy["phone_phase_tolerant_acoustic_gate"]
    reference = load_audio(args.reference)
    pairs = []
    for path in args.candidate:
        metrics = compare(reference, load_audio(path))
        checks = {
            "same_shape": metrics["same_shape"],
            "spectral_convergence": metrics["magnitude_spectral_convergence"] <= thresholds["stft"]["magnitude_spectral_convergence_max"],
            "log_magnitude_pearson": metrics["flattened_log_magnitude_pearson"] >= thresholds["stft"]["flattened_log_magnitude_pearson_min"],
            "log_mel_cosine": metrics["log_mel_cosine"] >= thresholds["mel"]["log_mel_cosine_min"],
            "log_mel_mae_db": metrics["mean_absolute_log_mel_db"] <= thresholds["mel"]["mean_absolute_log_mel_db_max"],
            "rms_envelope_pearson": metrics["rms_envelope_pearson"] >= thresholds["amplitude_envelope"]["rms_envelope_pearson_min"],
        }
        pairs.append({"candidate": str(path), "metrics": metrics, "checks": checks, "status": "passed" if all(checks.values()) else "failed"})
    document = {"schema_version": 1, "reference": str(args.reference), "policy_sha256": __import__("hashlib").sha256(args.policy.read_bytes()).hexdigest(), "pairs": pairs, "status": "passed" if all(x["status"] == "passed" for x in pairs) else "failed"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2))
    return 0 if document["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
