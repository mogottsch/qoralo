#!/usr/bin/env python3
"""Run calls 0-3 through the exported PTE using actual prior runtime outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch

from fixture_utils import repo_root
from four_call_abi import AtomicFourCallController, canonical_cache, load_contract, tensor_sha256


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pte", type=Path)
    parser.add_argument("--trace", type=Path, default=root / "artifacts/0002/recurrent-calls-0-19/capture-1")
    parser.add_argument("--abi", type=Path, default=root / "experiments/0002-vibevoice-1.5b-executorch-android/fixtures/four-call-cache-abi.json")
    parser.add_argument("--trace-manifest", type=Path, default=root / "experiments/0002-vibevoice-1.5b-executorch-android/fixtures/recurrent-calls-0-19-manifest.json")
    parser.add_argument("--output", type=Path, default=root / "experiments/0002-vibevoice-1.5b-executorch-android/results/four-call-host-validation.json")
    parser.add_argument("--listener-result", type=Path, help="JSON response to the frozen chunk-3 perceptual prompt")
    return parser.parse_args()


def boundary(actual: torch.Tensor, expected: torch.Tensor, atol: float, rtol: float) -> dict[str, object]:
    error = (actual.float() - expected.float()).abs()
    close = torch.isclose(actual.float(), expected.float(), atol=atol, rtol=rtol)
    return {"finite": bool(torch.isfinite(actual).all()), "max_abs_error": error.max().item(),
            "mean_abs_error": error.mean().item(), "mismatch_count": int(torch.count_nonzero(~close)),
            "atol": atol, "rtol": rtol, "passed": bool(torch.isfinite(actual).all() and close.all())}


def s16(value: torch.Tensor) -> np.ndarray:
    samples = np.clip(value.detach().cpu().numpy().reshape(-1), -1, 1)
    return np.round(samples * np.where(samples < 0, 32768, 32767)).astype(np.int16)


def prior_boundary_integrity(trace: dict[str, object], manifest_call: dict[str, object]) -> dict[str, object]:
    """Prove upstream inputs are the committed actual prior outputs, not substitutes."""
    paths = [
        ("qwen", "hidden"), ("qwen", "logits"),
        ("diffusion", "final_latent"), ("decoder", "input_latent"),
        ("connector", "acoustic"), ("connector", "semantic"),
        ("connector", "combined"),
    ]
    checked = []
    for path in paths:
        actual = trace[path[0]][path[1]]
        expected = manifest_call[path[0]][path[1]]["sha256"]
        digest = tensor_sha256(actual)
        checked.append({"boundary": ".".join(path), "sha256": digest, "passed": digest == expected})
    for name, actual in trace["qwen"]["post_cache"].items():
        digest = tensor_sha256(actual)
        checked.append({"boundary": f"qwen.post_cache.{name}", "sha256": digest,
                        "passed": digest == manifest_call["qwen"]["post_cache"][name]["sha256"]})
    for index, step in enumerate(trace["diffusion"]["steps"]):
        # Each captured prediction is a required diffusion boundary.
        actual = step["prediction"]
        digest = tensor_sha256(actual)
        checked.append({"boundary": f"diffusion.steps.{index}.prediction", "sha256": digest,
                        "passed": digest == manifest_call["diffusion"]["steps"][index]["prediction"]["sha256"]})
    token_ok = trace["selected_token"] == manifest_call["selected_token"]
    return {"selected_token": trace["selected_token"], "selected_token_exact": token_ok,
            "tensor_count": len(checked), "failed": [item["boundary"] for item in checked if not item["passed"]],
            "passed": token_ok and all(item["passed"] for item in checked), "boundaries": checked}


def perceptual(path: Path | None, protocol: dict[str, object]) -> dict[str, object]:
    if path is None:
        return {"status": "pending_user_review", "passed": False, "prompt": protocol["prompt"],
                "reason": "No human listener response was supplied; automation must not invent an audibility rating."}
    value = json.loads(path.read_text())
    exclusions = ("silence", "steady_tone", "broadband_noise", "click_only", "dropout")
    passed = value.get("listener_count", 0) >= protocol["listener_count_minimum"] and value.get("speech_like_voiced_onset") is True and all(value.get(item) is False for item in exclusions)
    return {**value, "status": "pass" if passed else "fail", "passed": passed, "prompt": protocol["prompt"]}


def main() -> int:
    args = parse_args()
    from executorch.runtime import Runtime
    contract = load_contract(args.abi)
    trace_manifest = json.loads(args.trace_manifest.read_text())
    program = Runtime.get().load_program(args.pte)
    if set(program.method_names) != {"acoustic_decode", "semantic_encode"}:
        raise SystemExit(f"wrong methods: {program.method_names}")
    decoder_runtime = program.load_method("acoustic_decode")
    semantic_runtime = program.load_method("semantic_encode")
    thresholds = contract["thresholds"]
    started = time.perf_counter()
    repeat_results = []
    repeat_hashes = []
    final_chunks: list[torch.Tensor] = []
    for repeat in range(2):
        controller = AtomicFourCallController(contract)
        calls = []
        hashes = []
        for index in range(4):
            trace = torch.load(args.trace / f"call_{index:03d}.pt", map_location="cpu", weights_only=True)
            upstream = prior_boundary_integrity(trace, trace_manifest["calls"][index])
            if not upstream["passed"]:
                raise ValueError(f"call {index}: prior runtime boundary integrity failed")
            pcm, semantic = controller.execute(
                trace["decoder"]["input_latent"].contiguous(),
                lambda *values: decoder_runtime.execute(tuple(values)),
                lambda *values: semantic_runtime.execute(tuple(values)),
            )
            pcm_cmp = boundary(pcm, trace["decoder"]["pcm"], **thresholds["fp32_boundaries"]["decoder_pcm_host"])
            semantic_cmp = boundary(semantic, trace["semantic"]["output"], **thresholds["fp32_boundaries"]["semantic_output"])
            decoder_cache = []
            semantic_cache = []
            for domain, state, target, output in (
                ("decoder", controller.decoder, trace["decoder"]["post_cache"], decoder_cache),
                ("semantic", controller.semantic, trace["semantic"]["post_cache"], semantic_cache),
            ):
                method = contract["methods"]["acoustic_decode" if domain == "decoder" else "semantic_encode"]
                tolerance = thresholds["fp32_boundaries"]["decoder_cache_host" if domain == "decoder" else "semantic_cache"]
                for actual, spec in zip(state.caches, method["caches"], strict=True):
                    expected = canonical_cache(target[spec["source_name"]], spec["capacity_shape"])
                    output.append(boundary(actual, expected, **tolerance))
            actual_s16, expected_s16 = s16(pcm), s16(trace["decoder"]["pcm"])
            maximum_s16 = int(np.max(np.abs(actual_s16.astype(np.int32) - expected_s16.astype(np.int32))))
            # The frozen dBFS references were measured on FP32 decoder output;
            # S16 conversion is a separate per-sample gate and quantizes calls
            # 0-1 to zero by design.
            float_samples = pcm.detach().cpu().numpy().astype(np.float64, copy=False)
            rms = float(np.sqrt(np.mean(np.square(float_samples))))
            dbfs = 20 * math.log10(rms) if rms else float("-inf")
            energy_ref = thresholds["chunk_energy_dbfs"]["reference_calls_0_3"][index]
            energy_pass = abs(dbfs - energy_ref) <= thresholds["chunk_energy_dbfs"]["comparison_tolerance_db"]
            passed = pcm_cmp["passed"] and semantic_cmp["passed"] and all(item["passed"] for item in decoder_cache + semantic_cache) and maximum_s16 <= 1 and energy_pass
            calls.append({"call": index, "upstream_input_provenance": "locked actual prior recurrent output",
                          "upstream_boundaries": upstream,
                          "decoder_pcm": pcm_cmp, "decoder_caches": decoder_cache,
                          "semantic_output": semantic_cmp, "semantic_caches": semantic_cache,
                          "pcm_s16": {"samples": len(actual_s16), "alignment_error_samples": 0, "maximum_absolute_difference_units": maximum_s16, "passed": maximum_s16 <= 1},
                          "energy": {"rms_dbfs": dbfs, "reference_dbfs": energy_ref, "difference_db": dbfs - energy_ref, "passed": energy_pass},
                          "peak_s16": int(np.max(np.abs(actual_s16.astype(np.int32)))), "passed": passed})
            hashes.extend([tensor_sha256(pcm), tensor_sha256(semantic), *(tensor_sha256(v) for v in controller.decoder.caches), *(tensor_sha256(v) for v in controller.semantic.caches)])
            if repeat == 0:
                final_chunks.append(pcm)
        repeat_results.append({"repeat": repeat, "calls": calls})
        repeat_hashes.append(hashes)
    deterministic = repeat_hashes[0] == repeat_hashes[1]
    chunk3 = repeat_results[0]["calls"][3]
    energy = thresholds["chunk_energy_dbfs"]
    chunk3_gate = chunk3["passed"] and energy["chunk_3_required_range_dbfs"][0] <= chunk3["energy"]["rms_dbfs"] <= energy["chunk_3_required_range_dbfs"][1] and energy["chunk_3_minimum_peak_s16"] <= chunk3["peak_s16"] <= energy["chunk_3_maximum_peak_s16"]
    listener = perceptual(args.listener_result, thresholds["perceptual_protocol"])
    numerical = deterministic and all(call["passed"] for call in repeat_results[0]["calls"]) and chunk3_gate
    accepted = numerical and listener["passed"]
    result = {"schema_version": 1, "status": "passed" if accepted else "rejected", "deployable": accepted,
              "pte": {"path": str(args.pte), "bytes": args.pte.stat().st_size, "sha256": hashlib.sha256(args.pte.read_bytes()).hexdigest()},
              "calls_use_actual_prior_runtime_outputs": True, "repeats": repeat_results,
              "deterministic_reset_four_call_repeat": deterministic,
              "chunk_3": {"numerical_and_energy_gate": chunk3_gate, "perceptual_protocol": listener},
              "acceptance": {"numerical": numerical, "perceptual": listener["passed"], "accepted": accepted,
                             "reason": None if accepted else "artifact deployment is prohibited until every numerical and protocol-defined perceptual gate passes"},
              "wall_seconds": time.perf_counter() - started, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
