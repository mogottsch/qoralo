#!/usr/bin/env python3
"""Compare raw float tensors and optionally enforce a frozen numerical gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def parse_shape(text: str | None) -> list[int] | None:
    if text is None:
        return None
    try:
        shape = [int(part) for part in text.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid shape: {text}") from error
    if not shape or any(dimension <= 0 for dimension in shape):
        raise argparse.ArgumentTypeError("shape dimensions must be positive")
    return shape


def run(args: argparse.Namespace) -> int:
    reference_path = args.reference.resolve()
    candidate_path = args.candidate.resolve()
    reference = np.fromfile(reference_path, dtype="<f4")
    candidate = np.fromfile(candidate_path, dtype="<f4")
    if reference.shape != candidate.shape:
        raise SystemExit(
            f"element-count mismatch: reference={reference.size}, candidate={candidate.size}"
        )
    shape = parse_shape(args.shape)
    if shape is not None and math.prod(shape) != reference.size:
        raise SystemExit(
            f"declared shape {shape} has {math.prod(shape)} elements; file has {reference.size}"
        )

    reference64 = reference.astype(np.float64)
    candidate64 = candidate.astype(np.float64)
    delta = candidate64 - reference64
    reference_energy = float(np.dot(reference64, reference64))
    candidate_energy = float(np.dot(candidate64, candidate64))
    noise_energy = float(np.dot(delta, delta))
    denominator = math.sqrt(reference_energy * candidate_energy)
    finite = bool(np.all(np.isfinite(candidate)))
    metrics = {
        "finite": finite,
        "max_abs": float(np.max(np.abs(delta))) if delta.size else 0.0,
        "mean_abs": float(np.mean(np.abs(delta))) if delta.size else 0.0,
        "rmse": float(np.sqrt(np.mean(np.square(delta)))) if delta.size else 0.0,
        "cosine_similarity": (
            float(np.dot(reference64, candidate64)) / denominator
            if denominator
            else None
        ),
        "snr_db": (
            10.0 * math.log10(reference_energy / noise_energy)
            if noise_energy and reference_energy
            else (math.inf if reference_energy else None)
        ),
        "reference_rms": (
            float(np.sqrt(reference_energy / reference.size)) if reference.size else 0.0
        ),
        "candidate_rms": (
            float(np.sqrt(candidate_energy / candidate.size)) if candidate.size else 0.0
        ),
        "reference_peak_abs": (
            float(np.max(np.abs(reference64))) if reference.size else 0.0
        ),
        "candidate_peak_abs": (
            float(np.max(np.abs(candidate64))) if candidate.size else 0.0
        ),
    }

    checks: dict[str, bool] = {"finite": finite}
    if args.max_abs is not None:
        checks["max_abs"] = metrics["max_abs"] <= args.max_abs
    if args.max_mean_abs is not None:
        checks["mean_abs"] = metrics["mean_abs"] <= args.max_mean_abs
    if args.max_rmse is not None:
        checks["rmse"] = metrics["rmse"] <= args.max_rmse
    if args.min_cosine is not None:
        cosine = metrics["cosine_similarity"]
        checks["cosine_similarity"] = cosine is not None and cosine >= args.min_cosine
    if args.min_snr_db is not None:
        snr = metrics["snr_db"]
        checks["snr_db"] = snr is not None and snr >= args.min_snr_db

    gate_frozen = any(
        value is not None
        for value in (
            args.max_abs,
            args.max_mean_abs,
            args.max_rmse,
            args.min_cosine,
            args.min_snr_db,
        )
    )
    passed = bool(all(checks.values())) if gate_frozen else None
    report = {
        "schema_version": 1,
        "dtype": "float32-little-endian",
        "shape": shape or [int(reference.size)],
        "elements": int(reference.size),
        "reference": file_record(reference_path),
        "candidate": file_record(candidate_path),
        "metrics": metrics,
        "gate": {
            "thresholds_frozen": gate_frozen,
            "thresholds": {
                "max_abs": args.max_abs,
                "max_mean_abs": args.max_mean_abs,
                "max_rmse": args.max_rmse,
                "min_cosine": args.min_cosine,
                "min_snr_db": args.min_snr_db,
            },
            "checks": checks,
            "passed": passed,
        },
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if passed is not False else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--shape", help="comma-separated positive dimensions")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-abs", type=float)
    parser.add_argument("--max-mean-abs", type=float)
    parser.add_argument("--max-rmse", type=float)
    parser.add_argument("--min-cosine", type=float)
    parser.add_argument("--min-snr-db", type=float)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
