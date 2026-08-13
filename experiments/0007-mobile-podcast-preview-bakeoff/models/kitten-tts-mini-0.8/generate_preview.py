#!/usr/bin/env python3
"""Write-once Candidate F generation; each invocation is one gated attempt."""
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
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"BLOCKED: {message}")


def attempt_by_id(attempt_id: str) -> dict:
    matches = [item for item in PLAN["attempts"] if item["id"] == attempt_id]
    if len(matches) != 1:
        fail("attempt is not in the precommitted grid")
    return matches[0]


def attempt_directory(attempt: dict, generation_root: Path) -> Path:
    return generation_root / f"attempt-{attempt['ordinal']:02d}-{attempt['id']}"


def _legacy_report(attempt: dict, generation_root: Path) -> dict | None:
    """Recognize task-8's preserved pre-hardening default evidence without changing it."""
    if attempt["id"] != "default":
        return None
    path = generation_root / "attempt-01-default-primary.f32le.json"
    raw_path = generation_root / "attempt-01-default-primary.f32le"
    if not path.is_file() or not raw_path.is_file():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    raw = report.get("raw", {})
    if raw.get("sha256") != sha256(raw_path):
        fail("preserved default raw evidence hash mismatch")
    return report


def primary_report(attempt: dict, generation_root: Path) -> dict | None:
    report_path = attempt_directory(attempt, generation_root) / "primary" / "report.json"
    if report_path.is_file():
        return json.loads(report_path.read_text(encoding="utf-8"))
    return _legacy_report(attempt, generation_root)


def check_sequence(attempt: dict, run: str, generation_root: Path) -> None:
    prior = [item for item in PLAN["attempts"] if item["ordinal"] < attempt["ordinal"]]
    for item in prior:
        report = primary_report(item, generation_root)
        if report is None:
            fail(f"attempt {item['id']} must complete before {attempt['id']}")
        if report.get("accepted_by_duration") is True:
            fail(f"attempt {item['id']} already passed; later attempts are forbidden")
    if run == "repeat-1":
        report = primary_report(attempt, generation_root)
        if not report or report.get("accepted_by_duration") is not True:
            fail("repeat-1 requires an intact accepted primary report")
        for item in prior:
            if primary_report(item, generation_root).get("accepted_by_duration") is True:
                fail("repeat must target the first accepted attempt")
    elif primary_report(attempt, generation_root) is not None:
        fail(f"write-once primary already exists for {attempt['id']}")


def claim_run_directory(attempt: dict, run: str, generation_root: Path) -> tuple[Path, Path]:
    if run not in PLAN["run_workflow"]["runs"]:
        fail("run must be primary or repeat-1")
    check_sequence(attempt, run, generation_root)
    run_dir = attempt_directory(attempt, generation_root) / run
    run_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_dir.mkdir()
    except FileExistsError:
        fail(f"write-once run directory already exists: {run_dir}")
    return run_dir / "native.f32le", run_dir / "report.json"


def verify(attempt_id: str, run: str) -> tuple[dict, Path, Path]:
    if (
        os.environ.get("KITTEN_GATED_GENERATION") != "1"
        or os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "full-generation"
        or os.environ.get("PREVIEW_RESOURCE_GRANT_TASK") != "task-8"
    ):
        fail("every attempt/repeat must run through generate-preview.sh and the task-8 full-generation gate")
    if hashlib.sha256(TRANSCRIPT.read_bytes()).hexdigest() != TRANSCRIPT_SHA256:
        fail("frozen protocol-v2 transcript byte drift")
    for relative, expected in PINS["model"]["files"].items():
        path = SNAPSHOT / relative
        if not path.is_file() or {"bytes": path.stat().st_size, "sha256": sha256(path)} != expected:
            fail(f"missing or mismatched pinned artifact: {relative}")
    attempt = attempt_by_id(attempt_id)
    output, metadata = claim_run_directory(attempt, run, ARTIFACT_ROOT / "generation")
    return attempt, output, metadata


def render(run: str, attempt: dict, output: Path, metadata_path: Path) -> dict:
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
    if audio.size == 0 or not np.all(np.isfinite(audio)):
        fail("official API returned empty or non-finite samples")
    with output.open("xb") as stream:
        stream.write(audio.tobytes(order="C"))
    duration = audio.size / PINS["native_output"]["sample_rate_hz"]
    accepted = duration >= 15.0
    is_final = attempt["ordinal"] == PLAN["attempts"][-1]["ordinal"]
    report = {
        "schema_version": 1, "model": PINS["model"]["repo_id"], "revision": PINS["model"]["revision"],
        "run": run, "attempt": attempt, "voice": PINS["voice"]["display_id"], "cpu_providers": providers,
        "raw": {"path": str(output), "sha256": sha256(output), "byte_count": output.stat().st_size,
                "sample_count": int(audio.size), "sample_rate_hz": 24000, "channels": 1,
                "duration_seconds": duration, "format": "float32le"},
        "timing": timer.result(duration), "memory": memory,
        "api_timing_note": "The API is non-streaming; first API output is completion-equivalent.",
        "accepted_by_duration": accepted,
        "short_output_outcome": None if accepted else (PLAN["short_final_outcome"] if is_final else PLAN["short_default_outcome"]),
    }
    with metadata_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    status = "accepted" if accepted else "short"
    print(json.dumps({"status": status, "output": str(output), "duration_seconds": duration, "wall_seconds": wall}, sort_keys=True))
    if not accepted:
        fail(f"{attempt['id']} produced {duration:.6f}s; preserve it and run the next precommitted attempt")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, choices=[item["id"] for item in PLAN["attempts"]])
    parser.add_argument("--run", required=True, choices=PLAN["run_workflow"]["runs"])
    args = parser.parse_args()
    attempt, output, metadata = verify(args.attempt, args.run)
    render(args.run, attempt, output, metadata)


if __name__ == "__main__":
    main()
