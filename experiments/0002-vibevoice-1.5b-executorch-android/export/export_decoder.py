#!/usr/bin/env python3
"""Export the FP32 acoustic-decoder operator-coverage probe to ExecuTorch."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch

from acoustic_decoder import NonStreamingDecoderProbe, load_acoustic_decoder
from fixture_utils import repo_root, tensor_metadata


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=root / "artifacts/source/microsoft-vibevoice",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=root / "artifacts/models/microsoft-VibeVoice-1.5B",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=root / "artifacts/0002/acoustic-decoder-fixtures/call_000.pt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "artifacts/0002/acoustic-decoder-nonstreaming-xnnpack.pte",
    )
    parser.add_argument("--backend", choices=("portable", "xnnpack"), default="xnnpack")
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    try:
        from executorch.exir import to_edge, to_edge_transform_and_lower
    except ImportError as error:
        raise SystemExit(
            "ExecuTorch is not installed in this Python environment. Install the "
            "version paired with the Android AAR, then rerun this command. "
            f"Original error: {error}"
        ) from error

    fixture = torch.load(args.fixture, map_location="cpu", weights_only=True)
    latent = fixture["latent_b64t"].to(dtype=torch.float32).contiguous()
    if tuple(latent.shape) != (1, 64, 1):
        raise SystemExit(f"Expected fixed input shape [1,64,1], got {tuple(latent.shape)}")

    decoder = load_acoustic_decoder(args.model.resolve(), dtype=torch.float32)
    wrapper = NonStreamingDecoderProbe(decoder).eval()
    with torch.no_grad():
        reference = wrapper(latent)
    exported = torch.export.export(wrapper, (latent,), strict=True)

    if args.backend == "xnnpack":
        try:
            from executorch.backends.xnnpack.partition.xnnpack_partitioner import (
                XnnpackPartitioner,
            )
        except ImportError as error:
            raise SystemExit(f"ExecuTorch XNNPACK backend is unavailable: {error}") from error
        edge = to_edge_transform_and_lower(
            exported,
            partitioner=[XnnpackPartitioner()],
        )
    else:
        edge = to_edge(exported)
    program = edge.to_executorch()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as handle:
        program.write_to_file(handle)
    reference_path = args.output.with_suffix(".reference.pt")
    torch.save({"input": latent, "output": reference}, reference_path)
    metadata = {
        "schema_version": 1,
        "probe": "non_streaming_operator_coverage",
        "backend": args.backend,
        "input": tensor_metadata(latent),
        "reference_output": tensor_metadata(reference),
        "pte": {
            "path": str(args.output),
            "bytes": args.output.stat().st_size,
            "sha256": file_sha256(args.output),
        },
        "limitations": [
            "The probe does not reproduce streaming cache behavior.",
            "Its output must not be compared directly with call_000 streaming PCM.",
            "The final ABI must consume and return explicitly ordered cache tensors.",
        ],
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
