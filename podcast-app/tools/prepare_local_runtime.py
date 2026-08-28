#!/usr/bin/env python3
"""Prepare authorized local runtime injection and authenticated data-only packs.

Large/licensed inputs and generated packs remain under podcast-app/.local or the
Git-ignored runtime-libs directory. Nothing produced by this tool is publishable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, expected: dict[str, object], label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"trusted {label} is missing: {path}")
    if "bytes" in expected and path.stat().st_size != expected["bytes"]:
        raise SystemExit(f"trusted {label} size mismatch")
    actual = sha256(path)
    if actual != expected["sha256"]:
        raise SystemExit(f"trusted {label} SHA-256 mismatch: expected {expected['sha256']}, got {actual}")


def verify_stage(stage: Path, authority: dict[str, object]) -> None:
    manifest = stage / "stage-manifest.sha256"
    verify_file(manifest, {"sha256": authority["acceptedStageManifestFileSha256"]}, "Supertonic stage manifest")
    listed: set[str] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split(maxsplit=1)
        relative = relative.strip().lstrip("*")
        listed.add(relative)
        verify_file(stage / relative, {"sha256": digest}, f"Supertonic stage payload {relative}")
    actual = {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()}
    extras = actual - listed - {"stage-manifest.sha256"}
    if extras:
        raise SystemExit(f"Supertonic stage has files outside its trusted manifest: {sorted(extras)}")


def link_or_copy(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise SystemExit(f"required authorized artifact is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def file_entry(root: Path, role: str, relative: str) -> dict[str, object]:
    path = root / relative
    return {"role": role, "path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_manifest(root: Path, value: dict[str, object]) -> str:
    path = root / "manifest.json"
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return sha256(path)


def update_properties(path: Path, values: dict[str, str]) -> None:
    existing: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                existing[key] = value
    existing.update(values)
    path.write_text("".join(f"{key}={value}\n" for key, value in sorted(existing.items())), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    project = Path(__file__).resolve().parents[1]
    repo = project.parent
    parser.add_argument("--authority", type=Path, default=project / "config/trusted-local-runtime.json", help="separately reviewed expected-hash authority")
    parser.add_argument("--gemma-model", type=Path, default=repo / "experiments/0025-gemma-4-e2b-it-android/.local/model/gemma-4-E2B-it.litertlm")
    parser.add_argument("--gemma-tokenizer", type=Path, default=repo / "experiments/0025-gemma-4-e2b-it-android/.local/model/gpu-embedded-tokenizer.model")
    parser.add_argument("--supertonic-stage", type=Path, default=repo / "experiments/0023-supertonic-qnn-precompiled-context-startup/.local/phone-stage")
    parser.add_argument("--onnxruntime-include", type=Path, default=repo / "experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source/include/onnxruntime/core/session")
    default_aar = next((Path.home() / ".gradle/caches/modules-2/files-2.1/com.google.ai.edge.litertlm/litertlm-android/0.16.1").glob("*/*.aar"), Path("missing-litertlm-0.16.1.aar"))
    parser.add_argument("--litert-aar", type=Path, default=default_aar)
    args = parser.parse_args()

    if not args.authority.is_file():
        raise SystemExit(f"trusted hash authority is missing: {args.authority}")
    authority = json.loads(args.authority.read_text(encoding="utf-8"))
    if authority.get("schemaVersion") != 1:
        raise SystemExit("unsupported trusted hash authority")
    gemma_authority = authority["gemma"]
    super_authority = authority["supertonic"]
    verify_file(args.gemma_model, gemma_authority["model"], "Gemma model")
    verify_file(args.gemma_tokenizer, gemma_authority["tokenizer"], "Gemma tokenizer")
    verify_file(args.litert_aar, gemma_authority["litertAar"], "LiteRT-LM AAR")
    verify_stage(args.supertonic_stage, super_authority)

    local = project / ".local"
    packs = local / "model-packs"
    gemma = packs / "gemma-4-e2b/current"
    supertonic = packs / "supertonic-3/current"
    shutil.rmtree(gemma, ignore_errors=True)
    shutil.rmtree(supertonic, ignore_errors=True)
    gemma.mkdir(parents=True)
    supertonic.mkdir(parents=True)

    link_or_copy(args.gemma_model, gemma / "models/gemma-4-e2b.litertlm")
    link_or_copy(args.gemma_tokenizer, gemma / "models/tokenizer.model")
    gemma_roles = [
        ("GEMMA_MODEL", "models/gemma-4-e2b.litertlm"),
        ("GEMMA_TOKENIZER", "models/tokenizer.model"),
    ]
    gemma_manifest = {
        "schemaVersion": 2,
        "id": "gemma-4-e2b",
        "version": "hf-6b78abd-litertlm-0.16.1",
        "route": "GEMMA_4_E2B_LITERT_GPU",
        "androidAbi": "arm64-v8a",
        "runtime": {"apiVersion": 1, "backend": "LITERT_GPU", "cpuFallbackAllowed": False, "buildIdentity": "LiteRT-LM 0.16.1"},
        "contract": {"generationPlan": "OUTLINE_THEN_CHAPTERS", "completeChapterPerRequest": True, "contextTokens": 8192, "runtimeVersion": "0.16.1"},
        "files": [file_entry(gemma, role, relative) for role, relative in gemma_roles],
    }
    gemma_hash = write_manifest(gemma, gemma_manifest)
    if gemma_hash != gemma_authority["generatedPackManifestSha256"]:
        raise SystemExit(f"generated Gemma pack manifest is not authorized: {gemma_hash}")

    stage = args.supertonic_stage
    super_files = [
        ("SUPERTONIC_DURATION_DESCRIPTOR", "contexts/duration-context.onnx", stage / "contexts/duration-context.onnx"),
        ("SUPERTONIC_DURATION_BINARY", "contexts/duration-context_qnn.bin", stage / "contexts/duration-context_qnn.bin"),
        ("SUPERTONIC_TEXT_DESCRIPTOR", "contexts/text-context.onnx", stage / "contexts/text-context.onnx"),
        ("SUPERTONIC_TEXT_BINARY", "contexts/text-context_qnn.bin", stage / "contexts/text-context_qnn.bin"),
        ("SUPERTONIC_VECTOR_DESCRIPTOR", "contexts/vector-context.onnx", stage / "contexts/vector-context.onnx"),
        ("SUPERTONIC_VECTOR_BINARY", "contexts/vector-context_qnn.bin", stage / "contexts/vector-context_qnn.bin"),
        ("SUPERTONIC_VOCODER_DESCRIPTOR", "contexts/vocoder-context.onnx", stage / "contexts/vocoder-context.onnx"),
        ("SUPERTONIC_VOCODER_BINARY", "contexts/vocoder-context_qnn.bin", stage / "contexts/vocoder-context_qnn.bin"),
        ("SUPERTONIC_UNICODE_INDEXER", "assets/unicode-indexer.i32", stage / "assets/unicode_indexer.bin"),
        ("SUPERTONIC_VOICE", "assets/voice.bin", stage / "assets/voice.bin"),
    ]
    for _, relative, source in super_files:
        link_or_copy(source, supertonic / relative)
    generated = {
        "assets/config.json": {"model": "supertonic-3", "sampleRateHz": 44100, "voiceId": "M1/SID5", "speakerIndex": 0},
        "assets/tokenizer.json": {"type": "unicode-indexer", "languagePrefix": "<en>", "languageSuffix": "</en>", "paddingId": 0},
        "assets/voice-style.json": {"voiceId": "M1/SID5", "speakerIndex": 0, "source": "voice.bin"},
    }
    for relative, value in generated.items():
        path = supertonic / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    role_paths = [
        ("SUPERTONIC_CONFIG", "assets/config.json"),
        *[(role, relative) for role, relative, _ in super_files],
        ("SUPERTONIC_TOKENIZER", "assets/tokenizer.json"),
        ("SUPERTONIC_STYLE", "assets/voice-style.json"),
    ]
    super_manifest = {
        "schemaVersion": 2,
        "id": "supertonic-3",
        "version": "qnn-2.49.0-sm8550-v73",
        "route": "SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP",
        "androidAbi": "arm64-v8a",
        "runtime": {"apiVersion": 1, "backend": "QNN_HTP", "cpuFallbackAllowed": False, "buildIdentity": "ONNX Runtime 1.27.1 + QAIRT 2.49.0.260730"},
        "contract": {
            "synthesisUnit": "COMPLETE_CHAPTER", "externalContextCount": 4,
            "sampleRateHz": 44100, "channelCount": 1, "pcmBits": 16,
            "textLength": super_authority["contract"]["textLength"], "latentLength": super_authority["contract"]["latentLength"],
            "latentChannels": super_authority["contract"]["latentChannels"], "diffusionSteps": super_authority["contract"]["diffusionSteps"],
        },
        "files": [file_entry(supertonic, role, relative) for role, relative in role_paths],
    }
    super_hash = write_manifest(supertonic, super_manifest)
    if super_hash != super_authority["generatedPackManifestSha256"]:
        raise SystemExit(f"generated Supertonic pack manifest is not authorized: {super_hash}")

    runtime_source = stage / "lib"
    runtime_dest = project / "app/runtime-libs/arm64-v8a"
    runtime_dest.mkdir(parents=True, exist_ok=True)
    runtime_names = [
        "libonnxruntime.so", "libQnnHtp.so", "libQnnHtpPrepare.so",
        "libQnnHtpV73Skel.so", "libQnnHtpV73Stub.so", "libQnnSystem.so",
    ]
    if set(runtime_names) != set(super_authority["runtimeLibraries"]):
        raise SystemExit("trusted runtime library inventory does not match the injection inventory")
    runtime_provenance = []
    for name in runtime_names:
        source = runtime_source / name
        expected_runtime = super_authority["runtimeLibraries"].get(name)
        if expected_runtime is None:
            raise SystemExit(f"runtime library is not present in trusted authority: {name}")
        verify_file(source, expected_runtime, f"runtime library {name}")
        destination = runtime_dest / name
        link_or_copy(source, destination)
        runtime_provenance.append({"name": name, "source": str(source), "bytes": source.stat().st_size, "sha256": sha256(source)})
    (local / "runtime-provenance.json").write_text(json.dumps(runtime_provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    update_properties(project / "local.properties", {
        "gemma.manifest.sha256": gemma_hash,
        "native.runtime.enabled": "true",
        "onnxruntime.include.dir": str(args.onnxruntime_include.resolve()),
        "supertonic.manifest.sha256": super_hash,
    })
    print(json.dumps({
        "result": "prepared", "packsRoot": str(packs),
        "gemmaManifestSha256": gemma_hash, "supertonicManifestSha256": super_hash,
        "runtimeProvenance": str(local / "runtime-provenance.json"),
        "warning": "authorized local/debug use only; do not commit or publish generated artifacts",
    }, indent=2))


if __name__ == "__main__":
    main()
