#!/usr/bin/env python3
"""Execute a streaming decoder PTE and compare PCM plus every cache tensor."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import resource
import sys
import time
from pathlib import Path

import torch

from fixture_utils import tensor_metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pte", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--atol", type=float, default=2e-5)
    parser.add_argument("--rtol", type=float, default=1e-5)
    return parser.parse_args()


def version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def main() -> None:
    args = parse_args()
    reference_path = args.reference or args.pte.with_suffix(".reference.pt")
    output_path = args.output or args.pte.with_suffix(".host-result.json")
    reference = torch.load(reference_path, map_location="cpu", weights_only=True)
    from executorch.runtime import Runtime

    started = time.perf_counter()
    program = Runtime.get().load_program(str(args.pte))
    load_seconds = time.perf_counter() - started
    method = program.load_method("forward")
    started = time.perf_counter()
    actual = tuple(method.execute(tuple(value.contiguous() for value in reference["inputs"])))
    inference_seconds = time.perf_counter() - started
    expected = tuple(reference["outputs"])
    if len(actual) != len(expected):
        raise SystemExit(f"Expected {len(expected)} outputs, got {len(actual)}")
    errors = [(value - target).abs() for value, target in zip(actual, expected)]
    checks = [
        bool(torch.allclose(value, target, atol=args.atol, rtol=args.rtol))
        for value, target in zip(actual, expected)
    ]
    cache_names = reference["cache_names"]
    result = {
        "schema_version": 1,
        "status": "passed" if all(checks) else "failed",
        "entry": reference["entry"],
        "pte": str(args.pte),
        "reference": str(reference_path),
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": version("executorch"),
        },
        "load_seconds": load_seconds,
        "inference_seconds": inference_seconds,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "output_count": len(actual),
        "pcm": {
            "metadata": tensor_metadata(actual[0]),
            "max_abs_error": errors[0].max().item(),
            "mean_abs_error": errors[0].float().mean().item(),
            "allclose": checks[0],
        },
        "cache": {
            "count": len(actual) - 1,
            "max_abs_error": max(error.max().item() for error in errors[1:]),
            "mean_abs_error_max": max(
                error.float().mean().item() for error in errors[1:]
            ),
            "allclose": all(checks[1:]),
            "failed_names": [
                name for name, passed in zip(cache_names, checks[1:]) if not passed
            ],
        },
        "atol": args.atol,
        "rtol": args.rtol,
    }
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
