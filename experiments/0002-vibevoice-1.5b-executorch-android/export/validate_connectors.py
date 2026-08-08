#!/usr/bin/env python3
"""Validate a connector PTE against its eager reference on the host."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

import torch

from fixture_utils import tensor_metadata
from export_connectors import validated_inputs


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def compare_output(actual: torch.Tensor, expected: torch.Tensor, atol: float, rtol: float) -> dict[str, Any]:
    if actual.shape != expected.shape:
        raise ValueError(f"Output shape mismatch: {tuple(actual.shape)} != {tuple(expected.shape)}")
    if actual.dtype != torch.float32:
        raise ValueError(f"Expected runtime float32 output, got {actual.dtype}")
    finite = bool(torch.isfinite(actual).all())
    difference = (actual - expected).abs()
    close = torch.isclose(actual, expected, atol=atol, rtol=rtol)
    return {
        "output": tensor_metadata(actual), "finite": finite,
        "max_abs_error": difference.max().item(), "mean_abs_error": difference.float().mean().item(),
        "mismatch_count": int((~close).sum().item()), "atol": atol, "rtol": rtol,
        "allclose": bool(finite and close.all()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pte", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--rtol", type=float, default=1e-4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reference_path = args.reference or args.pte.with_suffix(".reference.pt")
    output_path = args.output or args.pte.with_suffix(".host-result.json")
    result: dict[str, Any] = {
        "schema_version": 1, "component": "speech_connector_join", "status": "failed",
        "backend": "xnnpack" if "xnnpack" in args.pte.name else "portable", "precision": "fp32",
        "pte": str(args.pte), "reference": str(reference_path),
        "versions": {"python": sys.version.split()[0], "torch": torch.__version__, "executorch": package_version("executorch")},
    }
    exit_code = 1
    try:
        from executorch.runtime import Runtime
        reference = torch.load(reference_path, map_location="cpu", weights_only=True)
        inputs = validated_inputs(dict(zip(("acoustic_features", "semantic_features"), reference["inputs"], strict=True)))
        started = time.perf_counter()
        program = Runtime.get().load_program(str(args.pte))
        result["load_seconds"] = time.perf_counter() - started
        method = program.load_method("forward")
        started = time.perf_counter()
        actual = method.execute(inputs)[0]
        result["inference_seconds"] = time.perf_counter() - started
        result["comparison"] = compare_output(actual, reference["output"], args.atol, args.rtol)
        if result["comparison"]["allclose"]:
            result["status"], exit_code = "passed", 0
        else:
            result["error"] = "Runtime output does not satisfy the documented FP32 threshold"
            exit_code = 2
    except Exception as error:
        result["error_type"], result["error"] = type(error).__name__, str(error)
    finally:
        result["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
