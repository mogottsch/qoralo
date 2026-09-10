#!/usr/bin/env python3
"""Prepare ignored single-process AR171→AR1 integrated Android runner stage."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil
from pathlib import Path

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def hardlink(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, destination)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ar171-context", type=Path, required=True)
    parser.add_argument("--ar1-context", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--runtime-stage", type=Path, required=True)
    parser.add_argument("--prompt-tokens", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    hardlink(args.ar171_context, output / "contexts/ar171.bin")
    hardlink(args.ar1_context, output / "contexts/ar1.bin")
    hardlink(args.runner, output / "direct_lfm2_qnn_runner")
    hardlink(args.prompt_tokens, output / "short.int32le")
    for name in (
        "embedding-quant.u8", "embedding-scales.f32le", "embedding-zp.u8",
        "libQnnHtp.so", "libQnnSystem.so", "libQnnHtpV73Stub.so",
        "libQnnHtpV73Skel.so", "libc++_shared.so",
    ):
        hardlink(args.runtime_stage / name, output / name)
    files = sorted(path for path in output.rglob("*") if path.is_file())
    entries = []
    with (output / "SHA256SUMS").open("w") as manifest:
        for path in files:
            digest = sha256(path)
            relative = path.relative_to(output).as_posix()
            manifest.write(f"{digest}  {relative}\n")
            entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest})
    metadata = {
        "schema_version": 1,
        "classification": "ignored_license_controlled_single_process_integrated_ar171_ar1_android_stage",
        "route": "one process/backend/device; AR171 context loaded once then freed; in-memory 38-state bridge; AR1 context loaded once for max16; no simultaneous contexts or per-token reload",
        "qairt_android_runtime": "2.49.40.260810",
        "qnn_backend_build_id_expected": "v2.49.40.260810104044",
        "prompt_tokens": 171,
        "max_new_tokens": 16,
        "ar171_context_sha256": sha256(args.ar171_context),
        "ar1_context_sha256": sha256(args.ar1_context),
        "runner_sha256": sha256(args.runner),
        "prompt_token_sha256": sha256(args.prompt_tokens),
        "simultaneous_contexts": 1,
        "explicit_phase_transitions": 1,
        "context_reloads_per_phase": 0,
        "per_token_context_streaming": False,
        "output_finite_scan": "all 60 AR171 outputs and all 60 outputs of every AR1 token call",
        "profile_capture": "recursive QNN detailed profile events emitted with phase labels before profile reset/free",
        "payload_files": len(entries),
        "payload_bytes": sum(item["bytes"] for item in entries),
        "files": entries,
        "retained_outside_git": True,
    }
    (output / "stage.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    with (output / "SHA256SUMS").open("a") as manifest:
        manifest.write(f"{sha256(output / 'stage.json')}  stage.json\n")
    print(json.dumps({key: metadata[key] for key in (
        "ar171_context_sha256", "ar1_context_sha256", "runner_sha256",
        "prompt_token_sha256", "payload_files", "payload_bytes",
    )}, indent=2))

if __name__ == "__main__":
    main()
