#!/usr/bin/env python3
"""Export and host-validate sequential INT8 Qwen2 prefill and chained decode.

The full backbone is deliberately split at the already accepted 60-stage Android
boundary. Each stage is quantized and validated before moving to the next; decode
always consumes caches produced by the INT8 prefill stages.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import resource
import time
from pathlib import Path
from typing import Any

import torch
from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
from executorch.exir import EdgeCompileConfig, to_edge_transform_and_lower
from executorch.runtime import Runtime

from fixture_utils import repo_root
from qwen2_backbone import Qwen2PrefillFinal, Qwen2PrefillLayer, Qwen2PrefillPrepare, cache_tensor_names
from qwen2_checkpoint import load_qwen2_backbone
from qwen2_quantization import deployment_benefit, quantization_spec, quantize_dynamic_int8, quantized_comparison
from validate_qwen2_fixtures import expected_outputs, wrapper_inputs
from validate_qwen2_pte import compare_outputs

LAYERS = 28
NAMES = ["last_hidden_state", "next_token_logits", *cache_tensor_names(LAYERS)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_hash(values: tuple[torch.Tensor, ...]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.detach().contiguous().cpu().numpy().tobytes())
    return digest.hexdigest()


def memory() -> dict[str, int]:
    fields = {"VmRSS": -1, "VmHWM": -1}
    for line in Path("/proc/self/status").read_text().splitlines():
        key = line.split(":", 1)[0]
        if key in fields:
            fields[key] = int(line.split()[1])
    return {"rss_kib": fields["VmRSS"], "vmhwm_kib": fields["VmHWM"]}


def emit(module: torch.nn.Module, inputs: tuple[torch.Tensor, ...], path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    converted, coverage = quantize_dynamic_int8(module, inputs)
    exported = torch.export.export(converted, inputs, strict=True)
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
        "coverage": coverage,
        "export_seconds": time.perf_counter() - started,
    }


def execute(path: Path, inputs: tuple[torch.Tensor, ...]) -> tuple[torch.Tensor, ...]:
    method = Runtime.get().load_program(str(path)).load_method("forward")
    return tuple(method.execute(tuple(value.contiguous() for value in inputs)))


def run_chain(
    package: Path,
    prefill_inputs: tuple[torch.Tensor, ...],
    decode_inputs: tuple[torch.Tensor, ...],
) -> tuple[tuple[torch.Tensor, ...], tuple[torch.Tensor, ...], dict[str, float]]:
    started = time.perf_counter()
    hidden, causal, cos, sin = execute(package / "prepare.pte", prefill_inputs)
    capacity = int(prefill_inputs[1].shape[1])
    zero = torch.zeros(1, 2, capacity, 128)
    caches: list[torch.Tensor] = []
    for layer in range(LAYERS):
        hidden, key, value = execute(
            package / f"layer-{layer:02d}.pte",
            (hidden, causal, prefill_inputs[3], cos, sin, zero, zero),
        )
        caches.extend((key, value))
    last_hidden, logits = execute(package / "final.pte", (hidden,))
    prefill = (last_hidden, logits, *caches)
    prefill_seconds = time.perf_counter() - started

    started = time.perf_counter()
    hidden, causal, cos, sin = execute(package / "decode-prepare.pte", decode_inputs)
    decode_caches: list[torch.Tensor] = []
    for layer in range(LAYERS):
        hidden, key, value = execute(
            package / f"decode-layer-{layer:02d}.pte",
            (hidden, causal, decode_inputs[3], cos, sin, caches[layer * 2], caches[layer * 2 + 1]),
        )
        decode_caches.extend((key, value))
    last_hidden, logits = execute(package / "decode-final.pte", (hidden,))
    return prefill, (last_hidden, logits, *decode_caches), {
        "prefill_seconds": prefill_seconds,
        "decode_seconds": time.perf_counter() - started,
    }


def main() -> None:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=root / "artifacts/models/microsoft-VibeVoice-1.5B")
    parser.add_argument("--fixture-dir", type=Path, default=root / "artifacts/0002/lane-c/qwen2-fixtures")
    parser.add_argument("--output", type=Path, default=root / "artifacts/0002/lane-c/qwen2-int8-package")
    parser.add_argument("--result", type=Path, default=root / "experiments/0002-vibevoice-1.5b-executorch-android/results/qwen2-int8-host.json")
    parser.add_argument("--fp32-package-manifest", type=Path, default=root / "artifacts/0002/lane-c/qwen2-prefill-android-package/manifest.json")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "failed",
        "component": "qwen2_prefill_decode_sequential_int8_xnnpack",
        "source_revision": "6dd49cb7200c0367205a5f1e650244259e9e423d",
        "model_revision": "c00898d257e6b46004e3e2866a47534085fb685a",
        "quantization": quantization_spec(),
        "cache_handoff": {"source": "actual_int8_prefill_outputs", "tensor_count": 56, "order": cache_tensor_names(LAYERS)},
        "commands": {
            "export_host": "artifacts/venv-executorch-1.2/bin/python experiments/0002-vibevoice-1.5b-executorch-android/export/export_qwen2_quantized.py",
            "android": "PACKAGE_DIR=artifacts/0002/lane-c/qwen2-int8-package RESULT_NAME=qwen2-int8-android.json experiments/0002-vibevoice-1.5b-executorch-android/android/run-qwen2-int8-probe.sh",
        },
    }
    exit_code = 1
    try:
        prefill_fixture = torch.load(args.fixture_dir / "prefill.pt", map_location="cpu", weights_only=True)
        decode_fixture = torch.load(args.fixture_dir / "decode.pt", map_location="cpu", weights_only=True)
        prefill_inputs = wrapper_inputs(prefill_fixture, False)
        decode_inputs = wrapper_inputs(decode_fixture, False)
        fixture_manifest = args.fixture_dir / "manifest.json"
        result["calibration_fixture"] = {
            "manifest_sha256": sha256(fixture_manifest),
            "prefill_sha256": sha256(args.fixture_dir / "prefill.pt"),
            "decode_sha256": sha256(args.fixture_dir / "decode.pt"),
            "seed": json.loads(fixture_manifest.read_text()).get("seed", 42),
        }
        backbone, lm_head = load_qwen2_backbone(args.model.resolve(), torch.float32)
        options = dict(num_hidden_layers=LAYERS, num_key_value_heads=2, head_dim=128, cache_capacity=int(prefill_inputs[1].shape[1]))
        stages: list[dict[str, Any]] = []

        definitions: list[tuple[str, torch.nn.Module, tuple[torch.Tensor, ...]]] = []
        definitions.append(("prepare.pte", Qwen2PrefillPrepare(backbone, **options), prefill_inputs))
        with torch.no_grad():
            hidden, causal, cos, sin = definitions[-1][1](*prefill_inputs)
        zero = torch.zeros(1, 2, options["cache_capacity"], 128)
        for index, layer in enumerate(backbone.layers):
            module = Qwen2PrefillLayer(layer, index)
            inputs = (hidden, causal, prefill_inputs[3], cos, sin, zero, zero)
            definitions.append((f"layer-{index:02d}.pte", module, inputs))
            with torch.no_grad():
                hidden, _, _ = module(*inputs)
        final = Qwen2PrefillFinal(backbone.norm, lm_head)
        definitions.append(("final.pte", final, (hidden,)))

        definitions.append(("decode-prepare.pte", Qwen2PrefillPrepare(backbone, **options), decode_inputs))
        with torch.no_grad():
            d_hidden, d_causal, d_cos, d_sin = definitions[-1][1](*decode_inputs)
        # Shapes and quantization observers are independent of cache values. Real
        # INT8 prefill caches are still mandatory at host/device execution time.
        fixture_caches = tuple(prefill_fixture["post_cache"])
        for index, layer in enumerate(backbone.layers):
            module = Qwen2PrefillLayer(layer, index)
            inputs = (d_hidden, d_causal, decode_inputs[3], d_cos, d_sin, fixture_caches[index * 2], fixture_caches[index * 2 + 1])
            definitions.append((f"decode-layer-{index:02d}.pte", module, inputs))
            with torch.no_grad():
                d_hidden, _, _ = module(*inputs)
        definitions.append(("decode-final.pte", final, (d_hidden,)))

        for filename, module, inputs in definitions:
            metadata = emit(module.eval(), inputs, args.output / filename)
            metadata["kind"] = filename.removesuffix(".pte")
            stages.append(metadata)
        result["stages"] = stages
        result["stage_count"] = len(stages)

        first_prefill, first_decode, first_timing = run_chain(args.output, prefill_inputs, decode_inputs)
        second_prefill, second_decode, second_timing = run_chain(args.output, prefill_inputs, decode_inputs)
        result["prefill"] = {
            "int8_vs_pinned_fp32": quantized_comparison(first_prefill, expected_outputs(prefill_fixture), NAMES),
            "strict_fp32_threshold_metrics": compare_outputs(first_prefill, expected_outputs(prefill_fixture), 1e-5, 1e-4),
            "timing": first_timing["prefill_seconds"],
            "ordered_output_sha256": tensor_hash(first_prefill),
        }
        result["decode"] = {
            "int8_vs_pinned_fp32": quantized_comparison(first_decode, expected_outputs(decode_fixture), NAMES),
            "strict_fp32_threshold_metrics": compare_outputs(first_decode, expected_outputs(decode_fixture), 1e-5, 1e-4),
            "timing": first_timing["decode_seconds"],
            "ordered_output_sha256": tensor_hash(first_decode),
            "cache_source": "actual INT8 prefill stage outputs",
        }
        result["determinism"] = {
            "repeat_exact": tensor_hash(first_prefill) == tensor_hash(second_prefill) and tensor_hash(first_decode) == tensor_hash(second_decode),
            "repeat_prefill_sha256": tensor_hash(second_prefill),
            "repeat_decode_sha256": tensor_hash(second_decode),
            "repeat_timing": second_timing,
        }
        fp32 = json.loads(args.fp32_package_manifest.read_text())
        int8_bytes = sum(stage["bytes"] for stage in stages)
        result["size_and_fallback_acceptance"] = deployment_benefit(
            int8_bytes=int8_bytes,
            fp32_bytes=int(fp32["total_bytes"]),
            coverages=[stage["coverage"] for stage in stages],
        )
        result["fp32_baseline"] = {
            "package_bytes": fp32["total_bytes"],
            "largest_stage_bytes": fp32["largest_stage_bytes"],
            "prefill": fp32["host_revalidation"]["prefill"],
            "decode": fp32["host_revalidation"]["decode_from_prefill_outputs"],
            "manifest_sha256": sha256(args.fp32_package_manifest),
        }
        accepted = (
            result["prefill"]["int8_vs_pinned_fp32"]["accepted"]
            and result["decode"]["int8_vs_pinned_fp32"]["accepted"]
            and result["determinism"]["repeat_exact"]
            and result["size_and_fallback_acceptance"]["accepted"]
        )
        result["status"] = "passed" if accepted else "rejected"
        result["conclusion"] = (
            "Accepted: INT8 materially reduces deployment size with covered XNNPACK Linear operators, deterministic outputs, exact next-token decisions, and decode chained from actual INT8 prefill caches."
            if accepted else
            "Rejected for deployment: at least one numerical, token, determinism, coverage, or size-benefit criterion failed; fallback is not silently accepted."
        )
        (args.output / "manifest.json").write_text(json.dumps({
            "schema_version": 1, "status": result["status"], "precision": "int8", "backend": "xnnpack",
            "stage_count": len(stages), "total_bytes": int8_bytes, "largest_stage_bytes": max(x["bytes"] for x in stages),
            "stages": stages, "host_result": str(args.result), "cache_source": "actual_int8_prefill_outputs",
        }, indent=2) + "\n")
        exit_code = 0 if accepted else 2
    except Exception as error:
        result["error_type"] = type(error).__name__
        result["error"] = str(error)
    finally:
        result["wall_seconds"] = time.perf_counter() - started
        result["memory"] = {**memory(), "resource_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        result["versions"] = {"torch": torch.__version__, "executorch": importlib.metadata.version("executorch")}
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
