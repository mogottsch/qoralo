#!/usr/bin/env python3
"""Generate and measure the frozen Kokoro preview under one atomic grant."""
from __future__ import annotations

import argparse
import ctypes.util
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import NoReturn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
ARTIFACT_ROOT = Path(os.environ.get("KOKORO_ARTIFACT_ROOT", ROOT / "artifacts/kokoro"))
SNAPSHOT = ARTIFACT_ROOT / "snapshot"
VENV_PYTHON = ARTIFACT_ROOT / "venv/bin/python"
OUTPUT = Path(os.environ.get("KOKORO_PREVIEW_OUTPUT", ROOT / "artifacts/previews/kokoro"))
RESULT = ROOT / "results/kokoro-preview.json"
TRANSCRIPT = ROOT / "protocol/transcript.txt"
SPEED = 0.85

sys.path.insert(0, str(ROOT / "tools"))
import protocol  # noqa: E402


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def refuse(message: str) -> NoReturn:
    raise SystemExit(f"Kokoro preview refused: {message}")


def verify_inputs() -> bytes:
    if os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "generation-kokoro":
        refuse("missing atomic generation-kokoro grant; use generate_preview.sh")
    transcript = TRANSCRIPT.read_bytes()
    if hashlib.sha256(transcript).hexdigest() != protocol.protocol_reference()["transcript_sha256"]:
        refuse("frozen transcript byte drift")
    for relative, expected in PINS["model"]["files"].items():
        path = SNAPSHOT / relative
        actual = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        if actual != expected:
            refuse(f"pinned artifact mismatch for {relative}: {actual}")
    if not VENV_PYTHON.is_file():
        refuse(f"isolated Kokoro environment is absent: {VENV_PYTHON}")
    return transcript


def pcm32_wav(path: Path, samples: "object") -> None:
    """Write a deterministic PCM32 carrier while retaining native floats separately."""
    import numpy as np
    pcm = np.clip(np.rint(np.clip(samples, -1.0, 1.0) * 2147483648.0), -2147483648, 2147483647).astype("<i4")
    with path.open("xb") as raw, wave.open(raw, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(4)
        stream.setframerate(PINS["native_output"]["sample_rate_hz"])
        stream.writeframes(pcm.tobytes())


def first_audible_offset(samples: "object", threshold_dbfs: float = -50.0) -> float | None:
    import numpy as np
    frame = 240
    threshold = 10 ** (threshold_dbfs / 20.0)
    values = np.asarray(samples, dtype=np.float64)
    for start in range(0, max(0, values.size - frame + 1), frame):
        if float(np.sqrt(np.mean(values[start:start + frame] ** 2))) >= threshold:
            return start / 24000.0
    return None


def render(destination: Path, metadata_path: Path) -> None:
    """Fresh-process renderer used twice to verify the supported seed controls."""
    import espeakng_loader
    espeak_library = os.environ.get("KOKORO_ESPEAK_LIBRARY") or ctypes.util.find_library("espeak-ng")
    espeak_data = Path(os.environ.get("KOKORO_ESPEAK_DATA", "/usr/share/espeak-ng-data"))
    espeak = shutil.which("espeak-ng")
    if not espeak or not espeak_library or not espeak_data.is_dir():
        refuse("eSpeak NG executable, library, or data is unavailable")
    espeakng_loader.get_library_path = lambda: espeak_library
    espeakng_loader.get_data_path = lambda: str(espeak_data)

    import numpy as np
    import torch
    from kokoro import KModel, KPipeline, __version__ as kokoro_version

    if kokoro_version != PINS["implementation"]["version"]:
        refuse(f"kokoro package version drift: {kokoro_version}")
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    model = KModel(
        repo_id=PINS["model"]["repo_id"],
        config=str(SNAPSHOT / "config.json"),
        model=str(SNAPSHOT / "kokoro-v1_0.pth"),
    ).cpu().eval()
    pipeline = KPipeline(lang_code=PINS["voice"]["lang_code"], repo_id=PINS["model"]["repo_id"], model=model, device="cpu")
    voice_path = str(SNAPSHOT / "voices/af_heart.pt")

    # Kokoro exposes no generator argument. Reapply its documented global torch
    # seed immediately before each inference, after all model/voice setup.
    pipeline.load_voice(voice_path)
    torch.manual_seed(0)
    started = time.monotonic()
    arrivals: list[float] = []
    chunks = []
    phonemes: list[str] = []
    with torch.inference_mode():
        for item in pipeline(TRANSCRIPT.read_text(encoding="utf-8"), voice=voice_path, speed=SPEED):
            arrivals.append(time.monotonic() - started)
            if item.audio is None:
                refuse("generation yielded a result without audio")
            chunks.append(item.audio.detach().cpu().contiguous().to(torch.float32))
            phonemes.append(item.phonemes)
    wall = time.monotonic() - started
    if not chunks:
        refuse("generation returned no audio")
    native = torch.cat(chunks).numpy().astype("<f4", copy=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(native.tobytes())
    metadata = {
        "generation_wall_seconds": wall,
        "api_first_output_seconds": arrivals[0],
        "first_audible_output_seconds": arrivals[0] + (first_audible_offset(native) or 0.0),
        "chunk_count": len(chunks),
        "chunk_samples": [int(chunk.numel()) for chunk in chunks],
        "phoneme_sha256": hashlib.sha256("\n".join(phonemes).encode("utf-8")).hexdigest(),
        "phoneme_character_count": sum(len(value) for value in phonemes),
        "environment": {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__, "kokoro": kokoro_version, "device": "cpu"},
        "phonemizer": {
            "implementation": "misaki English G2P with eSpeak NG out-of-dictionary fallback",
            "espeak_ng": subprocess.check_output([espeak, "--version"], text=True).splitlines()[0],
            "library": str(espeak_library),
            "data": str(espeak_data),
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_render(destination: Path, metadata: Path) -> None:
    environment = os.environ.copy()
    environment.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    subprocess.run(
        [str(VENV_PYTHON), str(Path(__file__).resolve()), "--render", str(destination), str(metadata)],
        check=True,
        env=environment,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    verify_inputs()
    if args.render:
        if len(args.paths) != 2:
            parser.error("--render requires DESTINATION METADATA")
        render(Path(args.paths[0]), Path(args.paths[1]))
        return
    if args.paths:
        parser.error("unexpected positional arguments")
    from audio_protocol import audio_statistics, derive, real_time_factor, validate_preview
    from preflight_common import RssSampler
    if OUTPUT.exists():
        refuse(f"output already exists (raw capture is write-once): {OUTPUT}")

    raw_dir = OUTPUT / "raw"
    normalized_dir = OUTPUT / "normalized"
    raw_dir.mkdir(parents=True)
    normalized_dir.mkdir(parents=True)
    run1 = raw_dir / "kokoro-native-run-1.f32le"
    run2 = raw_dir / "kokoro-native-run-2.f32le"
    meta1 = raw_dir / "kokoro-native-run-1.json"
    meta2 = raw_dir / "kokoro-native-run-2.json"

    sampler = RssSampler(interval_seconds=0.02).start()
    baseline = sampler.sample_now()
    try:
        sampler.mark("fresh_generation_1")
        run_render(run1, meta1)
        sampler.mark("fresh_generation_2")
        run_render(run2, meta2)
    finally:
        rss = sampler.stop()
    hash1, hash2 = sha256_file(run1), sha256_file(run2)
    if hash1 != hash2:
        refuse(f"fresh-process deterministic repeat mismatch: {hash1} != {hash2}")

    import numpy as np
    samples = np.fromfile(run1, dtype="<f4")
    sample_rate = PINS["native_output"]["sample_rate_hz"]
    raw_seconds = samples.size / sample_rate
    if raw_seconds < 15.0:
        refuse(f"native output is only {raw_seconds:.6f}s at documented speed {SPEED}; protocol forbids padding")
    carrier = raw_dir / "kokoro-native-pcm32.wav"
    pcm32_wav(carrier, samples)
    normalized = normalized_dir / "kokoro-15s.wav"
    derivation_path = normalized_dir / "kokoro-15s.derivation.json"
    derivation = derive(carrier, normalized)
    derivation_path.write_text(json.dumps(derivation, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    validation = validate_preview(normalized)
    timing1 = json.loads(meta1.read_text(encoding="utf-8"))
    timing2 = json.loads(meta2.read_text(encoding="utf-8"))
    model_bytes = PINS["model"]["files"]["kokoro-v1_0.pth"]["bytes"]
    total_resource_bytes = sum(item["bytes"] for item in PINS["model"]["files"].values())

    result = {
        "schema_version": 1,
        "model": "kokoro",
        "status": "accepted",
        "protocol": protocol.protocol_reference(),
        "provenance": {
            "source_url": PINS["implementation"]["repository"],
            "source_revision": PINS["implementation"]["revision"],
            "source_package": PINS["implementation"]["package"],
            "source_package_version": PINS["implementation"]["version"],
            "source_wheel_sha256": PINS["implementation"]["wheel_sha256"],
            "model_repository": PINS["model"]["repo_id"],
            "model_revision": PINS["model"]["revision"],
            "model_bytes": model_bytes,
            "stock_voice_bytes": PINS["model"]["files"]["voices/af_heart.pt"]["bytes"],
            "total_pinned_resource_bytes": total_resource_bytes,
            "download_bytes_during_generation": 0,
            "environment": timing1["environment"],
            "phonemizer": timing1["phonemizer"] | {
                "phoneme_sha256": timing1["phoneme_sha256"],
                "phoneme_character_count": timing1["phoneme_character_count"],
                "requirements": "espeak-ng executable, libespeak-ng, and espeak-ng-data; no privileged installation performed",
            },
            "determinism": {
                "seed_api_supported": False,
                "global_torch_seed": 0,
                "torch_deterministic_algorithms": True,
                "set_immediately_before_each_generation": True,
                "fresh_process_repeat_count": 2,
                "raw_hashes_match": True,
                "claim": "Bit-identical fresh-process repeats on this pinned CPU environment; no cross-platform bit-exact claim.",
            },
            "resource_grant": {"task": "task-8", "kind": "generation-kokoro", "atomic": True, "policy_version": 2},
        },
        "voice": {
            "name": PINS["voice"]["id"],
            "source": PINS["voice"]["provenance_document"],
            "stock_voice": True,
            "cloning_performed": False,
            "language": PINS["voice"]["language"],
            "overall_grade": PINS["voice"]["overall_grade"],
        },
        "command": ["models/kokoro/generate_preview.sh"],
        "speed_control": {"documented": True, "setting": SPEED, "note": "KPipeline speed duration control; not time stretching. Chosen before accepted capture so the frozen 36-word input exceeds 15 seconds."},
        "raw": {
            "artifact_path": str(run1.relative_to(ROOT)),
            "sha256": hash1,
            "duration_seconds": raw_seconds,
            "sample_rate_hz": sample_rate,
            "channels": 1,
            "output_format": "headerless little-endian IEEE float32 PCM (native library tensor bytes)",
            "sample_count": int(samples.size),
            "byte_count": run1.stat().st_size,
            "chunk_count": timing1["chunk_count"],
            "chunk_samples": timing1["chunk_samples"],
            "repeat_artifact_path": str(run2.relative_to(ROOT)),
            "repeat_sha256": hash2,
            "derivation_carrier_path": str(carrier.relative_to(ROOT)),
            "derivation_carrier_sha256": sha256_file(carrier),
            "statistics": audio_statistics(samples.astype(np.float64)),
            "repeat_timing": {
                "generation_wall_seconds": timing2["generation_wall_seconds"],
                "api_first_output_seconds": timing2["api_first_output_seconds"],
                "first_audible_output_seconds": timing2["first_audible_output_seconds"],
                "rtf": real_time_factor(timing2["generation_wall_seconds"], raw_seconds),
            },
            "anomalies": ["The non-streaming API yielded the transcript as one audio result, so API-first-output latency equals full utterance inference latency."],
            "preserved_unchanged": True,
        },
        "normalized": {
            "artifact_path": str(normalized.relative_to(ROOT)),
            "sha256": validation["sha256"],
            "duration_seconds": 15.0,
            "sample_rate_hz": 24000,
            "channels": 1,
            "sample_count": 360000,
            "sample_format": "PCM_S16LE",
            "byte_count": normalized.stat().st_size,
            "statistics": derivation["statistics"],
            "derivation_metadata_path": str(derivation_path.relative_to(ROOT)),
        },
        "timing": {
            "generation_wall_seconds": timing1["generation_wall_seconds"],
            "api_first_output_seconds": timing1["api_first_output_seconds"],
            "first_audible_output_seconds": timing1["first_audible_output_seconds"],
            "rtf": real_time_factor(timing1["generation_wall_seconds"], raw_seconds),
        },
        "memory": {"baseline_rss_bytes": baseline, "peak_process_tree_rss_bytes": rss["peak_process_tree_rss_bytes"], "sample_interval_ms": 20},
        "forbidden_transformations_used": [],
        "conclusion": "Accepted host listening preview only; this result does not establish Android feasibility.",
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(RESULT), "raw_seconds": raw_seconds, "normalized_sha256": validation["sha256"], "repeat_match": True}, sort_keys=True))


if __name__ == "__main__":
    main()
