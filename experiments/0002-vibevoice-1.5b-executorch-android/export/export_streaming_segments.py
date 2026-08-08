#!/usr/bin/env python3
"""Export the streaming acoustic decoder as eight cache-functional segments."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from pathlib import Path

import torch

from acoustic_decoder import load_acoustic_decoder
from fixture_utils import repo_root, tensor_metadata
from streaming_decoder import (
    FunctionalStreamingSegment,
    cache_module_names,
    replace_streaming_sconv1d,
    segment_cache_names,
)


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", choices=("first", "cached"), required=True)
    parser.add_argument("--precision", choices=("fp32", "fp16"), default="fp32")
    parser.add_argument("--source", type=Path, default=root / "artifacts/source/microsoft-vibevoice")
    parser.add_argument("--model", type=Path, default=root / "artifacts/models/microsoft-VibeVoice-1.5B")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--atol",
        type=float,
        help="Absolute FP32-fixture tolerance (default: 2e-5 FP32, 2e-3 FP16)",
    )
    parser.add_argument(
        "--rtol",
        type=float,
        help="Relative FP32-fixture tolerance (default: 1e-5 FP32, 2e-3 FP16)",
    )
    parser.add_argument(
        "--cache-atol",
        type=float,
        help="Cache-only absolute tolerance (default: atol FP32, 5e-2 FP16)",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def main() -> None:
    args = parse_args()
    root = repo_root(Path(__file__))
    cached = args.entry == "cached"
    dtype = torch.float16 if args.precision == "fp16" else torch.float32
    atol = args.atol if args.atol is not None else (2e-3 if dtype == torch.float16 else 2e-5)
    rtol = args.rtol if args.rtol is not None else (2e-3 if dtype == torch.float16 else 1e-5)
    cache_atol = args.cache_atol if args.cache_atol is not None else (
        5e-2 if dtype == torch.float16 else atol
    )
    fixture_path = args.fixture or root / f"artifacts/0002/acoustic-decoder-fixtures/call_{1 if cached else 0:03d}.pt"
    suffix = "" if args.precision == "fp32" else f"-{args.precision}"
    output_dir = args.output_dir or root / f"artifacts/0002/acoustic-decoder-streaming-{args.entry}-segments{suffix}-1.2"
    output_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.source.resolve()))
    from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
    from executorch.exir import to_edge_transform_and_lower

    fixture = torch.load(fixture_path, map_location="cpu", weights_only=True)
    names = cache_module_names(fixture, "post_cache")
    pre_cache = fixture["pre_cache"]
    post_cache = fixture["post_cache"]
    decoder = load_acoustic_decoder(args.model.resolve(), dtype=dtype)
    replaced = replace_streaming_sconv1d(decoder)
    value = fixture["latent_b64t"].to(dtype=dtype).contiguous()
    segments = []
    total_bytes = 0
    for segment in range(8):
        local_names = segment_cache_names(names, segment)
        wrapper = FunctionalStreamingSegment(decoder, segment, local_names, cached).eval()
        cache_inputs = tuple(
            pre_cache[f"{name}/sample_0"].unsqueeze(0).to(dtype=dtype).contiguous()
            for name in local_names
        ) if cached else ()
        inputs = (value, *cache_inputs)
        started = time.perf_counter()
        with torch.no_grad():
            outputs = wrapper(*inputs)
        eager_seconds = time.perf_counter() - started
        expected_caches = tuple(
            post_cache[f"{name}/sample_0"].unsqueeze(0).to(dtype=torch.float32).contiguous()
            for name in local_names
        )
        cache_errors = [
            (actual - expected).abs()
            for actual, expected in zip(outputs[1:], expected_caches)
        ]
        if not all(
            torch.allclose(actual.float(), expected, atol=cache_atol, rtol=rtol)
            for actual, expected in zip(outputs[1:], expected_caches)
        ):
            maximum = max(
                (error.float().max().item() for error in cache_errors), default=0.0
            )
            raise SystemExit(
                f"Segment {segment} cache output mismatch (max_abs_error={maximum})"
            )
        value = outputs[0].detach()
        exported = torch.export.export(wrapper, inputs, strict=True)
        with torch.no_grad():
            exported_outputs = tuple(exported.module()(*inputs))
        export_errors = [
            (actual.float() - expected.float()).abs()
            for actual, expected in zip(exported_outputs, outputs)
        ]
        if not all(
            torch.allclose(actual, expected, atol=0, rtol=0)
            for actual, expected in zip(exported_outputs, outputs)
        ):
            raise SystemExit(f"Segment {segment} exported-program output mismatch")
        try:
            edge = to_edge_transform_and_lower(
                exported, partitioner=[XnnpackPartitioner()]
            )
            partition_mode = "maximal"
        except AssertionError as error:
            if "dependency cycles" not in str(error):
                raise
            edge = to_edge_transform_and_lower(
                exported, partitioner=[XnnpackPartitioner(per_op_mode=True)]
            )
            partition_mode = "per_op"
        program = edge.to_executorch()
        pte = output_dir / f"segment-{segment}.pte"
        with pte.open("wb") as handle:
            program.write_to_file(handle)
        reference = pte.with_suffix(".reference.pt")
        torch.save(
            {
                "inputs": inputs,
                "outputs": (value, *expected_caches),
                "fixture_pcm": fixture["pcm"].to(dtype=torch.float32).contiguous()
                if segment == 7
                else None,
                "cache_names": local_names,
                "entry": args.entry,
                "segment": segment,
            },
            reference,
        )
        total_bytes += pte.stat().st_size
        segments.append(
            {
                "segment": segment,
                "cache_names": local_names,
                "input_count": len(inputs),
                "output_count": len(outputs),
                "activation_input": tensor_metadata(inputs[0]),
                "activation_output": tensor_metadata(value),
                "eager_seconds": eager_seconds,
                "cache_max_abs_error": max(
                    (error.float().max().item() for error in cache_errors), default=0.0
                ),
                "cache_mean_abs_error_max": max(
                    (error.float().mean().item() for error in cache_errors), default=0.0
                ),
                "exported_program_max_abs_error": max(
                    (error.max().item() for error in export_errors), default=0.0
                ),
                "partition_mode": partition_mode,
                "pte": {
                    "file": pte.name,
                    "bytes": pte.stat().st_size,
                    "sha256": sha256(pte),
                },
            }
        )
    pcm = fixture["pcm"].to(dtype=torch.float32)
    pcm_error = (value.float() - pcm).abs()
    pcm_allclose = bool(torch.allclose(value.float(), pcm, atol=atol, rtol=rtol))
    if not pcm_allclose:
        raise SystemExit("Segmented eager PCM does not match fixture")
    metadata = {
        "schema_version": 1,
        "entry": args.entry,
        "precision": args.precision,
        "model_dtype": str(dtype).removeprefix("torch."),
        "tensor_abi_dtype": str(dtype).removeprefix("torch."),
        "backend": "xnnpack",
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": version("executorch"),
        },
        "interface": {
            "segment_count": 8,
            "global_cache_order": names,
            "cache_tensors": len(names),
            "description": "segment activation plus local cache tensors in; next activation plus updated local cache tensors out",
        },
        "rewrite": {"replaced_sconv1d_modules": len(replaced)},
        "eager": {
            "pcm_max_abs_error": pcm_error.max().item(),
            "pcm_mean_abs_error": pcm_error.float().mean().item(),
            "cache_allclose": True,
            "pcm_allclose": pcm_allclose,
            "pcm_atol": atol,
            "cache_atol": cache_atol,
            "rtol": rtol,
            "reference": "original captured FP32 fixture",
        },
        "segments": segments,
        "total_pte_bytes": total_bytes,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
