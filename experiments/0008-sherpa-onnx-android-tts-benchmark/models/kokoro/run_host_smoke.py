#!/usr/bin/env python3
"""Run configuration-only synthesis with the pinned host wheels; never records timing."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import struct
import sys
import wave
from pathlib import Path

from validate_track import sha256, validate_committed

HERE = Path(__file__).resolve().parent
WHEELS = {
    "sherpa_onnx-1.13.5-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.whl": (4390212, "452bb53ca6464a6809b1ea338dd869bc05ba6b7a71b4674545b594045501b853"),
    "sherpa_onnx_core-1.13.5-py3-none-manylinux2014_x86_64.whl": (10371666, "485b20188ddf905ffbd7504ed456a05d0ff84d10c592a16c0adb7d69bb845f82"),
}


def verify_runtime(wheel_dir: Path) -> None:
    if platform.system() != "Linux" or platform.machine() != "x86_64" or sys.version_info[:3] != (3, 11, 9):
        raise RuntimeError("smoke requires pinned Linux x86_64 CPython 3.11.9 runtime")
    os_release = Path("/etc/os-release").read_text()
    if 'VERSION_ID="22.04"' not in os_release or "Ubuntu" not in os_release:
        raise RuntimeError("smoke requires pinned Ubuntu 22.04 platform")
    if set(path.name for path in wheel_dir.iterdir() if path.is_file()) != set(WHEELS):
        raise RuntimeError("host wheel set is not exact")
    for name, (size, digest) in WHEELS.items():
        path = wheel_dir / name
        if path.stat().st_size != size or sha256(path) != digest:
            raise RuntimeError(f"host wheel drifted: {name}")
    if importlib.metadata.version("sherpa-onnx") != "1.13.5" or importlib.metadata.version("sherpa-onnx-core") != "1.13.5":
        raise RuntimeError("installed host runtime is not sherpa-onnx 1.13.5")


def write_pcm16(path: Path, samples: list[float], sample_rate: int) -> None:
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, sample_rate, len(samples), "NONE", "not compressed"))
        frames = bytearray()
        for sample in samples:
            if not math.isfinite(sample):
                raise RuntimeError("non-finite source sample")
            frames.extend(struct.pack("<h", round(max(-1.0, min(1.0, sample)) * 32767)))
        output.writeframes(frames)


def validate_wav(path: Path) -> dict[str, object]:
    with wave.open(str(path), "rb") as source:
        channels, width, rate, frames = source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes()
        payload = source.readframes(frames)
        if source.readframes(1):
            raise RuntimeError("WAV has undeclared trailing frames")
    if channels != 1 or width != 2 or rate != 24000 or len(payload) != frames * 2 or frames == 0:
        raise RuntimeError("WAV format/frame validation failed")
    values = struct.unpack(f"<{frames}h", payload)
    peak = max(abs(value) for value in values)
    rms = math.sqrt(sum(value * value for value in values) / frames) / 32768.0
    if peak == 0 or rms < 1e-5:
        raise RuntimeError("WAV is silent")
    return {"decoder": "python_stdlib_wave_full_decode", "channels": channels, "sample_width_bytes": width,
            "sample_rate_hz": rate, "frames": frames, "duration_seconds": frames / rate,
            "pcm_peak": peak / 32768.0, "pcm_rms": rms, "non_silent": True,
            "sha256": sha256(path), "bytes": path.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--output-wav", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    validate_committed(args.model_root)
    verify_runtime(args.wheel_dir)
    if sha256(args.transcript) != "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f":
        raise RuntimeError("transcript is not the frozen experiment input")

    import sherpa_onnx
    root = args.model_root
    model_config = sherpa_onnx.OfflineTtsModelConfig(
        kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
            model=str(root / "model.onnx"), voices=str(root / "voices.bin"),
            tokens=str(root / "tokens.txt"), data_dir=str(root / "espeak-ng-data"),
            lexicon=str(root / "lexicon-us-en.txt")),
        provider="cpu", num_threads=1, debug=False)
    config = sherpa_onnx.OfflineTtsConfig(model=model_config)
    if not config.validate():
        raise RuntimeError("sherpa rejected pinned Kokoro configuration")
    tts = sherpa_onnx.OfflineTts(config)
    generation = sherpa_onnx.GenerationConfig()
    generation.sid = 3
    generation.speed = 1.0
    audio = tts.generate(args.transcript.read_text(encoding="utf-8"), generation)
    samples = list(audio.samples)
    if not samples:
        raise RuntimeError("host smoke returned empty audio")
    args.output_wav.parent.mkdir(parents=True, exist_ok=True)
    write_pcm16(args.output_wav, samples, audio.sample_rate)
    validation = validate_wav(args.output_wav)
    report = {
        "schema_version": 1, "status": "passed", "purpose": "configuration_and_audio_validity_only",
        "android_performance_evidence": False, "timing_recorded": False,
        "deployment_variant": "kokoro-multi-lang-v1_0", "archive_sha256": "c133d26353d776da730870dac7da07dbfc9a5e3bc80cc5e8e83ab6e823be7046",
        "configuration": {"provider": "cpu", "num_threads": 1, "language": "en-US", "speaker_id": 3, "speaker": "af_heart", "filesystem_backed": True},
        "runtime": {"platform": "Ubuntu 22.04 x86_64", "python": "CPython 3.11.9", "sherpa_onnx": "1.13.5", "wheel_sha256": {name: digest for name, (_, digest) in WHEELS.items()}},
        "input": {"transcript_sha256": sha256(args.transcript), "bytes": args.transcript.stat().st_size},
        "output": validation,
        "note": "This proves pinned host configuration and decodable non-silent output only. It is not Android timing, memory, or performance evidence."
    }
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
