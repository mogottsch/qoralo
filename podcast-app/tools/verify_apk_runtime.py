#!/usr/bin/env python3
"""Verify packaged native bytes and ELF identities before any phone install."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def elf_identity(path: Path) -> tuple[str, str, str | None]:
    header = subprocess.run(["readelf", "-h", str(path)], check=True, text=True, capture_output=True).stdout
    dynamic = subprocess.run(["readelf", "-d", str(path)], check=True, text=True, capture_output=True).stdout
    elf_class = re.search(r"Class:\s+(\S+)", header)
    machine = re.search(r"Machine:\s+(.+)", header)
    soname = re.search(r"\(SONAME\).*\[(.+?)\]", dynamic)
    if not elf_class or not machine:
        raise SystemExit(f"could not inspect ELF identity: {path}")
    return elf_class.group(1), machine.group(1).strip(), soname.group(1) if soname else None


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, default=project / "app/build/outputs/apk/debug/app-debug.apk")
    parser.add_argument("--authority", type=Path, default=project / "config/trusted-local-runtime.json")
    parser.add_argument("--output", type=Path, default=project / ".local/apk-runtime-provenance.json")
    args = parser.parse_args()
    authority = json.loads(args.authority.read_text(encoding="utf-8"))
    expected = authority["supertonic"]["runtimeLibraries"]
    records: list[dict[str, object]] = []
    with zipfile.ZipFile(args.apk) as archive, tempfile.TemporaryDirectory() as temporary:
        names = set(archive.namelist())
        required_names = {f"lib/arm64-v8a/{name}" for name in expected}
        required_names |= {"lib/arm64-v8a/liblitertlm_jni.so", "lib/arm64-v8a/libpodcast_runtime.so"}
        missing = required_names - names
        if missing:
            raise SystemExit(f"APK is missing runtime libraries: {sorted(missing)}")
        for name, identity in expected.items():
            entry = f"lib/arm64-v8a/{name}"
            payload = archive.read(entry)
            digest = sha256_bytes(payload)
            if len(payload) != identity["bytes"] or digest != identity["sha256"]:
                raise SystemExit(f"APK mutated trusted runtime library {name}: bytes={len(payload)} sha256={digest}")
            extracted = Path(temporary) / name
            extracted.write_bytes(payload)
            elf_class, machine, soname = elf_identity(extracted)
            if (elf_class, machine, soname) != (identity["elfClass"], identity["machine"], identity["soname"]):
                raise SystemExit(f"APK runtime ELF identity mismatch for {name}: {(elf_class, machine, soname)}")
            records.append({"name": name, "scope": "trusted-injected", "bytes": len(payload), "sha256": digest,
                            "elfClass": elf_class, "machine": machine, "soname": soname})

        lite_entry = "lib/arm64-v8a/liblitertlm_jni.so"
        lite_payload = archive.read(lite_entry)
        lite_digest = sha256_bytes(lite_payload)
        if lite_digest != authority["gemma"]["litertAar"]["jniSha256"]:
            raise SystemExit(f"APK LiteRT JNI does not match trusted Maven AAR: {lite_digest}")
        lite_path = Path(temporary) / "liblitertlm_jni.so"
        lite_path.write_bytes(lite_payload)
        elf_class, machine, soname = elf_identity(lite_path)
        records.append({"name": "liblitertlm_jni.so", "scope": "trusted-maven-aar", "bytes": len(lite_payload),
                        "sha256": lite_digest, "elfClass": elf_class, "machine": machine, "soname": soname})

        bridge_entry = "lib/arm64-v8a/libpodcast_runtime.so"
        bridge_payload = archive.read(bridge_entry)
        bridge_path = Path(temporary) / "libpodcast_runtime.so"
        bridge_path.write_bytes(bridge_payload)
        elf_class, machine, soname = elf_identity(bridge_path)
        if elf_class != "ELF64" or machine != "AArch64" or soname != "libpodcast_runtime.so":
            raise SystemExit(f"app bridge ELF identity mismatch: {(elf_class, machine, soname)}")
        records.append({"name": "libpodcast_runtime.so", "scope": "app-source-built", "bytes": len(bridge_payload),
                        "sha256": sha256_bytes(bridge_payload), "elfClass": elf_class, "machine": machine, "soname": soname})

    result = {"schemaVersion": 1, "apk": str(args.apk), "apkSha256": sha256_bytes(args.apk.read_bytes()),
              "authority": str(args.authority), "libraries": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": "passed", "apkSha256": result["apkSha256"], "libraries": len(records),
                      "provenance": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
