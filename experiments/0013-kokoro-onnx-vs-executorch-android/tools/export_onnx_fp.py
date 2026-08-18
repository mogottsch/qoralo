#!/usr/bin/env python3
"""Export the exact pinned Kokoro v1.0 weights to controlled FP ONNX.

This is a fixed-contract mobile representation, not a new checkpoint. It uses
an ONNX STFT symbolic plus a source-equivalent real iSTFT decomposition and
materializes the official model's two stochastic inputs from the frozen seed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from collections import Counter
from pathlib import Path

import onnx
import torch
from kokoro import KModel
from kokoro.model import KModelForONNX

from deterministic_sine import SeededSineGen
from kokoro_contract import frontend, sha256_file
from onnx_exact_stft import OnnxExactSTFT

EXPECTED = {
    "model": (327_212_226, "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"),
    "voice": (523_425, "0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff"),
    "config": (2_351, "5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f"),
    "tokens": (687, "6ebb6bb288f20f3ae8d004d3c2ca27697da27c037d75e81a60e2a6a663f95425"),
    "lexicon": (5_956_885, "7daaab53a181be9885b853a8582bf1838186317e5dadacbcef9c426d6fa0da14"),
}
SEED = 20_260_818
F0_SHAPE = (1, 182_400, 1)


def verify(path: Path, key: str) -> None:
    size, digest = EXPECTED[key]
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"{key} is not a regular file: {path}")
    if path.stat().st_size != size or sha256_file(path) != digest:
        raise RuntimeError(f"{key} pin mismatch: {path}")


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--voice", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--tokens", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    for key in ("model", "voice", "config", "tokens", "lexicon"):
        verify(getattr(args, key), key)
    text = args.transcript.read_text(encoding="utf-8")
    contract = frontend(text, args.tokens, args.lexicon)
    if len(contract.segments) != 1 or contract.style_indices != (123,):
        raise RuntimeError("frozen frontend shape drift")

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
        f0_shape=F0_SHAPE, seed=SEED
    )
    wrapper = KModelForONNX(model).cpu().eval()
    token_ids = torch.tensor(contract.segments[0], dtype=torch.long).unsqueeze(0)
    voice_pack = torch.load(args.voice, map_location="cpu", weights_only=True)
    if tuple(voice_pack.shape) != (510, 1, 256) or voice_pack.dtype != torch.float32:
        raise RuntimeError("official voice tensor contract drift")
    style = voice_pack[contract.style_indices[0]].contiguous()
    speed = torch.tensor([1.0], dtype=torch.float32)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    torch.onnx.export(
        wrapper,
        (token_ids, style, speed),
        str(args.output),
        input_names=["tokens", "style", "speed"],
        output_names=["audio", "pred_dur"],
        opset_version=17,
        do_constant_folding=True,
        dynamo=False,
    )
    export_seconds = time.perf_counter() - started

    graph = onnx.load(args.output, load_external_data=False)
    onnx.checker.check_model(graph)
    operators = Counter(node.op_type for node in graph.graph.node)
    initializer_types = Counter(
        onnx.TensorProto.DataType.Name(value.data_type)
        for value in graph.graph.initializer
    )
    if any(name in operators for name in ("QuantizeLinear", "DequantizeLinear", "DynamicQuantizeLinear", "MatMulInteger")):
        raise RuntimeError("quantized operator unexpectedly present")
    if set(initializer_types) != {"FLOAT"}:
        raise RuntimeError(f"non-FP32 initializers: {initializer_types}")
    if any("Random" in name for name in operators):
        raise RuntimeError("uncontrolled random operator unexpectedly present")
    imports = {entry.domain or "ai.onnx": entry.version for entry in graph.opset_import}
    document = {
        "schema_version": 1,
        "status": "exported_and_onnx_checker_passed",
        "official_source": {
            "repository": "https://huggingface.co/hexgrad/Kokoro-82M",
            "revision": "f3ff3571791e39611d31c381e3a41a3af07b4987",
            "model": {"bytes": args.model.stat().st_size, "sha256": sha256_file(args.model)},
            "voice": {"bytes": args.voice.stat().st_size, "sha256": sha256_file(args.voice)},
            "config": {"bytes": args.config.stat().st_size, "sha256": sha256_file(args.config)},
        },
        "frontend": {
            "transcript_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "tokens_sha256": sha256_file(args.tokens),
            "lexicon_sha256": sha256_file(args.lexicon),
            "token_shape": list(token_ids.shape),
            "style_shape": list(style.shape),
            "style_index": contract.style_indices[0],
            "speed": 1.0,
        },
        "transformations": {
            "learned_weights_changed": False,
            "quantized": False,
            "stft": "PyTorch STFT represented by standard ONNX STFT; iSTFT represented by source-equivalent real overlap-add and Hann-envelope normalization",
            "random_inputs": "official torch.rand/torch.randn_like values materialized at fixed seed 20260818 and fixed F0 shape [1,182400,1]",
            "fixed_contract_only": True,
            "tool_sha256": {
                "export_onnx_fp.py": file_sha(Path(__file__)),
                "onnx_exact_stft.py": file_sha(Path(__file__).with_name("onnx_exact_stft.py")),
                "exact_stft.py": file_sha(Path(__file__).with_name("exact_stft.py")),
                "deterministic_sine.py": file_sha(Path(__file__).with_name("deterministic_sine.py")),
                "kokoro_contract.py": file_sha(Path(__file__).with_name("kokoro_contract.py")),
            },
        },
        "toolchain": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "kokoro": importlib.metadata.version("kokoro"),
            "onnx": onnx.__version__,
        },
        "output": {
            "path": args.output.name,
            "bytes": args.output.stat().st_size,
            "sha256": sha256_file(args.output),
            "export_seconds": export_seconds,
            "ir_version": graph.ir_version,
            "opset_imports": imports,
            "node_count": len(graph.graph.node),
            "initializer_count": len(graph.graph.initializer),
            "initializer_types": dict(sorted(initializer_types.items())),
            "operators": dict(sorted(operators.items())),
            "inputs": [value.name for value in graph.graph.input],
            "outputs": [value.name for value in graph.graph.output],
        },
    }
    args.provenance.parent.mkdir(parents=True, exist_ok=True)
    args.provenance.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document["output"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
