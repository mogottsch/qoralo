#!/usr/bin/env python3
"""Compare original and rewritten vectors on real per-step and recursive CPU inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(reference: np.ndarray, candidate: np.ndarray) -> dict:
    delta = candidate.astype(np.float64) - reference.astype(np.float64)
    r = reference.astype(np.float64).reshape(-1)
    c = candidate.astype(np.float64).reshape(-1)
    return {
        "elements": int(r.size),
        "all_finite": bool(np.isfinite(candidate).all()),
        "max_abs_error": float(np.max(np.abs(delta))),
        "mae": float(np.mean(np.abs(delta))),
        "rmse": float(np.sqrt(np.mean(delta * delta))),
        "cosine": float(np.dot(r, c) / (np.linalg.norm(r) * np.linalg.norm(c))),
    }


def passes(value: dict, policy: dict) -> bool:
    return value["elements"] == policy["elements"] and value["all_finite"] == policy["all_finite"] and value["max_abs_error"] <= policy["max_abs_error_lte"] and value["rmse"] <= policy["rmse_lte"] and value["cosine"] >= policy["cosine_gte"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--original", type=Path, required=True)
    p.add_argument("--rewritten", type=Path, required=True)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    policy = json.loads(a.policy.read_text())["cpu_rewrite_equivalence"]
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    original = ort.InferenceSession(str(a.original), options, providers=["CPUExecutionProvider"])
    rewritten = ort.InferenceSession(str(a.rewritten), options, providers=["CPUExecutionProvider"])
    def load(name, shape, dtype=np.float32): return np.fromfile(a.inputs / f"{name}.raw", dtype=dtype).reshape(shape)
    shared = {"text_emb": load("text_emb", (1, 256, 239)), "style_ttl": load("style_ttl", (1, 50, 256)), "latent_mask": load("latent_mask", (1, 1, 238)), "text_mask": load("text_mask", (1, 1, 239)), "total_step": load("total_step", (1,))}
    initial = load("step0_noisy_latent", (1, 144, 238))
    real_input = initial.copy()
    candidate_recursive = initial.copy()
    per_step = []
    recursive = []
    for step in range(5):
        current = np.asarray([step], dtype=np.float32)
        original_feed = {"noisy_latent": real_input, "current_step": current, **shared}
        reference = np.asarray(original.run(None, original_feed)[0], dtype=np.float32)
        same_input_candidate = np.asarray(rewritten.run(None, original_feed)[0], dtype=np.float32)
        per = metrics(reference, same_input_candidate)
        per["step"] = step
        per["passed"] = passes(per, policy["each_real_step"])
        candidate_feed = {"noisy_latent": candidate_recursive, "current_step": current, **shared}
        candidate_recursive = np.asarray(rewritten.run(None, candidate_feed)[0], dtype=np.float32)
        rec = metrics(reference, candidate_recursive)
        rec["step"] = step
        rec["passed"] = passes(rec, policy["five_step_recursive_final"] if step == 4 else policy["each_real_step"])
        per_step.append(per)
        recursive.append(rec)
        real_input = reference
    report = {"schema_version": 1, "runtime": {"onnxruntime": ort.__version__, "provider": "CPUExecutionProvider", "graph_optimization": "ORT_ENABLE_ALL", "threads": 1}, "models": {"original_sha256": sha(a.original), "rewritten_sha256": sha(a.rewritten)}, "policy_sha256": sha(a.policy), "real_step_same_input": per_step, "recursive_chain": recursive, "passed": all(x["passed"] for x in per_step + recursive)}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
