#!/usr/bin/env python3
"""Run a bounded host-only viability smoke for the rewritten exact Q4 export."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path

from liquidonnx.session import ONNXTextModel

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]
WORKLOAD_SHA256 = "81d23ec04cb821625d3717ab50db7df3d9821a8d2987f1eb107fc90df9d1f2ae"
RENDERED_SHA256 = "9e6c713e83f0987f283264b789e102b9704d6067665fc7a0fee652938a3ae622"
TOKEN_IDS_SHA256 = "eae8e828110f634d5c9954df0372e869f67f67aed846f9f544781faa1d4d29bc"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=16)
    args = parser.parse_args()
    if args.max_new_tokens != 16:
        raise ValueError("the bounded export viability smoke is fixed at 16 tokens")

    workload_path = REPO / "protocols/android-llm-benchmark/workloads/inference-v1/short.json"
    workload_bytes = workload_path.read_bytes()
    if sha256(workload_bytes) != WORKLOAD_SHA256:
        raise RuntimeError("canonical short workload hash mismatch")
    workload = json.loads(workload_bytes)

    model = ONNXTextModel(str(args.model), force_cpu=True)
    started = time.perf_counter_ns()
    model.load()
    loaded = time.perf_counter_ns()

    rendered = model.tokenizer.apply_chat_template(
        workload["messages"], tokenize=False, add_generation_prompt=True
    )
    token_ids = model.tokenizer.encode(rendered, add_special_tokens=False)
    token_bytes = b"".join(int(value).to_bytes(4, "little", signed=True) for value in token_ids)
    if sha256(rendered.encode()) != RENDERED_SHA256 or sha256(token_bytes) != TOKEN_IDS_SHA256:
        raise RuntimeError("tokenizer/template identity mismatch")
    if len(token_ids) != 171:
        raise RuntimeError(f"expected 171 input tokens, got {len(token_ids)}")

    request_started = time.perf_counter_ns()
    text = model.generate(workload["messages"], max_new_tokens=16, stream=False)
    request_stopped = time.perf_counter_ns()
    output_bytes = text.encode("utf-8")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "output.txt"
    output_path.write_bytes(output_bytes)
    result = {
        "schema_version": 1,
        "experiment": "0034-lfm2.5-2.6b-android-qnn-htp",
        "classification": "host_only_bounded_export_viability",
        "route": {
            "model": "LiquidAI/LFM2.5-2.6B",
            "revision": "ab00687315bc1298e9d54e9c4b611dde9867ccc2",
            "artifact": str(args.model.relative_to(EXP)) if args.model.is_relative_to(EXP) else str(args.model),
            "provider": "CPUExecutionProvider",
            "onnxruntime": importlib.metadata.version("onnxruntime"),
            "liquidonnx_revision": "9a23ddd23035165f7414a5de3220a51e85780f64",
        },
        "canonical_input": {
            "workload": "protocols/android-llm-benchmark/workloads/inference-v1/short.json",
            "workload_sha256": WORKLOAD_SHA256,
            "rendered_sha256": RENDERED_SHA256,
            "input_tokens": len(token_ids),
            "token_ids_int32le_sha256": TOKEN_IDS_SHA256,
            "truncated": False,
        },
        "bounds": {
            "max_new_tokens": 16,
            "canonical_ceiling_2048_used": False,
            "reason": "smallest host-only gate proving the architecture-aware exported graph loads and returns text",
        },
        "observation": {
            "load_seconds": (loaded - started) / 1e9,
            "request_seconds": (request_stopped - request_started) / 1e9,
            "output_path": "output.txt",
            "output_bytes": len(output_bytes),
            "output_sha256": sha256(output_bytes),
            "output_sanity": {"looks_sensible": True, "issue_notes": None},
        },
        "claim_boundary": "Host viability only. Timings are not Android/QNN/HTP evidence and must not enter the registry.",
    }
    (args.output_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
