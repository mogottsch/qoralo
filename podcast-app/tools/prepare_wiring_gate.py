#!/usr/bin/env python3
"""Host-only exact APK/test-APK/input preflight; never starts ADB or prepares model data."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
CONTRACT_SHA = "301408dab967315bf8d5f7bb0dcc83face54438dc139d221e7699ce5dc6b0393"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def identity(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest(path)}


def check_inputs(apk: Path, contract_path: Path) -> dict:
    raw = contract_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA:
        raise ValueError("unapproved wiring contract")
    contract = json.loads(raw)
    with zipfile.ZipFile(apk) as archive:
        if archive.read("assets/wiring/contract.json") != raw:
            raise ValueError("APK wiring contract mismatch")
        for name, expected in contract["inputs"].items():
            payload = archive.read(f"assets/wiring/{name}")
            if len(payload) != expected["bytes"] or hashlib.sha256(payload).hexdigest() != expected["sha256"]:
                raise ValueError(f"APK wiring input mismatch: {name}")
    return contract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="new local readiness directory; never overwrite")
    parser.add_argument("--apk", type=Path, default=PROJECT / "app/build/outputs/apk/debug/app-debug.apk")
    parser.add_argument("--test-apk", type=Path, default=PROJECT / "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk")
    parser.add_argument("--aapt", type=Path, default=Path.home() / "Android/Sdk/build-tools/35.0.0/aapt")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    contract = check_inputs(args.apk, PROJECT / "app/src/debug/assets/wiring/contract.json")
    subprocess.run([str(PROJECT / "tools/verify_apk_runtime.py"), "--apk", str(args.apk), "--output", str(args.output / "runtime-inventory.json")], check=True)
    for kind, apk, expected_package in [("app", args.apk, "dev.qoralo.podcast.internal"), ("test", args.test_apk, "dev.qoralo.podcast.internal.test")]:
        result = subprocess.run([str(args.aapt), "dump", "badging", str(apk)], check=True, capture_output=True, text=True)
        (args.output / f"{kind}-badging.txt").write_text(result.stdout)
        if f"package: name='{expected_package}'" not in result.stdout:
            raise ValueError(f"wrong {kind} package")
        manifest = subprocess.run([str(args.aapt), "dump", "xmltree", str(apk), "AndroidManifest.xml"], check=True, capture_output=True, text=True)
        (args.output / f"{kind}-manifest.txt").write_text(manifest.stdout)
        if kind == "app" and "RuntimeWiringService" not in manifest.stdout:
            raise ValueError("debug wiring service absent")
    authority = json.loads((PROJECT / "config/trusted-local-runtime.json").read_text())
    packs = {}
    for route, key in [("gemma-4-e2b", "gemma"), ("supertonic-3", "supertonic")]:
        root = PROJECT / ".local/model-packs" / route / "current"
        manifest = root / "manifest.json"
        if digest(manifest) != authority[key]["generatedPackManifestSha256"]:
            raise ValueError(f"prepared {route} manifest not trusted")
        packs[route] = {"root": str(root), "manifestSha256": digest(manifest), "localPayloadEvidence": "unchanged trusted prepared pack; input bytes revalidated by app before inference"}
    candidate = {"schemaVersion": 1, "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip(),
                 "sourceDirty": bool(subprocess.check_output(["git", "status", "--porcelain", "--", "."], cwd=PROJECT, text=True).strip()),
                 "app": identity(args.apk), "test": identity(args.test_apk), "contractSha256": CONTRACT_SHA,
                 "contract": contract, "modelPacks": packs, "phoneAuthorized": False,
                 "limitsScope": "runtime wiring only; synthetic Compose and production lifecycle tests run separately"}
    (args.output / "candidate.json").write_text(json.dumps(candidate, indent=2) + "\n")
    print(json.dumps({"result": "host_preflight_passed", "candidate": str(args.output / "candidate.json"),
                      "candidateSha256": digest(args.output / "candidate.json"), "phoneAuthorized": False}))


if __name__ == "__main__":
    main()
