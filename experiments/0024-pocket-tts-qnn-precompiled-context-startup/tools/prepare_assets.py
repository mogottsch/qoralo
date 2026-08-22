#!/usr/bin/env python3
"""Create hash-bound canonical-v2 Pocket token, Alba-cache, and noise fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import sentencepiece as spm
from safetensors import safe_open

EXPECTED = {
    "transcript": "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67",
    "weights": "be9c6b4876d3f30740a8225dfcaa2e43dc4aeb753c15272735bee16bbb4abb0a",
    "tokenizer": "d461765ae179566678c93091c5fa6f2984c31bbe990bf1aa62d92c64d91bc3f6",
    "alba": "e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c",
    "tokens": "56d50c958627be19a7f2c86dde68a537a80f3f6d9087c16f55fde58c4d117c82",
    "cache": "eb6e2d714fe75cb9a726c7742f32e7c6b500cc6de4dae8b533f2bfa7b41bc6d2",
    "noise": "c70130d0d42d7a281bad2258b7820fab85d5cd0c6b869b463a1a3281869ddbb1",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--alba", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ("transcript", "weights", "tokenizer", "alba"):
        path = getattr(args, name)
        if sha(path) != EXPECTED[name]:
            raise SystemExit(f"{name} hash mismatch: {sha(path)}")

    transcript = args.transcript.read_bytes()
    if len(transcript) != 226 or transcript.endswith(b"\n"):
        raise SystemExit("canonical transcript byte contract failed")
    processor = spm.SentencePieceProcessor(model_file=str(args.tokenizer))
    ids = np.asarray(processor.encode(transcript.decode("utf-8")), dtype="<i8")
    if ids.shape != (64,):
        raise SystemExit(f"expected 64 tokens, got {ids.shape}")
    token_path = args.output / "canonical-token-ids-64.i64"
    token_path.write_bytes(ids.tobytes())

    parts: list[np.ndarray] = []
    with safe_open(str(args.alba), framework="np") as source:
        for layer in range(6):
            key = f"transformer.layers.{layer}.self_attn/cache"
            offset_key = f"transformer.layers.{layer}.self_attn/offset"
            value = np.ascontiguousarray(source.get_tensor(key), dtype="<f4")
            offset = np.asarray(source.get_tensor(offset_key), dtype=np.int64)
            if value.shape != (2, 1, 126, 16, 64) or offset.tolist() != [126]:
                raise SystemExit(f"unexpected Alba ABI at layer {layer}")
            parts.append(value)
    cache = np.concatenate([part.reshape(-1) for part in parts]).astype("<f4")
    cache_path = args.output / "alba-flow-cache-v1.f32"
    cache_path.write_bytes(cache.tobytes())

    noise = np.random.RandomState(0).normal(0, np.sqrt(0.3), (292, 32)).astype("<f4")
    noise_path = args.output / "numpy-randomstate-seed0-temp0p3-292x32.f32"
    noise_path.write_bytes(noise.tobytes())
    for name, path in (("tokens", token_path), ("cache", cache_path), ("noise", noise_path)):
        if sha(path) != EXPECTED[name]:
            raise SystemExit(f"{name} derivative hash mismatch: {sha(path)}")

    report = {
        "schema_version": 1,
        "route": "pocket-fixed-alba-text64-cache512-canonical-v2-0024-reconstruction-derivative",
        "canonical_transcript": {
            "bytes": len(transcript), "trailing_newline": False,
            "sha256": sha(args.transcript), "utf8": transcript.decode("utf-8"),
        },
        "model": {"weights_sha256": sha(args.weights), "tokenizer_sha256": sha(args.tokenizer),
                  "alba_state_sha256": sha(args.alba), "voice_contract": "fixed Alba; not voice cloning"},
        "frontend": {"token_count": 64, "token_ids": ids.tolist(), "token_fixture_sha256": sha(token_path)},
        "fixtures": {"alba_cache_pack_sha256": sha(cache_path), "noise_sha256": sha(noise_path),
                     "noise_algorithm": "NumPy RandomState MT19937 normal", "seed": 0,
                     "temperature": 0.3, "noise_shape": [292, 32]},
        "static_abi": {"capacity": 512, "voice_positions": 126, "text_positions": 64,
                       "maximum_generated_positions": 292, "bos_absolute_position": 190},
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
