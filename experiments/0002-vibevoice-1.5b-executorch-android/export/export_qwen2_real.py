#!/usr/bin/env python3
"""Export a real locked-checkpoint FP32 Qwen2 prefill or decode entry."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import resource
import time
from pathlib import Path
from typing import Any

import torch
from fixture_utils import repo_root
from qwen2_backbone import Qwen2Decode, Qwen2Prefill, cache_tensor_names
from qwen2_checkpoint import load_qwen2_backbone
from validate_qwen2_fixtures import compare_tuple, expected_outputs, wrapper_inputs

LAYERS = 28


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", choices=("prefill", "decode"), required=True)
    parser.add_argument(
        "--model",
        type=Path,
        default=root / "artifacts/models/microsoft-VibeVoice-1.5B",
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=root / "artifacts/0002/lane-c/qwen2-fixtures",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("portable", "xnnpack"), default="xnnpack")
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--rtol", type=float, default=1e-4)
    return parser.parse_args()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    result: dict[str, Any] = {
        "schema_version": 1,
        "component": f"qwen2_real_{args.entry}",
        "backend": args.backend,
        "precision": "fp32",
        "status": "failed",
        "cache_order": cache_tensor_names(LAYERS),
        "versions": {
            "torch": torch.__version__,
            "executorch": package_version("executorch"),
            "transformers": package_version("transformers"),
        },
    }
    result_path = args.output.with_suffix(".export.json")
    try:
        try:
            from executorch.exir import (
                EdgeCompileConfig,
                to_edge,
                to_edge_transform_and_lower,
            )
        except ImportError as error:
            raise RuntimeError(f"ExecuTorch is unavailable: {error}") from error

        fixture = torch.load(
            args.fixture_dir / f"{args.entry}.pt", map_location="cpu", weights_only=True
        )
        manifest = json.loads((args.fixture_dir / "manifest.json").read_text())
        backbone, lm_head = load_qwen2_backbone(args.model.resolve(), torch.float32)
        options = {
            "num_hidden_layers": LAYERS,
            "num_key_value_heads": 2,
            "head_dim": 128,
            "cache_capacity": manifest["cache_capacity"],
        }
        if args.entry == "prefill":
            wrapper = Qwen2Prefill(backbone, lm_head, **options).eval()
            inputs = wrapper_inputs(fixture, False)
        else:
            wrapper = Qwen2Decode(backbone, lm_head, **options).eval()
            inputs = wrapper_inputs(fixture, True)
        with torch.no_grad():
            eager = tuple(wrapper(*inputs))
        result["eager_fixture_agreement"] = compare_tuple(
            eager,
            expected_outputs(fixture),
            label=args.entry,
            atol=args.atol,
            rtol=args.rtol,
        )
        del eager

        phase_started = time.perf_counter()
        exported = torch.export.export(wrapper, inputs, strict=True)
        result["strict_export_seconds"] = time.perf_counter() - phase_started
        result["exported_graph_nodes"] = len(list(exported.graph.nodes))

        compile_config = EdgeCompileConfig(_skip_dim_order=False)
        phase_started = time.perf_counter()
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
        result["edge_lowering_seconds"] = time.perf_counter() - phase_started
        result["delegate_segments"] = sum(
            1
            for _, child in edge.exported_program().graph_module.named_modules()
            if getattr(child, "original_module", None) is not None
        )

        phase_started = time.perf_counter()
        program = edge.to_executorch()
        result["executorch_emit_seconds"] = time.perf_counter() - phase_started
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("wb") as handle:
            program.write_to_file(handle)
        result["pte"] = {
            "bytes": args.output.stat().st_size,
            "sha256": file_sha256(args.output),
        }
        result["status"] = "passed"
    except Exception as error:
        result["error_type"] = type(error).__name__
        result["error"] = str(error)
        raise
    finally:
        result["wall_seconds"] = time.perf_counter() - started
        result["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
