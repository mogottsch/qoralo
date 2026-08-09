#!/usr/bin/env python3
"""Compare a locked Android generation WAV with the pinned host reference."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "experiments/0002-vibevoice-1.5b-executorch-android"
REFERENCE_SHA256 = "fb0152dc686836fe23d9c39c3b24c1de82398f51b9747f5e36ad1db819ce0358"
REFERENCE_SAMPLES = 313_600
SAMPLE_RATE = 24_000
SPEECH_RMS_DBFS = -50.0


@dataclass(frozen=True)
class WavAudio:
    path: Path
    samples_i16: np.ndarray
    samples: np.ndarray
    wav_sha256: str
    pcm_sha256: str
    channels: int
    sample_rate_hz: int
    sample_width_bytes: int
    compression_type: str

    @property
    def frame_count(self) -> int:
        return int(self.samples_i16.size)

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.sample_rate_hz


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_pcm_s16le_mono(path: Path) -> WavAudio:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_rate = wav.getframerate()
        width = wav.getsampwidth()
        compression = wav.getcomptype()
        frames = wav.getnframes()
        pcm = wav.readframes(frames)
        if wav.readframes(1):
            raise ValueError(f"{path}: WAV contains data beyond declared frame count")
    if channels != 1 or width != 2 or compression != "NONE":
        raise ValueError(
            f"{path}: expected mono uncompressed PCM S16LE, got "
            f"channels={channels}, width={width}, compression={compression}"
        )
    samples_i16 = np.frombuffer(pcm, dtype="<i2").copy()
    if samples_i16.size != frames:
        raise ValueError(f"{path}: decoded {samples_i16.size} samples, header declares {frames}")
    return WavAudio(
        path=path,
        samples_i16=samples_i16,
        samples=samples_i16.astype(np.float64) / 32768.0,
        wav_sha256=file_sha256(path),
        pcm_sha256=hashlib.sha256(pcm).hexdigest(),
        channels=channels,
        sample_rate_hz=sample_rate,
        sample_width_bytes=width,
        compression_type=compression,
    )


def verify_audio(audio: WavAudio, *, expected_sha256: str | None, expected_samples: int | None) -> dict[str, Any]:
    checks = {
        "wav_sha256": expected_sha256 is None or audio.wav_sha256 == expected_sha256,
        "sample_rate_hz": audio.sample_rate_hz == SAMPLE_RATE,
        "channels": audio.channels == 1,
        "bits_per_sample": audio.sample_width_bytes * 8 == 16,
        "encoding": audio.compression_type == "NONE",
        "sample_count": expected_samples is None or audio.frame_count == expected_samples,
    }
    return {
        "path": str(audio.path),
        "wav_sha256": audio.wav_sha256,
        "expected_wav_sha256": expected_sha256,
        "pcm_sha256": audio.pcm_sha256,
        "sample_rate_hz": audio.sample_rate_hz,
        "channels": audio.channels,
        "bits_per_sample": audio.sample_width_bytes * 8,
        "encoding": "PCM_S16LE",
        "sample_count": audio.frame_count,
        "duration_seconds": audio.duration_seconds,
        "checks": checks,
        "verified": all(checks.values()),
    }


def waveform_stats(samples: np.ndarray) -> dict[str, Any]:
    if samples.size == 0:
        return {"rms": 0.0, "rms_dbfs": None, "peak": 0.0, "dc_offset": 0.0, "clipped_samples": 0, "zero_crossing_rate": None}
    rms = float(np.sqrt(np.mean(np.square(samples))))
    crossings = int(np.count_nonzero(np.signbit(samples[1:]) != np.signbit(samples[:-1])))
    return {
        "rms": rms,
        "rms_dbfs": 20.0 * math.log10(rms) if rms > 0 else None,
        "peak": float(np.max(np.abs(samples))),
        "dc_offset": float(np.mean(samples)),
        "clipped_samples": int(np.count_nonzero(np.abs(samples) >= 32767.0 / 32768.0)),
        "zero_crossing_rate": crossings / max(1, samples.size - 1),
    }


def spectral_stats(samples: np.ndarray, sample_rate: int) -> dict[str, Any]:
    if samples.size < 2 or not np.any(samples):
        return {"status": "insufficient_energy", "centroid_hz": None, "rolloff_95_hz": None, "flatness": None, "band_energy_fraction": None}
    windowed = samples * np.hanning(samples.size)
    power = np.square(np.abs(np.fft.rfft(windowed)))
    total = float(power.sum())
    if total <= np.finfo(np.float64).tiny:
        return {"status": "insufficient_energy", "centroid_hz": None, "rolloff_95_hz": None, "flatness": None, "band_energy_fraction": None}
    frequencies = np.fft.rfftfreq(samples.size, 1.0 / sample_rate)
    rolloff = int(np.searchsorted(np.cumsum(power), total * 0.95))
    positive = power[power > 0]
    flatness = float(np.exp(np.mean(np.log(positive))) / np.mean(positive)) if positive.size else None
    bands = ((0, 300), (300, 1000), (1000, 4000), (4000, 8000), (8000, 12000))
    fractions = {
        f"{low}-{high}_hz": float(power[(frequencies >= low) & (frequencies < high)].sum() / total)
        for low, high in bands
    }
    return {
        "status": "measured",
        "centroid_hz": float(np.dot(frequencies, power) / total),
        "rolloff_95_hz": float(frequencies[min(rolloff, frequencies.size - 1)]),
        "flatness": flatness,
        "band_energy_fraction": fractions,
    }


def alignment(reference: np.ndarray, candidate: np.ndarray, sample_rate: int) -> dict[str, Any]:
    ref_energy = float(np.dot(reference, reference))
    candidate_energy = float(np.dot(candidate, candidate))
    ref_rms = math.sqrt(ref_energy / reference.size) if reference.size else 0.0
    candidate_rms = math.sqrt(candidate_energy / candidate.size) if candidate.size else 0.0
    # Below -80 dBFS, cross-correlation is dominated by quantization residue and
    # must not be presented as meaningful waveform alignment.
    if not reference.size or not candidate.size or ref_rms < 1e-4 or candidate_rms < 1e-4:
        return {"status": "insufficient_energy", "lag_samples": None, "lag_seconds": None, "normalized_cross_correlation": None, "overlap_samples": 0}

    # FFT convolution computes cross-correlation at every possible overlap. Per-lag
    # cumulative energies prevent short edge overlaps from winning by scale alone.
    size = reference.size + candidate.size - 1
    fft_size = 1 << (size - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(reference, fft_size) * np.fft.rfft(candidate[::-1], fft_size), fft_size)[:size]
    lags = np.arange(-(candidate.size - 1), reference.size, dtype=np.int64)
    starts_ref = np.maximum(lags, 0)
    starts_candidate = np.maximum(-lags, 0)
    overlap = np.minimum(reference.size - starts_ref, candidate.size - starts_candidate)
    ref_sq = np.concatenate(([0.0], np.cumsum(np.square(reference))))
    cand_sq = np.concatenate(([0.0], np.cumsum(np.square(candidate))))
    norm = np.sqrt(
        (ref_sq[starts_ref + overlap] - ref_sq[starts_ref])
        * (cand_sq[starts_candidate + overlap] - cand_sq[starts_candidate])
    )
    coefficient = np.divide(corr, norm, out=np.zeros_like(corr), where=norm > 1e-15)
    # Require at least 20 ms so one accidental sample cannot be called alignment.
    coefficient[overlap < min(candidate.size, max(1, sample_rate // 50))] = -np.inf
    best = int(np.argmax(coefficient))
    return {
        "status": "measured",
        "lag_samples": int(lags[best]),
        "lag_seconds": float(lags[best] / sample_rate),
        "normalized_cross_correlation": float(coefficient[best]),
        "overlap_samples": int(overlap[best]),
    }


def intermediate_evidence(step35: dict[str, Any]) -> dict[str, Any]:
    generation = step35["generation"]
    runs = generation["runs"]
    required_chunks = math.ceil(generation["locked_reference_required_duration_seconds"] * SAMPLE_RATE / 3200)
    return {
        "step35_status": step35["status"],
        "locked_preflight_status": step35["locked_preflight"]["status"],
        "exact_transcript_consumed": step35["provenance"]["exact_transcript_consumed"],
        "deterministic_runs": generation["deterministic"],
        "wav_byte_identical_across_runs": generation["wav_byte_identical_across_runs"],
        "stop_reasons": [run["stop_reason"] for run in runs],
        "produced_chunks_per_run": [len(run["chunks"]) for run in runs],
        "required_chunks": required_chunks,
        "selected_tokens_per_run": [run["tokens"] for run in runs],
        "chunk_pcm_sha256": [[chunk["pcm_sha256"] for chunk in run["chunks"]] for run in runs],
        "divergence_localization": "All locked inputs passed and both phone runs agreed byte-for-byte. Divergence is therefore localized to generation: token selection repeated ID 151654 and the fixed decoder/semantic cache ABI stopped at CAPACITY after two chunks, before a complete or voiced waveform existed.",
    }


def build_result(args: argparse.Namespace) -> dict[str, Any]:
    reference = read_pcm_s16le_mono(args.reference)
    android = read_pcm_s16le_mono(args.android)
    step35 = json.loads(args.step35.read_text())
    ref_record = verify_audio(reference, expected_sha256=REFERENCE_SHA256, expected_samples=REFERENCE_SAMPLES)
    android_record = verify_audio(android, expected_sha256=args.android_sha256, expected_samples=args.android_samples)
    if not ref_record["verified"]:
        raise ValueError("locked reference WAV metadata/hash verification failed")
    if not android_record["verified"]:
        raise ValueError("Android WAV metadata/hash verification failed")

    ref_wave = waveform_stats(reference.samples)
    android_wave = waveform_stats(android.samples)
    coverage = android.duration_seconds / reference.duration_seconds
    speech_present = android_wave["rms_dbfs"] is not None and android_wave["rms_dbfs"] >= SPEECH_RMS_DBFS
    complete = android.frame_count >= reference.frame_count
    evidence = intermediate_evidence(step35)
    quality = {
        "rubric_version": 1,
        "acceptance": "All four categories must pass; not-assessable is not a pass.",
        "omissions": {
            "criterion": "At least 95% duration coverage and both transcript speakers/turns must be intelligible.",
            "status": "pass" if coverage >= 0.95 else "fail",
            "evidence": f"Android covers {coverage:.6%} of the reference ({android.frame_count}/{reference.frame_count} samples); the remainder is omitted.",
        },
        "repetitions": {
            "criterion": "No repeated words, phrases, chunks, or stuck generation tokens not present in the reference.",
            "status": "fail" if len(set(evidence["selected_tokens_per_run"][0])) == 1 else ("pass" if complete else "not_assessable"),
            "evidence": "All three recorded selected tokens are ID 151654 in each run; the two emitted PCM chunk hashes differ, but the incomplete silent fragment cannot clear perceptual repetition.",
        },
        "corruption": {
            "criterion": "Intelligible speech, RMS at least -50 dBFS, no sustained silence/noise/metallic artifacts, and no clipping.",
            "status": "pass" if speech_present and android_wave["clipped_samples"] == 0 else "fail",
            "evidence": f"RMS is {android_wave['rms_dbfs']!r} dBFS; no intelligible speech is present in the effectively silent fragment.",
        },
        "speaker_consistency": {
            "criterion": "Carter and Maya must both be audible, perceptually distinct, and stable within their turns.",
            "status": "not_assessable" if not speech_present or not complete else "pass",
            "evidence": "The output ends before audible Carter/Maya turns and is below the speech threshold, so identity consistency cannot be assessed.",
        },
        "listening_notes": args.listening_notes,
    }
    accepted = all(quality[name]["status"] == "pass" for name in ("omissions", "repetitions", "corruption", "speaker_consistency"))
    return {
        "schema_version": 1,
        "status": "passed" if accepted else "rejected",
        "scope": "objective and fixed-rubric comparison of the Step 35 Android WAV with the locked host reference",
        "inputs": {"reference": ref_record, "android": android_record},
        "duration": {
            "reference_seconds": reference.duration_seconds,
            "android_seconds": android.duration_seconds,
            "difference_seconds": android.duration_seconds - reference.duration_seconds,
            "coverage_ratio": coverage,
            "missing_samples": max(0, reference.frame_count - android.frame_count),
        },
        "alignment": alignment(reference.samples, android.samples, SAMPLE_RATE),
        "waveform": {"reference": ref_wave, "android": android_wave, "comparison_status": "insufficient_energy" if not speech_present else "measured"},
        "spectral": {"reference": spectral_stats(reference.samples, SAMPLE_RATE), "android": spectral_stats(android.samples, SAMPLE_RATE), "comparison_status": "insufficient_android_energy" if not speech_present else "measured"},
        "quality_rubric": quality,
        "intermediate_evidence": evidence,
        "implementation_commits": args.commit,
        "commands": [
            "python3 experiments/0002-vibevoice-1.5b-executorch-android/export/compare_generation_audio.py --reference artifacts/0001/output-cpu/reference_generated.wav --android artifacts/0002/lane-d/locked-reference/generation-run-0.wav --step35 experiments/0002-vibevoice-1.5b-executorch-android/results/locked-reference-android.json --android-sha256 f5c90fdf64f563d0aa97f0acfe04abc26943f35c1cb7d78730449283682f64c9 --android-samples 6400 --commit <implementation-commit> --output experiments/0002-vibevoice-1.5b-executorch-android/results/locked-reference-comparison.json",
            "artifacts/venv-executorch-1.2/bin/python -m pytest -q experiments/0002-vibevoice-1.5b-executorch-android/tests/test_compare_generation_audio.py",
            "python3 -m json.tool experiments/0002-vibevoice-1.5b-executorch-android/results/locked-reference-comparison.json >/dev/null",
        ],
        "conclusion": "Rejected. The verified Android WAV is a deterministic 0.266667-second, effectively silent fragment covering only 2.0408% of the verified 13.066667-second reference. Alignment and comparative spectral similarity are invalid because Android energy is insufficient. The fixed rubric fails omissions, repetitions, and corruption; speaker consistency is not assessable. Step 35 evidence localizes the divergence to repeated token selection followed by the two-chunk static-cache capacity stop, not to input provenance or WAV assembly.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--android", type=Path, required=True)
    parser.add_argument("--step35", type=Path, default=BASE / "results/locked-reference-android.json")
    parser.add_argument("--android-sha256", required=True)
    parser.add_argument("--android-samples", type=int, required=True)
    parser.add_argument("--commit", action="append", required=True, help="Implementation/evidence commit; repeat as needed")
    parser.add_argument("--listening-notes", default="The Android fragment is effectively silent. No intelligible words, speaker turn, metallic artifact, or speaker identity can be heard; silence itself is disqualifying corruption.")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_result(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
