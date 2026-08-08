#!/usr/bin/env python3
"""Execute an ExecuTorch PTE on the host and compare it with its saved reference."""

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pte", type=Path)
    parser.add_argument(
        "--reference",
        type=Path,
        help="Defaults to PTE path with .reference.pt replacing .pte",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--rtol", type=float, default=1e-4)
    return parser.parse_args()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def main() -> None:
    args = parse_args()
    reference_path = args.reference or args.pte.with_suffix(".reference.pt")
    output_path = args.output or args.pte.with_suffix(".host-result.json")
    result: dict[str, Any] = {
        "schema_version": 1,
        "pte": str(args.pte),
        "reference": str(reference_path),
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": package_version("executorch"),
        },
        "status": "failed",
    }
    exit_code = 1
    try:
        from executorch.runtime import Runtime

        reference = torch.load(reference_path, map_location="cpu", weights_only=True)
        started = time.perf_counter()
        program = Runtime.get().load_program(str(args.pte))
        result["load_seconds"] = time.perf_counter() - started
        method = program.load_method("forward")
        started = time.perf_counter()
        output = method.execute((reference["input"].contiguous(),))[0]
        result["inference_seconds"] = time.perf_counter() - started
        difference = (output - reference["output"]).abs()
        result.update(
            {
                "status": "passed",
                "output": tensor_metadata(output),
                "max_abs_error": difference.max().item(),
                "mean_abs_error": difference.float().mean().item(),
                "atol": args.atol,
                "rtol": args.rtol,
                "allclose": bool(
                    torch.allclose(
                        output, reference["output"], atol=args.atol, rtol=args.rtol
                    )
                ),
            }
        )
        if result["allclose"]:
            exit_code = 0
        else:
            result["status"] = "failed"
            result["error"] = "Output does not satisfy the configured tolerance"
            exit_code = 2
    except Exception as error:  # The JSON failure record is the purpose of this CLI.
        result["error_type"] = type(error).__name__
        result["error"] = str(error)
    finally:
        result["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
