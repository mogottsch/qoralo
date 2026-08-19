#!/usr/bin/env python3
"""Materialize and verify experiment 0013's fixed Kokoro graph inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

EXPECTED = {
    "frontend": (None, "680f5f1795a6427aaec31b1f20969c655fc5309dc2917fb22f9afb494bac3a4b"),
    "voice_f32": (522_240, "d583ccff3cdca2f7fae535cb998ac07e9fcb90f09737b9a41fa2734ec44a8f0b"),
    "transcript": (116, "bec8bf482f4d816f0c95471c289a2607a7a169e33389b8b13e525214ec639461"),
}
EXPECTED_TOKENS = "35ebb50fb1ba0cca3862c880cf0571c9a51623c5243a9f2307b4bb4a6dcd2078"
EXPECTED_STYLE = "b5c2627313e7e45bbb50470307ef66730b5510ebc7e92671cf7aad0449cdf899"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(path: Path, key: str) -> None:
    size, expected = EXPECTED[key]
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"not a regular {key} file: {path}")
    if size is not None and path.stat().st_size != size:
        raise RuntimeError(f"{key} size mismatch")
    actual = digest(path)
    if actual != expected:
        raise RuntimeError(f"{key} SHA-256 mismatch: expected {expected}, got {actual}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--voice-f32", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.frontend, "frontend")
    verify(args.voice_f32, "voice_f32")
    verify(args.transcript, "transcript")

    front = json.loads(args.frontend.read_text())
    if len(front["segments"]) != 1 or front["style_indices"] != [123]:
        raise RuntimeError("frontend contract drift")
    tokens = np.asarray(front["segments"][0], dtype="<i8").reshape(1, 125)
    voice = np.fromfile(args.voice_f32, dtype="<f4").reshape(510, 1, 256)
    style = np.ascontiguousarray(voice[123], dtype="<f4")
    speed = np.asarray([1.0], dtype="<f4")
    if hashlib.sha256(tokens.tobytes()).hexdigest() != EXPECTED_TOKENS:
        raise RuntimeError("token tensor hash drift")
    if hashlib.sha256(style.tobytes()).hexdigest() != EXPECTED_STYLE:
        raise RuntimeError("style tensor hash drift")

    args.output.mkdir(parents=True, exist_ok=True)
    tensors = {"tokens": tokens, "style": style, "speed": speed}
    records = {}
    for name, value in tensors.items():
        raw = args.output / f"{name}.raw"
        raw.write_bytes(value.tobytes())
        records[name] = {
            "path": raw.name,
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "bytes": raw.stat().st_size,
            "sha256": digest(raw),
        }
    np.savez(args.output / "inputs.npz", **tensors)
    manifest = {
        "schema_version": 1,
        "source_frontend_sha256": digest(args.frontend),
        "source_voice_f32_sha256": digest(args.voice_f32),
        "transcript_sha256": digest(args.transcript),
        "style_index": 123,
        "tensors": records,
    }
    path = args.output / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
