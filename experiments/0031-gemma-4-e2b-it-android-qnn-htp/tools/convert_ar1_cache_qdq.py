#!/usr/bin/env python3
"""Add explicit uint16 QAT value-cache boundaries to AR1, then QNN-convert it."""
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
PATCHED = EXP / ".local/qairt-2.49.40-ar1-cache-qdq"
CONVERT_CACHE = EXP / ".local/qairt-2.49.40-cache-aligned-v5"
EXPECTED = {
    "ar1_onnx": "9f3077b4a8ccec48781843f6391bb9d77bf4d0c2578a864c108a916b24c9e472",
    "ar1_encodings": "0dbb1aad69b419594707cc45d31656b95457b5a78c0bce462f1f03db77bfe2a8",
    "ar128_encodings": "7e26400519d338171bc9d3e9c87182ef0853ce6dfc0c543ad85ea2d815dea251",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encoding_map(path: Path) -> dict[str, dict[str, object]]:
    return {item["name"]: item for item in json.loads(path.read_text())["activation_encodings"]}


def replace_with_hardlink(source: Path, destination: Path) -> None:
    if destination.exists():
        if os.path.samefile(source, destination):
            return
        destination.unlink()
    os.link(source, destination)


def main() -> None:
    import numpy as np
    import onnx
    from onnx import helper, numpy_helper
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
    if sha256(Path(ar1.onnx_path)) != EXPECTED["ar1_onnx"]:
        raise RuntimeError("AR1 ONNX identity mismatch")
    if sha256(Path(ar1.encodings_path)) != EXPECTED["ar1_encodings"]:
        raise RuntimeError("AR1 encodings identity mismatch")
    if sha256(Path(ar128.encodings_path)) != EXPECTED["ar128_encodings"]:
        raise RuntimeError("AR128 encodings identity mismatch")

    ar1_enc = encoding_map(Path(ar1.encodings_path))
    ar128_enc = encoding_map(Path(ar128.encodings_path))
    model = onnx.load(ar1.onnx_path, load_external_data=False)
    producers = {output: node for node in model.graph.node for output in node.output}
    graph_outputs = {output.name: output for output in model.graph.output}
    alignments = []
    q_nodes = []
    for input_name, target in sorted(ar128_enc.items()):
        if not (input_name.endswith("_in") and "_value_" in input_name):
            continue
        output_name = input_name[:-3] + "_out"
        source = ar1_enc.get(output_name)
        if source is None or output_name not in graph_outputs or output_name not in producers:
            raise RuntimeError(f"missing AR1 cache output boundary: {output_name}")
        fields = ("bw", "dtype", "is_sym", "offset", "scale")
        if any(source[field] != target[field] for field in fields):
            raise RuntimeError(f"published cache encodings differ: {output_name} -> {input_name}")
        if int(target["bw"]) != 16 or int(target["offset"][0]) != -32768:
            raise RuntimeError(f"unexpected target encoding: {input_name}")
        scale = np.asarray(float(target["scale"][0]), dtype=np.float32)
        zero_point = np.asarray(32768, dtype=np.uint16)
        internal_name = output_name + "__float_before_q"
        fork_name = output_name + "__float_for_q"
        scale_name = output_name + "__scale"
        zero_name = output_name + "__zero_point"
        producer = producers[output_name]
        producer.output[:] = [internal_name if value == output_name else value for value in producer.output]
        for consumer in model.graph.node:
            consumer.input[:] = [internal_name if value == output_name else value for value in consumer.input]
        graph_outputs[output_name].type.tensor_type.elem_type = onnx.TensorProto.UINT16
        model.graph.initializer.extend([
            numpy_helper.from_array(scale, name=scale_name),
            numpy_helper.from_array(zero_point, name=zero_name),
        ])
        q_nodes.extend([
            helper.make_node(
                "Cast", [internal_name], [fork_name], to=onnx.TensorProto.FLOAT,
                name=output_name + "__cache_output_fork",
            ),
            helper.make_node(
                "QuantizeLinear", [fork_name, scale_name, zero_name], [output_name],
                name=output_name + "__uint16_cache_boundary",
            ),
        ])
        alignments.append({
            "ar1_output": output_name, "ar128_input": input_name,
            "onnx_output_datatype": "UINT16", "scale": float(scale),
            "zero_point": 32768, "qnn_offset": -32768,
        })
    if len(alignments) != 15:
        raise RuntimeError(f"expected 15 value-cache boundaries, got {len(alignments)}")
    model.graph.node.extend(q_nodes)

    PATCHED.mkdir(parents=True, exist_ok=True)
    patched_onnx = PATCHED / "ar1_cl4096_1_of_1.onnx"
    patched_encodings = PATCHED / "ar1_cl4096_1_of_1.encodings"
    shutil.copy2(ar1.encodings_path, patched_encodings)
    source_data = Path(ar1.data_path)
    patched_data = PATCHED / source_data.name
    replace_with_hardlink(source_data, patched_data)
    onnx.save_model(model, patched_onnx, save_as_external_data=False)
    previous_cwd = Path.cwd()
    try:
        os.chdir(PATCHED)
        onnx.checker.check_model(onnx.load(patched_onnx.name, load_external_data=False))
    finally:
        os.chdir(previous_cwd)
    patched_onnx.chmod(0o600)
    patched_encodings.chmod(0o600)
    patched_data.chmod(0o600)
    PATCHED.chmod(0o700)

    patched_ar1 = ar1.model_copy(update={
        "onnx_path": patched_onnx, "data_path": patched_data,
        "encodings_path": patched_encodings,
    })
    CONVERT_CACHE.mkdir(parents=True, exist_ok=True)
    builder.cache_dir = CONVERT_CACHE
    builder._conversion_config.input_tensor_config = get_input_layout(patched_onnx)
    builder._conversion_config.output_tensor_config = []
    print(json.dumps({
        "event": "ar1_cache_qdq_conversion_start",
        "qairt_version": "2.49.40.260810", "target": "chipset:SM8550",
        "source_onnx_sha256": EXPECTED["ar1_onnx"],
        "source_encodings_sha256": EXPECTED["ar1_encodings"],
        "patched_onnx_sha256": sha256(patched_onnx),
        "patched_encodings_sha256": sha256(patched_encodings),
        "shared_external_data_sha256": sha256(patched_data),
        "graph_output_count": len(model.graph.output),
        "explicit_uint16_cache_boundaries": alignments,
        "boundary_semantics": "ONNX float Cast fork plus QuantizeLinear(float, float32 scale, uint16 zero-point) at graph output",
        "checkpoint_modified": False, "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)
    try:
        converted = builder.convert(patched_ar1, builder._conversion_config, builder._calibration_config)
        path = Path(converted.module.path)
    except Exception as error:
        print(json.dumps({
            "event": "ar1_cache_qdq_conversion_failed",
            "exception_type": type(error).__name__, "exception_message": str(error),
            "phone_access": False, "inference": False,
        }, sort_keys=True), flush=True)
        raise
    print(json.dumps({
        "event": "ar1_cache_qdq_conversion_complete", "model_name": converted.name,
        "dlc_path": str(path), "dlc_bytes": path.stat().st_size, "dlc_sha256": sha256(path),
        "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
