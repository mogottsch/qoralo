#!/usr/bin/env python3
"""Export the fixed-shape FP32 acoustic/semantic connector join."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import resource
import sys
import time
from pathlib import Path

import torch

from fixture_utils import repo_root, tensor_metadata
from speech_connectors import SpeechConnectorJoin, load_speech_connectors

ABI = (
    ("acoustic_features", (1, 1, 64), torch.float32),
    ("semantic_features", (1, 1, 128), torch.float32),
)


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


def validated_inputs(fixture: dict[str, torch.Tensor], order: tuple[str, ...] | None = None) -> tuple[torch.Tensor, ...]:
    """Reject malformed or reordered connector inputs instead of silently coercing them."""
    actual_order = order or tuple(name for name, _, _ in ABI)
    expected_order = tuple(name for name, _, _ in ABI)
    if actual_order != expected_order:
        raise ValueError(f"Expected connector input order {expected_order}, got {actual_order}")
    values: list[torch.Tensor] = []
    for name, shape, dtype in ABI:
        if name not in fixture:
            raise ValueError(f"Missing connector input {name}")
        value = fixture[name]
        if tuple(value.shape) != shape:
            raise ValueError(f"Expected {name} shape {shape}, got {tuple(value.shape)}")
        if value.dtype != dtype:
            raise ValueError(f"Expected {name} dtype {dtype}, got {value.dtype}")
        if not value.is_contiguous():
            raise ValueError(f"Expected {name} to be contiguous")
        if not torch.isfinite(value).all():
            raise ValueError(f"Expected finite {name}")
        values.append(value)
    return tuple(values)


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=root / "artifacts/models/microsoft-VibeVoice-1.5B")
    parser.add_argument("--fixture", type=Path, default=root / "artifacts/0002/lane-b/connectors/capture-1/fixture.pt")
    parser.add_argument("--output", type=Path, default=root / "artifacts/0002/lane-b/connectors/connectors-xnnpack.pte")
    parser.add_argument("--backend", choices=("portable", "xnnpack"), default="xnnpack")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    try:
        from executorch.exir import EdgeCompileConfig, to_edge, to_edge_transform_and_lower
    except ImportError as error:
        raise SystemExit(f"ExecuTorch is unavailable: {error}") from error
    fixture = torch.load(args.fixture, map_location="cpu", weights_only=True)
    try:
        inputs = validated_inputs(fixture)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    acoustic, semantic = load_speech_connectors(args.model.resolve(), dtype=torch.float32)
    module = SpeechConnectorJoin(acoustic, semantic).eval()
    with torch.no_grad():
        eager = module(*inputs)
    if not torch.isfinite(eager).all():
        raise SystemExit("Eager connector output is non-finite")
    torch.testing.assert_close(eager, fixture["joined_output"], atol=1e-5, rtol=1e-4)

    exported = torch.export.export(module, inputs, strict=True)
    with torch.no_grad():
        exported_output = exported.module()(*inputs)
    torch.testing.assert_close(exported_output, eager, atol=1e-5, rtol=1e-4)
    compile_config = EdgeCompileConfig(_skip_dim_order=False)
    if args.backend == "xnnpack":
        from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
        edge = to_edge_transform_and_lower(exported, partitioner=[XnnpackPartitioner()], compile_config=compile_config)
    else:
        edge = to_edge(exported, compile_config=compile_config)
    delegate_segments = sum(
        1
        for _, child in edge.exported_program().graph_module.named_modules()
        if getattr(child, "original_module", None) is not None
    )
    if args.backend == "xnnpack" and delegate_segments == 0:
        raise SystemExit("XNNPACK was requested but no delegate segment was produced")
    program = edge.to_executorch()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as handle:
        program.write_to_file(handle)
    torch.save({"inputs": inputs, "output": eager}, args.output.with_suffix(".reference.pt"))
    metadata = {
        "schema_version": 1, "component": "speech_connector_join", "backend": args.backend, "precision": "fp32",
        "versions": {"python": sys.version.split()[0], "torch": torch.__version__, "executorch": package_version("executorch")},
        "abi_order": [name for name, _, _ in ABI], "inputs": [tensor_metadata(value) for value in inputs],
        "output": tensor_metadata(eager),
        "eager_vs_capture_max_abs_error": (eager - fixture["joined_output"]).abs().max().item(),
        "exported_vs_eager_max_abs_error": (exported_output - eager).abs().max().item(),
        "delegation": {"requested_backend": args.backend, "partitioner": "XnnpackPartitioner" if args.backend == "xnnpack" else None, "delegate_segments": delegate_segments},
        "pte": {"path": str(args.output), "bytes": args.output.stat().st_size, "sha256": file_sha256(args.output)},
        "export": {"wall_seconds": time.perf_counter() - started, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
