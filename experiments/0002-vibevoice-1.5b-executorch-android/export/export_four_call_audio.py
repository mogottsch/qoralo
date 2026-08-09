#!/usr/bin/env python3
"""Export the frozen two-method four-call audio PTE.

The command performs eager calls 0-3 from the locked recurrent trace before it
writes any deployable artifact. A failed boundary or fixed-cache comparison is a
reproducible rejection and leaves no multi-method PTE behind.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import resource
import sys
import time
from pathlib import Path

import torch

from acoustic_decoder import load_acoustic_decoder
from fixture_utils import repo_root
from four_call_abi import (
    AtomicFourCallController,
    FourCallAudioMethod,
    load_contract,
    replace_transpose,
    tensor_sha256,
)
from semantic_encoder import load_semantic_encoder
from streaming_decoder import replace_streaming_sconv1d


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, object]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "artifacts/source/microsoft-vibevoice")
    parser.add_argument("--model", type=Path, default=root / "artifacts/models/microsoft-VibeVoice-1.5B")
    parser.add_argument("--trace", type=Path, default=root / "artifacts/0002/recurrent-calls-0-19/capture-1")
    parser.add_argument("--abi", type=Path, default=root / "experiments/0002-vibevoice-1.5b-executorch-android/fixtures/four-call-cache-abi.json")
    parser.add_argument("--output-dir", type=Path, default=root / "artifacts/0002/four-call-audio-export")
    parser.add_argument("--result", type=Path, default=root / "experiments/0002-vibevoice-1.5b-executorch-android/results/four-call-audio-export.json")
    parser.add_argument("--backend", choices=("portable", "xnnpack"), default="portable")
    return parser.parse_args()


def trace_inputs(call: dict[str, object], controller: AtomicFourCallController) -> tuple[torch.Tensor, ...]:
    return (call["decoder"]["input_latent"].contiguous(), torch.tensor(controller.phase, dtype=torch.int32),
            controller.decoder.lengths, *controller.decoder.caches)


def compare(actual: torch.Tensor, expected: torch.Tensor, atol: float, rtol: float, label: str) -> dict[str, object]:
    if actual.dtype != expected.dtype or tuple(actual.shape) != tuple(expected.shape):
        raise RuntimeError(f"{label}: tensor metadata mismatch")
    error = (actual - expected).abs()
    passed = bool(torch.isfinite(actual).all() and torch.allclose(actual, expected, atol=atol, rtol=rtol))
    result = {"max_abs_error": error.max().item(), "mean_abs_error": error.mean().item(), "atol": atol, "rtol": rtol, "passed": passed}
    if not passed:
        raise RuntimeError(f"{label}: boundary comparison failed: {result}")
    return result


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    multi = args.output_dir / f"vibevoice-four-call-audio-{args.backend}.pte"
    multi.unlink(missing_ok=True)
    result: dict[str, object] = {
        "schema_version": 1, "status": "rejected", "deployable": False,
        "abi": str(args.abi), "backend": args.backend,
        "invocation": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
    }
    try:
        contract = load_contract(args.abi)
        sys.path.insert(0, str(args.source.resolve()))
        decoder = load_acoustic_decoder(args.model.resolve(), dtype=torch.float32)
        conv_replacements = replace_streaming_sconv1d(decoder)
        transpose_replacements = replace_transpose(decoder)
        semantic = load_semantic_encoder(args.model.resolve())
        decoder_method = FourCallAudioMethod(decoder, "decoder", contract["methods"]["acoustic_decode"]["caches"], contract["call_transitions"]).eval()
        semantic_method = FourCallAudioMethod(semantic, "semantic", contract["methods"]["semantic_encode"]["caches"], contract["call_transitions"]).eval()
        controller = AtomicFourCallController(contract)
        calls = []
        export_inputs: dict[str, tuple[torch.Tensor, ...]] = {}
        with torch.no_grad():
            for index in range(4):
                call = torch.load(args.trace / f"call_{index:03d}.pt", map_location="cpu", weights_only=True)
                if index == 0:
                    export_inputs["acoustic_decode"] = trace_inputs(call, controller)
                pcm, encoded = controller.execute(call["decoder"]["input_latent"].contiguous(), decoder_method, semantic_method)
                if index == 0:
                    export_inputs["semantic_encode"] = (pcm, torch.tensor(0, dtype=torch.int32), torch.zeros(34, dtype=torch.int32), *AtomicFourCallController(contract).semantic.caches)
                calls.append({
                    "call": index,
                    "decoder_pcm": compare(pcm, call["decoder"]["pcm"], 2e-5, 1e-5, f"call {index} decoder PCM"),
                    "semantic_output": compare(encoded, call["semantic"]["output"], 1e-5, 1e-4, f"call {index} semantic output"),
                    "pcm_sha256": tensor_sha256(pcm), "semantic_sha256": tensor_sha256(encoded),
                    "cache_source": "actual prior eager adapter outputs",
                })
        # A second reset must be byte deterministic before serialization.
        repeated = AtomicFourCallController(contract)
        repeat_hashes = []
        with torch.no_grad():
            for index in range(4):
                call = torch.load(args.trace / f"call_{index:03d}.pt", map_location="cpu", weights_only=True)
                pcm, encoded = repeated.execute(call["decoder"]["input_latent"].contiguous(), decoder_method, semantic_method)
                repeat_hashes.append((tensor_sha256(pcm), tensor_sha256(encoded), *(tensor_sha256(v) for v in repeated.decoder.caches), *(tensor_sha256(v) for v in repeated.semantic.caches)))
        deterministic = all(pair[0] == calls[i]["pcm_sha256"] and pair[1] == calls[i]["semantic_sha256"] for i, pair in enumerate(repeat_hashes))
        if not deterministic:
            raise RuntimeError("reset-and-four-call eager repeat was not deterministic")

        programs = {
            "acoustic_decode": torch.export.export(decoder_method, export_inputs["acoustic_decode"], strict=True),
            "semantic_encode": torch.export.export(semantic_method, export_inputs["semantic_encode"], strict=True),
        }
        from executorch.exir import EdgeCompileConfig, to_edge, to_edge_transform_and_lower
        config = EdgeCompileConfig(_skip_dim_order=False)
        if args.backend == "xnnpack":
            from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
            make_edge = lambda selected: to_edge_transform_and_lower(selected, partitioner=[XnnpackPartitioner(per_op_mode=True)], compile_config=config)
        else:
            make_edge = lambda selected: to_edge(selected, compile_config=config)
        singles = {}
        for name, program in programs.items():
            path = args.output_dir / f"{name}-{args.backend}.pte"
            make_edge(program).to_executorch().save(str(path))
            singles[name] = artifact(path)
        make_edge(programs).to_executorch().save(str(multi))
        multi_artifact = artifact(multi)
        sum_single = sum(item["bytes"] for item in singles.values())
        parameter_bytes = {
            "acoustic_decode": sum(value.numel() * value.element_size() for value in decoder_method.parameters()),
            "semantic_encode": sum(value.numel() * value.element_size() for value in semantic_method.parameters()),
        }
        # Methods own disjoint components. Any excess approaching the smaller full
        # component payload indicates an unintended additional parameter copy.
        excess = multi_artifact["bytes"] - sum_single
        duplicate_full_copy = excess >= min(parameter_bytes.values()) * 0.9
        if duplicate_full_copy:
            raise RuntimeError("multi-method artifact contains an apparent duplicate full parameter payload")
        result.update({
            "status": "exported_pending_host_validation", "deployable": False,
            "methods": ["acoustic_decode", "semantic_encode"], "calls": calls,
            "deterministic_eager_repeat": deterministic,
            "rewrite": {"sconv1d": len(conv_replacements), "sconvtranspose1d": len(transpose_replacements)},
            "artifacts": {"single_method_baselines": singles, "multi_method": multi_artifact},
            "duplication": {"parameter_payload_bytes": parameter_bytes, "sum_single_pte_bytes": sum_single,
                            "multi_pte_bytes": multi_artifact["bytes"], "multi_minus_sum_single_bytes": excess,
                            "duplicate_full_parameter_copy": duplicate_full_copy,
                            "phase_specific_artifacts": 0, "external_ptd_files": 0},
        })
        code = 0
    except Exception as error:
        multi.unlink(missing_ok=True)
        result["rejection"] = {"type": type(error).__name__, "message": str(error)}
        code = 2
    result["versions"] = {"python": sys.version.split()[0], "torch": torch.__version__, "executorch": importlib.metadata.version("executorch")}
    result["wall_seconds"] = time.perf_counter() - started
    result["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    args.result.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
