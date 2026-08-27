#!/usr/bin/env python3
"""Create non-secret provenance for the exact pinned LFM2.5 Q4 ONNX export."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

import onnx

EXP = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "ab00687315bc1298e9d54e9c4b611dde9867ccc2"
EXPORTER_REVISION = "9a23ddd23035165f7414a5de3220a51e85780f64"
EXPECTED_SOURCE = {
    "model-00001-of-00002.safetensors": (
        5_329_406_264,
        "05be188e6570a7642b4690545ab22ebf4d0a6068775dd776a452eebf738854cc",
    ),
    "model-00002-of-00002.safetensors": (
        65_021_192,
        "532f803a9e6f127adc124d977503b438d8cc9c18f96e0862bf6835e38867bca8",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--onnx", type=Path, required=True)
    parser.add_argument("--external-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_files = {}
    for name, (expected_bytes, expected_sha) in EXPECTED_SOURCE.items():
        path = args.source_dir / name
        actual = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        if actual != {"bytes": expected_bytes, "sha256": expected_sha}:
            raise RuntimeError(f"source identity mismatch for {name}: {actual}")
        source_files[name] = actual

    model = onnx.load(str(args.onnx), load_external_data=False)
    onnx.checker.check_model(str(args.onnx), full_check=False)
    ops = collections.Counter(
        f"{node.domain + ':' if node.domain else ''}{node.op_type}" for node in model.graph.node
    )
    if ops["Conv"] != 22 or ops["com.microsoft:GroupQueryAttention"] != 8:
        raise RuntimeError(f"architecture inventory mismatch: {ops}")

    exporter = EXP / ".local/liquidonnx"
    import subprocess

    revision = subprocess.check_output(
        ["git", "-C", str(exporter), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != EXPORTER_REVISION:
        raise RuntimeError(f"exporter revision mismatch: {revision}")

    result = {
        "schema_version": 1,
        "experiment": "0034-lfm2.5-2.6b-android-qnn-htp",
        "classification": "host_only_exact_export_provenance",
        "model": {
            "repository": "LiquidAI/LFM2.5-2.6B",
            "revision": SOURCE_REVISION,
            "source_files": source_files,
        },
        "exporter": {
            "repository": "https://github.com/Liquid4All/onnx-export.git",
            "revision": revision,
            "license_sha256": sha256(exporter / "LICENSE"),
            "license_matches_bound_model_license": True,
            "command_shape": "lfm2-export <pinned-local-source> --skip-export --precision q4 --no-split-data",
        },
        "quantization": {
            "format": "ONNX MatMulNBits/GatherBlockQuantized",
            "weight_bits": 4,
            "block_size": 32,
            "symmetric": True,
            "calibration": None,
            "calibration_null_reason": "weight-only symmetric block quantization does not use activation calibration",
        },
        "exported_graph": {
            "onnx": {
                "bytes": args.onnx.stat().st_size,
                "sha256": sha256(args.onnx),
            },
            "external_data": {
                "bytes": args.external_data.stat().st_size,
                "sha256": sha256(args.external_data),
                "retained_outside_git": True,
            },
            "ir_version": model.ir_version,
            "opsets": {item.domain or "ai.onnx": item.version for item in model.opset_import},
            "node_count": len(model.graph.node),
            "initializer_count": len(model.graph.initializer),
            "input_count": len(model.graph.input),
            "output_count": len(model.graph.output),
            "operator_counts": dict(sorted(ops.items())),
            "architecture_state_inventory": {
                "recurrent_conv_layers": ops["Conv"],
                "group_query_attention_layers": ops["com.microsoft:GroupQueryAttention"],
                "matmul_nbits": ops["com.microsoft:MatMulNBits"],
            },
            "onnx_checker": "passed_after_standard_rms_norm_rewrite",
        },
        "rms_norm_rewrite": {
            "tool": "tools/rewrite_rms_norm.py",
            "simplified_layer_norm_nodes": 76,
            "skip_simplified_layer_norm_nodes": 1,
            "formula": "x * scale / sqrt(reduce_mean(pow(x, 2), axis=-1) + 1e-5)",
            "reason": "LiquidONNX 9a23ddd emitted the contrib op in the standard domain; ORT 1.26 rejected it before provider selection.",
        },
        "claim_boundary": "This is exact source/export and host graph evidence only; it is not Android, QNN, HTP, performance, or campaign evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
