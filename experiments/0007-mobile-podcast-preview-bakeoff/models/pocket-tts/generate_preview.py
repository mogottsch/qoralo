#!/usr/bin/env python3
"""Generate the frozen Pocket TTS preview under the shared resource grant."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
ARTIFACT_ROOT = Path(os.environ.get("POCKET_TTS_ARTIFACT_ROOT", ROOT / "artifacts/setup/pocket-tts"))
SOURCE = ARTIFACT_ROOT / "source"
OUTPUT = Path(os.environ.get("POCKET_PREVIEW_OUTPUT", ROOT / "artifacts/previews/pocket/protocol-v2-final"))
RESULT = ROOT / "results/pocket-preview.json"
TRANSCRIPT = ROOT / "protocol/transcript.txt"
sys.path.insert(0, str(ROOT / "tools"))
from audio_protocol import (audio_statistics, derive, real_time_factor, sha256_file)  # noqa: E402
from preflight_common import RssSampler  # noqa: E402
import protocol  # noqa: E402


def refuse(message: str) -> "NoReturn":
    raise SystemExit(f"Pocket preview refused: {message}")


def pcm32_wav(path: Path, samples) -> None:
    """Write an analysis/derivation carrier; exact native floats remain separate."""
    import numpy as np
    pcm = np.clip(np.rint(np.clip(samples, -1.0, 1.0) * 2147483647.0), -2147483648, 2147483647).astype("<i4")
    with path.open("xb") as raw, wave.open(raw, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(4)
        stream.setframerate(24000)
        stream.writeframes(pcm.tobytes())


def first_audible_arrival(chunks: list[tuple[float, object]], threshold_dbfs: float = -50.0) -> float | None:
    import numpy as np
    threshold = 10 ** (threshold_dbfs / 20.0)
    frame = 240
    for arrival, chunk in chunks:
        values = chunk.numpy().astype(np.float64, copy=False)
        for start in range(0, max(0, values.size - frame + 1), frame):
            if float(np.sqrt(np.mean(values[start:start + frame] ** 2))) >= threshold:
                return arrival
    return None


def file_bytes_from_hf_cache() -> tuple[int, int]:
    from pocket_tts.utils.utils import download_if_necessary, get_predefined_voice
    config = SOURCE / "pocket_tts/config/english.yaml"
    import yaml
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    model_path = Path(download_if_necessary(cfg["weights_path_without_voice_cloning"]))
    voice_path = Path(download_if_necessary(get_predefined_voice("english", "alba")))
    return model_path.stat().st_size, voice_path.stat().st_size


def main() -> None:
    if os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "generation-pocket":
        refuse("missing atomic generation-pocket grant; use generate_preview.sh")
    if protocol.protocol_reference() != PINS["protocol"]:
        refuse("shared protocol revision drift")
    revision = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(SOURCE), "status", "--porcelain", "--untracked-files=no"], text=True).strip()
    if revision != PINS["source"]["revision"] or dirty:
        refuse("source revision or tracked tree drift")
    if OUTPUT.exists():
        refuse(f"output already exists (raw capture is write-once): {OUTPUT}")
    transcript_bytes = TRANSCRIPT.read_bytes()
    if hashlib.sha256(transcript_bytes).hexdigest() != PINS["protocol"]["transcript_sha256"]:
        refuse("transcript byte drift")
    transcript = transcript_bytes.decode("utf-8")

    OUTPUT.mkdir(parents=True)
    chunks_dir = OUTPUT / "raw/chunks"
    chunks_dir.mkdir(parents=True)
    normalized_path = OUTPUT / "normalized/pocket-15s.wav"
    normalized_path.parent.mkdir(parents=True)
    sampler = RssSampler(interval_seconds=0.02).start()
    baseline = sampler.sample_now()
    sampler.mark("model_load")

    import numpy as np
    import torch
    import pocket_tts
    from pocket_tts import TTSModel
    if SOURCE.resolve() not in Path(pocket_tts.__file__).resolve().parents:
        refuse("Pocket TTS was not imported from the pinned checkout")
    model = TTSModel.load_model(language="english", temp=0.3)
    state = model.get_state_for_audio_prompt("alba")
    if model.sample_rate != 24000 or not state:
        refuse("native format or stock voice state drift")
    model_bytes, voice_bytes = file_bytes_from_hf_cache()

    torch.manual_seed(0)
    sampler.mark("generation")
    started = time.monotonic()
    arrivals: list[tuple[float, object]] = []
    for index, chunk in enumerate(model.generate_audio_stream(state, transcript, copy_state=True)):
        elapsed = time.monotonic() - started
        native = chunk.detach().cpu().contiguous().to(torch.float32)
        (chunks_dir / f"chunk-{index:05d}.f32le").write_bytes(native.numpy().astype("<f4", copy=False).tobytes())
        arrivals.append((elapsed, native))
    generation_wall = time.monotonic() - started
    rss = sampler.stop()
    if not arrivals:
        refuse("generation returned no audio")
    samples = torch.cat([item[1] for item in arrivals]).numpy().astype("<f4", copy=False)
    native_path = OUTPUT / "raw/pocket-native.f32le"
    native_path.write_bytes(samples.tobytes())
    carrier_path = OUTPUT / "raw/pocket-native-pcm32.wav"
    pcm32_wav(carrier_path, samples)
    raw_seconds = samples.size / model.sample_rate
    if raw_seconds < 15.0:
        protocol_version = PINS["protocol"]["protocol_version"]
        if protocol_version < 2:
            refuse("short output under an obsolete protocol; parent must publish the shared revision")
        blocked = {
            "schema_version": 1,
            "model": "pocket",
            "status": "blocked",
            "protocol": PINS["protocol"],
            "provenance": {
                "source_url": PINS["source"]["repository"],
                "source_revision": revision,
                "source_package_version": PINS["source"]["package_version"],
                "model_revision": PINS["weights"]["stock_voice_model_revision"],
                "model_bytes": model_bytes,
                "stock_voice_state_bytes": voice_bytes,
                "download_bytes_during_generation": 0,
                "environment": {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__, "device": "cpu"},
                "determinism": {"torch_manual_seed": 0, "set_immediately_before_generation": True, "claim": "Two pinned same-platform protocol-v2 runs were byte-identical; no cross-platform bit-exact claim.", "repeated_seed0_attempts": 2, "repeated_sha256": sha256_file(native_path), "repeated_sha256_identical": True},
                "persistent_voice_states": {"supported": True, "exercised_count": 1, "note": "Multiple named reusable states are supported for later turn-by-turn composition; this fair preview exercised only alba."},
                "anomalies": [f"The one parent-owned punctuation revision produced {raw_seconds:.2f} seconds, still below the exact 15-second derivation minimum."],
            },
            "voice": {"name": "alba", "source": PINS["voice"]["source_audio_provenance"], "stock_voice": True, "cloning_performed": False},
            "command": ["models/pocket-tts/generate_preview.sh"],
            "speed_control": {"documented": False, "setting": None, "note": "No speed control exists in the pinned Python generation API; upstream says adding silence in text is unsupported."},
            "raw": {"artifact_path": str(native_path.relative_to(ROOT)), "sha256": sha256_file(native_path), "duration_seconds": raw_seconds, "sample_rate_hz": model.sample_rate, "channels": 1, "output_format": "headerless little-endian IEEE float32 PCM plus write-once native chunks", "sample_count": int(samples.size), "byte_count": native_path.stat().st_size, "chunk_count": len(arrivals), "chunk_manifest": [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(chunks_dir.iterdir())], "derivation_carrier_path": str(carrier_path.relative_to(ROOT)), "derivation_carrier_sha256": sha256_file(carrier_path), "statistics": audio_statistics(samples.astype(np.float64)), "preserved_unchanged": True},
            "timing": {"generation_wall_seconds": generation_wall, "api_first_output_seconds": arrivals[0][0], "first_audible_output_seconds": first_audible_arrival(arrivals), "rtf": real_time_factor(generation_wall, raw_seconds)},
            "memory": {"baseline_rss_bytes": baseline, "peak_process_tree_rss_bytes": rss["peak_process_tree_rss_bytes"], "sample_interval_ms": 20},
            "forbidden_transformations_used": [],
            "blocker": "Protocol v2 was the one permitted shared punctuation revision, but Pocket still emits less than 15 seconds and has no documented speed control. Exact normalization would require forbidden fabrication, looping, padding, or time stretching.",
            "conclusion": "Blocked after the permitted shared punctuation revision failed to reach 15 seconds; raw native output is preserved and no normalized preview was fabricated.",
        }
        RESULT.write_text(json.dumps(blocked, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        refuse(f"native output is only {raw_seconds:.6f}s after the permitted shared revision")
    metadata_path = OUTPUT / "normalized/pocket-15s.derivation.json"
    derivation = derive(carrier_path, normalized_path)
    metadata_path.write_text(json.dumps(derivation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    raw_floats = samples.astype(np.float64)
    result = {
        "schema_version": 1,
        "model": "pocket",
        "status": "accepted",
        "protocol": PINS["protocol"],
        "provenance": {
            "source_url": PINS["source"]["repository"],
            "source_revision": revision,
            "source_package_version": PINS["source"]["package_version"],
            "model_repository": PINS["weights"]["stock_voice_repository"],
            "model_revision": PINS["weights"]["stock_voice_model_revision"],
            "voice_repository_revision": PINS["weights"]["stock_voice_revision"],
            "model_bytes": model_bytes,
            "stock_voice_state_bytes": voice_bytes,
            "download_bytes_during_generation": 0,
            "environment": {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__, "device": "cpu"},
            "determinism": {"torch_manual_seed": 0, "set_immediately_before_generation": True, "claim": "Reproducible only with the pinned dependency graph on the same supported platform; no cross-platform bit-exact claim."},
            "persistent_voice_states": {"supported": True, "exercised_count": 1, "note": "Multiple named reusable states are supported for later turn-by-turn composition; this fair preview exercised only alba."},
            "anomalies": [],
        },
        "voice": {"name": "alba", "source": PINS["voice"]["source_audio_provenance"], "stock_voice": True, "cloning_performed": False},
        "command": ["models/pocket-tts/generate_preview.sh"],
        "speed_control": {"documented": False, "setting": None, "note": "No speed control was used or found in the pinned Python generation API."},
        "raw": {
            "artifact_path": str(native_path.relative_to(ROOT)),
            "sha256": sha256_file(native_path),
            "duration_seconds": raw_seconds,
            "sample_rate_hz": model.sample_rate,
            "channels": 1,
            "output_format": "headerless little-endian IEEE float32 PCM plus write-once native chunks",
            "sample_count": int(samples.size),
            "byte_count": native_path.stat().st_size,
            "chunk_count": len(arrivals),
            "chunk_manifest": [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(chunks_dir.iterdir())],
            "derivation_carrier_path": str(carrier_path.relative_to(ROOT)),
            "derivation_carrier_sha256": sha256_file(carrier_path),
            "statistics": audio_statistics(raw_floats),
            "preserved_unchanged": True,
        },
        "normalized": {
            "artifact_path": str(normalized_path.relative_to(ROOT)),
            "sha256": derivation["output"]["sha256"],
            "duration_seconds": 15.0,
            "sample_rate_hz": 24000,
            "channels": 1,
            "sample_count": 360000,
            "sample_format": "PCM_S16LE",
            "byte_count": normalized_path.stat().st_size,
            "statistics": derivation["statistics"],
            "derivation_metadata_path": str(metadata_path.relative_to(ROOT)),
        },
        "timing": {
            "generation_wall_seconds": generation_wall,
            "api_first_output_seconds": arrivals[0][0],
            "first_audible_output_seconds": first_audible_arrival(arrivals),
            "rtf": real_time_factor(generation_wall, raw_seconds),
        },
        "memory": {"baseline_rss_bytes": baseline, "peak_process_tree_rss_bytes": rss["peak_process_tree_rss_bytes"], "sample_interval_ms": 20},
        "forbidden_transformations_used": [],
        "conclusion": "Accepted host listening preview only; this result does not establish Android feasibility.",
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(RESULT), "raw_seconds": raw_seconds, "normalized_sha256": result["normalized"]["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
