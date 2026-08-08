#!/usr/bin/env python3
"""Host-validate real Qwen2 PTEs, chaining prefill caches into decode."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import resource
import time
from pathlib import Path
from typing import Any

import torch
from qwen2_backbone import cache_tensor_names
from validate_qwen2_fixtures import expected_outputs, wrapper_inputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefill_pte", type=Path)
    parser.add_argument("--decode-pte", type=Path)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--rtol", type=float, default=1e-4)
    return parser.parse_args()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def execute(
    runtime: Any, pte: Path, inputs: tuple[torch.Tensor, ...]
) -> tuple[tuple[torch.Tensor, ...], dict[str, float]]:
    started = time.perf_counter()
    program = runtime.load_program(str(pte))
    load_seconds = time.perf_counter() - started
    method = program.load_method("forward")
    started = time.perf_counter()
    outputs = tuple(method.execute(tuple(value.contiguous() for value in inputs)))
    return outputs, {
        "load_seconds": load_seconds,
        "inference_seconds": time.perf_counter() - started,
    }


def compare_outputs(
    actual: tuple[torch.Tensor, ...],
    expected: tuple[torch.Tensor, ...],
    atol: float,
    rtol: float,
) -> dict[str, Any]:
    if len(actual) != len(expected):
        raise RuntimeError(f"Expected {len(expected)} outputs, got {len(actual)}")
    names = ["last_hidden_state", "next_token_logits", *cache_tensor_names(28)]
    details: list[dict[str, Any]] = []
    total_error = 0.0
    total_values = 0
    total_mismatches = 0
    maximum = 0.0
    for name, actual_tensor, expected_tensor in zip(names, actual, expected):
        difference = (actual_tensor - expected_tensor).abs().float()
        mismatch_count = torch.count_nonzero(
            ~torch.isclose(actual_tensor, expected_tensor, atol=atol, rtol=rtol)
        ).item()
        details.append(
            {
                "name": name,
                "max_abs_error": difference.max().item(),
                "mean_abs_error": difference.mean().item(),
                "mismatch_count": mismatch_count,
                "numel": difference.numel(),
                "finite": bool(torch.isfinite(actual_tensor).all()),
            }
        )
        maximum = max(maximum, difference.max().item())
        total_error += difference.sum().item()
        total_values += difference.numel()
        total_mismatches += mismatch_count
    return {
        "outputs": len(actual),
        "max_abs_error": maximum,
        "mean_abs_error": total_error / total_values,
        "mismatch_count": total_mismatches,
        "all_finite": all(item["finite"] for item in details),
        "allclose": total_mismatches == 0,
        "atol": atol,
        "rtol": rtol,
        "output_details": details,
    }


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    result: dict[str, Any] = {
        "schema_version": 1,
        "component": "qwen2_real_prefill_decode",
        "backend": "xnnpack",
        "precision": "fp32",
        "status": "failed",
        "versions": {
            "torch": torch.__version__,
            "executorch": package_version("executorch"),
        },
    }
    exit_code = 1
    try:
        from executorch.runtime import Runtime

        prefill_fixture = torch.load(
            args.fixture_dir / "prefill.pt", map_location="cpu", weights_only=True
        )
        decode_fixture = torch.load(
            args.fixture_dir / "decode.pt", map_location="cpu", weights_only=True
        )
        runtime = Runtime.get()
        prefill_outputs, timing = execute(
            runtime, args.prefill_pte, wrapper_inputs(prefill_fixture, False)
        )
        result["prefill"] = {
            **timing,
            **compare_outputs(
                prefill_outputs, expected_outputs(prefill_fixture), args.atol, args.rtol
            ),
        }
        if args.decode_pte:
            decode_inputs = wrapper_inputs(decode_fixture, False) + prefill_outputs[2:]
            decode_outputs, timing = execute(runtime, args.decode_pte, decode_inputs)
            result["decode"] = {
                **timing,
                **compare_outputs(
                    decode_outputs,
                    expected_outputs(decode_fixture),
                    args.atol,
                    args.rtol,
                ),
                "cache_source": "actual ExecuTorch prefill outputs",
            }
        else:
            result["decode"] = {"status": "not-run"}
        accepted = result["prefill"]["allclose"] and (
            not args.decode_pte or result["decode"]["allclose"]
        )
        result["status"] = "passed" if accepted else "failed"
        if not accepted:
            result["error"] = "Outputs do not satisfy the configured tolerance"
        exit_code = 0 if accepted else 2
    except Exception as error:
        result["error_type"] = type(error).__name__
        result["error"] = str(error)
    finally:
        result["wall_seconds"] = time.perf_counter() - started
        result["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
