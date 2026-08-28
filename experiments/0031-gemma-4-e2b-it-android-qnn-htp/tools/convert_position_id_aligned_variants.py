#!/usr/bin/env python3
"""Rename global RoPE inputs to Genie's documented/default names and reconvert both variants."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from qairt_constant_compat import install

EXP = Path(__file__).resolve().parents[1]
CKPT = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16"
SOURCE_CACHE = EXP / ".local/qairt-2.49.40-transform-compat"
CORRECTED_AR1 = EXP / ".local/qairt-2.49.40-ar1-cache-qdq"
PATCHED_ROOT = EXP / ".local/qairt-2.49.40-position-id-aligned"
CONVERT_CACHE = EXP / ".local/qairt-2.49.40-cache-aligned-v6"
EXPECTED = {
    "ar1_qdq_onnx": "2be60a02bc205fe43ba68b45f110c70071fdedd8842a5b8774af2b65675bb40e",
    "ar1_encodings": "0dbb1aad69b419594707cc45d31656b95457b5a78c0bce462f1f03db77bfe2a8",
    "ar128_onnx": "d1171990305f50e89076709dcf024056f66393a90d35a79e774dc5612b0e3a9a",
    "ar128_encodings": "7e26400519d338171bc9d3e9c87182ef0853ce6dfc0c543ad85ea2d815dea251",
    "shared_data": "b9b73b984c2258099bc77ce6d1e2aa92d12bb67abe456e5ef509136d7494a65d",
}
RENAMES = {
    "position_ids_global_cos": "position_ids_cos",
    "position_ids_global_sin": "position_ids_sin",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_with_hardlink(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if os.path.samefile(source, destination):
            return
        destination.unlink()
    os.link(source, destination)


def patch_variant(source: object, ar: int, onnx_source: Path, encodings_source: Path) -> tuple[object, dict[str, object]]:
    import onnx

    if sha256(onnx_source) != EXPECTED[f"ar{ar}_{'qdq_' if ar == 1 else ''}onnx"]:
        raise RuntimeError(f"AR{ar} source ONNX identity mismatch")
    if sha256(encodings_source) != EXPECTED[f"ar{ar}_encodings"]:
        raise RuntimeError(f"AR{ar} source encodings identity mismatch")
    source_data = Path(source.data_path)
    if sha256(source_data) != EXPECTED["shared_data"]:
        raise RuntimeError(f"AR{ar} source external-data identity mismatch")

    destination = PATCHED_ROOT / f"ar{ar}_cl4096_1_of_1"
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    onnx_out = destination / f"ar{ar}_cl4096_1_of_1.onnx"
    encodings_out = destination / f"ar{ar}_cl4096_1_of_1.encodings"
    data_out = destination / source_data.name

    model = onnx.load(onnx_source, load_external_data=False)
    graph_inputs = {item.name: item for item in model.graph.input}
    for old, new in RENAMES.items():
        if old not in graph_inputs or new in graph_inputs:
            raise RuntimeError(f"AR{ar} positional input rename precondition failed: {old} -> {new}")
        graph_inputs[old].name = new
        for node in model.graph.node:
            node.input[:] = [new if value == old else value for value in node.input]
    onnx.save_model(model, onnx_out, save_as_external_data=False)
    replace_with_hardlink(source_data, data_out)

    encodings_text = encodings_source.read_text()
    for old, new in RENAMES.items():
        needle = f'"name": "{old}"'
        if encodings_text.count(needle) != 1:
            raise RuntimeError(f"AR{ar} encoding rename precondition failed: {old}")
        encodings_text = encodings_text.replace(needle, f'"name": "{new}"')
    encodings_out.write_text(encodings_text)

    previous_cwd = Path.cwd()
    try:
        os.chdir(destination)
        onnx.checker.check_model(onnx.load(onnx_out.name, load_external_data=False))
    finally:
        os.chdir(previous_cwd)
    for path in (onnx_out, encodings_out, data_out):
        path.chmod(0o600)
    destination.chmod(0o700)
    patched = source.model_copy(update={
        "onnx_path": onnx_out, "data_path": data_out, "encodings_path": encodings_out,
    })
    return patched, {
        "ar": ar,
        "source_onnx_sha256": sha256(onnx_source),
        "source_encodings_sha256": sha256(encodings_source),
        "patched_onnx_sha256": sha256(onnx_out),
        "patched_encodings_sha256": sha256(encodings_out),
        "external_data_sha256": EXPECTED["shared_data"],
        "input_renames": RENAMES,
        "onnx_checker_passed": True,
    }


def main() -> None:
    from qairt.gen_ai_api.builders.gen_ai_utils import get_input_layout
    from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory

    install()
    builder = GenAIBuilderFactory.create(
        str(CKPT), "HTP", cache_root=str(SOURCE_CACHE),
        tokenizer_path=str(CKPT / "tokenizer.json"), config_path=str(CKPT / "config.json"),
    )
    builder.set_targets(["chipset:SM8550"])
    transform = builder._transformation_config.model_transformer_config
    transform.arn_cl_options.auto_regression_number = [1, 128]
    transform.arn_cl_options.context_length = [4096]
    transform.split_model.num_splits = 1
    transform.split_model.split_embedding = False
    transform.split_model.split_lm_head = False
    builder.set_transformation_options(transform)
    transformed = builder.transform(
        model_path=builder.framework_model_path, config=builder._transformation_config,
        encodings_path=SOURCE_CACHE / "model.encodings", lora_output_config=None,
    )
    ar1, ar128 = transformed[0][0], transformed[1][0]
    patched = []
    evidence = []
    for ar, source, onnx_source, encodings_source in (
        (1, ar1, CORRECTED_AR1 / "ar1_cl4096_1_of_1.onnx", CORRECTED_AR1 / "ar1_cl4096_1_of_1.encodings"),
        (128, ar128, Path(ar128.onnx_path), Path(ar128.encodings_path)),
    ):
        item, item_evidence = patch_variant(source, ar, onnx_source, encodings_source)
        patched.append((ar, item))
        evidence.append(item_evidence)

    CONVERT_CACHE.mkdir(parents=True, exist_ok=True)
    builder.cache_dir = CONVERT_CACHE
    print(json.dumps({
        "event": "position_id_aligned_conversion_start",
        "qairt_version": "2.49.40.260810", "target": "chipset:SM8550",
        "checkpoint_modified": False, "rename_is_numerically_identity": True,
        "variants": evidence, "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)
    outputs = []
    try:
        for ar, exported in patched:
            builder._conversion_config.input_tensor_config = get_input_layout(exported.onnx_path)
            builder._conversion_config.output_tensor_config = []
            converted = builder.convert(exported, builder._conversion_config, builder._calibration_config)
            path = Path(converted.module.path)
            outputs.append({
                "ar": ar, "name": converted.name, "path": str(path),
                "bytes": path.stat().st_size, "sha256": sha256(path),
            })
    except Exception as error:
        print(json.dumps({
            "event": "position_id_aligned_conversion_failed",
            "exception_type": type(error).__name__, "exception_message": str(error),
            "completed_models": outputs, "phone_access": False, "inference": False,
        }, sort_keys=True), flush=True)
        raise
    print(json.dumps({
        "event": "position_id_aligned_conversion_complete", "converted_models": outputs,
        "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
