#!/usr/bin/env python3
"""Fully checksum an installed model pack after provisioning, without inference.

The caller must own artifacts/locks/phone.lock and establish that the phone/app
is idle. This read-only helper does not install, stop the app or replace packs.
Normal generation uses the cheaper manifest/metadata check instead.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import time

FILES = {
    "GEMMA_MODEL": "models/gemma-4-e2b.litertlm",
    "GEMMA_TOKENIZER": "models/tokenizer.model",
}
SUPERTONIC_FILES = {
    "SUPERTONIC_CONFIG": "assets/config.json",
    "SUPERTONIC_DURATION_DESCRIPTOR": "contexts/duration-context.onnx",
    "SUPERTONIC_DURATION_BINARY": "contexts/duration-context_qnn.bin",
    "SUPERTONIC_TEXT_DESCRIPTOR": "contexts/text-context.onnx",
    "SUPERTONIC_TEXT_BINARY": "contexts/text-context_qnn.bin",
    "SUPERTONIC_VECTOR_DESCRIPTOR": "contexts/vector-context.onnx",
    "SUPERTONIC_VECTOR_BINARY": "contexts/vector-context_qnn.bin",
    "SUPERTONIC_VOCODER_DESCRIPTOR": "contexts/vocoder-context.onnx",
    "SUPERTONIC_VOCODER_BINARY": "contexts/vocoder-context_qnn.bin",
    "SUPERTONIC_TOKENIZER": "assets/tokenizer.json",
    "SUPERTONIC_UNICODE_INDEXER": "assets/unicode-indexer.i32",
    "SUPERTONIC_VOICE": "assets/voice.bin",
    "SUPERTONIC_STYLE": "assets/voice-style.json",
}
PROFILES = {
    "gemma-4-e2b": ("GEMMA_4_E2B_LITERT_GPU", FILES),
    "supertonic-3": ("SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP", SUPERTONIC_FILES),
    "supertonic-3-provider": ("SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP", SUPERTONIC_FILES),
}
SHA256 = re.compile(r"[0-9a-f]{64}")


def checked_manifest(raw: bytes, expected_sha256: str, pack_id: str = "gemma-4-e2b") -> dict:
    route, files = PROFILES[pack_id]
    if not SHA256.fullmatch(expected_sha256):
        raise ValueError("A trusted model-pack manifest SHA-256 is required")
    if not 0 < len(raw) <= 1_048_576:
        raise ValueError("Invalid manifest size")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Installed manifest differs from the trusted pin")
    manifest = json.loads(raw)
    if (manifest["schemaVersion"] != 2 or manifest["id"] != pack_id
            or manifest["route"] != route):
        raise ValueError("Not the expected model pack")
    entries = manifest["files"]
    if len(entries) != len(files) or {e["role"] for e in entries} != set(files):
        raise ValueError("Invalid model-pack role inventory")
    for entry in entries:
        if entry["path"] != files[entry["role"]]:
            raise ValueError("Unexpected model payload path")
        if type(entry["bytes"]) is not int or entry["bytes"] <= 0:
            raise ValueError("Invalid model payload size")
        if not SHA256.fullmatch(entry["sha256"]):
            raise ValueError("Invalid model payload checksum")
    return manifest


def verify_installed_pack(adb: str, serial: str, package: str, expected_sha256: str,
                          pack_id: str = "gemma-4-e2b") -> dict:
    _, files = PROFILES[pack_id]
    root = "no_backup/model-packs/" + pack_id + "/current"
    if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
        raise ValueError("Invalid application ID")
    command = [adb, "-s", serial]

    def run(*args: str, timeout: int = 60) -> bytes:
        return subprocess.check_output(command + list(args), timeout=timeout)

    started = time.monotonic()
    raw = run("exec-out", "run-as", package, "cat", root + "/manifest.json")
    manifest = checked_manifest(raw, expected_sha256, pack_id)
    # All paths come from fixed inventories, not arbitrary shell input.
    safety = (f"set -e; test -d {root}; test ! -L {root}; "
              f'test -z "$(find {root} -type l)"; '
              f"cd {root}; find . -type f")
    inventory = run("shell", "run-as", package, "sh", "-c", shlex.quote(safety)).decode().splitlines()
    if set(inventory) != {"./manifest.json", *("./" + p for p in files.values())}:
        raise ValueError("Unexpected installed model-pack inventory")
    results = []
    for entry in manifest["files"]:
        path = root + "/" + entry["path"]
        size = int(run("exec-out", "run-as", package, "stat", "-c", "%s", path).strip())
        if size != entry["bytes"]:
            raise ValueError("Installed model size mismatch: " + entry["path"])
        actual = run("exec-out", "run-as", package, "sha256sum", path, timeout=300).decode().split()[0]
        if actual != entry["sha256"]:
            raise ValueError("Installed model SHA-256 mismatch: " + entry["path"])
        results.append({"path": entry["path"], "bytes": size, "sha256": actual})
    return {"result": "fully_verified", "packId": pack_id, "package": package,
            "manifestSha256": expected_sha256, "files": results,
            "elapsedSeconds": time.monotonic() - started, "inference": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--package", default="dev.qoralo.podcast.internal")
    parser.add_argument("--pack-id", choices=PROFILES, default="gemma-4-e2b")
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args()
    result = verify_installed_pack(args.adb, args.serial, args.package, args.expected_manifest_sha256, args.pack_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
