#!/usr/bin/env python3
"""Audit how prior qnn-net-run position raw files were interpreted."""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
import numpy as np
import yaml

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def lines_containing(path: Path, needles: list[str]) -> dict[str, list[int]]:
    lines = path.read_text(errors="replace").splitlines()
    return {needle: [index for index, line in enumerate(lines, 1) if needle in line] for needle in needles}

def graph_position(path: Path) -> dict:
    graph = json.loads(path.read_text())["info"]["graphs"][0]["info"]
    value = next(item["info"] for item in graph["graphInputs"] if item["info"]["name"] == "position_ids")
    return {"data_type": value["dataType"], "dimensions": value["dimensions"]}

def raw_audit(path: Path) -> dict:
    data = path.read_bytes()
    ints = struct.unpack(f"<{len(data) // 4}i", data)
    floats = struct.unpack(f"<{len(data) // 4}f", data)
    converted = tuple(int(value) for value in floats)
    return {
        "path_outside_git": str(path),
        "bytes": len(data),
        "sha256": sha256(path),
        "int32_count": len(ints),
        "int32_first": list(ints[:4]),
        "int32_last": list(ints[-4:]),
        "float32_reinterpret_first": list(floats[:4]),
        "float32_reinterpret_last": list(floats[-4:]),
        "float32_to_int64_unique": sorted(set(converted)),
        "all_converted_to_zero": set(converted) == {0},
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qairt-root", type=Path, required=True)
    parser.add_argument("--ar171-context-info", type=Path, required=True)
    parser.add_argument("--ar1-context-info", type=Path, required=True)
    parser.add_argument("--ar171-position", type=Path, required=True)
    parser.add_argument("--ar1-position", type=Path, required=True)
    parser.add_argument("--ar171-execution-metadata", type=Path, required=True)
    parser.add_argument("--ar1-execution-metadata", type=Path, required=True)
    parser.add_argument("--ar171-script", type=Path, required=True)
    parser.add_argument("--phase-script", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_root = args.qairt_root / "examples/QNN/SampleApp/SampleApp/src"
    main_cpp = source_root / "main.cpp"
    io_cpp = source_root / "Utils/IOTensor.cpp"
    data_cpp = source_root / "Utils/DataUtil.cpp"
    docs = args.qairt_root / "docs/QAIRT-Docs/QNN/general/tools.html"
    source_checks = {
        "main": lines_containing(main_cpp, [
            "parsedInputDataType     = iotensor::InputDataType::FLOAT",
            "case OPT_INPUT_DATA_TYPE:",
            "parsedInputDataType,",
        ]),
        "io": lines_containing(io_cpp, [
            "inputDataType == InputDataType::FLOAT",
            "QNN_TENSOR_GET_DATA_TYPE(input) != QNN_DATATYPE_FLOAT_32",
            "QNN_DATATYPE_FLOAT_32,",
            "copyFromFloatToNative(reinterpret_cast<float*>(fileToBuffer), input)",
            "case QNN_DATATYPE_INT_64:",
            "datautil::castFromFloat<int64_t>",
        ]),
        "data": lines_containing(data_cpp, [
            "out[i] = static_cast<T_QuantType>(in[i]);",
        ]),
        "docs": lines_containing(docs, [
            "--use_native_input_files",
            "If not specified, input files will",
            "be parsed in floating point",
        ]),
    }
    if any(not locations for group in source_checks.values() for locations in group.values()):
        raise SystemExit("required QAIRT source/documentation evidence missing")
    scripts = {}
    for label, path in (("ar171", args.ar171_script), ("phase_switch", args.phase_script)):
        text = path.read_text()
        scripts[label] = {
            "path": str(path), "sha256": sha256(path),
            "invokes_qnn_net_run": "qnn-net-run" in text,
            "sets_input_data_type": "--input_data_type" in text,
            "uses_native_input_files": "--use_native_input_files" in text,
        }
        if not scripts[label]["invokes_qnn_net_run"] or scripts[label]["sets_input_data_type"] or scripts[label]["uses_native_input_files"]:
            raise SystemExit(f"unexpected qnn-net-run flags in {label}")
    commands = {}
    for label, path in (("ar171", args.ar171_execution_metadata), ("ar1_phase", args.ar1_execution_metadata)):
        command = yaml.safe_load(path.read_text())["command"]
        commands[label] = {
            "path": str(path), "sha256": sha256(path), "command": command,
            "sets_input_data_type": "--input_data_type" in command,
            "uses_native_input_files": "--use_native_input_files" in command,
        }
        if commands[label]["sets_input_data_type"] or commands[label]["uses_native_input_files"]:
            raise SystemExit(f"unexpected recorded input flags in {label}")
    ar171_raw = raw_audit(args.ar171_position)
    ar1_raw = raw_audit(args.ar1_position)
    ar171_descriptor = graph_position(args.ar171_context_info)
    ar1_descriptor = graph_position(args.ar1_context_info)
    if ar171_descriptor != {"data_type": "QNN_DATATYPE_INT_64", "dimensions": [1, 171]}:
        raise SystemExit("AR171 position descriptor mismatch")
    if ar1_descriptor != {"data_type": "QNN_DATATYPE_INT_64", "dimensions": [1, 1]}:
        raise SystemExit("AR1 position descriptor mismatch")
    if not ar171_raw["all_converted_to_zero"] or not ar1_raw["all_converted_to_zero"]:
        raise SystemExit("expected zero conversion was not reproduced")
    result = {
        "schema_version": 1,
        "classification": "source_verified_qnn_net_run_position_ingestion_error",
        "qairt": {
            "version": "2.49.40.260810",
            "qnn_net_run_sha256": sha256(args.qairt_root / "bin/aarch64-android/qnn-net-run"),
            "source_files": {
                "main.cpp": {"sha256": sha256(main_cpp), "matched_lines": source_checks["main"]},
                "IOTensor.cpp": {"sha256": sha256(io_cpp), "matched_lines": source_checks["io"]},
                "DataUtil.cpp": {"sha256": sha256(data_cpp), "matched_lines": source_checks["data"]},
                "tools.html": {"sha256": sha256(docs), "matched_lines": source_checks["docs"]},
            },
            "source_behavior": [
                "qnn-net-run defaults InputDataType to FLOAT unless an input-data-type option is supplied.",
                "For a non-FLOAT32 graph tensor, IOTensor reads one FLOAT32 value per tensor element, then calls copyFromFloatToNative.",
                "For QNN_DATATYPE_INT_64, copyFromFloatToNative calls castFromFloat<int64_t>, whose implementation static_casts each float value.",
            ],
        },
        "recorded_invocations": {"scripts": scripts, "physical_execution_metadata": commands},
        "graph_descriptors": {"ar171_position": ar171_descriptor, "ar1_position": ar1_descriptor},
        "raw_position_files": {"ar171": ar171_raw, "ar1_phase_switch": ar1_raw},
        "proved_interpretation": {
            "ar171": "The 684-byte int32[171] file had the required byte length for default FLOAT32 file input. Its integer bit patterns 0..170 were read as float32 values 0..2.382e-43 and static_cast to INT64; all 171 became zero.",
            "ar1_phase_switch": "The 4-byte int32 value 171 was read as float32 2.396e-43 and static_cast to INT64 zero.",
            "not_ambiguous": True,
        },
        "impact": {
            "invalidated_claims": [
                "The qnn-net-run physical AR171 call did not prove rotary positions 0..170.",
                "The qnn-net-run physical phase-switch AR1 call did not prove position 171; it executed with position zero.",
                "Their endpoint argmax agreement cannot establish exact position/state semantics.",
            ],
            "still_valid": [
                "Both calls loaded and executed their QNN HTP graphs physically and produced the retained raw outputs.",
                "Provider, context/runtime identity, finite-output, timing, memory, and cleanup evidence remain factual when scoped to the actual all-zero position inputs.",
                "The direct-QNN AR1 max16 runner copied INT64 position 171 directly and is a separate API path, but its initial state came from the affected AR171 output.",
                "The integrated direct-QNN runner is designed for correct INT64 buffers and remains physically unexecuted.",
            ],
        },
        "required_fix": {
            "qnn_net_run": "Use FLOAT32 files containing numeric 0..170/171 with default input mode, or pass --input_data_type native and provide native INT64 files of 1368/8 bytes. Verify the chosen mode with a bounded diagnostic before reusing qnn-net-run for position-sensitive claims.",
            "direct_qnn": "Continue using graph descriptor INT64 buffers (1368 bytes AR171; 8 bytes AR1) with no qnn-net-run file conversion.",
        },
        "phone_boundary": "Source audit only; no model load, inference, compilation, or phone access occurred.",
        "claim_boundary": "This audit corrects interpretation of immutable prior physical evidence. It does not erase physical HTP execution, but it invalidates exact position-semantic and fidelity conclusions drawn from those qnn-net-run attempts.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "ar171_converted_unique": ar171_raw["float32_to_int64_unique"],
        "ar1_converted_unique": ar1_raw["float32_to_int64_unique"],
        "default_float_source_line": source_checks["main"]["parsedInputDataType     = iotensor::InputDataType::FLOAT"],
        "native_conversion_line": source_checks["io"]["datautil::castFromFloat<int64_t>"],
    }, indent=2))

if __name__ == "__main__":
    main()
