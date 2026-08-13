#!/usr/bin/env python3
"""One write-once Inflect-Nano-v1 attempt. Invoke only through generate-attempt.sh."""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

from track import EXPERIMENT, NLTK_DATA, PINS, PLAN, SNAPSHOT, attempt_directory, attempt_value, frozen_transcript, install_local_tokenizer_resolution, verify_snapshot

sys.path.insert(0, str(EXPERIMENT / "tools"))
from generation_metrics import GenerationTimer, ProcessTreeRssSampler

RATE = 24_000


def validate_attempt_order(root: Path, index: int, repeat: bool) -> None:
    if repeat:
        primary = attempt_directory(root, index) / "attempt.json"
        if not primary.is_file():
            raise RuntimeError("repeat requires its accepted primary attempt")
        evidence = json.loads(primary.read_text(encoding="utf-8"))
        if evidence["raw_duration_seconds"] < PLAN["minimum_accepted_raw_duration_seconds"]:
            raise RuntimeError("repeat is allowed only for the accepted primary attempt")
        return
    for prior_index in range(index):
        prior = attempt_directory(root, prior_index) / "attempt.json"
        if not prior.is_file():
            raise RuntimeError(f"attempt {index} cannot skip predeclared attempt {prior_index}")
        evidence = json.loads(prior.read_text(encoding="utf-8"))
        if evidence["raw_duration_seconds"] >= PLAN["minimum_accepted_raw_duration_seconds"]:
            raise RuntimeError("a prior attempt passed; the first-passing rule forbids later attempts")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-index", required=True, type=int)
    parser.add_argument("--repeat", action="store_true")
    args = parser.parse_args()
    if os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "full-generation":
        raise SystemExit("BLOCKED: every attempt/repeat requires the global full-generation gate")
    if os.environ.get("PREVIEW_RESOURCE_GRANT_TASK") != "task-7-inflect-generation":
        raise SystemExit("BLOCKED: unexpected resource-grant task")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise SystemExit("BLOCKED: CUDA must be hidden for CPU-only generation")

    verify_snapshot()
    transcript = frozen_transcript()
    root = Path(os.environ.get("INFLECT_NANO_RAW_ROOT", EXPERIMENT / "artifacts" / "raw" / "inflect-nano-v1" / "v2"))
    root.mkdir(parents=True, exist_ok=True)
    validate_attempt_order(root, args.attempt_index, args.repeat)
    output_dir = attempt_directory(root, args.attempt_index, repeat=args.repeat)
    output_dir.mkdir()  # deliberately fails if an attempt path already exists
    length_scale = attempt_value(args.attempt_index)

    os.environ["NLTK_DATA"] = str(NLTK_DATA)
    sys.path[:0] = [str(SNAPSHOT), str(SNAPSHOT / "third_party" / "tiny_tts_frontend")]
    install_local_tokenizer_resolution()
    import numpy as np
    import soundfile as sf
    import torch
    from inference import load_acoustic, load_vocoder, synthesize

    sampler = ProcessTreeRssSampler().start_before_model_load()
    device = torch.device("cpu")
    acoustic, speakers, _ = load_acoustic(SNAPSHOT / PINS["artifacts"]["acoustic_path"], device)
    vocoder, _ = load_vocoder(SNAPSHOT / PINS["artifacts"]["vocoder_path"], device)
    if set(speakers) != {PINS["voice"]["id"]}:
        raise RuntimeError("fixed stock voice identity drift")
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    timer = GenerationTimer().start()
    audio = np.asarray(synthesize(
        transcript, acoustic, vocoder, speakers, device,
        length_scale=length_scale, pitch_scale=1.0, energy_scale=1.0,
    ), dtype=np.float32).reshape(-1)
    timer.mark_api_output(audio, RATE)  # official API returns only the complete waveform
    wall = timer.stop()
    duration = audio.size / RATE
    timing = timer.result(duration)
    rss = sampler.stop()

    buffer = io.BytesIO()
    sf.write(buffer, audio, RATE, format="WAV", subtype="PCM_16")
    wav = output_dir / "native.wav"
    with wav.open("xb") as stream:
        stream.write(buffer.getvalue())
    from track import sha256
    evidence = {
        "schema_version": 1,
        "model": "inflect-nano-v1",
        "repository": PINS["identity"]["repository"],
        "revision": PINS["identity"]["revision"],
        "attempt_index": args.attempt_index,
        "repeat": args.repeat,
        "length_scale": length_scale,
        "pitch_scale": 1.0,
        "energy_scale": 1.0,
        "device": "cpu",
        "voice": PINS["voice"]["id"],
        "sample_rate_hz": RATE,
        "channels": 1,
        "sample_format": "PCM_S16LE",
        "raw_sample_count": int(audio.size),
        "raw_duration_seconds": duration,
        "passes_minimum_duration": duration >= PLAN["minimum_accepted_raw_duration_seconds"],
        "native_wav": {"path": str(wav), "bytes": wav.stat().st_size, "sha256": sha256(wav)},
        "timing": timing,
        "rss": rss,
        "api_output_semantics": "non-streaming completion-equivalent",
        "transcript_sha256": PINS["protocol"]["transcript_sha256"],
        "resource_gate": "full-generation",
        "forbidden_transformations_used": [],
    }
    report = output_dir / "attempt.json"
    with report.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"attempt": str(report), "duration_seconds": duration, "passed": evidence["passes_minimum_duration"]}, sort_keys=True))


if __name__ == "__main__":
    main()
