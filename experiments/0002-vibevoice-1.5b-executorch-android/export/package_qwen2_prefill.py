#!/usr/bin/env python3
"""Export and host-validate a phone-safe, sequential Qwen2 prefill package."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import resource
import time
from pathlib import Path

import torch
from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
from executorch.exir import EdgeCompileConfig, to_edge_transform_and_lower
from executorch.runtime import Runtime

from diagnose_qwen2 import evaluate_acceptance
from qwen2_backbone import (
    Qwen2PrefillFinal,
    Qwen2PrefillLayer,
    Qwen2PrefillPrepare,
    cache_tensor_names,
)
from qwen2_checkpoint import load_qwen2_backbone
from validate_qwen2_fixtures import expected_outputs, wrapper_inputs
from validate_qwen2_pte import compare_outputs

LAYERS = 28


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def emit(module: torch.nn.Module, inputs: tuple[torch.Tensor, ...], path: Path) -> dict:
    started = time.perf_counter()
    exported = torch.export.export(module.eval(), inputs, strict=True)
    edge = to_edge_transform_and_lower(
        exported,
        partitioner=[XnnpackPartitioner()],
        compile_config=EdgeCompileConfig(_skip_dim_order=False),
    )
    program = edge.to_executorch()
    with path.open("wb") as stream:
        program.write_to_file(stream)
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "graph_nodes": len(list(exported.graph.nodes)),
        "delegate_segments": sum(
            1 for _, child in edge.exported_program().graph_module.named_modules()
            if getattr(child, "original_module", None) is not None
        ),
        "export_seconds": time.perf_counter() - started,
    }


def execute(path: Path, inputs: tuple[torch.Tensor, ...]) -> tuple[torch.Tensor, ...]:
    method = Runtime.get().load_program(str(path)).load_method("forward")
    return tuple(method.execute(tuple(value.contiguous() for value in inputs)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    fixture = torch.load(args.fixture_dir / "prefill.pt", map_location="cpu", weights_only=True)
    fixture_inputs = wrapper_inputs(fixture, False)
    cache_capacity = int(fixture_inputs[1].shape[1])
    backbone, lm_head = load_qwen2_backbone(args.model.resolve(), torch.float32)
    options = dict(num_hidden_layers=LAYERS, num_key_value_heads=2,
                   head_dim=128, cache_capacity=cache_capacity)
    stages = []

    prepare = Qwen2PrefillPrepare(backbone, **options).eval()
    prepare_path = args.output / "prepare.pte"
    stages.append({"kind": "prepare", **emit(prepare, fixture_inputs, prepare_path)})
    hidden, causal_mask, cos, sin = execute(prepare_path, fixture_inputs)

    zero = torch.zeros(1, 2, cache_capacity, 128)
    caches = []
    for index, layer in enumerate(backbone.layers):
        stage = Qwen2PrefillLayer(layer, index).eval()
        stage_inputs = (hidden, causal_mask, fixture_inputs[3], cos, sin, zero, zero)
        path = args.output / f"layer-{index:02d}.pte"
        stages.append({"kind": "decoder_layer", "layer": index,
                       **emit(stage, stage_inputs, path)})
        hidden, key, value = execute(path, stage_inputs)
        caches.extend((key, value))

    final = Qwen2PrefillFinal(backbone.norm, lm_head).eval()
    final_path = args.output / "final.pte"
    stages.append({"kind": "final_norm_and_lm_head", **emit(final, (hidden,), final_path)})
    last_hidden, logits = execute(final_path, (hidden,))
    comparison = compare_outputs(
        (last_hidden, logits, *caches), expected_outputs(fixture), 1e-5, 1e-4
    )
    acceptance = evaluate_acceptance(comparison)
    total = sum(stage["bytes"] for stage in stages)
    manifest = {
        "schema_version": 1,
        "component": "qwen2_prefill_android_sequential_package",
        "status": "passed" if acceptance["bounded_xnnpack_accepted"] else "failed",
        "precision": "fp32",
        "backend": "xnnpack",
        "packaging_rationale": (
            "The monolithic 6.18 GB graph predictably exceeds currently available phone memory "
            "once XNNPACK packs weights. These 30 graphs preserve FP32 operations and checkpoint "
            "weights but load prepare, one decoder layer, and final head sequentially; the largest "
            "resident model file, rather than their sum, bounds model mapping/packing pressure."
        ),
        "graph_boundaries": {
            "prepare": "conditioned embeddings -> embeddings, causal mask, shared RoPE cos/sin",
            "decoder_layer_00_through_27": "hidden + mask/RoPE + one zero KV pair -> hidden + updated KV pair",
            "final": "layer-27 hidden -> final-norm hidden and FP32 logits",
            "cache_order": cache_tensor_names(LAYERS),
        },
        "stages": stages,
        "stage_count": len(stages),
        "total_bytes": total,
        "largest_stage_bytes": max(stage["bytes"] for stage in stages),
        "host_revalidation": {"strict": comparison, "acceptance": acceptance},
        "versions": {
            "torch": torch.__version__,
            "executorch": importlib.metadata.version("executorch"),
        },
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    raise SystemExit(0 if manifest["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
