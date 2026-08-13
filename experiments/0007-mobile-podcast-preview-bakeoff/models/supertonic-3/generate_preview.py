#!/usr/bin/env python3
"""One-attempt Supertonic generator scaffold; normalization belongs to protocol-v2 tooling."""
from __future__ import annotations
import argparse, hashlib, json, os, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
PLAN = json.loads((HERE / "speed-attempts.json").read_text(encoding="utf-8"))
ARTIFACT_ROOT = Path(os.environ.get("SUPERTONIC_ARTIFACT_ROOT", EXPERIMENT / "artifacts/supertonic-3"))
TRANSCRIPT = EXPERIMENT / "protocol/transcript.txt"
TRANSCRIPT_SHA256 = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"


def refuse(message: str) -> "None": raise SystemExit(f"Supertonic generation refused: {message}")


def choose_attempt(index: int) -> dict:
    attempts = PLAN["attempts"]
    if index < 0 or index >= len(attempts) or attempts[index]["index"] != index: refuse("attempt is not in the committed sequence")
    return attempts[index]


def render(index: int) -> dict:
    if os.environ.get("SUPERTONIC_ATTEMPT_GRANT") != "1" or os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "full-generation": refuse("one global full-generation grant is required")
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"): refuse("credentials are forbidden")
    if hashlib.sha256(TRANSCRIPT.read_bytes()).hexdigest() != TRANSCRIPT_SHA256: refuse("frozen transcript changed")
    attempt = choose_attempt(index); snapshot = ARTIFACT_ROOT / "snapshot"
    from smoke_load import verify_snapshot
    verify_snapshot(snapshot)
    output = ARTIFACT_ROOT / "attempts" / f"attempt-{index:02d}"
    if output.exists(): refuse(f"write-once attempt already exists: {output}")
    output.mkdir(parents=True)
    import numpy as np
    import onnxruntime as ort
    from supertonic import TTS
    if "CPUExecutionProvider" not in ort.get_available_providers(): refuse("CPUExecutionProvider is unavailable")
    np.random.seed(0)
    tts = TTS(model="supertonic-3", model_dir=snapshot, auto_download=False)
    sessions = ("dp_ort", "text_enc_ort", "vector_est_ort", "vocoder_ort")
    if any(getattr(tts.model, name).get_providers() != ["CPUExecutionProvider"] for name in sessions): refuse("every model session must use CPUExecutionProvider only")
    style = tts.get_voice_style("M1")
    kwargs = {"voice_style": style, "lang": "en"}
    if attempt["argument"] != "omitted": kwargs["speed"] = attempt["argument"]
    started = time.monotonic(); wav, _duration = tts.synthesize(TRANSCRIPT.read_text(encoding="utf-8"), **kwargs); elapsed = time.monotonic() - started
    samples = np.asarray(wav, dtype="<f4").reshape(-1)
    raw = output / "native.f32le"
    with raw.open("xb") as stream: stream.write(samples.tobytes())
    metadata = {"schema_version": 1, "candidate": "D", "attempt": attempt, "model_revision": PINS["model"]["revision"], "voice": "M1", "sample_rate_hz": 44100, "channels": 1, "sample_count": int(samples.size), "duration_seconds": samples.size / 44100, "generation_wall_seconds": elapsed, "api_first_output_seconds": elapsed, "api_first_output_note": "The official Python SDK is non-streaming; its first API output is the completed waveform.", "raw_sha256": hashlib.sha256(samples.tobytes()).hexdigest(), "raw_preserved_unchanged": True, "normalization_performed": False}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--attempt-index", type=int, required=True); args = parser.parse_args()
    print(json.dumps(render(args.attempt_index), sort_keys=True))

if __name__ == "__main__": main()
