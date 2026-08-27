#!/usr/bin/env python3
"""Prepare a private, hash-bound Gemma4 phone viability stage without ADB."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
BUNDLE = EXP / ".local/runtime-bundle"
STAGE = EXP / ".local/phone-stage"
SHORT = EXP / "protocol/rendered/short.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def main() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    for source in sorted(path for path in BUNDLE.rglob("*") if path.is_file()):
        if source.name in {"build.stdout.log", "build.stderr.log"}:
            continue
        link_or_copy(source, STAGE / source.relative_to(BUNDLE))
    link_or_copy(SHORT, STAGE / "short.txt")

    required_runtime_files = [
        "bin/genie-app",
        "lib/libGenie.so",
        "lib/libQnnHtp.so",
        "lib/libQnnSystem.so",
        "lib/libQnnHtpV73Stub.so",
        "lib/libQnnHtpV73Skel.so",
        "lib/libQnnHtpNetRunExtensions.so",
        "htp_backend_ext_config.json",
    ]
    missing = [name for name in required_runtime_files if not (STAGE / name).is_file()]
    if missing:
        raise RuntimeError(f"incomplete QnnHtp runtime stage, missing: {missing}")

    script = """log create log1 verbose genie-verbose.log
profile create profile1
dialog config create config1 gemma4-e2b-htp-cl4096-greedy.json
dialog config bind profile config1 profile1
dialog config bind log config1 log1
dialog create dialog1 config1
dialog setMaxNumTokens dialog1 16
dialog query dialog1 short.txt viability-output.txt
dialog getValue dialog1 GENIE_DIALOG_PARAM_CONTEXT_OCCUPANCY
profile save profile1 viability-profile.json
dialog free dialog1
dialog config free config1
profile free profile1
log free log1
exit
"""
    (STAGE / "viability.script").write_text(script)

    files = {}
    for path in sorted(item for item in STAGE.rglob("*") if item.is_file()):
        if path.name in {"SHA256SUMS", "stage-manifest.json"}:
            continue
        files[str(path.relative_to(STAGE))] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "schema_version": 1,
        "classification": "private_phone_stage_preparation_only",
        "source_bundle_manifest_sha256": sha256(BUNDLE / "runtime-manifest.json"),
        "canonical_short_rendered_sha256": sha256(SHORT),
        "viability_output_ceiling_tokens": 16,
        "canonical_campaign": False,
        "adb_used": False,
        "phone_lock_acquired": False,
        "required_runtime_files": required_runtime_files,
        "stage_completeness_check_passed": True,
        "files": files,
    }
    (STAGE / "stage-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with (STAGE / "SHA256SUMS").open("w") as out:
        for path in sorted(item for item in STAGE.rglob("*") if item.is_file() and item.name != "SHA256SUMS"):
            out.write(f"{sha256(path)}  {path.relative_to(STAGE)}\n")
    os.chmod(STAGE / "bin/genie-app", 0o700)
    for path in STAGE.rglob("*"):
        if path.is_dir():
            path.chmod(0o700)
        elif path != STAGE / "bin/genie-app":
            path.chmod(0o600)
    print(STAGE)


if __name__ == "__main__":
    main()
