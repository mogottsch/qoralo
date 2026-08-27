#!/usr/bin/env python3
"""Validate the private Gemma4 LUT + Genie/QnnHtp runtime bundle."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from safetensors import safe_open

from build_embedding_luts import SPECS, dequantize_block

EXP = Path(__file__).resolve().parents[1]
BUNDLE = EXP / ".local/runtime-bundle"
CHECKPOINT = EXP / ".local/hf-checkpoint/model.safetensors"
OUT = EXP / "results/gemma4-sm8550-runtime-bundle/result.json"
EXPECTED_CONTEXT = "b8c169cedf9a00dde67e2e555805b1a773cb6fd128f5c3912a684c371f4af95a"
EXPECTED_TOKENIZER = "cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sample_fidelity(handle: object, spec: object, lut_path: Path, encoding: dict[str, object]) -> dict[str, object]:
    rows = sorted({0, 1, 2, 105, 106, 256000, 258880, 258881, 258882, 258883, 262143})
    quantized = handle.get_slice(spec.quantized_key)
    scales = handle.get_slice(spec.scale_key)
    packed = np.concatenate([np.asarray(quantized[row : row + 1]) for row in rows], axis=0)
    row_scales = np.concatenate([np.asarray(scales[row : row + 1]) for row in rows], axis=0)
    source = dequantize_block(packed, row_scales, spec)
    lut = np.memmap(lut_path, mode="r", dtype=np.uint8, shape=(262144, spec.width))
    codes = np.asarray(lut[rows])
    restored = (codes.astype(np.float32) + int(encoding["offset"])) * float(encoding["scale"])
    error = np.abs(source - restored)
    max_error = float(error.max())
    allowed = float(encoding["scale"]) / 2 + 1e-6
    if max_error > allowed:
        raise RuntimeError(f"{spec.name} LUT error {max_error} exceeds {allowed}")
    return {
        "sample_row_ids": rows,
        "sample_values": int(source.size),
        "max_abs_error": max_error,
        "mean_abs_error": float(error.mean()),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "half_step_error_bound": allowed,
        "within_half_step": True,
    }


def main() -> None:
    provenance = json.loads((BUNDLE / "lut-provenance.json").read_text())
    manifest = json.loads((BUNDLE / "runtime-manifest.json").read_text())
    config = json.loads((BUNDLE / "gemma4-e2b-htp-cl4096-greedy.json").read_text())
    file_manifest = manifest["files"]
    for name, identity in file_manifest.items():
        path = BUNDLE / name
        if path.stat().st_size != identity["bytes"] or sha256(path) != identity["sha256"]:
            raise RuntimeError(f"bundle identity mismatch: {name}")

    context_name = "models/weight_sharing_model_ar128_ar1_cl4096_scl512_1_of_1.serialized.bin"
    if file_manifest[context_name]["sha256"] != EXPECTED_CONTEXT:
        raise RuntimeError("wrong compiled context in bundle")
    if file_manifest["tokenizer.json"]["sha256"] != EXPECTED_TOKENIZER:
        raise RuntimeError("wrong tokenizer in bundle")

    dialog = config["dialog"]
    if dialog["engine"]["backend"]["type"] != "QnnHtp":
        raise RuntimeError("runtime backend is not QnnHtp")
    if dialog["context"]["size"] != 4096 or dialog["max-num-tokens"] != 2048:
        raise RuntimeError("runtime context/output ceiling mismatch")
    if not dialog["sampler"]["greedy"] or dialog["sampler"]["top-k"] != 1:
        raise RuntimeError("runtime sampling is not greedy")
    if dialog["engine"]["model"]["binary"]["ctx-bins"] != [f"./{context_name}"]:
        raise RuntimeError("runtime context path mismatch")

    luts = {item["name"]: item for item in provenance["luts"]}
    fidelity = {}
    with safe_open(str(CHECKPOINT), framework="numpy") as handle:
        for spec in SPECS:
            item = luts[spec.name]
            fidelity[spec.name] = sample_fidelity(
                handle, spec, BUNDLE / item["filename"], item["encoding"]
            )
    if dialog["embedding"]["quant-param"] != {
        "scale": luts["embedding"]["encoding"]["scale"],
        "offset": luts["embedding"]["encoding"]["offset"],
    }:
        raise RuntimeError("token LUT config encoding mismatch")
    if dialog["perlayer-embedding"]["quant-param"] != {
        "scale": luts["perlayer_embedding"]["encoding"]["scale"],
        "offset": luts["perlayer_embedding"]["encoding"]["offset"],
    }:
        raise RuntimeError("PLE LUT config encoding mismatch")

    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_runtime_bundle_and_lut_fidelity",
        "claim_boundary": (
            "A private Genie bundle now binds the SM8550/v73 context, exact tokenizer, QnnHtp runtime libraries, "
            "and source-derived token/PLE LUTs whose sampled dequantization error is within half of one uint8 step. "
            "This is host preparation only; no Android staging, physical HTP loading/execution, text, or performance is claimed."
        ),
        "route": manifest["route"],
        "source": provenance["source"],
        "formula": provenance["dequantization_formula"],
        "luts": {
            name: {
                "filename": item["filename"],
                "bytes": item["bytes"],
                "sha256": item["sha256"],
                "source_bits": item["source_bits"],
                "width": item["width"],
                "architectural_scale": item["architectural_scale"],
                "encoding": item["encoding"],
                "fidelity": fidelity[name],
            }
            for name, item in luts.items()
        },
        "runtime": {
            "config_path": "gemma4-e2b-htp-cl4096-greedy.json",
            "config_sha256": file_manifest["gemma4-e2b-htp-cl4096-greedy.json"]["sha256"],
            "backend": "QnnHtp",
            "target": "SM8550/v73",
            "context_length": 4096,
            "ar_variants": [1, 128],
            "context_sha256": EXPECTED_CONTEXT,
            "tokenizer_sha256": EXPECTED_TOKENIZER,
            "sampling": "greedy",
            "max_new_tokens": 2048,
            "cache_groups": ["past_ global KV dim 512", "swa_ sliding-window KV dim 256/window 512"],
            "runtime_files": {
                name: file_manifest[name]
                for name in (
                    "bin/genie-app",
                    "lib/libGenie.so",
                    "lib/libQnnHtp.so",
                    "lib/libQnnSystem.so",
                    "lib/libQnnHtpV73Stub.so",
                    "lib/libQnnHtpV73Skel.so",
                    "htp_backend_ext_config.json",
                )
            },
        },
        "bundle_manifest": {
            "bytes": (BUNDLE / "runtime-manifest.json").stat().st_size,
            "sha256": sha256(BUNDLE / "runtime-manifest.json"),
            "large_or_restricted_files_stored_outside_git": True,
        },
        "requested": {
            "phone_access": False,
            "physical_htp_execution": False,
            "inference": False,
            "performance_campaign": False,
        },
        "next_gate": (
            "After explicit phone-priority transfer, acquire phone.lock for the full ADB lifecycle, stage to an "
            "experiment-specific directory, and run one bounded context-load/short-prompt viability request with verbose QNN/HTP evidence."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
