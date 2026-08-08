#!/usr/bin/env python3
"""Export fixed-shape decoder micro-probes to isolate ExecuTorch failures."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn.functional as F

from acoustic_decoder import load_acoustic_decoder, replace_constant_pad_modules
from export_decoder import file_sha256, graph_diagnostics, package_version
from fixture_utils import repo_root, tensor_metadata


@dataclass
class Probe:
    name: str
    module: torch.nn.Module
    input: torch.Tensor
    output: torch.Tensor


class ComponentWrapper(torch.nn.Module):
    def __init__(self, component: torch.nn.Module):
        super().__init__()
        self.component = component

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.component(value)


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "probe",
        help="stem, upsample-N, stage-N, norm, or head (N is zero-based)",
    )
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
        "--output-dir",
        type=Path,
        default=root / "artifacts/0002/decoder-microprobes",
    )
    parser.add_argument("--backend", choices=("portable", "xnnpack"), default="xnnpack")
    parser.add_argument("--skip-dim-order", action="store_true")
    parser.add_argument(
        "--rewrite-constant-pad",
        action="store_true",
        help="Move causal padding into Conv1d and crop right-padding-only outputs",
    )
    return parser.parse_args()


def collect_probes(decoder: torch.nn.Module, latent: torch.Tensor) -> dict[str, Probe]:
    probes: dict[str, Probe] = {}
    with torch.no_grad():
        stem_container = decoder.upsample_layers[0]
        stem_layer = (
            stem_container[0]
            if isinstance(stem_container, torch.nn.Sequential)
            else None
        )
        if stem_layer is not None and stem_layer.__class__.__name__ == "SConv1d":
            padded = F.pad(
                latent,
                (stem_layer.padding_total, 0),
                mode="constant",
                value=0,
            ).contiguous()
            probes["stem-conv"] = Probe(
                "stem-conv",
                stem_layer.conv,
                padded,
                stem_layer.conv(padded).contiguous(),
            )
        value = latent
        for index, (upsample, stage) in enumerate(
            zip(decoder.upsample_layers, decoder.stages)
        ):
            upsample_input = value.contiguous()
            value = upsample(upsample_input)
            name = "stem" if index == 0 else f"upsample-{index}"
            probes[name] = Probe(name, upsample, upsample_input, value.contiguous())

            stage_input = value.contiguous()
            value = stage(stage_input)
            probes[f"stage-{index}"] = Probe(
                f"stage-{index}", stage, stage_input, value.contiguous()
            )

        norm_input = value.contiguous()
        value = decoder.norm(norm_input)
        probes["norm"] = Probe("norm", decoder.norm, norm_input, value.contiguous())

        head_input = value.contiguous()
        value = decoder.head(head_input)
        probes["head"] = Probe("head", decoder.head, head_input, value.contiguous())

        expected = decoder(latent)
        torch.testing.assert_close(value, expected, atol=1e-6, rtol=1e-5)

        if len(decoder.upsample_layers) > 1:
            stage_then_upsample = torch.nn.Sequential(
                decoder.stages[0], decoder.upsample_layers[1]
            )
            composite_input = probes["stage-0"].input
            composite_output = stage_then_upsample(composite_input).contiguous()
            probes["stage-0-upsample-1"] = Probe(
                "stage-0-upsample-1",
                stage_then_upsample,
                composite_input,
                composite_output,
            )
            initial = torch.nn.Sequential(
                decoder.upsample_layers[0],
                decoder.stages[0],
                decoder.upsample_layers[1],
            )
            probes["initial-through-upsample-1"] = Probe(
                "initial-through-upsample-1",
                initial,
                latent,
                initial(latent).contiguous(),
            )
    return probes


def main() -> None:
    args = parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    try:
        from executorch.exir import EdgeCompileConfig, to_edge, to_edge_transform_and_lower
    except ImportError as error:
        raise SystemExit(f"ExecuTorch is unavailable: {error}") from error

    fixture = torch.load(args.fixture, map_location="cpu", weights_only=True)
    latent = fixture["latent_b64t"].float().contiguous()
    decoder = load_acoustic_decoder(args.model.resolve(), dtype=torch.float32)
    original_probes = collect_probes(decoder, latent)
    replaced: list[str] = []
    if args.rewrite_constant_pad:
        replaced = replace_constant_pad_modules(decoder)
        probes = collect_probes(decoder, latent)
        for name in probes:
            torch.testing.assert_close(
                probes[name].output,
                original_probes[name].output,
                atol=1e-6,
                rtol=1e-5,
            )
    else:
        probes = original_probes
    if args.probe not in probes:
        raise SystemExit(
            f"Unknown probe {args.probe!r}; choose one of: {', '.join(probes)}"
        )
    probe = probes[args.probe]
    wrapper = ComponentWrapper(probe.module).eval()
    with torch.no_grad():
        torch.testing.assert_close(
            wrapper(probe.input), probe.output, atol=1e-6, rtol=1e-5
        )
    exported = torch.export.export(wrapper, (probe.input,), strict=True)
    noncontiguous = [
        name
        for values in (exported.state_dict, exported.constants)
        for name, value in values.items()
        if isinstance(value, torch.Tensor) and not value.is_contiguous()
    ]
    if noncontiguous:
        raise SystemExit(f"Non-contiguous exported constants: {noncontiguous}")

    config = EdgeCompileConfig(_skip_dim_order=args.skip_dim_order)
    if args.backend == "xnnpack":
        if args.skip_dim_order:
            raise SystemExit("--skip-dim-order is portable-only")
        from executorch.backends.xnnpack.partition.xnnpack_partitioner import (
            XnnpackPartitioner,
        )

        edge = to_edge_transform_and_lower(
            exported,
            partitioner=[XnnpackPartitioner()],
            compile_config=config,
        )
    else:
        edge = to_edge(exported, compile_config=config)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    base = args.output_dir / f"{probe.name}-{args.backend}"
    graph_path = base.with_suffix(".graphs.txt")
    graph_path.write_text(graph_diagnostics(exported, edge))
    program = edge.to_executorch()
    pte_path = base.with_suffix(".pte")
    with pte_path.open("wb") as handle:
        program.write_to_file(handle)
    torch.save(
        {"input": probe.input, "output": probe.output},
        base.with_suffix(".reference.pt"),
    )
    metadata = {
        "schema_version": 1,
        "probe": probe.name,
        "backend": args.backend,
        "skip_dim_order": args.skip_dim_order,
        "rewrite_constant_pad": args.rewrite_constant_pad,
        "replaced_modules": replaced,
        "versions": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "executorch": package_version("executorch"),
        },
        "input": tensor_metadata(probe.input),
        "reference_output": tensor_metadata(probe.output),
        "exported_noncontiguous_constants": noncontiguous,
        "pte": {
            "bytes": pte_path.stat().st_size,
            "sha256": file_sha256(pte_path),
        },
        "graph": str(graph_path),
    }
    base.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
