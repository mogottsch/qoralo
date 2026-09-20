#!/usr/bin/env python3
"""Freeze a new host-only duration-load candidate; old wiring APK/candidate stays intact."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
from prepare_wiring_gate import PROJECT, digest, identity

CONTRACT_SHA = "51edc271c52b43e14f901169315136f29298c29f7e8954eb6b99d6fe21954f02"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--test-apk", type=Path, required=True)
    parser.add_argument("--aapt", type=Path, default=Path.home() / "Android/Sdk/build-tools/35.0.0/aapt")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    apk = args.output / "app.apk"
    tests = args.output / "test.apk"
    shutil.copy2(args.apk, apk); shutil.copy2(args.test_apk, tests)
    contract_file = PROJECT / "app/src/debug/assets/duration-load/contract.json"
    contract_bytes = contract_file.read_bytes()
    if hashlib.sha256(contract_bytes).hexdigest() != CONTRACT_SHA:
        raise ValueError("duration-load contract is not pinned")
    with zipfile.ZipFile(apk) as archive:
        if archive.read("assets/duration-load/contract.json") != contract_bytes:
            raise ValueError("APK diagnostic contract mismatch")
    subprocess.run([str(PROJECT / "tools/verify_apk_runtime.py"), "--apk", str(apk), "--output", str(args.output / "native-inventory.json")], check=True)
    for name, path, pkg in [("app", apk, "dev.qoralo.podcast.internal"), ("test", tests, "dev.qoralo.podcast.internal.test")]:
        badging = subprocess.check_output([str(args.aapt), "dump", "badging", str(path)], text=True)
        if f"package: name='{pkg}'" not in badging:
            raise ValueError("wrong diagnostic package")
        (args.output / f"{name}-badging.txt").write_text(badging)
        manifest = subprocess.check_output([str(args.aapt), "dump", "xmltree", str(path), "AndroidManifest.xml"], text=True)
        (args.output / f"{name}-manifest.txt").write_text(manifest)
    value = {"schemaVersion": 1, "kind": "duration-load-only", "contractSha256": CONTRACT_SHA, "contract": json.loads(contract_bytes),
             "app": identity(apk), "test": identity(tests), "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip(),
             "sourceDirty": bool(subprocess.check_output(["git", "status", "--porcelain", "--", "."], cwd=PROJECT, text=True).strip()),
             "phoneAuthorized": False, "gemmaRequests": 0, "sessionRunCalls": 0,
             "collectionPrerequisite": "unchanged pinned Supertonic pack already installed; no model staging in diagnostic controller"}
    file = args.output / "candidate.json"
    file.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"result": "host_candidate_preflight_passed", "candidate": str(file), "candidateSha256": digest(file), "phoneAuthorized": False}))


if __name__ == "__main__":
    main()
