#!/usr/bin/env python3
"""Fully checksum the installed Gemma pack after provisioning, without inference.

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

ROOT = "no_backup/model-packs/gemma-4-e2b/current"
FILES = {
    "GEMMA_MODEL": "models/gemma-4-e2b.litertlm",
    "GEMMA_TOKENIZER": "models/tokenizer.model",
}
SHA256 = re.compile(r"[0-9a-f]{64}")


def checked_manifest(raw: bytes, expected_sha256: str) -> dict:
    if not SHA256.fullmatch(expected_sha256):
        raise ValueError("A trusted Gemma manifest SHA-256 is required")
    if not 0 < len(raw) <= 1_048_576:
        raise ValueError("Invalid manifest size")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Installed Gemma manifest differs from the trusted pin")
    manifest = json.loads(raw)
    if (manifest["schemaVersion"] != 2 or manifest["id"] != "gemma-4-e2b"
            or manifest["route"] != "GEMMA_4_E2B_LITERT_GPU"):
        raise ValueError("Not the expected Gemma pack")
    entries = manifest["files"]
    if len(entries) != len(FILES) or {e["role"] for e in entries} != set(FILES):
        raise ValueError("Gemma requires exactly one model and one tokenizer")
    for entry in entries:
        if entry["path"] != FILES[entry["role"]]:
            raise ValueError("Unexpected Gemma payload path")
        if type(entry["bytes"]) is not int or entry["bytes"] <= 0:
            raise ValueError("Invalid Gemma payload size")
        if not SHA256.fullmatch(entry["sha256"]):
            raise ValueError("Invalid Gemma payload checksum")
    return manifest


def verify_installed_pack(adb: str, serial: str, package: str, expected_sha256: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.]+", package):
        raise ValueError("Invalid application ID")
    command = [adb, "-s", serial]

    def run(*args: str, timeout: int = 60) -> bytes:
        return subprocess.check_output(command + list(args), timeout=timeout)

    started = time.monotonic()
    raw = run("exec-out", "run-as", package, "cat", ROOT + "/manifest.json")
    manifest = checked_manifest(raw, expected_sha256)
    # Refuse links and unlisted files before hashing anything large. All paths
    # below come from the fixed two-file inventory, not arbitrary shell input.
    safety = (f"set -e; test -d {ROOT}; test ! -L {ROOT}; "
              f'test -z "$(find {ROOT} -type l)"; '
              f"cd {ROOT}; find . -type f")
    inventory = run("shell", "run-as", package, "sh", "-c", shlex.quote(safety)).decode().splitlines()
    if set(inventory) != {"./manifest.json", *("./" + p for p in FILES.values())}:
        raise ValueError("Unexpected installed Gemma inventory")
    results = []
    for entry in manifest["files"]:
        path = ROOT + "/" + entry["path"]
        size = int(run("exec-out", "run-as", package, "stat", "-c", "%s", path).strip())
        if size != entry["bytes"]:
            raise ValueError("Installed Gemma size mismatch: " + entry["path"])
        actual = run("exec-out", "run-as", package, "sha256sum", path, timeout=300).decode().split()[0]
        if actual != entry["sha256"]:
            raise ValueError("Installed Gemma SHA-256 mismatch: " + entry["path"])
        results.append({"path": entry["path"], "bytes": size, "sha256": actual})
    return {"result": "fully_verified", "package": package, "manifestSha256": expected_sha256,
            "files": results, "elapsedSeconds": time.monotonic() - started, "inference": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True)
    parser.add_argument("--package", default="dev.qoralo.podcast.internal")
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args()
    result = verify_installed_pack(args.adb, args.serial, args.package, args.expected_manifest_sha256)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
