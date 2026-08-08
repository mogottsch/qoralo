#!/usr/bin/env python3
"""Export the FP32 acoustic-decoder operator-coverage probe to ExecuTorch."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import torch

from acoustic_decoder import (
    NonStreamingDecoderProbe,
    load_acoustic_decoder,
    replace_constant_pad_modules,
)
from fixture_utils import repo_root, tensor_metadata


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=root / "artifacts/source/microsoft-vibevoice",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=root / "artifacts/models/microsoft-VibeVoice-1.5B",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=root / "artifacts/0002/acoustic-decoder-fixtures/call_000.pt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "artifacts/0002/acoustic-decoder-nonstreaming-xnnpack.pte",
    )
    parser.add_argument("--backend", choices=("portable", "xnnpack"), default="xnnpack")
    parser.add_argument(
        "--skip-dim-order",
        action="store_true",
        help="Diagnostic only: disable Edge dim-order lowering for the portable backend",
    )
    parser.add_argument(
        "--graph-output",
        type=Path,
        help="Write ATen and lowered Edge graphs for delegate diagnosis",
    )
    parser.add_argument(
        "--rewrite-constant-pad",
        action="store_true",
        help="Move causal padding into Conv1d and crop right-padding-only outputs",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def graph_diagnostics(exported: object, edge: object) -> str:
    sections = [
        "# Exported ATen graph",
        str(exported.graph_module.graph),
        "\n# Lowered Edge graph",
        str(edge.exported_program().graph_module.graph),
    ]
    lowered_count = 0
    for name, module in edge.exported_program().graph_module.named_modules():
        original = getattr(module, "original_module", None)
        if original is None:
            continue
        lowered_count += 1
        graph_module = getattr(original, "graph_module", original)
        sections.extend(
            [
                f"\n# Delegate {lowered_count}: {name}",
                str(getattr(graph_module, "graph", graph_module)),
            ]
        )
    sections.insert(0, f"# Delegate modules: {lowered_count}")
    return "\n".join(sections) + "\n"


def main() -> None:
    args = parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    try:
        from executorch.exir import EdgeCompileConfig, to_edge, to_edge_transform_and_lower
    except ImportError as error:
        raise SystemExit(
            "ExecuTorch is not installed in this Python environment. Install the "
            "version paired with the Android AAR, then rerun this command. "
            f"Original error: {error}"
        ) from error

    fixture = torch.load(args.fixture, map_location="cpu", weights_only=True)
    latent = fixture["latent_b64t"].to(dtype=torch.float32).contiguous()
    if tuple(latent.shape) != (1, 64, 1):
        raise SystemExit(f"Expected fixed input shape [1,64,1], got {tuple(latent.shape)}")

    decoder = load_acoustic_decoder(args.model.resolve(), dtype=torch.float32)
    wrapper = NonStreamingDecoderProbe(decoder).eval()
    with torch.no_grad():
        original_reference = wrapper(latent)
    replaced_modules: list[str] = []
    if args.rewrite_constant_pad:
        replaced_modules = replace_constant_pad_modules(decoder)
    with torch.no_grad():
        reference = wrapper(latent)
        torch.testing.assert_close(
            reference, original_reference, atol=1e-6, rtol=1e-5
        )
        rewrite_difference = (reference - original_reference).abs()
    exported = torch.export.export(wrapper, (latent,), strict=True)
    noncontiguous = [
        name
        for values in (exported.state_dict, exported.constants)
        for name, value in values.items()
        if isinstance(value, torch.Tensor) and not value.is_contiguous()
    ]
    if noncontiguous:
        raise SystemExit(f"Exported program has non-contiguous constants: {noncontiguous}")

    compile_config = EdgeCompileConfig(_skip_dim_order=args.skip_dim_order)
    if args.backend == "xnnpack":
        if args.skip_dim_order:
            raise SystemExit("--skip-dim-order is a portable-backend diagnostic only")
        try:
            from executorch.backends.xnnpack.partition.xnnpack_partitioner import (
                XnnpackPartitioner,
            )
        except ImportError as error:
            raise SystemExit(f"ExecuTorch XNNPACK backend is unavailable: {error}") from error
        edge = to_edge_transform_and_lower(
            exported,
            partitioner=[XnnpackPartitioner()],
            compile_config=compile_config,
        )
    else:
        edge = to_edge(exported, compile_config=compile_config)
    if args.graph_output:
        args.graph_output.parent.mkdir(parents=True, exist_ok=True)
        args.graph_output.write_text(graph_diagnostics(exported, edge))
    program = edge.to_executorch()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as handle:
        program.write_to_file(handle)
    reference_path = args.output.with_suffix(".reference.pt")
    torch.save({"input": latent, "output": reference}, reference_path)
    metadata = {
        "schema_version": 1,
        "probe": "non_streaming_operator_coverage",
        "backend": args.backend,
        "skip_dim_order": args.skip_dim_order,
        "rewrite_constant_pad": args.rewrite_constant_pad,
        "replaced_modules": replaced_modules,
        "rewrite_eager_max_abs_error": rewrite_difference.max().item(),
        "rewrite_eager_mean_abs_error": rewrite_difference.float().mean().item(),
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": package_version("executorch"),
        },
        "exported_noncontiguous_constants": noncontiguous,
        "graph_output": str(args.graph_output) if args.graph_output else None,
        "input": tensor_metadata(latent),
        "reference_output": tensor_metadata(reference),
        "pte": {
            "path": str(args.output),
            "bytes": args.output.stat().st_size,
            "sha256": file_sha256(args.output),
        },
        "limitations": [
            "The probe does not reproduce streaming cache behavior.",
            "Its output must not be compared directly with call_000 streaming PCM.",
            "The final ABI must consume and return explicitly ordered cache tensors.",
        ],
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
