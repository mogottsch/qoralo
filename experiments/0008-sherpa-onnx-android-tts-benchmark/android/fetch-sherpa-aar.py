#!/usr/bin/env python3
"""Fetch the pinned arm64 sherpa-onnx runtime; never accept mutable bytes."""
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen

URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.5/sherpa-onnx-1.13.5.aar"
SIZE = 49_095_090
SHA256 = "6419cd8bc983e0c4fab06067f0fe0313fdc0f7103818ac1e7a08d50787b7a82b"
out = Path(__file__).parent / "libs" / "sherpa-onnx-1.13.5.aar"
if out.exists():
    data = out.read_bytes()
else:
    data = urlopen(URL, timeout=120).read()
if len(data) != SIZE or sha256(data).hexdigest() != SHA256:
    raise SystemExit("pinned sherpa AAR size/hash mismatch")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(data)
print(out)
