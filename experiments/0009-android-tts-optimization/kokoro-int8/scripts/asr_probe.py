#!/usr/bin/env python3
"""Run a pinned Whisper intelligibility probe over the blind-gate WAV set.

Run this script with the separately pinned /usr/bin/python3.14 environment recorded
in toolchain.lock.json. ASR agreement is supporting evidence, not a listening verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import platform
import time
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, load_json, sha256_file, word_errors, write_json


def record_sha256(distribution: str) -> str:
    installed = importlib.metadata.distribution(distribution)
    records = [entry for entry in installed.files or [] if str(entry).endswith(".dist-info/RECORD")]
    if len(records) != 1:
        raise RuntimeError(f"could not locate one RECORD for {distribution}")
    return sha256_file(Path(installed.locate_file(records[0])))


def verify_environment(lock: dict[str, Any], checkpoint: Path) -> dict[str, Any]:
    probe = lock["supporting_asr_probe"]
    if platform.python_version() != probe["python"].removeprefix("CPython "):
        raise RuntimeError(f"ASR requires {probe['python']}, got {platform.python_version()}")
    executable = Path(probe["python_executable"])
    if sha256_file(executable) != probe["python_executable_sha256"]:
        raise RuntimeError("ASR Python executable drifted")
    for distribution, version_key, record_key in (
        ("openai-whisper", "openai_whisper", "openai_whisper_record_sha256"),
        ("torch", "torch", "torch_record_sha256"),
        ("numpy", "numpy", "numpy_record_sha256"),
    ):
        version = importlib.metadata.version(distribution)
        if version != probe[version_key] or record_sha256(distribution) != probe[record_key]:
            raise RuntimeError(f"ASR distribution drifted: {distribution}")
    ffmpeg = Path("/usr/bin/ffmpeg")
    if sha256_file(ffmpeg) != probe["ffmpeg_executable_sha256"]:
        raise RuntimeError("ffmpeg executable drifted")
    expected_checkpoint = probe["checkpoint"]
    if checkpoint.stat().st_size != expected_checkpoint["bytes"] or sha256_file(checkpoint) != expected_checkpoint["sha256"]:
        raise RuntimeError("Whisper checkpoint drifted")
    return {
        "python": probe["python"],
        "python_executable_sha256": probe["python_executable_sha256"],
        "openai_whisper": probe["openai_whisper"],
        "openai_whisper_record_sha256": probe["openai_whisper_record_sha256"],
        "torch": probe["torch"],
        "torch_record_sha256": probe["torch_record_sha256"],
        "numpy": probe["numpy"],
        "numpy_record_sha256": probe["numpy_record_sha256"],
        "ffmpeg": probe["ffmpeg"],
        "ffmpeg_executable_sha256": probe["ffmpeg_executable_sha256"],
        "checkpoint": {**expected_checkpoint, "path": str(checkpoint)},
    }


def transcribe(model: Any, path: Path) -> tuple[str, float]:
    started = time.perf_counter()
    result = model.transcribe(
        str(path),
        language="en",
        task="transcribe",
        fp16=False,
        temperature=0.0,
        beam_size=5,
        condition_on_previous_text=False,
        word_timestamps=False,
        verbose=None,
    )
    return result["text"].strip(), time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-analysis", type=Path, default=EXPERIMENT_ROOT / "reports" / "audio-analysis.json")
    parser.add_argument("--toolchain-lock", type=Path, default=EXPERIMENT_ROOT / "toolchain.lock.json")
    parser.add_argument("--checkpoint", type=Path, default=Path.home() / ".cache" / "whisper" / "small.pt")
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "reports" / "asr-report.json")
    args = parser.parse_args()

    lock = load_json(args.toolchain_lock)
    runtime = verify_environment(lock, args.checkpoint)
    analysis = load_json(args.audio_analysis)
    if analysis["status"] != "passed":
        raise RuntimeError("audio integrity/acoustic analysis must pass before ASR")

    import torch
    import whisper

    torch.set_num_threads(4)
    model = whisper.load_model("small", device="cpu", download_root=str(args.checkpoint.parent))
    pairs: list[dict[str, Any]] = []
    fp32_errors = fp32_words = int8_errors = int8_words = agreement_errors = agreement_words = 0
    for pair in analysis["pairs"]:
        reference = pair["text"]
        fp32_path = EXPERIMENT_ROOT / pair["fp32"]["path"]
        int8_path = EXPERIMENT_ROOT / pair["int8"]["path"]
        fp32_text, fp32_seconds = transcribe(model, fp32_path)
        int8_text, int8_seconds = transcribe(model, int8_path)
        f_errors, f_words = word_errors(reference, fp32_text)
        q_errors, q_words = word_errors(reference, int8_text)
        a_errors, a_words = word_errors(fp32_text, int8_text)
        fp32_errors += f_errors
        fp32_words += f_words
        int8_errors += q_errors
        int8_words += q_words
        agreement_errors += a_errors
        agreement_words += a_words
        pairs.append(
            {
                "id": pair["id"],
                "reference": reference,
                "fp32_transcript": fp32_text,
                "int8_transcript": int8_text,
                "fp32_reference_word_errors": f_errors,
                "int8_reference_word_errors": q_errors,
                "fp32_to_int8_hypothesis_word_errors": a_errors,
                "reference_word_count": f_words,
                "fp32_hypothesis_word_count": a_words,
                "host_asr_timing_context_only": {
                    "fp32_seconds": fp32_seconds,
                    "int8_seconds": int8_seconds,
                },
            }
        )

    fp32_wer = fp32_errors / max(fp32_words, 1)
    int8_wer = int8_errors / max(int8_words, 1)
    agreement_wer = agreement_errors / max(agreement_words, 1)
    checks = {
        "int8_corpus_wer_no_more_than_fp32_plus_0_10": int8_wer <= fp32_wer + 0.10,
        "fp32_to_int8_hypothesis_wer_at_most_0_20": agreement_wer <= 0.20,
    }
    report = {
        "schema_version": 1,
        "status": "passed" if all(checks.values()) else "failed",
        "role": "supporting transcript/intelligibility agreement only",
        "not_a_subjective_quality_verdict": True,
        "runtime": runtime,
        "decode_settings": {
            "model": "small",
            "language": "en",
            "task": "transcribe",
            "fp16": False,
            "temperature": 0.0,
            "beam_size": 5,
            "condition_on_previous_text": False,
            "word_timestamps": False,
            "torch_threads": 4,
        },
        "pairs": pairs,
        "corpus": {
            "fp32_reference_errors": fp32_errors,
            "int8_reference_errors": int8_errors,
            "reference_words": fp32_words,
            "fp32_reference_wer": fp32_wer,
            "int8_reference_wer": int8_wer,
            "fp32_to_int8_hypothesis_errors": agreement_errors,
            "fp32_hypothesis_words": agreement_words,
            "fp32_to_int8_hypothesis_wer": agreement_wer,
        },
        "checks": checks,
    }
    write_json(args.output, report)
    print(f"ASR probe {report['status']}: {args.output}")


if __name__ == "__main__":
    main()
