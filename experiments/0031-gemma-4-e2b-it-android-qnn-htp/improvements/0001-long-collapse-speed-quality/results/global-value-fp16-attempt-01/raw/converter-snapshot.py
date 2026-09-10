#!/usr/bin/env python3
"""Build an HTP-only candidate with FP16 global-attention value-cache IO."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
TRACK = HERE.parents[1]
EXP = HERE.parents[3]
sys.path.insert(0, str(EXP / "tools"))

from qairt_constant_compat import install  # noqa: E402
CKPT = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16"
SOURCE_ROOT = EXP / ".local/qairt-2.49.40-position-id-aligned"
EXPECTED = {
    1: {
        "onnx": "eb530a0bf7aedeabe7d7a706d69aa72168d415c6afdc948e6c642c54c550c478",
        "encodings": "a09c73d919cda428e53d3b0f3bc16ed079847ba696cca6026f47e59bfa5dce75",
    },
    128: {
        "onnx": "819a8af4d6244dc7cea57b5f930778d324b8b81c8012e981780fd4adcdf9fb89",
        "encodings": "9ed0d5deb5bff959c738dc3bca7994b1f7796f257377479c82959c5bb693e12f",
    },
}
EXPECTED_DATA = "b9b73b984c2258099bc77ce6d1e2aa92d12bb67abe456e5ef509136d7494a65d"
GLOBAL_LAYERS = (4, 9, 14)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hardlink(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Never replace artifacts from an earlier attempt.
    os.link(source, destination)


def patch_variant(ar: int, patched_root: Path) -> tuple[object, dict[str, object]]:
    import onnx
    from onnx import helper
    from qairt.optimizer.onnx.graph import ExportedFiles

    source_dir = SOURCE_ROOT / f"ar{ar}_cl4096_1_of_1"
    onnx_source = source_dir / f"ar{ar}_cl4096_1_of_1.onnx"
    encodings_source = source_dir / f"ar{ar}_cl4096_1_of_1.encodings"
    data_source = source_dir / f"ar{ar}_cl4096_1_of_1.data"
    if sha256(onnx_source) != EXPECTED[ar]["onnx"]:
        raise RuntimeError(f"AR{ar} source ONNX mismatch")
    if sha256(encodings_source) != EXPECTED[ar]["encodings"]:
        raise RuntimeError(f"AR{ar} source encodings mismatch")
    if sha256(data_source) != EXPECTED_DATA:
        raise RuntimeError(f"AR{ar} external data mismatch")

    output_dir = patched_root / f"ar{ar}_cl4096_1_of_1"
    output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    onnx_out = output_dir / onnx_source.name
    encodings_out = output_dir / encodings_source.name
    data_out = output_dir / data_source.name
    model = onnx.load(onnx_source, load_external_data=False)
    graph_inputs = {item.name: item for item in model.graph.input}
    graph_outputs = {item.name: item for item in model.graph.output}
    nodes = list(model.graph.node)
    removed_node_names = []
    input_casts = []
    output_casts = []
    removed_initializers = set()
    removed_encodings = set()

    for layer in GLOBAL_LAYERS:
        input_name = f"past_value_{layer}_h0_in"
        output_name = f"past_value_{layer}_h0_out"
        if input_name not in graph_inputs or output_name not in graph_outputs:
            raise RuntimeError(f"AR{ar} missing global value cache {layer}")

        internal_input = input_name + "__float_internal"
        graph_inputs[input_name].type.tensor_type.elem_type = onnx.TensorProto.FLOAT16
        for node in nodes:
            node.input[:] = [internal_input if value == input_name else value for value in node.input]
        input_casts.append(helper.make_node(
            "Cast", [input_name], [internal_input], to=onnx.TensorProto.FLOAT,
            name=input_name + "__fp16_to_float",
        ))
        graph_outputs[output_name].type.tensor_type.elem_type = onnx.TensorProto.FLOAT16

        if ar == 1:
            cast_name = output_name + "__cache_output_fork"
            q_name = output_name + "__uint16_cache_boundary"
            cast_node = next((node for node in nodes if node.name == cast_name), None)
            q_node = next((node for node in nodes if node.name == q_name), None)
            if cast_node is None or q_node is None:
                raise RuntimeError(f"AR1 QDQ boundary missing for {output_name}")
            cast_node.output[:] = [output_name]
            for attribute in cast_node.attribute:
                if attribute.name == "to":
                    attribute.i = onnx.TensorProto.FLOAT16
            removed_node_names.append(q_name)
            removed_initializers.update({output_name + "__scale", output_name + "__zero_point"})
        else:
            producer = next((node for node in nodes if output_name in node.output), None)
            if producer is None:
                raise RuntimeError(f"AR128 producer missing for {output_name}")
            internal_output = output_name + "__float_before_fp16"
            producer.output[:] = [internal_output if value == output_name else value for value in producer.output]
            for node in nodes:
                if node is producer:
                    continue
                node.input[:] = [internal_output if value == output_name else value for value in node.input]
            output_casts.append(helper.make_node(
                "Cast", [internal_output], [output_name], to=onnx.TensorProto.FLOAT16,
                name=output_name + "__float_to_fp16",
            ))
        removed_encodings.update({input_name, output_name})

    if ar == 1:
        kept = [node for node in nodes if node.name not in removed_node_names]
    else:
        kept = nodes
    model.graph.ClearField("node")
    model.graph.node.extend([*input_casts, *kept, *output_casts])
    kept_initializers = [item for item in model.graph.initializer if item.name not in removed_initializers]
    model.graph.ClearField("initializer")
    model.graph.initializer.extend(kept_initializers)

    encodings = json.loads(encodings_source.read_text())
    before = len(encodings["activation_encodings"])
    found = {item["name"] for item in encodings["activation_encodings"] if item["name"] in removed_encodings}
    if found != removed_encodings:
        raise RuntimeError(f"AR{ar} encoding removal mismatch: {found}")
    encodings["activation_encodings"] = [
        item for item in encodings["activation_encodings"] if item["name"] not in removed_encodings
    ]
    if before - len(encodings["activation_encodings"]) != 6:
        raise RuntimeError(f"AR{ar} expected six removed encodings")

    onnx.save_model(model, onnx_out, save_as_external_data=False)
    encodings_out.write_text(json.dumps(encodings, indent=2) + "\n")
    hardlink(data_source, data_out)
    previous_cwd = Path.cwd()
    try:
        os.chdir(output_dir)
        onnx.checker.check_model(onnx.load(onnx_out.name, load_external_data=False))
    finally:
        os.chdir(previous_cwd)
    for path in (onnx_out, encodings_out, data_out):
        path.chmod(0o600)
    output_dir.chmod(0o700)
    exported = ExportedFiles(
        onnx_path=onnx_out, data_path=data_out, encodings_path=encodings_out,
    )
    return exported, {
        "ar": ar,
        "source_onnx_sha256": EXPECTED[ar]["onnx"],
        "source_encodings_sha256": EXPECTED[ar]["encodings"],
        "candidate_onnx_sha256": sha256(onnx_out),
        "candidate_encodings_sha256": sha256(encodings_out),
        "external_data_sha256": EXPECTED_DATA,
        "global_fp16_inputs": [f"past_value_{layer}_h0_in" for layer in GLOBAL_LAYERS],
        "global_fp16_outputs": [f"past_value_{layer}_h0_out" for layer in GLOBAL_LAYERS],
        "removed_activation_encodings": sorted(removed_encodings),
        "onnx_checker_passed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    patched_root = run / "onnx"
    convert_cache = run / "dlc"
    if patched_root.exists() or convert_cache.exists():
        raise RuntimeError("refusing to overwrite an earlier attempt; use a fresh run directory")
    from qairt.gen_ai_api.builders.gen_ai_utils import get_input_layout
    from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory

    install()
    builder = GenAIBuilderFactory.create(
        str(CKPT), "HTP", cache_root=str(convert_cache),
        tokenizer_path=str(CKPT / "tokenizer.json"), config_path=str(CKPT / "config.json"),
    )
    builder.set_targets(["chipset:SM8550"])
    candidates = [patch_variant(ar, patched_root) for ar in (1, 128)]
    (run / "patch-receipt.json").write_text(json.dumps({
        "variants": [evidence for _, evidence in candidates],
        "script_sha256": sha256(HERE),
        "conversion_config": builder._conversion_config.model_dump(mode="json"),
    }, indent=2) + "\n")
    convert_cache.mkdir(parents=True, exist_ok=True)
    print(json.dumps({
        "event": "global_value_fp16_conversion_start",
        "qairt_version": "2.49.40.260810", "target": "chipset:SM8550",
        "candidate": "global_value_cache_fp16_layers_4_9_14",
        "checkpoint_modified": False, "external_data_modified": False,
        "transformer_backend": "HTP", "cpu_conversion_boundary": False,
        "variants": [evidence for _, evidence in candidates],
        "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)
    outputs = []
    try:
        for ar, (exported, _) in zip((1, 128), candidates, strict=True):
            builder._conversion_config.input_tensor_config = get_input_layout(exported.onnx_path)
            builder._conversion_config.output_tensor_config = []
            converted = builder.convert(exported, builder._conversion_config, builder._calibration_config)
            path = Path(converted.module.path)
            outputs.append({
                "ar": ar, "name": converted.name, "path": str(path),
                "bytes": path.stat().st_size, "sha256": sha256(path),
            })
            (run / "converted-models.json").write_text(json.dumps(outputs, indent=2) + "\n")
    except Exception as error:
        print(json.dumps({
            "event": "global_value_fp16_conversion_failed",
            "exception_type": type(error).__name__, "exception_message": str(error),
            "completed_models": outputs, "phone_access": False, "inference": False,
        }, sort_keys=True), flush=True)
        raise
    print(json.dumps({
        "event": "global_value_fp16_conversion_complete", "converted_models": outputs,
        "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
