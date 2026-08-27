#!/usr/bin/env python3
"""Build Gemma4 token/PLE uint8 LUTs from the pinned public QAT checkpoint.

Packing and dequantization follow Hugging Face Transformers
``integrations/gemma_quant.py`` at commit
323f24345ed92f88e68a14aeef7db78ee2b52475 (Apache-2.0): low bits first,
unsigned codes shifted to signed, then multiplied by per-row/per-block scales.
Global uint8 requantization follows the QAIRT Gemma4 LUT example and the public
AI Hub Models rounding formula. Large tables are processed in row blocks.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from safetensors import safe_open

EXP = Path(__file__).resolve().parents[1]
CHECKPOINT = EXP / ".local/hf-checkpoint/model.safetensors"
OUT = EXP / ".local/runtime-bundle"
EXPECTED_CHECKPOINT_SHA256 = "efab429012b97ab986c4d4838a46ff3ad95d618b42ce514771ca40fadc76a9a4"
SOURCE_REVISION = "dd693ff40353f057ca5f07e945ad867f4afbf2ec"
FORMULA_REVISION = "323f24345ed92f88e68a14aeef7db78ee2b52475"
FORMULA_SHA256 = "9bf6d109dfc3540a46953f5b183af766edcf6a044529c12d7751db47ee71cc17"
VOCAB = 262144


@dataclass(frozen=True)
class LutSpec:
    name: str
    quantized_key: str
    scale_key: str
    bits: int
    width: int
    architectural_scale: float
    rows_per_block: int
    filename: str


SPECS = (
    LutSpec(
        name="embedding",
        quantized_key="model.language_model.embed_tokens.embedding_quantized",
        scale_key="model.language_model.embed_tokens.embedding_scale",
        bits=2,
        width=1536,
        architectural_scale=math.sqrt(1536),
        rows_per_block=4096,
        filename="embedding_int8_lut.bin",
    ),
    LutSpec(
        name="perlayer_embedding",
        quantized_key="model.language_model.embed_tokens_per_layer.embedding_quantized",
        scale_key="model.language_model.embed_tokens_per_layer.embedding_scale",
        bits=4,
        width=35 * 256,
        architectural_scale=math.sqrt(256),
        rows_per_block=512,
        filename="embed_tokens_per_layer_int8_lut.bin",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unpack_signed(packed: np.ndarray, bits: int, width: int) -> np.ndarray:
    if bits not in (2, 4, 8):
        raise ValueError(f"unsupported bits: {bits}")
    if bits == 8:
        return packed.view(np.int8)[..., :width]
    mask = (1 << bits) - 1
    shifts = range(0, 8, bits)
    values = [((packed >> shift) & mask).astype(np.int8) - (1 << (bits - 1)) for shift in shifts]
    return np.stack(values, axis=-1).reshape(*packed.shape[:-1], -1)[..., :width]


def dequantize_block(packed: np.ndarray, scales: np.ndarray, spec: LutSpec) -> np.ndarray:
    integers = unpack_signed(packed.astype(np.uint8, copy=False), spec.bits, spec.width)
    if spec.width % scales.shape[-1] != 0:
        raise ValueError("embedding width is not divisible by scale columns")
    scale = np.repeat(scales.astype(np.float32, copy=False), spec.width // scales.shape[-1], axis=-1)
    values = integers.astype(np.float32) * scale
    values *= np.float32(spec.architectural_scale)
    return values


def global_encoding(fmin: float, fmax: float) -> dict[str, float | int]:
    scale = (fmax - fmin) / 255
    offset = round(fmin / scale)
    return {"bw": 8, "scale": scale, "offset": offset, "min": fmin, "max": fmax}


def quantize_uint8(values: np.ndarray, scale: float, offset: int) -> np.ndarray:
    shifted = values / scale - offset
    rounded = np.floor(np.abs(shifted) + 0.5) * np.where(shifted < 0, -1, 1)
    return np.clip(rounded, 0, 255).astype(np.uint8)


def slices(handle: object, spec: LutSpec):
    quantized = handle.get_slice(spec.quantized_key)
    scales = handle.get_slice(spec.scale_key)
    qshape = quantized.get_shape()
    sshape = scales.get_shape()
    expected_packed = (spec.width + (8 // spec.bits) - 1) // (8 // spec.bits)
    if qshape != [VOCAB, expected_packed] or sshape[0] != VOCAB:
        raise ValueError(f"unexpected {spec.name} shapes: quantized={qshape}, scales={sshape}")
    for start in range(0, VOCAB, spec.rows_per_block):
        end = min(VOCAB, start + spec.rows_per_block)
        yield start, end, np.asarray(quantized[start:end]), np.asarray(scales[start:end])


def build_one(handle: object, spec: LutSpec) -> dict[str, object]:
    fmin = math.inf
    fmax = -math.inf
    blocks = 0
    for _, _, packed, scales in slices(handle, spec):
        values = dequantize_block(packed, scales, spec)
        fmin = min(fmin, float(values.min()))
        fmax = max(fmax, float(values.max()))
        blocks += 1
    encoding = global_encoding(fmin, fmax)

    output = OUT / spec.filename
    with output.open("wb") as dst:
        for _, _, packed, scales in slices(handle, spec):
            values = dequantize_block(packed, scales, spec)
            quantize_uint8(values, float(encoding["scale"]), int(encoding["offset"])).tofile(dst)
    expected_bytes = VOCAB * spec.width
    if output.stat().st_size != expected_bytes:
        raise RuntimeError(f"unexpected LUT size for {output}: {output.stat().st_size}")
    return {
        "name": spec.name,
        "filename": spec.filename,
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
        "source_quantized_key": spec.quantized_key,
        "source_scale_key": spec.scale_key,
        "source_bits": spec.bits,
        "width": spec.width,
        "vocab": VOCAB,
        "architectural_scale": spec.architectural_scale,
        "blocks_per_pass": blocks,
        "encoding": encoding,
    }


def main() -> None:
    actual = sha256(CHECKPOINT)
    if actual != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError(f"checkpoint hash mismatch: {actual}")
    OUT.mkdir(parents=True, exist_ok=True)
    with safe_open(str(CHECKPOINT), framework="numpy") as handle:
        luts = [build_one(handle, spec) for spec in SPECS]
    provenance = {
        "schema_version": 1,
        "source": {
            "repo": "google/gemma-4-E2B-it-qat-mobile-transformers",
            "revision": SOURCE_REVISION,
            "filename": CHECKPOINT.name,
            "bytes": CHECKPOINT.stat().st_size,
            "sha256": actual,
            "gated": False,
            "license": "apache-2.0",
        },
        "dequantization_formula": {
            "source": "https://github.com/huggingface/transformers/blob/323f24345ed92f88e68a14aeef7db78ee2b52475/src/transformers/integrations/gemma_quant.py",
            "revision": FORMULA_REVISION,
            "sha256": FORMULA_SHA256,
            "bit_order": "low bits first",
            "signed_mapping": {"int2": "unsigned 0..3 minus 2", "int4": "unsigned 0..15 minus 8"},
            "scale": "per-row/per-block multiplication, followed by architectural embedding scale",
        },
        "requantization": {
            "dtype": "uint8",
            "encoding": "single asymmetric scale/offset per complete table",
            "rounding": "nearest with halves away from zero, then clip 0..255",
        },
        "luts": luts,
    }
    path = OUT / "lut-provenance.json"
    path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    print(json.dumps(provenance, sort_keys=True))


if __name__ == "__main__":
    main()
