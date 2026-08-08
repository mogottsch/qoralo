#!/usr/bin/env python3
"""Export first and cached semantic audio encoder calls through XNNPACK."""

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
from semantic_encoder import (
    FunctionalSemanticEncoder,
    cache_shapes,
    load_semantic_encoder,
    semantic_cache_names,
    validate_call_inputs,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "artifacts/source/microsoft-vibevoice")
    parser.add_argument("--model", type=Path, default=root / "artifacts/models/microsoft-VibeVoice-1.5B")
    parser.add_argument("--fixture", type=Path, default=root / "artifacts/0002/lane-b/semantic-encoder/capture-1/fixture.pt")
    parser.add_argument("--output-dir", type=Path, default=root / "artifacts/0002/lane-b/semantic-encoder")
    parser.add_argument("--backend", choices=("portable", "xnnpack"), default="xnnpack")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    sys.path.insert(0, str(args.source.resolve()))
    from executorch.exir import EdgeCompileConfig, to_edge, to_edge_transform_and_lower

    fixture = torch.load(args.fixture, map_location="cpu", weights_only=True)
    encoder = load_semantic_encoder(args.model.resolve())
    names = semantic_cache_names(encoder)
    if tuple(fixture["cache_names"]) != names:
        raise SystemExit("Fixture cache order differs from encoder ABI")
    shapes = cache_shapes(encoder, names)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, object] = {
        "schema_version": 1,
        "component": "semantic_audio_encoder",
        "backend": args.backend,
        "precision": "fp32",
        "versions": {"python": sys.version.split()[0], "torch": torch.__version__, "executorch": importlib.metadata.version("executorch")},
        "cache_order": list(names),
        "cache_shapes": [list(shape) for shape in shapes],
        "entry_points": {},
    }
    previous_runtime_inputs: tuple[torch.Tensor, ...] | None = None
    for index, label in enumerate(("first", "cached")):
        call = fixture["calls"][index]
        if index == 0:
            inputs = validate_call_inputs(call["audio"], (), shapes, cached=False)
        else:
            # Export call two with the exact call-one post-cache capture.
            cache_inputs = tuple(fixture["calls"][0]["post_cache"][f"{name}/sample_0"].unsqueeze(0) for name in names)
            inputs = validate_call_inputs(call["audio"], cache_inputs, shapes, cached=True)
        module = FunctionalSemanticEncoder(encoder, names, cached=index == 1).eval()
        with torch.no_grad():
            eager = module(*inputs)
        expected = (call["features"], *(call["post_cache"][f"{name}/sample_0"].unsqueeze(0) for name in names))
        for actual, wanted in zip(eager, expected, strict=True):
            torch.testing.assert_close(actual, wanted, atol=1e-5, rtol=1e-4)
        exported = torch.export.export(module, inputs, strict=True)
        with torch.no_grad():
            exported_outputs = exported.module()(*inputs)
        for actual, wanted in zip(exported_outputs, eager, strict=True):
            torch.testing.assert_close(actual, wanted, atol=1e-5, rtol=1e-4)
        config = EdgeCompileConfig(_skip_dim_order=False)
        if args.backend == "xnnpack":
            from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
            edge = to_edge_transform_and_lower(exported, partitioner=[XnnpackPartitioner()], compile_config=config)
        else:
            edge = to_edge(exported, compile_config=config)
        delegate_segments = sum(1 for _, child in edge.exported_program().graph_module.named_modules() if getattr(child, "original_module", None) is not None)
        if args.backend == "xnnpack" and delegate_segments == 0:
            raise SystemExit(f"{label}: XNNPACK produced no delegate segment")
        path = args.output_dir / f"semantic-encoder-{label}-{args.backend}.pte"
        with path.open("wb") as handle:
            edge.to_executorch().write_to_file(handle)
        torch.save({"inputs": inputs, "outputs": eager}, path.with_suffix(".reference.pt"))
        metadata["entry_points"][label] = {
            "pte": {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)},
            "inputs": [tensor_metadata(value) for value in inputs],
            "outputs": [tensor_metadata(value) for value in eager],
            "delegate_segments": delegate_segments,
            "eager_vs_capture_max_abs_error": max((actual - wanted).abs().max().item() for actual, wanted in zip(eager, expected, strict=True)),
            "exported_vs_eager_max_abs_error": max((actual - wanted).abs().max().item() for actual, wanted in zip(exported_outputs, eager, strict=True)),
        }
        previous_runtime_inputs = eager
    metadata["chaining"] = {"cached_export_inputs_are_call_one_captured_outputs": previous_runtime_inputs is not None}
    metadata["export"] = {"wall_seconds": time.perf_counter() - started, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    output = args.output_dir / f"semantic-encoder-{args.backend}.json"
    output.write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
