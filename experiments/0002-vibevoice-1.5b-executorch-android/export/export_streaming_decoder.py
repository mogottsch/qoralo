#!/usr/bin/env python3
"""Export a tensor-only first or cached VibeVoice streaming decoder entry point."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from pathlib import Path

import torch

from acoustic_decoder import load_acoustic_decoder
from fixture_utils import repo_root, tensor_metadata
from streaming_decoder import (
    FunctionalStreamingDecoder,
    cache_module_names,
    fixture_inputs,
    fixture_outputs,
    replace_streaming_sconv1d,
)


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", choices=("first", "cached"), required=True)
    parser.add_argument(
        "--source", type=Path,
        default=root / "artifacts/source/microsoft-vibevoice",
    )
    parser.add_argument(
        "--model", type=Path,
        default=root / "artifacts/models/microsoft-VibeVoice-1.5B",
    )
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--backend", choices=("portable", "xnnpack"), default="xnnpack")
    parser.add_argument("--atol", type=float, default=2e-5)
    parser.add_argument("--rtol", type=float, default=1e-5)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def main() -> None:
    args = parse_args()
    root = repo_root(Path(__file__))
    cached = args.entry == "cached"
    fixture_path = args.fixture or (
        root / f"artifacts/0002/acoustic-decoder-fixtures/call_{1 if cached else 0:03d}.pt"
    )
    output = args.output or (
        root / f"artifacts/0002/acoustic-decoder-streaming-{args.entry}-xnnpack-1.2.pte"
    )
    sys.path.insert(0, str(args.source.resolve()))
    from executorch.exir import to_edge, to_edge_transform_and_lower

    fixture = torch.load(fixture_path, map_location="cpu", weights_only=True)
    cache_names = cache_module_names(fixture, "post_cache")
    inputs = fixture_inputs(fixture, cache_names, cached)
    expected = fixture_outputs(fixture, cache_names)
    decoder = load_acoustic_decoder(args.model.resolve(), dtype=torch.float32)
    replaced = replace_streaming_sconv1d(decoder)
    wrapper = FunctionalStreamingDecoder(decoder, cache_names, cached).eval()

    started = time.perf_counter()
    with torch.no_grad():
        eager = wrapper(*inputs)
    eager_seconds = time.perf_counter() - started
    eager_errors = [(actual - reference).abs() for actual, reference in zip(eager, expected)]
    if not all(
        torch.allclose(actual, reference, atol=args.atol, rtol=args.rtol)
        for actual, reference in zip(eager, expected)
    ):
        raise SystemExit("Functional eager output does not match the captured fixture")

    exported = torch.export.export(wrapper, inputs, strict=True)
    if args.backend == "xnnpack":
        from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
        # Multiple cache tensors branch out from internal activations. Per-op
        # mode avoids a cycle in the default maximal partitioner.
        edge = to_edge_transform_and_lower(
            exported, partitioner=[XnnpackPartitioner(per_op_mode=True)]
        )
    else:
        edge = to_edge(exported)
    program = edge.to_executorch()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        program.write_to_file(handle)
    reference_path = output.with_suffix(".reference.pt")
    torch.save(
        {
            "inputs": inputs,
            "outputs": expected,
            "cache_names": cache_names,
            "entry": args.entry,
        },
        reference_path,
    )
    metadata = {
        "schema_version": 1,
        "entry": args.entry,
        "backend": args.backend,
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": package_version("executorch"),
        },
        "interface": {
            "input_count": len(inputs),
            "output_count": len(expected),
            "cache_order": cache_names,
            "inputs": [tensor_metadata(value) for value in inputs],
            "outputs": [tensor_metadata(value) for value in expected],
        },
        "rewrite": {
            "replaced_sconv1d_modules": len(replaced),
            "modules": replaced,
        },
        "eager": {
            "seconds": eager_seconds,
            "pcm_max_abs_error": eager_errors[0].max().item(),
            "pcm_mean_abs_error": eager_errors[0].float().mean().item(),
            "cache_max_abs_error": max(error.max().item() for error in eager_errors[1:]),
            "cache_mean_abs_error_max": max(
                error.float().mean().item() for error in eager_errors[1:]
            ),
            "atol": args.atol,
            "rtol": args.rtol,
            "allclose": True,
        },
        "pte": {
            "path": str(output),
            "bytes": output.stat().st_size,
            "sha256": file_sha256(output),
        },
        "reference": str(reference_path),
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
