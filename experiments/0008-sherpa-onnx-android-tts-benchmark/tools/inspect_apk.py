#!/usr/bin/env python3
"""Fail-closed content gate for the ignored host-built benchmark APK."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

PINNED_AAR_SIZE = 49_095_090
PINNED_AAR_SHA256 = "6419cd8bc983e0c4fab06067f0fe0313fdc0f7103818ac1e7a08d50787b7a82b"
NATIVE_LIBS = {"libonnxruntime.so", "libsherpa-onnx-c-api.so", "libsherpa-onnx-cxx-api.so", "libsherpa-onnx-jni.so"}
FORBIDDEN_SUFFIXES = (".onnx", ".wav", ".flac", ".tar", ".tar.bz2", ".zip", ".7z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inspect(apk: Path, aar: Path) -> dict:
    if aar.stat().st_size != PINNED_AAR_SIZE or sha256_bytes(aar.read_bytes()) != PINNED_AAR_SHA256:
        raise ValueError("sherpa AAR does not match pinned 1.13.5 bytes")
    with zipfile.ZipFile(aar) as source:
        aar_libs = {name.removeprefix("jni/arm64-v8a/"): sha256_bytes(source.read(name))
                    for name in source.namelist() if name.startswith("jni/arm64-v8a/") and not name.endswith("/")}
    with zipfile.ZipFile(apk) as package:
        names = package.namelist()
        if len(names) != len(set(names)):
            raise ValueError("APK contains duplicate ZIP paths")
        forbidden = [name for name in names if name.lower().endswith(FORBIDDEN_SUFFIXES)
                     or name.lower().startswith(("assets/models/", "assets/model/"))]
        if forbidden:
            raise ValueError(f"APK bundles model/archive/audio content: {forbidden}")
        native = [name for name in names if name.startswith("lib/") and not name.endswith("/")]
        abis = {name.split("/")[1] for name in native}
        if abis != {"arm64-v8a"}:
            raise ValueError(f"APK is not arm64-only: {sorted(abis)}")
        apk_libs = {Path(name).name: sha256_bytes(package.read(name)) for name in native}
        if set(apk_libs) != NATIVE_LIBS or apk_libs != aar_libs:
            raise ValueError("APK native libraries do not exactly match pinned AAR arm64 payload")
    return {
        "apk": str(apk),
        "apk_bytes": apk.stat().st_size,
        "apk_sha256": sha256_bytes(apk.read_bytes()),
        "abi": "arm64-v8a",
        "pinned_aar_sha256": PINNED_AAR_SHA256,
        "native_libraries": sorted(apk_libs),
        "bundled_models_archives_or_audio": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    parser.add_argument("--aar", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.apk, args.aar), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
