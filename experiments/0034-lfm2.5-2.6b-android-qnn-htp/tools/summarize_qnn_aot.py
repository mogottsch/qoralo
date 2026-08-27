#!/usr/bin/env python3
"""Validate and summarize fallback-disabled QNN AOT pipeline evidence."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path, *, outside_git: bool = True) -> dict[str, object]:
    return {"bytes": path.stat().st_size, "sha256": sha256(path), "retained_outside_git": outside_git}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-source", type=Path, required=True)
    parser.add_argument("--shard-data", type=Path, required=True)
    parser.add_argument("--parts-dir", type=Path, required=True)
    parser.add_argument("--aot-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    route = json.loads((args.parts_dir / "manifest.json").read_text())
    compile_summary = json.loads((args.aot_dir / "summary.json").read_text())
    if route["htp_part_count"] != 263 or compile_summary["part_count"] != 263:
        raise RuntimeError("expected 263 compiled HTP parts")
    if not compile_summary["all_parts_compiled"]:
        raise RuntimeError("AOT summary is incomplete")

    compiled_by_name = {item["name"]: item for item in compile_summary["parts"]}
    qnn_ops: collections.Counter[str] = collections.Counter()
    kinds: collections.Counter[str] = collections.Counter()
    retained_parts = []
    total_source_nodes = 0
    total_qnn_ops = 0
    total_context_bytes = 0
    for part in route["parts"]:
        name = part["name"]
        compiled = compiled_by_name[name]
        source_path = args.parts_dir / part["path"]
        context_model = args.aot_dir / name / compiled["context_model"]["path"]
        context_binary = args.aot_dir / name / compiled["context_binary"]["path"]
        trace_path = args.aot_dir / name / compiled["framework_op_trace"]["path"]
        for path, evidence in (
            (context_model, compiled["context_model"]),
            (context_binary, compiled["context_binary"]),
            (trace_path, compiled["framework_op_trace"]),
        ):
            if artifact(path)["sha256"] != evidence["sha256"] or path.stat().st_size != evidence["bytes"]:
                raise RuntimeError(f"compiled artifact mismatch: {path}")

        trace = json.loads(trace_path.read_text())
        target = trace["compilation_target"]
        summary = trace["summary"]
        if trace["backend_type"] != "htp" or target != {"device_id": 0, "htp_arch": "V73", "soc_model": 43}:
            raise RuntimeError(f"target mismatch for {name}")
        if trace["unsupported_nodes"] or summary["unsupported_nodes"] != 0:
            raise RuntimeError(f"unsupported source nodes in {name}")
        if summary["supported_nodes"] != summary["total_onnx_nodes"]:
            raise RuntimeError(f"incomplete QNN ownership in {name}")
        for subgraph in trace["subgraph_traces"]:
            for mapping in subgraph["op_mappings"]:
                qnn_ops[mapping["dst_qnn_op_type"]] += 1
        kinds[part["kind"]] += 1
        total_source_nodes += summary["total_onnx_nodes"]
        total_qnn_ops += summary["total_qnn_ops"]
        total_context_bytes += context_binary.stat().st_size
        retained_parts.append(
            {
                "name": name,
                "kind": part["kind"],
                "source_onnx": artifact(source_path),
                "source_nodes": summary["total_onnx_nodes"],
                "supported_nodes": summary["supported_nodes"],
                "unsupported_nodes": summary["unsupported_nodes"],
                "qnn_ops": summary["total_qnn_ops"],
                "context_model": artifact(context_model),
                "context_binary": artifact(context_binary),
                "framework_op_trace": artifact(trace_path),
            }
        )

    result = {
        "schema_version": 1,
        "experiment": "0034-lfm2.5-2.6b-android-qnn-htp",
        "classification": "fallback_disabled_sm8550_v73_host_aot_not_physical_execution",
        "route": {
            "model": "LiquidAI/LFM2.5-2.6B",
            "revision": "ab00687315bc1298e9d54e9c4b611dde9867ccc2",
            "quantization": "symmetric INT4 block-32 weights lowered by QNN EP block-quant optimization",
            "attention_capacity": 4096,
            "state": "22 explicit convolution caches plus 8 explicit attention K/V pairs",
            "pipeline_parts": len(retained_parts),
            "part_kind_counts": dict(sorted(kinds.items())),
            "explicit_cpu_operations": [
                "selected-row asymmetric Q4 token embedding dequantization",
                "global greedy argmax across HTP LM-head chunks",
                "tokenizer and request orchestration",
            ],
            "cpu_boundary_is_not_fallback": True,
        },
        "rewrites": {
            "rms_norm": "standard ONNX decomposition",
            "rotary_and_gqa": "standard one-token RoPE and causal grouped-query attention with explicit left-aligned cache state",
            "wide_mlp": "10,752 split as 6,144 + 4,608; second down-projection input/weights zero-padded to 6,144",
            "memory_bounded_pipeline": "30 layers split into core/norm, MLP projection/activation/down, and residual contexts",
            "lm_head": "128,000 logits split into 22 HTP chunks; CPU performs only global greedy reduction",
        },
        "source_derivatives": {
            "pipeline_source_onnx": artifact(args.pipeline_source),
            "wide_mlp_shard_data": artifact(args.shard_data),
            "parts_manifest": artifact(args.parts_dir / "manifest.json"),
        },
        "compiler": {
            "onnxruntime": "1.26.0",
            "onnxruntime_qnn": "2.5.0",
            "host_qnn_runtime": "2.49.40",
            "target": {"soc_model": 43, "chipset": "SM8550", "htp_arch": "V73"},
            "session_disable_cpu_ep_fallback": True,
            "enable_block_quant_weight_optimization": True,
            "all_parts_compiled": True,
            "total_context_binary_bytes": total_context_bytes,
            "total_source_onnx_nodes": total_source_nodes,
            "total_supported_source_nodes": total_source_nodes,
            "total_unsupported_source_nodes": 0,
            "total_qnn_ops": total_qnn_ops,
            "qnn_operator_counts": dict(sorted(qnn_ops.items())),
        },
        "parts": retained_parts,
        "claim_boundary": "Every retained source part compiled with CPU fallback disabled and its framework trace binds all source nodes to QNN HTP for SM8550/V73. This is target-specific host AOT evidence, not physical Android execution or benchmark evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
