#!/usr/bin/env python3
"""Fail-closed asset acquisition for experiment 0008 (standard library only)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from typing import Any, Iterable

CHUNK = 1024 * 1024
MAX_MEMBERS = 100_000
MAX_EXTRACTED_BYTES = 16 * 1024**3
REQUIRED_ASSET_FIELDS = {
    "id", "kind", "filename", "url", "release_tag", "release_published_at",
    "asset_created_at", "asset_updated_at", "bytes", "sha256",
    "allowed_top_level", "licenses", "conversion_provenance",
}

class PinError(RuntimeError):
    """An input was not exactly covered by the committed pins."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PinError(f"cannot read pin manifest: {exc}") from exc
    validate_manifest(data)
    return data


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _valid_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_manifest(data: dict[str, Any]) -> None:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise PinError("unsupported pin schema")
    sherpa = data.get("sherpa", {})
    if not isinstance(sherpa, dict) or sherpa.get("tag") != "v1.13.5" or sherpa.get("commit") != "3dc7c569f31ca2cd4a20ed6f7db780327e6714c5":
        raise PinError("sherpa tag/commit is not the experiment pin")
    assets = data.get("assets")
    if (not isinstance(assets, list) or len(assets) != 4
            or any(not isinstance(a, dict) for a in assets)
            or {a.get("id") for a in assets} != {"android-aar", "pocket", "kokoro", "supertonic-3"}):
        raise PinError("manifest must contain exactly the four required assets")
    filenames: set[str] = set()
    for asset in assets:
        missing = REQUIRED_ASSET_FIELDS - asset.keys()
        if missing:
            raise PinError(f"{asset.get('id', '<asset>')} missing {sorted(missing)}")
        if asset["filename"] in filenames or Path(asset["filename"]).name != asset["filename"]:
            raise PinError("asset filenames must be unique basenames")
        filenames.add(asset["filename"])
        if (not _valid_https_url(asset["url"]) or isinstance(asset["bytes"], bool)
                or not isinstance(asset["bytes"], int) or asset["bytes"] <= 0
                or not _valid_hash(asset["sha256"])):
            raise PinError(f"invalid immutable pin for {asset['id']}")
        if (not isinstance(asset["release_tag"], str) or not asset["release_tag"]
                or not all(_valid_timestamp(asset[x]) for x in ("release_published_at", "asset_created_at", "asset_updated_at"))):
            raise PinError(f"missing release metadata for {asset['id']}")
        if (not isinstance(asset["allowed_top_level"], list) or not asset["allowed_top_level"]
                or any(not isinstance(x, str) or not x or PurePosixPath(x).name != x for x in asset["allowed_top_level"])):
            raise PinError(f"missing or unsafe layout pin for {asset['id']}")
        if (not isinstance(asset["licenses"], list) or not asset["licenses"]
                or any(not isinstance(x, dict) or not x.get("spdx") or not x.get("source") for x in asset["licenses"])):
            raise PinError(f"missing license provenance for {asset['id']}")
        provenance = asset["conversion_provenance"]
        if not isinstance(provenance, dict) or any(not provenance.get(x) for x in ("type", "repository", "revision", "document")):
            raise PinError(f"missing conversion/build provenance for {asset['id']}")
    runtime = data.get("host_runtime", {})
    if not isinstance(runtime, dict) or runtime.get("purpose") != "configuration smoke tests only; timings are not Android evidence":
        raise PinError("host/runtime evidence boundary is missing")
    source = runtime.get("source", {})
    if (not isinstance(source, dict) or source.get("commit") != sherpa["commit"]
            or source.get("tag") != sherpa["tag"] or source.get("repository") != sherpa.get("source_url")):
        raise PinError("host source provenance drift")
    if runtime.get("platform") != {"system": "Linux", "distribution": "Ubuntu 22.04", "machine": "x86_64", "libc": "glibc 2.35", "python": "CPython 3.11.9", "abi": "cp311"}:
        raise PinError("host platform/toolchain is not exact")
    installer = runtime.get("installer", {})
    if (not isinstance(installer, dict) or installer.get("name") != "pip"
            or installer.get("version") != "24.0" or not installer.get("command")):
        raise PinError("host installer provenance is incomplete")
    if runtime.get("runtime_versions") != {"sherpa-onnx": "1.13.5", "sherpa-onnx-core": "1.13.5"}:
        raise PinError("host package versions are not exact")
    wheels = runtime.get("wheels")
    if (not isinstance(wheels, list) or len(wheels) != 2
            or any(not isinstance(w, dict) for w in wheels)
            or {w.get("distribution") for w in wheels} != {"sherpa-onnx", "sherpa-onnx-core"}):
        raise PinError("both host wheels must be pinned exactly once")
    wheel_filenames: set[str] = set()
    for wheel in wheels:
        if (set(("filename", "url", "uploaded_at", "bytes", "sha256")) - wheel.keys()
                or Path(wheel["filename"]).name != wheel["filename"]
                or wheel["filename"] in wheel_filenames or not wheel["filename"].endswith(".whl")
                or not _valid_https_url(wheel["url"]) or not _valid_timestamp(wheel["uploaded_at"])
                or isinstance(wheel["bytes"], bool) or not isinstance(wheel["bytes"], int) or wheel["bytes"] <= 0
                or not _valid_hash(wheel["sha256"])):
            raise PinError("incomplete host wheel provenance")
        wheel_filenames.add(wheel["filename"])


def find_asset(manifest: dict[str, Any], asset_id: str) -> dict[str, Any]:
    matches = [a for a in manifest["assets"] if a["id"] == asset_id]
    if len(matches) != 1:
        raise PinError(f"unknown asset id: {asset_id}")
    return matches[0]


def verify_file(path: Path, pin: dict[str, Any]) -> None:
    if not path.is_file() or path.is_symlink():
        raise PinError(f"not a regular file: {path}")
    actual_size = path.stat().st_size
    if actual_size != pin["bytes"]:
        raise PinError(f"size mismatch for {path.name}: {actual_size} != {pin['bytes']}")
    actual_hash = sha256_file(path)
    if actual_hash != pin["sha256"]:
        raise PinError(f"SHA-256 mismatch for {path.name}: {actual_hash}")


def download(pin: dict[str, Any], destination: Path) -> Path:
    """Download to a temporary file, verify, then atomically publish it."""
    if destination.name != pin["filename"]:
        raise PinError("download destination filename differs from pin")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as output, urllib.request.urlopen(pin["url"], timeout=60) as response:
            if not response.geturl().startswith("https://"):
                raise PinError("download redirected away from HTTPS")
            declared = response.headers.get("Content-Length")
            try:
                declared_bytes = int(declared) if declared is not None else None
            except ValueError as exc:
                raise PinError("server returned malformed Content-Length") from exc
            if declared_bytes is not None and declared_bytes != pin["bytes"]:
                raise PinError("server Content-Length differs from pin")
            count = 0
            while block := response.read(CHUNK):
                count += len(block)
                if count > pin["bytes"]:
                    raise PinError("download exceeds pinned size")
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        temporary = Path(temporary_name)
        verify_file(temporary, pin)
        os.replace(temporary, destination)
        return destination
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def verify_release_metadata(pin: dict[str, Any], release: dict[str, Any]) -> None:
    """Verify a GitHub release API response without trusting mutable asset names alone."""
    if release.get("tag_name") != pin["release_tag"] or release.get("published_at") != pin["release_published_at"]:
        raise PinError("release tag/timestamp drift")
    release_assets = release.get("assets")
    if not isinstance(release_assets, list) or any(not isinstance(a, dict) for a in release_assets):
        raise PinError("release assets metadata is malformed")
    matches = [a for a in release_assets if a.get("name") == pin["filename"]]
    if len(matches) != 1:
        raise PinError("release asset missing or duplicated")
    asset = matches[0]
    expected = {"size": pin["bytes"], "created_at": pin["asset_created_at"], "updated_at": pin["asset_updated_at"], "browser_download_url": pin["url"]}
    if any(asset.get(key) != value for key, value in expected.items()):
        raise PinError("release asset metadata drift")
    digest = asset.get("digest")
    if digest is not None and digest != f"sha256:{pin['sha256']}":
        raise PinError("release-reported digest drift")


def _safe_member_name(raw: str, allowed_roots: set[str]) -> PurePosixPath:
    if not raw or "\\" in raw or "\x00" in raw:
        raise PinError("empty, NUL, or ambiguous archive path")
    path = PurePosixPath(raw)
    parts = path.parts
    if (path.is_absolute() or not parts or raw != path.as_posix()
            or any(part in ("", ".", "..") for part in parts)):
        raise PinError(f"unsafe or non-canonical archive path: {raw!r}")
    if parts[0] not in allowed_roots:
        raise PinError(f"unexpected top-level archive layout: {parts[0]!r}")
    return path


def _validate_entries(entries: Iterable[tuple[str, str, int]], allowed: set[str]) -> list[tuple[PurePosixPath, str, int]]:
    result: list[tuple[PurePosixPath, str, int]] = []
    seen: set[str] = set()
    total = 0
    for raw, kind, size in entries:
        path = _safe_member_name(raw.rstrip("/"), allowed)
        key = path.as_posix()
        if key in seen:
            raise PinError(f"duplicate archive path: {key}")
        seen.add(key)
        if kind not in ("file", "dir") or size < 0:
            raise PinError(f"links or special archive entries are forbidden: {key}")
        total += size
        if len(seen) > MAX_MEMBERS or total > MAX_EXTRACTED_BYTES:
            raise PinError("archive exceeds extraction limits")
        result.append((path, kind, size))
    return result


def safe_extract(archive: Path, destination: Path, pin: dict[str, Any]) -> None:
    """Verify and extract tar/zip without links, traversal, duplicates, or layout drift."""
    verify_file(archive, pin)
    if destination.exists() and any(destination.iterdir()):
        raise PinError("extraction destination must be absent or empty")
    allowed = set(pin["allowed_top_level"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent.is_symlink() or not destination.parent.is_dir():
        raise PinError("extraction parent must be a real directory")
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as source:
                raw_entries = []
                for item in source.infolist():
                    mode = item.external_attr >> 16
                    file_type = stat.S_IFMT(mode) if item.create_system == 3 else 0
                    if file_type == stat.S_IFLNK:
                        kind = "link"
                    elif file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                        kind = "special"
                    else:
                        kind = "dir" if item.is_dir() else "file"
                    raw_entries.append((item.filename, kind, item.file_size))
                entries = _validate_entries(raw_entries, allowed)
                for (path, kind, _), item in zip(entries, source.infolist()):
                    target = staging.joinpath(*path.parts)
                    if kind == "dir": target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with source.open(item) as inp, target.open("xb") as out: shutil.copyfileobj(inp, out, CHUNK)
        else:
            with tarfile.open(archive, mode="r:*") as source:
                members = source.getmembers()
                entries = _validate_entries([(m.name, "file" if m.isfile() else "dir" if m.isdir() else "special", m.size) for m in members], allowed)
                for (path, kind, _), member in zip(entries, members):
                    target = staging.joinpath(*path.parts)
                    if kind == "dir": target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        inp = source.extractfile(member)
                        if inp is None: raise PinError(f"cannot read archive member: {path}")
                        with inp, target.open("xb") as out: shutil.copyfileobj(inp, out, CHUNK)
        if destination.exists(): destination.rmdir()
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def inventory(root: Path) -> dict[str, Any]:
    if not root.is_dir() or root.is_symlink():
        raise PinError("inventory root must be a real directory")
    files = []
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix().encode()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink(): raise PinError(f"inventory contains symlink: {relative}")
        if path.is_file(): files.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        elif not path.is_dir(): raise PinError(f"inventory contains special file: {relative}")
    return {"schema_version": 1, "root": root.name, "files": files, "total_bytes": sum(x["bytes"] for x in files)}


def verify_host_runtime(wheel_directory: Path, manifest: dict[str, Any], *, system: str | None = None, machine: str | None = None, python_version: tuple[int, int, int] | None = None) -> None:
    validate_manifest(manifest)
    runtime = manifest["host_runtime"]
    system = system or platform.system()
    machine = machine or platform.machine()
    python_version = python_version or sys.version_info[:3]
    if (system, machine, python_version) != ("Linux", "x86_64", (3, 11, 9)):
        raise PinError("host platform is outside the pinned runtime")
    if not wheel_directory.is_dir() or wheel_directory.is_symlink():
        raise PinError("host wheel directory must be a real directory")
    expected = {w["filename"] for w in runtime["wheels"]}
    entries = list(wheel_directory.iterdir())
    if any(not p.is_file() or p.is_symlink() for p in entries):
        raise PinError("host wheel directory contains non-regular entries")
    actual = {p.name for p in entries}
    if actual != expected:
        raise PinError("host wheel set is missing, extra, or unpinned")
    for wheel in runtime["wheels"]: verify_file(wheel_directory / wheel["filename"], wheel)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify"); verify.add_argument("asset_id"); verify.add_argument("path", type=Path)
    fetch = sub.add_parser("download"); fetch.add_argument("asset_id"); fetch.add_argument("directory", type=Path)
    extract = sub.add_parser("extract"); extract.add_argument("asset_id"); extract.add_argument("archive", type=Path); extract.add_argument("destination", type=Path)
    inv = sub.add_parser("inventory"); inv.add_argument("root", type=Path); inv.add_argument("--output", type=Path)
    host = sub.add_parser("verify-host-runtime"); host.add_argument("wheel_directory", type=Path)
    args = parser.parse_args(); manifest = load_manifest(args.manifest)
    if args.command == "verify": verify_file(args.path, find_asset(manifest, args.asset_id))
    elif args.command == "download":
        pin = find_asset(manifest, args.asset_id); download(pin, args.directory / pin["filename"])
    elif args.command == "extract": safe_extract(args.archive, args.destination, find_asset(manifest, args.asset_id))
    elif args.command == "inventory":
        text = json.dumps(inventory(args.root), indent=2, sort_keys=True) + "\n"
        args.output.write_text(text, encoding="utf-8") if args.output else print(text, end="")
    elif args.command == "verify-host-runtime": verify_host_runtime(args.wheel_directory, manifest)
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except PinError as exc:
        print(f"pinning error: {exc}", file=sys.stderr); raise SystemExit(2)
