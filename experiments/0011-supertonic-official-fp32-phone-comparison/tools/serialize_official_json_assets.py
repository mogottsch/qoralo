#!/usr/bin/env python3
"""Serialize official JSON indexer/M1 tensors for the minimal C++ runner."""

import argparse
import json
import struct
from pathlib import Path


def flatten(value):
    if isinstance(value, list):
        for child in value:
            yield from flatten(child)
    else:
        yield value


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    indexer = json.loads((a.assets / "onnx/unicode_indexer.json").read_text())
    if len(indexer) != 65536 or not all(isinstance(x, int) for x in indexer):
        raise SystemExit("unexpected Unicode indexer contract")
    (a.output / "unicode_indexer.bin").write_bytes(struct.pack("<65536i", *indexer))
    voice = json.loads((a.assets / "voice_styles/M1.json").read_text())
    tensors = []
    for name, dims in (("style_ttl", [1, 50, 256]), ("style_dp", [1, 8, 16])):
        item = voice[name]
        values = list(flatten(item["data"]))
        count = 1
        for dim in dims:
            count *= dim
        if item["dims"] != dims or item["type"] != "float32" or len(values) != count:
            raise SystemExit(f"unexpected {name} contract")
        tensors.append(struct.pack(f"<{count}f", *values))
    # Six int64 dimensions followed by the two official M1 float tensors.
    (a.output / "voice.bin").write_bytes(struct.pack("<6q", 1, 50, 256, 1, 8, 16) + b"".join(tensors))


if __name__ == "__main__":
    main()
