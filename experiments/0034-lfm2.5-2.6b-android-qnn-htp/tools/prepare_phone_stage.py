#!/usr/bin/env python3
"""Assemble the ignored, hash-bound Android stage for the 0034 viability gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

import numpy as np
import onnx


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hardlink(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    os.link(source, destination)


def external_fields(tensor: onnx.TensorProto) -> tuple[str, int, int]:
    fields = {item.key: item.value for item in tensor.external_data}
    return fields["location"], int(fields.get("offset", "0")), int(fields["length"])


def copy_external_slice(model_dir: Path, tensor: onnx.TensorProto, output: Path) -> None:
    location, offset, length = external_fields(tensor)
    with (model_dir / location).open("rb") as source, output.open("wb") as destination:
        source.seek(offset)
        remaining = length
        while remaining:
            chunk = source.read(min(8 * 1024 * 1024, remaining))
            if not chunk:
                raise EOFError(tensor.name)
            destination.write(chunk)
            remaining -= len(chunk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-source", type=Path, required=True)
    parser.add_argument("--aot-dir", type=Path, required=True)
    parser.add_argument("--android-deps", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--libcxx", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    stage = args.output_dir
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / "profiles").mkdir()

    summary = json.loads((args.aot_dir / "summary.json").read_text())
    for part in summary["parts"]:
        name = part["name"]
        hardlink(args.aot_dir / name / "context.onnx", stage / "contexts" / name / "context.onnx")
        hardlink(args.aot_dir / name / "context_qnn.bin", stage / "contexts" / name / "context_qnn.bin")

    model = onnx.load(str(args.pipeline_source), load_external_data=False)
    initializers = {item.name: item for item in model.graph.initializer}
    embedding = {
        "model_embed_tokens_weight_quant": "embedding-quant.u8",
        "model_embed_tokens_weight_scales": "embedding-scales.f32le",
        "model_embed_tokens_weight_zp": "embedding-zp.u8",
    }
    for tensor_name, filename in embedding.items():
        copy_external_slice(args.pipeline_source.parent, initializers[tensor_name], stage / filename)

    hardlink(args.runner, stage / "lfm2_qnn_runner")
    hardlink(args.prompt, stage / "short.int32le")
    libraries = {
        args.android_deps / "ort/jni/arm64-v8a/libonnxruntime.so": "libonnxruntime.so",
        args.android_deps / "qnnplugin/jni/arm64-v8a/libonnxruntime_providers_qnn.so": "libonnxruntime_providers_qnn.so",
        args.android_deps / "qnnruntime/jni/arm64-v8a/libQnnHtp.so": "libQnnHtp.so",
        args.android_deps / "qnnruntime/jni/arm64-v8a/libQnnSystem.so": "libQnnSystem.so",
        args.android_deps / "qnnruntime/jni/arm64-v8a/libQnnHtpV73Stub.so": "libQnnHtpV73Stub.so",
        args.android_deps / "qnnruntime/jni/arm64-v8a/libQnnHtpV73Skel.so": "libQnnHtpV73Skel.so",
        args.libcxx: "libc++_shared.so",
    }
    for source, name in libraries.items():
        hardlink(source, stage / name)

    retained = sorted(path for path in stage.rglob("*") if path.is_file())
    entries = []
    with (stage / "SHA256SUMS").open("w") as manifest:
        for path in retained:
            relative = path.relative_to(stage).as_posix()
            digest = sha256(path)
            manifest.write(f"{digest}  {relative}\n")
            entries.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest})
    metadata = {
        "schema_version": 1,
        "classification": "ignored_license_controlled_android_viability_stage",
        "experiment": "0034-lfm2.5-2.6b-android-qnn-htp",
        "route": "explicit CPU Q4 embedding; 263 fallback-disabled SM8550/V73 QNN contexts; CPU greedy reduction",
        "bounded_request": {"tier": "short", "prompt_tokens": 171, "max_new_tokens": 16},
        "files": entries,
        "total_bytes_excluding_manifests": sum(item["bytes"] for item in entries),
        "retained_outside_git": True,
    }
    (stage / "stage.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    with (stage / "SHA256SUMS").open("a") as manifest:
        manifest.write(f"{sha256(stage / 'stage.json')}  stage.json\n")
    print(json.dumps({"files": len(entries) + 1, "bytes": metadata["total_bytes_excluding_manifests"], "stage": str(stage)}, indent=2))


if __name__ == "__main__":
    main()
