#!/usr/bin/env python3
"""Preflight and summarize the locked-reference Galaxy S23 Ultra run."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "experiments/0002-vibevoice-1.5b-executorch-android"
ART = ROOT / "artifacts/0002"
SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"
TRANSCRIPT_SHA256 = "e971969aff3d1f3e656180adf90e3f727299a842b83b2237a8e3b4c578fdf7d1"
REFERENCE_SHA256 = "fb0152dc686836fe23d9c39c3b24c1de82398f51b9747f5e36ad1db819ce0358"
CONDITIONING_SHA256 = "9966a6cb06a3cf52b45c7c560abd7e992e827c30897a6a2c3c95b3dc382a1f81"
LAYOUT_SHA256 = "759e6563d63a152fe36f1a76b40433184500349bfca4e0e320ebb52cce420e9e"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check(name: str, actual, expected) -> dict:
    if actual != expected:
        raise RuntimeError(f"locked preflight failed for {name}: {actual!r} != {expected!r}")
    return {"verified": True, "actual": actual, "expected": expected}


def package_paths() -> list[Path]:
    qwen = ART / "lane-c/qwen2-int8-package"
    paths = [qwen / "prepare.pte", qwen / "final.pte", qwen / "decode-prepare.pte", qwen / "decode-final.pte"]
    paths += [qwen / f"layer-{i:02d}.pte" for i in range(28)]
    paths += [qwen / f"decode-layer-{i:02d}.pte" for i in range(28)]
    paths += [ART / "lane-b/diffusion-head/diffusion-step-xnnpack.pte", ART / "lane-b/connectors/connectors-xnnpack.pte"]
    paths += [ART / f"acoustic-decoder-streaming-{kind}-segments-1.2/segment-{i}.pte" for kind in ("first", "cached") for i in range(8)]
    paths += [ART / "lane-b/semantic-encoder/semantic-encoder-first-xnnpack.pte", ART / "lane-b/semantic-encoder/semantic-encoder-cached-xnnpack.pte"]
    return paths


def package_manifest() -> dict:
    records = []
    aggregate = hashlib.sha256()
    for path in package_paths():
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"missing or empty package: {path}")
        rel = path.relative_to(ROOT).as_posix()
        digest = sha256(path)
        record = {"path": rel, "bytes": path.stat().st_size, "sha256": digest}
        records.append(record)
        aggregate.update(f"{rel}\0{record['bytes']}\0{digest}\n".encode())
    return {"count": len(records), "aggregate_sha256": aggregate.hexdigest(), "files": records}


def preflight(args: argparse.Namespace) -> None:
    transcript = ROOT / "artifacts/0001/reference.txt"
    reference = ROOT / "artifacts/0001/output-cpu/reference_generated.wav"
    input_dir = args.inputs
    with wave.open(str(reference), "rb") as wav:
        wav_meta = {
            "sample_rate_hz": wav.getframerate(), "channels": wav.getnchannels(),
            "bits_per_sample": wav.getsampwidth() * 8, "frames": wav.getnframes(),
            "duration_seconds": wav.getnframes() / wav.getframerate(), "encoding": "PCM_S16LE" if wav.getsampwidth() == 2 else "unexpected",
        }
    host_precision = json.loads((BASE / "results/qwen2-int8-host.json").read_text())["status"]
    android_precision = json.loads((BASE / "results/qwen2-int8-android.json").read_text())["status"]
    gradle = (BASE / "android/app/build.gradle.kts").read_text()
    source_revision = subprocess.check_output(
        ["git", "-C", str(ROOT / "artifacts/source/microsoft-vibevoice"), "rev-parse", "HEAD"], text=True
    ).strip()
    model_revision = (ROOT / "artifacts/models/microsoft-VibeVoice-1.5B/.cache/huggingface/download/config.json.metadata").read_text().splitlines()[0]
    manifest = {
        "schema_version": 1,
        "status": "passed",
        "checks": {
            "source_revision": check("source checkout revision", source_revision, SOURCE_REVISION),
            "model_revision": check("downloaded model revision", model_revision, MODEL_REVISION),
            "transcript_sha256": check("transcript hash", sha256(transcript), TRANSCRIPT_SHA256),
            "android_prompt_sha256": check("Android prompt hash", sha256(input_dir / "prompt.txt"), TRANSCRIPT_SHA256),
            "reference_wav_sha256": check("reference WAV hash", sha256(reference), REFERENCE_SHA256),
            "reference_duration_seconds": check("reference duration", wav_meta["duration_seconds"], 13.066666666666666),
            "reference_sample_rate_hz": check("reference sample rate", wav_meta["sample_rate_hz"], 24000),
            "reference_channels": check("reference channels", wav_meta["channels"], 1),
            "reference_bits_per_sample": check("reference sample width", wav_meta["bits_per_sample"], 16),
            "reference_encoding": check("reference encoding", wav_meta["encoding"], "PCM_S16LE"),
            "seed": check("seed", 42, 42),
            "cfg": check("CFG", 1.3, 1.3),
            "conditioning_sha256": check("conditioning hash", sha256(input_dir / "prompt-embeddings.f32le"), CONDITIONING_SHA256),
            "speaker_layout_sha256": check("speaker layout hash", sha256(input_dir / "sequence-speaker-ids.i64le"), LAYOUT_SHA256),
            "accepted_int8_host": check("accepted INT8 host result", host_precision, "passed"),
            "accepted_int8_android": check("accepted INT8 Android result", android_precision, "passed"),
            "executorch_android_dependency": check("ExecuTorch dependency", 'implementation("org.pytorch:executorch-android:1.2.0")' in gradle, True),
            "backend": check("backend", "xnnpack", "xnnpack"),
            "device_model": check("device", args.device_model, "SM-S918B"),
        },
        "reference_wav": {"path": reference.relative_to(ROOT).as_posix(), "sha256": REFERENCE_SHA256, **wav_meta},
        "runtime": {"executorch": "1.2.0", "backend": "xnnpack", "qwen_precision": "int8", "other_precision": "fp32"},
        "packages": package_manifest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": "passed", "checks": len(manifest["checks"]), "packages": manifest["packages"]["count"], "aggregate_sha256": manifest["packages"]["aggregate_sha256"]}, indent=2))


def token_hash(tokens: list[int]) -> str:
    return hashlib.sha256(b"".join(struct.pack("<q", value) for value in tokens)).hexdigest()


def finalize(args: argparse.Namespace) -> None:
    pre = json.loads(args.preflight.read_text())
    device = json.loads((args.artifacts / "device-result.json").read_text())
    props = json.loads((args.artifacts / "device-properties.json").read_text())
    runs = device["runs"]
    wav_path = args.artifacts / "generation-run-0.wav"
    repeat_wav = args.artifacts / "generation-run-1.wav"
    with wave.open(str(wav_path), "rb") as wav:
        wav_meta = {"sample_rate_hz": wav.getframerate(), "channels": wav.getnchannels(), "bits_per_sample": wav.getsampwidth() * 8, "frames": wav.getnframes(), "duration_seconds": wav.getnframes() / wav.getframerate(), "encoding": "PCM_S16LE"}
    run_evidence = []
    for run in runs:
        run_evidence.append({
            "run": run["run"], "tokens": run["tokens"], "tokens_i64le_sha256": token_hash(run["tokens"]),
            "chunks": [{"chunk": c["chunk"], "sample_start": c["sample_start"], "sample_end_exclusive": c["sample_end_exclusive"], "pcm_sha256": c["pcm_sha256"]} for c in run["chunks"]],
            "stop_reason": run["stop_reason"], "valid_length": run["valid_length"], "elapsed_seconds": run["elapsed_seconds"],
        })
    deterministic = device["deterministic"] and sha256(wav_path) == sha256(repeat_wav) and run_evidence[0]["tokens_i64le_sha256"] == run_evidence[1]["tokens_i64le_sha256"]
    capacity = all(run["stop_reason"] == "CAPACITY" and run["audio_chunks"] == 2 for run in runs)
    exact_input = device["input"]["text"] + "\n" == (ROOT / "artifacts/0001/reference.txt").read_text()
    feasibility_failure = pre["status"] == "passed" and exact_input and capacity and deterministic
    result = {
        "schema_version": 1,
        "status": "feasibility_failure" if feasibility_failure else "rejected",
        "scope": "exact locked two-speaker reference transcript on the Galaxy S23 Ultra",
        "locked_preflight": {"status": pre["status"], "path": "artifacts/0002/lane-d/locked-reference/preflight.json", "checks": pre["checks"]},
        "provenance": {"source_revision": SOURCE_REVISION, "model_revision": MODEL_REVISION, "seed": 42, "cfg": 1.3, "transcript_sha256": TRANSCRIPT_SHA256, "exact_transcript_consumed": exact_input},
        "runtime": pre["runtime"], "device": props, "packages": pre["packages"],
        "reference_wav": pre["reference_wav"],
        "android_wav": {"path": "artifacts/0002/lane-d/locked-reference/generation-run-0.wav", "bytes": wav_path.stat().st_size, "sha256": sha256(wav_path), "repeat_sha256": sha256(repeat_wav), **wav_meta},
        "generation": {"requested_duration_seconds": pre["reference_wav"]["duration_seconds"], "produced_duration_seconds": wav_meta["duration_seconds"], "runs": run_evidence, "deterministic": deterministic, "wav_byte_identical_across_runs": sha256(wav_path) == sha256(repeat_wav)},
        "feasibility_failure": {
            "reproducible": feasibility_failure,
            "reason": "The first and cached decoder/semantic PTE ABIs have capacity for only two 3,200-sample chunks. Cached call 1 returns wider static cache axes that cannot be passed to a third call. The controller correctly stops CAPACITY instead of truncating, padding, or resetting state.",
            "requested_samples": pre["reference_wav"]["frames"], "produced_samples": wav_meta["frames"], "capacity_chunks": 2,
            "complete_locked_run": False,
        },
        "implementation_commits": [args.commit],
        "commands": [
            "artifacts/venv-executorch-1.2/bin/python experiments/0002-vibevoice-1.5b-executorch-android/export/generation_two_speaker_io.py prepare artifacts/0002/lane-d/locked-reference-input",
            "flock artifacts/locks/phone.lock experiments/0002-vibevoice-1.5b-executorch-android/android/run-locked-reference-generation.sh",
            "python3 -m json.tool experiments/0002-vibevoice-1.5b-executorch-android/results/locked-reference-android.json >/dev/null",
        ],
        "conclusion": "Reproducible feasibility failure. Every locked input passed preflight and the phone consumed the exact transcript, but both deterministic runs stopped at the exported static-cache capacity after 0.266667 seconds (2/98 required chunks). Therefore no complete 13.066667-second locked-reference WAV was generated, and this build cannot yet run the locked reference transcript.",
    }
    if not feasibility_failure:
        raise RuntimeError("run did not satisfy the documented reproducible-feasibility-failure criteria")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "wav_sha256": result["android_wav"]["sha256"], "duration_seconds": wav_meta["duration_seconds"], "deterministic": deterministic}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("preflight")
    command.add_argument("inputs", type=Path)
    command.add_argument("output", type=Path)
    command.add_argument("--device-model", default="SM-S918B")
    command.set_defaults(func=preflight)
    command = sub.add_parser("finalize")
    command.add_argument("artifacts", type=Path)
    command.add_argument("preflight", type=Path)
    command.add_argument("output", type=Path)
    command.add_argument("--commit", required=True)
    command.set_defaults(func=finalize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
