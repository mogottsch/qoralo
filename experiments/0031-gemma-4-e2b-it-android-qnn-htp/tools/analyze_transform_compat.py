#!/usr/bin/env python3
"""Validate and summarize the successful Gemma4 transform-only compatibility run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import onnx

EXP = Path(__file__).resolve().parents[1]
RUN = EXP / ".local/qairt-2.49.40-transform-compat-run"
SOURCE = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16"
OUT = EXP / "results/qairt-2.49.40-transform-compat/result.json"
EXPECTED_SOURCE = {
    "onnx": "51d4e8183a6734a8c7bbd24ebc072768f080e54b011725ae645dfa32498bf0d0",
    "external_data": "e156c33d176273555003039959ecb0ae0ddc8a328eceeec1e8f4a6255840e072",
    "encodings": "254c439615e1c0a7b40fb0076c844cc3f9a5ec7ef0b93001077eec2adb228e9c",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_local(path: Path) -> str:
    return str(path.resolve().relative_to(EXP.resolve()))


def dims(value_info: onnx.ValueInfoProto) -> list[int | str]:
    result: list[int | str] = []
    for dim in value_info.type.tensor_type.shape.dim:
        if dim.HasField("dim_value"):
            result.append(dim.dim_value)
        elif dim.HasField("dim_param"):
            result.append(dim.dim_param)
        else:
            result.append("")
    return result


def parse_events() -> list[dict[str, object]]:
    events = []
    for line in (RUN / "stdout.log").read_text(errors="replace").splitlines():
        if line.startswith("{"):
            events.append(json.loads(line))
    return events


def inspect_artifact(item: dict[str, object]) -> dict[str, object]:
    onnx_path = Path(str(item["onnx_path"]))
    encodings_path = Path(str(item["encodings_path"]))
    data_path = onnx_path.with_suffix(".data")
    model = onnx.load(onnx_path, load_external_data=False)
    # Path form gives the checker the external-data base directory and avoids
    # embedding a >2 GiB model into an in-memory protobuf.
    onnx.checker.check_model(str(onnx_path), full_check=False)

    inputs = {value.name: dims(value) for value in model.graph.input}
    outputs = {value.name: dims(value) for value in model.graph.output}
    symbolic_inputs = {
        name: shape for name, shape in inputs.items() if any(not isinstance(dim, int) for dim in shape)
    }
    symbolic_outputs = {
        name: shape for name, shape in outputs.items() if any(not isinstance(dim, int) for dim in shape)
    }
    external_locations = set()
    max_end = 0
    external_count = 0
    for initializer in model.graph.initializer:
        if initializer.data_location != onnx.TensorProto.EXTERNAL:
            continue
        external_count += 1
        fields = {entry.key: entry.value for entry in initializer.external_data}
        external_locations.add(fields["location"])
        max_end = max(max_end, int(fields.get("offset", 0)) + int(fields["length"]))

    if symbolic_inputs or symbolic_outputs:
        raise RuntimeError(
            f"non-static transformed IO in {onnx_path}: inputs={symbolic_inputs}, outputs={symbolic_outputs}"
        )
    if external_locations != {data_path.name}:
        raise RuntimeError(f"unexpected external locations: {external_locations}")
    if max_end > data_path.stat().st_size:
        raise RuntimeError("external initializer range exceeds transformed data file")
    data_hash = sha256(data_path)

    return {
        "variant_index": item["variant_index"],
        "split_index": item["split_index"],
        "onnx_path": relative_local(onnx_path),
        "onnx_bytes": onnx_path.stat().st_size,
        "onnx_sha256": sha256(onnx_path),
        "encodings_path": relative_local(encodings_path),
        "encodings_bytes": encodings_path.stat().st_size,
        "encodings_sha256": sha256(encodings_path),
        "external_data_path": relative_local(data_path),
        "external_data_bytes": data_path.stat().st_size,
        "external_data_sha256": data_hash,
        "external_initializer_count": external_count,
        "external_max_offset_plus_length": max_end,
        "onnx_checker_passed": True,
        "all_graph_inputs_static": True,
        "all_graph_outputs_static": True,
        "inputs": inputs,
        "outputs": outputs,
        "node_count": len(model.graph.node),
    }


def main() -> None:
    events = parse_events()
    if [event.get("event") for event in events] != ["transform_start", "transform_complete"]:
        raise RuntimeError(f"unexpected events: {[event.get('event') for event in events]}")
    start, complete = events
    if start["source_identity"] != EXPECTED_SOURCE:
        raise RuntimeError("unexpected source identity at transform start")
    if complete["source_identity_after"] != EXPECTED_SOURCE or not complete["source_identity_unchanged"]:
        raise RuntimeError("source identity changed during transform")
    artifacts = [inspect_artifact(item) for item in complete["artifacts"]]
    if len(artifacts) != 2:
        raise RuntimeError(f"expected two AR variants, got {len(artifacts)}")

    stderr = (RUN / "stderr.log").read_text(errors="replace")
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_transform_only_compatibility_result",
        "claim_boundary": (
            "The unchanged public Gemma4 w4a16 graph was materialized into static AR1 and AR128, "
            "CL4096, one-split ONNX+encodings variants. This is not QNN conversion, HTP compilation, "
            "serialized-context creation, Android execution, or inference evidence."
        ),
        "qairt_version": start["qairt_version"],
        "target_configuration": start["target"],
        "heavy_ram_lock_held": True,
        "source_identity": EXPECTED_SOURCE,
        "source_identity_unchanged": True,
        "constant_inventory": start["constant_inventory"],
        "compatibility_patch": complete["compatibility_patch"],
        "transform": {
            "auto_regression_number": start["auto_regression_number"],
            "context_length": start["context_length"],
            "num_splits": start["num_splits"],
            "split_embedding": start["split_embedding"],
            "split_lm_head": start["split_lm_head"],
            "variant_count": complete["variant_count"],
            "artifacts": artifacts,
        },
        "warnings": {
            "unknown_architecture_generic_builder": "Architecture is unknown or unsupported" in stderr,
            "axis_denotation_shape_warning_count": stderr.count(
                "No axis denotation propagation rule for op 'Shape'"
            ),
            "axis_denotation_matmul_warning_count": stderr.count(
                "No axis denotation propagation rule for op 'MatMul'"
            ),
            "warning_boundary": (
                "Warnings are retained. They are not treated as transform failure because every exported graph "
                "input/output is independently verified static and ONNX checker passes; conversion has not yet been attempted."
            ),
        },
        "requested": {
            "qnn_conversion": False,
            "htp_compilation": False,
            "phone_access": False,
            "inference": False,
            "paid_workbench_job": False,
        },
        "raw_logs": {
            "stdout_bytes": (RUN / "stdout.log").stat().st_size,
            "stdout_sha256": sha256(RUN / "stdout.log"),
            "stderr_bytes": (RUN / "stderr.log").stat().st_size,
            "stderr_sha256": sha256(RUN / "stderr.log"),
        },
        "next_gate": (
            "Run QNN conversion for both bound variants, then compile a weight-shared serialized context "
            "for chipset:SM8550/HTP v73 before any phone access."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
