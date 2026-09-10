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
REUSE_RESULT = TRACK / "results/global-value-fp16-attempt-05/result.json"
REUSE_RESULT_SHA256 = "b298cab9c895955069b8b671835d4ac29d66b58aaac37ec8398bdc9f6621dcac"
REUSE_AR1_SHA256 = "4e67d80ea342088f5235a9238dc209739d8961083b08895fa066d6857687a6cc"
REUSE_AR1_BYTES = 2_356_848_948
REUSE_RUN_ID = "global-value-fp16-20260910T090755Z-attempt-05"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_identity(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if not path.is_file() or path.stat().st_size != expected_bytes:
        raise RuntimeError("reused AR1 DLC missing or byte-size mismatch")
    if sha256(path) != expected_sha256:
        raise RuntimeError("reused AR1 DLC SHA-256 mismatch")


def verify_ar1_reuse(dlc_path: Path) -> dict[str, object]:
    # Verify before importing QAIRT or modifying any artifact. Never infer reuse
    # eligibility from a filename, converter exit code, or proposed FP16 IO.
    if sha256(REUSE_RESULT) != REUSE_RESULT_SHA256:
        raise RuntimeError("attempt05 provenance result SHA-256 mismatch")
    evidence = json.loads(REUSE_RESULT.read_text())
    model = evidence["ar1_dlc"]
    if (evidence["run_id"] != REUSE_RUN_ID or model["ar"] != 1
            or model["bytes"] != REUSE_AR1_BYTES or model["sha256"] != REUSE_AR1_SHA256
            or not evidence["outcome"]["ar1_conversion_completed"]
            or not evidence["ar1_interface_inspection"]["datatype_scope_passed"]):
        raise RuntimeError("attempt05 AR1 provenance/interface gate mismatch")
    path = dlc_path.resolve()
    verify_file_identity(path, REUSE_AR1_BYTES, REUSE_AR1_SHA256)
    return {
        **model, "path": str(path), "origin": "reused_verified_attempt05",
        "converted_in_this_attempt": False,
        "provenance": {
            "commit": "d5e6b94", "run_id": REUSE_RUN_ID,
            "result_path": str(REUSE_RESULT), "result_sha256": REUSE_RESULT_SHA256,
            "original_dlc_path": model["path"],
            "interface_gate": "passed_actual_ar1_dlc_input_and_output_signatures",
            "cross_ar_contract_proven": False,
        },
    }


def conversion_ars(reused_ar1: dict[str, object] | None) -> tuple[int, ...]:
    return (128,) if reused_ar1 is not None else (1, 128)


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
        removed_encodings.add(input_name)
        # Source-bound AR128 outputs inherit encodings from their producers;
        # only corrected AR1 has explicit output entries.
        if ar == 1:
            removed_encodings.add(output_name)

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
    if before - len(encodings["activation_encodings"]) != len(removed_encodings):
        raise RuntimeError(f"AR{ar} explicit cache encoding removal count mismatch")

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
    parser.add_argument("--reuse-ar1-dlc", type=Path,
                        help="Verify/reuse the accepted attempt05 AR1 DLC; convert only AR128")
    args = parser.parse_args()
    run = args.run_dir.resolve()
    patched_root = run / "onnx"
    convert_cache = run / "dlc"
    if (patched_root.exists() or convert_cache.exists()
            or any((run / name).exists() for name in
                   ("ar1-reuse.json", "candidate-models.json", "converted-models.json", "patch-receipt.json"))):
        raise RuntimeError("refusing to overwrite an earlier attempt; use a fresh run directory")
    reused_ar1 = verify_ar1_reuse(args.reuse_ar1_dlc) if args.reuse_ar1_dlc is not None else None
    ars = conversion_ars(reused_ar1)
    reused_models = [reused_ar1] if reused_ar1 is not None else []
    if reused_ar1 is not None:
        (run / "ar1-reuse.json").write_text(json.dumps(reused_ar1, indent=2) + "\n")
        print(json.dumps({"event": "ar1_reuse_verified", "model": reused_ar1}, sort_keys=True), flush=True)
    (run / "candidate-models.json").write_text(json.dumps(reused_models, indent=2) + "\n")
    from qairt.gen_ai_api.builders.gen_ai_utils import get_input_layout
    from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory

    install()
    builder = GenAIBuilderFactory.create(
        str(CKPT), "HTP", cache_root=str(convert_cache),
        tokenizer_path=str(CKPT / "tokenizer.json"), config_path=str(CKPT / "config.json"),
    )
    builder.set_targets(["chipset:SM8550"])
    candidates = [patch_variant(ar, patched_root) for ar in ars]
    (run / "patch-receipt.json").write_text(json.dumps({
        "variants": [evidence for _, evidence in candidates],
        "script_sha256": sha256(HERE),
        "conversion_ars": list(ars), "reused_models": reused_models,
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
        "conversion_ars": list(ars), "reused_models": reused_models,
        "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)
    outputs = []
    try:
        for ar, (exported, _) in zip(ars, candidates, strict=True):
            builder._conversion_config.input_tensor_config = get_input_layout(exported.onnx_path)
            builder._conversion_config.output_tensor_config = []
            converted = builder.convert(exported, builder._conversion_config, builder._calibration_config)
            path = Path(converted.module.path)
            outputs.append({
                "ar": ar, "name": converted.name, "path": str(path),
                "bytes": path.stat().st_size, "sha256": sha256(path),
                "origin": "converted_in_this_attempt", "converted_in_this_attempt": True,
            })
            (run / "converted-models.json").write_text(json.dumps(outputs, indent=2) + "\n")
            (run / "candidate-models.json").write_text(json.dumps(reused_models + outputs, indent=2) + "\n")
    except Exception as error:
        print(json.dumps({
            "event": "global_value_fp16_conversion_failed",
            "exception_type": type(error).__name__, "exception_message": str(error),
            "completed_models": outputs, "reused_models": reused_models,
            "phone_access": False, "inference": False,
        }, sort_keys=True), flush=True)
        raise
    print(json.dumps({
        "event": "global_value_fp16_conversion_complete", "converted_models": outputs,
        "reused_models": reused_models,
        "cross_ar_contract_proven": False,
        "next_gate": "Inspect actual AR128 DLC interfaces and compare both AR cache contracts before compilation.",
        "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
