#!/usr/bin/env python3
"""Validate and smoke-test the exact Pocket deployment descriptor."""
from __future__ import annotations

import argparse
import array
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import sys
import wave
from pathlib import Path, PurePosixPath
from typing import Any

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
EXPECTED_COMPONENTS = {
    "lm_flow": "lm_flow.int8.onnx",
    "lm_main": "lm_main.int8.onnx",
    "encoder": "encoder.onnx",
    "decoder": "decoder.int8.onnx",
    "text_conditioner": "text_conditioner.onnx",
    "vocab_json": "vocab.json",
    "token_scores_json": "token_scores.json",
}
EXPECTED_DEPLOYED = set(EXPECTED_COMPONENTS.values()) | {"test_wavs/bria.wav"}


class PocketError(RuntimeError):
    """The Pocket track differs from its fail-closed deployment contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PocketError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PocketError(f"JSON object required: {path}")
    return value


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise PocketError("model paths must be non-empty canonical POSIX relative paths")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(x in ("", ".", "..") for x in path.parts):
        raise PocketError(f"unsafe model path: {value!r}")
    if path.parts[0] in {"assets", "android_asset"}:
        raise PocketError("bundled-asset paths are forbidden")
    return value


def validate_descriptor(descriptor: dict[str, Any], inventory: dict[str, Any]) -> None:
    archive = descriptor.get("archive", {})
    if archive != {
        "id": "pocket",
        "filename": "sherpa-onnx-pocket-tts-int8-2026-01-26.tar.bz2",
        "root": "sherpa-onnx-pocket-tts-int8-2026-01-26",
        "bytes": 98336520,
        "sha256": "2f3b88823cbbb9bf0b2477ec8ae7b3fec417b3a87b6bb5f256dba66f2ad967cb",
    }:
        raise PocketError("Pocket archive identity or INT8 release date drift")
    runtime = descriptor.get("runtime", {})
    if runtime.get("sherpa_onnx_version") != "1.13.5" or runtime.get("sherpa_onnx_commit") != "3dc7c569f31ca2cd4a20ed6f7db780327e6714c5":
        raise PocketError("sherpa runtime drift")
    if runtime.get("model_root_kind") != "app_specific_external_files":
        raise PocketError("models must use app-specific external filesystem storage")
    if runtime.get("provider") != "cpu" or runtime.get("num_threads") != 1:
        raise PocketError("canonical Pocket configuration requires CPU and one thread")
    if runtime.get("sample_rate_hz") != 24000 or runtime.get("generation") != {"num_steps": 5}:
        raise PocketError("sample rate or generation configuration drift")
    pocket = descriptor.get("pocket")
    if pocket != EXPECTED_COMPONENTS:
        raise PocketError("Pocket components must be the exact pinned INT8 file set")
    for path in pocket.values():
        _safe_relative(path)

    voice = descriptor.get("voice", {})
    if (voice.get("requested_voice") != "Alba"
            or voice.get("actual_reference") != "test_wavs/bria.wav"
            or voice.get("actual_reference_sha256") != "85f46d6f0642f657a6bd689ddaa52d5a5f53e4314715e1032704c80917392181"
            or voice.get("actual_reference_sample_rate_hz") != 24000
            or voice.get("voice_match") is not False):
        raise PocketError("unverified reference or Alba/Bria labeling drift")
    _safe_relative(voice["actual_reference"])
    if "alba" in voice["actual_reference"].casefold():
        raise PocketError("the packaged Bria fallback must never be labeled Alba")

    entries = descriptor.get("deployed_files")
    if not isinstance(entries, list) or any(not isinstance(x, dict) for x in entries):
        raise PocketError("deployed file pins are required")
    paths = [_safe_relative(x.get("path")) for x in entries]
    if len(paths) != len(set(paths)) or set(paths) != EXPECTED_DEPLOYED:
        raise PocketError("deployed Pocket file set is missing, duplicated, or substituted")
    archive_files = {x.get("path"): x for x in inventory.get("files", []) if isinstance(x, dict)}
    if any("alba" in str(path).casefold() for path in archive_files):
        raise PocketError("inventory claims Alba is absent but contains an Alba-named file")
    if "test_wavs/bria.wav" not in archive_files:
        raise PocketError("packaged Bria reference is absent")
    for entry in entries:
        archived = archive_files.get(entry["path"])
        if archived is None or entry.get("bytes") != archived.get("bytes") or entry.get("sha256") != archived.get("sha256"):
            raise PocketError(f"deployed pin differs from archive inventory: {entry['path']}")

    evidence = descriptor.get("license_evidence", {})
    if evidence.get("disposition") != "research_only_unresolved":
        raise PocketError("license discrepancy must remain unresolved and research-only")
    if set(evidence) < {"non_commercial_statement", "bundled_license"}:
        raise PocketError("both license evidence artifacts are mandatory")
    if descriptor.get("transcript", {}).get("sha256") != "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f":
        raise PocketError("frozen transcript pin drift")


def _resolve_model_file(root: Path, relative: str) -> Path:
    relative = _safe_relative(relative)
    if not root.is_dir() or root.is_symlink():
        raise PocketError("model root must be a real directory")
    resolved_root = root.resolve(strict=True)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    if not candidate.is_file() or candidate.is_symlink():
        raise PocketError(f"missing or linked model file: {relative}")
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise PocketError(f"model file escapes model root: {relative}") from exc
    return resolved


def validate_model_root(descriptor: dict[str, Any], root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for pin in descriptor["deployed_files"]:
        path = _resolve_model_file(root, pin["path"])
        if path.stat().st_size != pin["bytes"] or sha256_file(path) != pin["sha256"]:
            raise PocketError(f"deployed file hash/size mismatch: {pin['path']}")
        result[pin["path"]] = path
    reference = result[descriptor["voice"]["actual_reference"]]
    try:
        with wave.open(str(reference), "rb") as stream:
            params = (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype())
    except (wave.Error, EOFError) as exc:
        raise PocketError(f"invalid reference WAV: {exc}") from exc
    if params != (1, 2, 24000, "NONE"):
        raise PocketError(f"reference WAV format drift: {params}")
    return result


def validate_evidence(descriptor: dict[str, Any]) -> None:
    evidence = descriptor["license_evidence"]
    readme = _resolve_model_file(HERE, evidence["non_commercial_statement"]["path"])
    license_path = _resolve_model_file(HERE, evidence["bundled_license"]["path"])
    for path, pin in ((readme, evidence["non_commercial_statement"]), (license_path, evidence["bundled_license"])):
        if sha256_file(path) != pin["sha256"]:
            raise PocketError("committed license evidence hash drift")
    if "It is for non-commercial." not in readme.read_text(encoding="utf-8"):
        raise PocketError("verbatim non-commercial statement is absent")
    if "Creative Commons Attribution 4.0 International Public License" not in license_path.read_text(encoding="utf-8"):
        raise PocketError("bundled CC BY 4.0 license evidence is absent")


def validate_audio(path: Path, expected_rate: int = 24000) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as stream:
            channels, width, rate, frames = stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()
            payload = stream.readframes(frames)
            trailing = stream.readframes(1)
    except (OSError, wave.Error, EOFError) as exc:
        raise PocketError(f"smoke WAV is not independently decodable: {exc}") from exc
    if (channels, width, rate) != (1, 2, expected_rate) or frames <= 0 or trailing or len(payload) != frames * 2:
        raise PocketError("smoke WAV format, frame count, or truncation failure")
    samples = array.array("h"); samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    peak = max(abs(int(x)) for x in samples)
    rms = math.sqrt(sum(int(x) * int(x) for x in samples) / len(samples))
    if peak == 0 or rms < 1.0:
        raise PocketError("smoke WAV is silent")
    if peak >= 32767:
        raise PocketError("smoke WAV clips")
    return {"channels": channels, "sample_width_bytes": width, "sample_rate_hz": rate, "sample_count": frames,
            "duration_seconds": frames / rate, "peak_abs_pcm16": peak, "rms_pcm16": rms,
            "bytes": path.stat().st_size, "sha256": sha256_file(path), "decodable": True, "non_silent": True,
            "not_clipped": True, "complete_decode": True}


def verify_pinned_runtime(wheel_directory: Path) -> None:
    spec = importlib.util.spec_from_file_location("pinning", EXPERIMENT / "tools" / "pinning.py")
    if spec is None or spec.loader is None:
        raise PocketError("cannot load common pin verifier")
    pinning = importlib.util.module_from_spec(spec); spec.loader.exec_module(pinning)
    manifest = pinning.load_manifest(EXPERIMENT / "pins" / "assets.json")
    try:
        pinning.verify_host_runtime(wheel_directory, manifest)
    except Exception as exc:
        raise PocketError(f"unpinned host runtime: {exc}") from exc
    os_release = Path("/etc/os-release").read_text(encoding="utf-8")
    if 'ID=ubuntu' not in os_release or 'VERSION_ID="22.04"' not in os_release:
        raise PocketError("host smoke requires pinned Ubuntu 22.04")
    if platform.libc_ver() != ("glibc", "2.35"):
        raise PocketError("host smoke requires pinned glibc 2.35")
    if importlib.metadata.version("sherpa-onnx") != "1.13.5" or importlib.metadata.version("sherpa-onnx-core") != "1.13.5":
        raise PocketError("installed sherpa packages differ from pinned 1.13.5 wheels")


def run_smoke(descriptor: dict[str, Any], model_root: Path, wheel_directory: Path, output: Path, report: Path) -> None:
    verify_pinned_runtime(wheel_directory)
    files = validate_model_root(descriptor, model_root)
    import sherpa_onnx
    pocket = descriptor["pocket"]
    config = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
        pocket=sherpa_onnx.OfflineTtsPocketModelConfig(
            lm_flow=str(files[pocket["lm_flow"]]), lm_main=str(files[pocket["lm_main"]]),
            encoder=str(files[pocket["encoder"]]), decoder=str(files[pocket["decoder"]]),
            text_conditioner=str(files[pocket["text_conditioner"]]), vocab_json=str(files[pocket["vocab_json"]]),
            token_scores_json=str(files[pocket["token_scores_json"]])),
        debug=False, num_threads=1, provider="cpu"))
    if not config.validate():
        raise PocketError("pinned sherpa rejected the Pocket configuration")
    tts = sherpa_onnx.OfflineTts(config)
    reference_path = files[descriptor["voice"]["actual_reference"]]
    with wave.open(str(reference_path), "rb") as source:
        pcm = array.array("h"); pcm.frombytes(source.readframes(source.getnframes()))
    if sys.byteorder != "little": pcm.byteswap()
    generation = sherpa_onnx.GenerationConfig()
    generation.reference_audio = [value / 32768.0 for value in pcm]
    generation.reference_sample_rate = 24000
    generation.num_steps = 5
    transcript = (EXPERIMENT / "protocol" / "transcript.txt").read_text(encoding="utf-8")
    audio = tts.generate(transcript, generation)
    if not audio.samples or audio.sample_rate != 24000:
        raise PocketError("host smoke returned empty audio or an unexpected sample rate")
    output.parent.mkdir(parents=True, exist_ok=True)
    ints = array.array("h", (max(-32768, min(32767, round(float(x) * 32767))) for x in audio.samples))
    if sys.byteorder != "little": ints.byteswap()
    with wave.open(str(output), "wb") as sink:
        sink.setnchannels(1); sink.setsampwidth(2); sink.setframerate(audio.sample_rate); sink.writeframes(ints.tobytes())
    validation = validate_audio(output)
    result = {
        "schema_version": 1,
        "model_id": "pocket",
        "status": "passed",
        "scope": "host_configuration_smoke_only",
        "android_performance_evidence": False,
        "timing_recorded": False,
        "transcript_sha256": descriptor["transcript"]["sha256"],
        "requested_voice": "Alba",
        "actual_reference": "test_wavs/bria.wav",
        "voice_match": False,
        "provider": "cpu",
        "num_threads": 1,
        "runtime": {"sherpa_onnx": "1.13.5", "python": platform.python_version(), "platform": "Ubuntu 22.04 x86_64 glibc 2.35"},
        "output": {"artifact_id": output.name, **validation},
    }
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--descriptor", type=Path, default=HERE / "model.json")
    parser.add_argument("--inventory", type=Path, default=HERE / "archive-inventory.json")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate"); check.add_argument("--model-root", type=Path)
    smoke = sub.add_parser("smoke"); smoke.add_argument("--model-root", type=Path, required=True); smoke.add_argument("--wheel-directory", type=Path, required=True); smoke.add_argument("--output", type=Path, required=True); smoke.add_argument("--report", type=Path, default=HERE / "host-smoke.json")
    args = parser.parse_args()
    descriptor, inventory = load_json(args.descriptor), load_json(args.inventory)
    validate_descriptor(descriptor, inventory); validate_evidence(descriptor)
    if args.command == "validate" and args.model_root: validate_model_root(descriptor, args.model_root)
    if args.command == "smoke": run_smoke(descriptor, args.model_root, args.wheel_directory, args.output, args.report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PocketError as exc:
        print(f"Pocket validation failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
