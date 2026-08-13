#!/usr/bin/env python3
"""Write-once Candidate F generation scaffold; each invocation is one gated job."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
PLAN = json.loads((HERE / "attempt-plan.json").read_text(encoding="utf-8"))
TRANSCRIPT = EXPERIMENT / "protocol/transcript.txt"
TRANSCRIPT_SHA256 = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
ARTIFACT_ROOT = Path(os.environ.get("KITTEN_ARTIFACT_ROOT", EXPERIMENT / "artifacts/kitten-tts-mini-0.8"))
SNAPSHOT = ARTIFACT_ROOT / "snapshot"
sys.path.insert(0, str(EXPERIMENT / "tools"))
from generation_metrics import GenerationTimer, ProcessTreeRssSampler  # noqa: E402


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"BLOCKED: {message}")


def verify(attempt_id: str, output: Path) -> dict:
    if os.environ.get("KITTEN_GATED_GENERATION") != "1" or os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "full-generation":
        fail("every default/repeat must run through generate-preview.sh and the global full-generation gate")
    if hashlib.sha256(TRANSCRIPT.read_bytes()).hexdigest() != TRANSCRIPT_SHA256:
        fail("frozen protocol-v2 transcript byte drift")
    matches = [attempt for attempt in PLAN["attempts"] if attempt["id"] == attempt_id]
    if len(matches) != 1:
        fail("attempt is absent from the precommitted plan")
    if output.exists():
        fail(f"write-once output already exists: {output}")
    allowed_root = (ARTIFACT_ROOT / "generation").resolve()
    if allowed_root not in output.resolve().parents:
        fail(f"output must be a unique path below {allowed_root}")
    for relative, expected in PINS["model"]["files"].items():
        path = SNAPSHOT / relative
        if not path.is_file() or {"bytes": path.stat().st_size, "sha256": sha256(path)} != expected:
            fail(f"missing or mismatched pinned artifact: {relative}")
    return matches[0]


def render(attempt: dict, output: Path) -> dict:
    import numpy as np
    import espeakng_loader
    espeak_library = Path(os.environ.get("KITTEN_ESPEAK_LIBRARY", "/usr/lib/libespeak-ng.so"))
    espeak_data = Path(os.environ.get("KITTEN_ESPEAK_DATA", "/usr/share/espeak-ng-data"))
    if not espeak_library.is_file() or not espeak_data.is_dir():
        fail("permitted eSpeak library/data unavailable")
    espeakng_loader.get_library_path = lambda: str(espeak_library)
    espeakng_loader.get_data_path = lambda: str(espeak_data)
    from kittentts.onnx_model import KittenTTS_1_Onnx

    config = json.loads((SNAPSHOT / "config.json").read_text(encoding="utf-8"))
    sampler = ProcessTreeRssSampler().start_before_model_load()
    timer = GenerationTimer()
    try:
        model = KittenTTS_1_Onnx(
            model_path=str(SNAPSHOT / config["model_file"]), voices_path=str(SNAPSHOT / config["voices"]),
            speed_priors=config.get("speed_priors", {}), voice_aliases=config.get("voice_aliases", {}),
        )
        providers = model.session.get_providers()
        if "CPUExecutionProvider" not in providers or {"CUDAExecutionProvider", "TensorrtExecutionProvider"} & set(providers):
            fail(f"CPU-only provider assertion failed: {providers}")
        timer.start()
        audio = np.asarray(model.generate(
            TRANSCRIPT.read_text(encoding="utf-8"), voice=PINS["voice"]["display_id"], speed=attempt["speed"]
        ), dtype="<f4").reshape(-1)
        timer.mark_api_output(audio, PINS["native_output"]["sample_rate_hz"])
        wall = timer.stop()
    finally:
        memory = sampler.stop()
    if audio.size == 0:
        fail("official API returned no samples")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(audio.tobytes(order="C"))
    duration = audio.size / PINS["native_output"]["sample_rate_hz"]
    timing = timer.result(duration)
    metadata = {
        "schema_version": 1, "model": PINS["model"]["repo_id"], "revision": PINS["model"]["revision"],
        "attempt": attempt, "voice": PINS["voice"]["display_id"], "cpu_providers": providers,
        "raw": {"path": str(output), "sha256": sha256(output), "sample_count": int(audio.size),
                "sample_rate_hz": 24000, "channels": 1, "duration_seconds": duration, "format": "float32le"},
        "timing": timing, "memory": memory,
        "api_timing_note": "The API is non-streaming; first API output is completion-equivalent.",
        "accepted_by_duration": duration >= 15.0,
        "short_output_outcome": None if duration >= 15.0 else PLAN["short_default_outcome"],
    }
    metadata_path = output.with_suffix(output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if duration < 15.0:
        fail(f"default produced {duration:.6f}s; no documented retry is eligible, terminal protocol blocker")
    print(json.dumps({"status": "accepted", "output": str(output), "duration_seconds": duration, "wall_seconds": wall}, sort_keys=True))
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, choices=[item["id"] for item in PLAN["attempts"]])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    render(verify(args.attempt, args.output), args.output)


if __name__ == "__main__":
    main()
