#!/usr/bin/env python3
"""Export the canonical-v2 official-frontend Kokoro fixed FP32 ONNX graph."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import onnx
import torch
from kokoro import KModel
from kokoro.model import KModelForONNX

PINS = {
    "model": (327212226, "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"),
    "config": (2351, "5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f"),
    "tokens": (1880, "9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280"),
    "style": (1024, "8acaca07623d98a1085f6b182fb997d715dd1d67862e350567e6d9b1bc8ec71b"),
    "speed": (4, "e00e5eb9444182f352323374ef4e08ebcb784725fdd4fd612d7730540b3e0c8c"),
    "oracle": (3507, "f696b3054a193cea0a650212ea2fc5a620da8e9375ad8b521943ac4cfb43ecd5"),
}
SEED = 20260818
TOKEN_COUNT = 235
DURATION_SUM = 602
AUDIO_SAMPLES = 361200


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, key: str) -> None:
    size, expected = PINS[key]
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"{key} is not a regular file")
    if path.stat().st_size != size or sha256(path) != expected:
        raise RuntimeError(f"{key} pin mismatch: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--tokens", type=Path, required=True)
    parser.add_argument("--style", type=Path, required=True)
    parser.add_argument("--speed", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--experiment-0013-tools", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    for key in PINS:
        verify(getattr(args, key), key)
    oracle = json.loads(args.oracle.read_text())
    if (
        oracle["outputs"]["duration"]["sum"] != DURATION_SUM
        or oracle["outputs"]["audio"]["shape"] != [AUDIO_SAMPLES]
    ):
        raise RuntimeError("controlled-eager oracle shape drift")
    if importlib.metadata.version("kokoro") != "0.9.4":
        raise RuntimeError("kokoro package version drift")

    sys.path.insert(0, str(args.experiment_0013_tools))
    from deterministic_sine import SeededSineGen
    from onnx_exact_stft import OnnxExactSTFT

    tool_paths = {
        name: args.experiment_0013_tools / name
        for name in (
            "deterministic_sine.py",
            "onnx_exact_stft.py",
            "exact_stft.py",
        )
    }
    tokens_np = np.fromfile(args.tokens, dtype="<i8").reshape(1, TOKEN_COUNT)
    style_np = np.fromfile(args.style, dtype="<f4").reshape(1, 256)
    speed_np = np.fromfile(args.speed, dtype="<f4").reshape(1)
    if speed_np[0] != 1.0:
        raise RuntimeError("speed drift")
    tokens = torch.from_numpy(tokens_np.copy())
    style = torch.from_numpy(style_np.copy())
    speed = torch.from_numpy(speed_np.copy())

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    model = KModel(
        repo_id="not-used",
        model=str(args.model),
        config=str(args.config),
        disable_complex=False,
    ).cpu().eval()
    model.decoder.generator.stft = OnnxExactSTFT(20, 5, 20)
    model.decoder.generator.m_source.l_sin_gen = SeededSineGen(
        f0_shape=(1, AUDIO_SAMPLES, 1), seed=SEED
    )
    wrapper = KModelForONNX(model).cpu().eval()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    torch.onnx.export(
        wrapper,
        (tokens, style, speed),
        str(args.output),
        input_names=["tokens", "style", "speed"],
        output_names=["audio", "pred_dur"],
        opset_version=17,
        do_constant_folding=True,
        dynamo=False,
    )
    export_seconds = time.perf_counter() - started

    graph = onnx.load(str(args.output), load_external_data=False)
    onnx.checker.check_model(graph, full_check=True)
    operators = Counter(node.op_type for node in graph.graph.node)
    initializer_types = Counter(
        onnx.TensorProto.DataType.Name(value.data_type)
        for value in graph.graph.initializer
    )
    quantized = sum(
        operators.get(name, 0)
        for name in (
            "QuantizeLinear",
            "DequantizeLinear",
            "DynamicQuantizeLinear",
            "MatMulInteger",
            "QLinearConv",
            "QLinearMatMul",
        )
    )
    random = sum(value for name, value in operators.items() if "Random" in name)
    if quantized or random:
        raise RuntimeError(
            f"unexpected quantized/random operators: quantized={quantized} random={random}"
        )
    if set(initializer_types) != {"FLOAT"}:
        raise RuntimeError(f"non-FP32 initializers: {initializer_types}")
    output_shapes = {}
    for value in graph.graph.output:
        output_shapes[value.name] = [
            dim.dim_value if dim.HasField("dim_value") else None
            for dim in value.type.tensor_type.shape.dim
        ]
    if set(output_shapes) != {"audio", "pred_dur"} or any(
        len(shape) != 1 for shape in output_shapes.values()
    ):
        raise RuntimeError(f"export output rank/name drift: {output_shapes}")

    record = {
        "schema_version": 1,
        "status": "exported_and_onnx_checker_passed",
        "route": "canonical_v2_official_frontend_exact_source_controlled_fp32_onnx",
        "source": {
            "repository": "https://huggingface.co/hexgrad/Kokoro-82M",
            "revision": "f3ff3571791e39611d31c381e3a41a3af07b4987",
            "model": {
                "bytes": args.model.stat().st_size,
                "sha256": sha256(args.model),
            },
            "config": {
                "bytes": args.config.stat().st_size,
                "sha256": sha256(args.config),
            },
            "controlled_eager_oracle": {
                "bytes": args.oracle.stat().st_size,
                "sha256": sha256(args.oracle),
            },
        },
        "inputs": {
            "tokens": {
                "shape": [1, TOKEN_COUNT],
                "sha256": sha256(args.tokens),
            },
            "style": {"shape": [1, 256], "sha256": sha256(args.style)},
            "speed": {"value": 1.0, "sha256": sha256(args.speed)},
            "seed": SEED,
        },
        "fixed_outputs": {
            "duration_shape": [TOKEN_COUNT],
            "duration_sum": DURATION_SUM,
            "audio_shape": [AUDIO_SAMPLES],
            "sample_rate_hz": 24000,
            "audio_duration_seconds": AUDIO_SAMPLES / 24000.0,
        },
        "transformations": {
            "learned_weights_changed": False,
            "quantized": False,
            "stft": "standard ONNX STFT plus experiment-0013 source-equivalent real inverse-STFT decomposition",
            "random_inputs": "SeededSineGen materialized at seed 20260818 for fixed F0 shape [1,361200,1]",
            "fixed_contract_only": True,
            "tool_sha256": {
                name: sha256(path) for name, path in tool_paths.items()
            },
        },
        "toolchain": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "kokoro": importlib.metadata.version("kokoro"),
            "onnx": onnx.__version__,
        },
        "output": {
            "ignored_path": str(args.output),
            "bytes": args.output.stat().st_size,
            "sha256": sha256(args.output),
            "export_seconds": export_seconds,
            "ir_version": graph.ir_version,
            "opset_imports": {
                entry.domain or "ai.onnx": entry.version
                for entry in graph.opset_import
            },
            "node_count": len(graph.graph.node),
            "initializer_count": len(graph.graph.initializer),
            "initializer_types": dict(sorted(initializer_types.items())),
            "operators": dict(sorted(operators.items())),
            "quantized_operator_count": quantized,
            "random_operator_count": random,
            "inputs": [value.name for value in graph.graph.input],
            "outputs": [value.name for value in graph.graph.output],
            "output_shapes": output_shapes,
        },
        "claim_boundary": "Fixed-contract canonical-v2 FP32 ONNX export derived from official weights/frontend inputs; not arbitrary text/shape, QNN assignment, physical HTP execution, benchmark performance, or listening acceptance.",
    }
    args.provenance.parent.mkdir(parents=True, exist_ok=True)
    args.provenance.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record["output"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
