#!/usr/bin/env python3
"""Host-execute and chain eight streaming decoder segment PTEs."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import resource
import sys
import time
from pathlib import Path

import torch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
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
    from executorch.runtime import Runtime

    chained_activation: torch.Tensor | None = None
    segment_results = []
    total_load = 0.0
    total_inference = 0.0
    final_reference: torch.Tensor | None = None
    for segment in range(8):
        pte = args.directory / f"segment-{segment}.pte"
        reference_path = pte.with_suffix(".reference.pt")
        reference = torch.load(reference_path, map_location="cpu", weights_only=True)
        inputs = list(reference["inputs"])
        if chained_activation is not None:
            inputs[0] = chained_activation
        started = time.perf_counter()
        program = Runtime.get().load_program(str(pte))
        load_seconds = time.perf_counter() - started
        method = program.load_method("forward")
        started = time.perf_counter()
        actual = tuple(method.execute(tuple(value.contiguous() for value in inputs)))
        inference_seconds = time.perf_counter() - started
        expected = tuple(reference["outputs"])
        errors = [(value - target).abs() for value, target in zip(actual, expected)]
        checks = [
            bool(torch.allclose(value, target, atol=args.atol, rtol=args.rtol))
            for value, target in zip(actual, expected)
        ]
        if not all(checks):
            raise SystemExit(f"Segment {segment} failed output comparison")
        chained_activation = actual[0]
        final_reference = expected[0]
        total_load += load_seconds
        total_inference += inference_seconds
        segment_results.append(
            {
                "segment": segment,
                "load_seconds": load_seconds,
                "inference_seconds": inference_seconds,
                "output_count": len(actual),
                "activation_shape": list(actual[0].shape),
                "activation_max_abs_error": errors[0].max().item(),
                "cache_max_abs_error": max(
                    (error.max().item() for error in errors[1:]), default=0.0
                ),
                "allclose": True,
            }
        )
        del method, program
    assert chained_activation is not None and final_reference is not None
    final_error = (chained_activation - final_reference).abs()
    result = {
        "schema_version": 1,
        "status": "passed",
        "directory": str(args.directory),
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": version("executorch"),
        },
        "segments": segment_results,
        "total_load_seconds": total_load,
        "total_inference_seconds": total_inference,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "final_pcm_shape": list(chained_activation.shape),
        "final_pcm_max_abs_error": final_error.max().item(),
        "final_pcm_mean_abs_error": final_error.float().mean().item(),
        "atol": args.atol,
        "rtol": args.rtol,
        "allclose": True,
    }
    output = args.output or args.directory / "host-result.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
