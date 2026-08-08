#!/usr/bin/env python3
"""Run ten PTE calls with the native-equivalent scheduler and save a loop fixture."""

from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path

import torch

from diffusion_scheduler import DpmSolverState, ten_step_schedule
from fixture_utils import tensor_metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pte", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--fixture-output", type=Path)
    parser.add_argument("--result-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reference_path = args.reference or args.pte.with_suffix(".reference.pt")
    fixture_output = args.fixture_output or args.pte.with_suffix(".loop-reference.pt")
    result_output = args.result_output or args.pte.with_suffix(".loop-host-result.json")

    from executorch.runtime import Runtime

    reference = torch.load(reference_path, map_location="cpu", weights_only=True)
    initial_latent, _, positive, negative = (
        value.float().contiguous() for value in reference["inputs"]
    )
    timesteps, sigmas = ten_step_schedule()
    scheduler = DpmSolverState(sigmas)

    load_started = time.perf_counter()
    program = Runtime.get().load_program(str(args.pte))
    method = program.load_method("forward")
    load_seconds = time.perf_counter() - load_started

    latent = initial_latent.clone()
    predictions: list[torch.Tensor] = []
    latents: list[torch.Tensor] = [latent.clone()]
    inference_seconds: list[float] = []
    loop_started = time.perf_counter()
    for timestep in timesteps:
        started = time.perf_counter()
        prediction = method.execute(
            (latent, timestep.reshape(1).float(), positive, negative)
        )[0].clone()
        inference_seconds.append(time.perf_counter() - started)
        predictions.append(prediction)
        latent = scheduler.step(prediction, latent)
        latents.append(latent.clone())
    loop_seconds = time.perf_counter() - loop_started

    fixture = {
        "initial_latent": initial_latent,
        "positive_condition": positive,
        "negative_condition": negative,
        "timesteps": timesteps,
        "sigmas": sigmas,
        "predictions": torch.stack(predictions),
        "latents": torch.stack(latents),
        "output": latent,
    }
    fixture_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(fixture, fixture_output)
    result = {
        "schema_version": 1,
        "status": "passed",
        "component": "ten_step_diffusion_loop",
        "orchestration": "host PTE calls plus native-equivalent FP32 DPM-Solver++ order-two midpoint scheduler",
        "pte": str(args.pte),
        "reference": str(reference_path),
        "fixture": str(fixture_output),
        "timesteps": timesteps.tolist(),
        "sigmas": sigmas.tolist(),
        "load_seconds": load_seconds,
        "head_inference_seconds": inference_seconds,
        "head_inference_total_seconds": sum(inference_seconds),
        "loop_seconds": loop_seconds,
        "output": tensor_metadata(latent),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    result_output.parent.mkdir(parents=True, exist_ok=True)
    result_output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
