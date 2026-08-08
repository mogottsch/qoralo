#!/usr/bin/env python3
"""Export one fixed-shape FP32 diffusion-head CFG prediction to ExecuTorch."""

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

from diffusion_head import DiffusionHeadStep, load_prediction_head
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
        default=root / "artifacts/0002/lane-b/diffusion-head/fixture.pt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "artifacts/0002/lane-b/diffusion-head/diffusion-step-xnnpack.pte",
    )
    parser.add_argument("--backend", choices=("portable", "xnnpack"), default="xnnpack")
    parser.add_argument("--cfg-scale", type=float, default=1.3)
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


def validated_inputs(fixture: dict[str, torch.Tensor]) -> tuple[torch.Tensor, ...]:
    names_and_shapes = (
        ("noisy_latent", (1, 64)),
        ("timestep", (1,)),
        ("positive_condition", (1, 1536)),
        ("negative_condition", (1, 1536)),
    )
    values: list[torch.Tensor] = []
    for name, shape in names_and_shapes:
        value = fixture[name].to(dtype=torch.float32).contiguous()
        if tuple(value.shape) != shape:
            raise SystemExit(f"Expected {name} shape {shape}, got {tuple(value.shape)}")
        values.append(value)
    return tuple(values)


def main() -> None:
    started = time.perf_counter()
    args = parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    try:
        from executorch.exir import EdgeCompileConfig, to_edge, to_edge_transform_and_lower
    except ImportError as error:
        raise SystemExit(f"ExecuTorch is unavailable: {error}") from error

    fixture = torch.load(args.fixture, map_location="cpu", weights_only=True)
    inputs = validated_inputs(fixture)
    head = load_prediction_head(args.model.resolve(), dtype=torch.float32)
    wrapper = DiffusionHeadStep(head, cfg_scale=args.cfg_scale).eval()
    with torch.no_grad():
        reference = wrapper(*inputs)
    fixture_difference = (reference - fixture["guided_prediction"]).abs()
    torch.testing.assert_close(
        reference, fixture["guided_prediction"], atol=1e-5, rtol=1e-4
    )

    exported = torch.export.export(wrapper, inputs, strict=True)
    noncontiguous = [
        name
        for values in (exported.state_dict, exported.constants)
        for name, value in values.items()
        if isinstance(value, torch.Tensor) and not value.is_contiguous()
    ]
    if noncontiguous:
        raise SystemExit(f"Exported program has non-contiguous constants: {noncontiguous}")

    compile_config = EdgeCompileConfig(_skip_dim_order=False)
    if args.backend == "xnnpack":
        from executorch.backends.xnnpack.partition.xnnpack_partitioner import (
            XnnpackPartitioner,
        )

        edge = to_edge_transform_and_lower(
            exported,
            partitioner=[XnnpackPartitioner()],
            compile_config=compile_config,
        )
    else:
        edge = to_edge(exported, compile_config=compile_config)
    program = edge.to_executorch()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as handle:
        program.write_to_file(handle)
    reference_path = args.output.with_suffix(".reference.pt")
    torch.save({"inputs": inputs, "output": reference}, reference_path)
    metadata = {
        "schema_version": 1,
        "component": "diffusion_head_cfg_prediction",
        "backend": args.backend,
        "precision": "fp32",
        "cfg_scale": args.cfg_scale,
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": package_version("executorch"),
        },
        "abi_order": [
            "noisy_latent",
            "timestep",
            "positive_condition",
            "negative_condition",
        ],
        "inputs": [tensor_metadata(value) for value in inputs],
        "reference_output": tensor_metadata(reference),
        "fixture_max_abs_error": fixture_difference.max().item(),
        "fixture_mean_abs_error": fixture_difference.float().mean().item(),
        "exported_noncontiguous_constants": noncontiguous,
        "pte": {
            "path": str(args.output),
            "bytes": args.output.stat().st_size,
            "sha256": file_sha256(args.output),
        },
        "export": {
            "wall_seconds": time.perf_counter() - started,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "scope": {
            "included": "prediction head plus classifier-free guidance combine",
            "excluded": "DPM scheduler update and ten-step loop",
        },
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
