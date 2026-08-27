#!/usr/bin/env python3
"""Validate the host-side AR1 value-cache correction and rebuilt SM8550 context."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
CONVERT_RUN = EXP / ".local/qairt-2.49.40-cache-aligned-v5-run"
COMPILE_RUN = EXP / ".local/qairt-2.49.40-context-cache-aligned-v5-run"
OUT = EXP / "results/qairt-2.49.40-cache-quantization-correction/result.json"
HTP_HEADER = Path("/home/moritz/opt/qairt/2.49.40.260810/include/QNN/HTP/QnnHtpCommon.h")
EXPECTED = {
    "source_ar1_onnx": "9f3077b4a8ccec48781843f6391bb9d77bf4d0c2578a864c108a916b24c9e472",
    "source_ar1_encodings": "0dbb1aad69b419594707cc45d31656b95457b5a78c0bce462f1f03db77bfe2a8",
    "shared_external_data": "b9b73b984c2258099bc77ce6d1e2aa92d12bb67abe456e5ef509136d7494a65d",
    "corrected_ar1_dlc": "7e88facdba8c8b015579cbc3bf76dbad4f2f913cd29b450d555d6174bd48c9e1",
    "ar128_dlc": "5f17ece8a99cd649abdadb61e2e104e5cd569a1d1735e9e6ecb5c297286156ee",
    "context": "a1d52d0087a0719d5907a98d99e8bc5996b699c9cf8f3a21b301588b9f51cc44",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(errors="replace").splitlines() if line.startswith("{")]


def contains_markers(path: Path, markers: list[bytes]) -> dict[str, bool]:
    found = {marker.decode(): False for marker in markers}
    overlap = max(map(len, markers)) - 1
    tail = b""
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            data = tail + chunk
            for marker in markers:
                if marker in data:
                    found[marker.decode()] = True
            tail = data[-overlap:]
    return found


def tensor_map(items: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {item["info"]["name"]: item["info"] for item in items}


def signature(info: dict[str, object]) -> dict[str, object]:
    return {"datatype": info["dataType"], "quantize_params": info["quantizeParams"]}


def main() -> None:
    convert_events = events(CONVERT_RUN / "stdout.log")
    if [item.get("event") for item in convert_events] != [
        "ar1_cache_qdq_conversion_start", "ar1_cache_qdq_conversion_complete"
    ]:
        raise RuntimeError("unexpected corrected conversion events")
    convert_start, convert_complete = convert_events
    if convert_start["source_onnx_sha256"] != EXPECTED["source_ar1_onnx"]:
        raise RuntimeError("source ONNX mismatch")
    if convert_start["source_encodings_sha256"] != EXPECTED["source_ar1_encodings"]:
        raise RuntimeError("source encodings mismatch")
    if convert_start["shared_external_data_sha256"] != EXPECTED["shared_external_data"]:
        raise RuntimeError("external data mismatch")
    if convert_start["graph_output_count"] != 31:
        raise RuntimeError("corrected ONNX did not preserve all outputs")
    boundaries = convert_start["explicit_uint16_cache_boundaries"]
    if len(boundaries) != 15 or any(item["qnn_offset"] != -32768 for item in boundaries):
        raise RuntimeError("unexpected explicit cache boundaries")
    if convert_complete["dlc_sha256"] != EXPECTED["corrected_ar1_dlc"]:
        raise RuntimeError("corrected DLC mismatch")

    dlc_info = (CONVERT_RUN / "aligned-ar1.dlc-info.log").read_text(errors="replace")
    output_section = dlc_info.split("Output Name", 1)[1].split("Total parameters:", 1)[0]
    output_rows = []
    for line in output_section.splitlines():
        if line.startswith("|"):
            fields = [value.strip() for value in line.strip("|").split("|")]
            if len(fields) >= 4 and fields[0] not in ("", "Output Name"):
                output_rows.append(fields)
    if len(output_rows) != 31 or Counter(row[2] for row in output_rows) != {"uFxp_16": 31}:
        raise RuntimeError("corrected DLC outputs are not all uFxp16")
    value_outputs = [row for row in output_rows if "_value_" in row[0]]
    if len(value_outputs) != 15:
        raise RuntimeError("corrected DLC value output count mismatch")
    parameter_match = re.search(r"Total parameters: (\d+)", dlc_info)
    if not parameter_match or int(parameter_match.group(1)) != 2_280_676_608:
        raise RuntimeError("corrected DLC parameter count mismatch")

    compile_events = events(COMPILE_RUN / "stdout.log")
    if [item.get("event") for item in compile_events] != [
        "cache_aligned_htp_compile_start", "cache_aligned_htp_compile_complete"
    ]:
        raise RuntimeError("unexpected corrected compile events")
    compile_start, compile_complete = compile_events
    input_dlcs = {item["ar"]: item["dlc_sha256"] for item in compile_start["models"]}
    if input_dlcs != {1: EXPECTED["corrected_ar1_dlc"], 128: EXPECTED["ar128_dlc"]}:
        raise RuntimeError("corrected compile input mismatch")
    context_path = Path(compile_complete["context"]["path"])
    if sha256(context_path) != EXPECTED["context"]:
        raise RuntimeError("corrected context mismatch")

    metadata_path = COMPILE_RUN / "context-info.json"
    metadata = json.loads(metadata_path.read_text())
    info = metadata["info"]
    if "#define QNN_BACKEND_ID_HTP 6" not in HTP_HEADER.read_text(errors="replace"):
        raise RuntimeError("HTP backend ID source mismatch")
    if info["backendId"] != 6 or info["numGraphs"] != 2:
        raise RuntimeError("corrected context is not the two-graph HTP context")
    graphs = {item["info"]["graphName"]: item["info"] for item in info["graphs"]}
    if set(graphs) != {"ar1_cl4096_1_of_1", "ar128_cl4096_1_of_1"}:
        raise RuntimeError("unexpected corrected graph names")
    ar1 = graphs["ar1_cl4096_1_of_1"]
    ar128 = graphs["ar128_cl4096_1_of_1"]
    for graph in (ar1, ar128):
        if len(graph["graphInputs"]) != 38 or len(graph["graphOutputs"]) != 31:
            raise RuntimeError("corrected graph IO count mismatch")
    ar1_inputs, ar1_outputs = tensor_map(ar1["graphInputs"]), tensor_map(ar1["graphOutputs"])
    ar128_inputs, ar128_outputs = tensor_map(ar128["graphInputs"]), tensor_map(ar128["graphOutputs"])
    cache_contracts = []
    for output_name in sorted(name for name in ar1_outputs if "_value_" in name):
        input_name = output_name[:-4] + "_in"
        tensors = [ar1_inputs[input_name], ar1_outputs[output_name], ar128_inputs[input_name], ar128_outputs[output_name]]
        signatures = [signature(tensor) for tensor in tensors]
        if not all(value == signatures[0] for value in signatures):
            raise RuntimeError(f"cache contract still differs: {output_name}")
        if signatures[0]["datatype"] != "QNN_DATATYPE_UFIXED_POINT_16":
            raise RuntimeError(f"cache contract is not uFxp16: {output_name}")
        scale_offset = signatures[0]["quantize_params"].get("scaleOffset")
        if signatures[0]["quantize_params"].get("definition") != "QNN_DEFINITION_DEFINED" or not scale_offset:
            raise RuntimeError(f"cache encoding is undefined: {output_name}")
        cache_contracts.append({
            "base": output_name[:-4], "ar1_input": input_name, "ar1_output": output_name,
            "ar128_input": input_name, "ar128_output": output_name,
            "datatype": signatures[0]["datatype"], "scale": scale_offset["scale"],
            "offset": scale_offset["offset"], "all_four_signatures_identical": True,
        })
    if len(cache_contracts) != 15:
        raise RuntimeError("expected 15 corrected cache contracts")

    markers = contains_markers(context_path, [
        b"soc_type=SM8550", b"arch=73", b"native_hmx_a16w4=true",
        b"ar1_cl4096_1_of_1", b"ar128_cl4096_1_of_1",
    ])
    if not all(markers.values()):
        raise RuntimeError("corrected context target markers missing")

    conversion_stdout = (CONVERT_RUN / "stdout.log").read_text(errors="replace")
    fallback_match = re.search(r"\[ WARNING \] Following OPs fallback to float:\n([^\n]+)\.", conversion_stdout)
    fallback_ops = [name.strip() for name in fallback_match.group(1).split(",")] if fallback_match else []

    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_cache_quantization_correction_and_sm8550_recompile",
        "status": "host_cache_quantization_corrected_recompiled_phone_gate_required",
        "claim_boundary": (
            "A schema-standard ONNX float fork plus QuantizeLinear boundary converted each of the 15 AR1 "
            "value-cache outputs to the exact uFxp16 scale/offset already required by the source QAT encodings. "
            "Official context metadata proves all four AR1-input/AR1-output/AR128-input/AR128-output signatures "
            "are identical in a two-graph QNN HTP backend-ID-6 SM8550/v73 context. This is host conversion and "
            "AOT inspection only; it does not prove physical context acceptance, graph execution, no-fallback "
            "execution, output, text quality, or performance."
        ),
        "source_identity": {
            "checkpoint_modified": False,
            "ar1_transformed_onnx_sha256": EXPECTED["source_ar1_onnx"],
            "ar1_source_encodings_sha256": EXPECTED["source_ar1_encodings"],
            "shared_external_data_sha256": EXPECTED["shared_external_data"],
        },
        "correction": {
            "method": "ONNX Cast fork plus QuantizeLinear at each public AR1 value-cache output",
            "internal_transformer_consumer_path_preserved": True,
            "quantize_zero_point_uint16": 32768,
            "qnn_offset": -32768,
            "boundary_count": len(boundaries),
            "patched_onnx_sha256": convert_start["patched_onnx_sha256"],
            "patched_encodings_sha256": convert_start["patched_encodings_sha256"],
            "corrected_ar1_dlc_bytes": convert_complete["dlc_bytes"],
            "corrected_ar1_dlc_sha256": EXPECTED["corrected_ar1_dlc"],
            "dlc_parameters": 2_280_676_608,
            "dlc_output_datatypes": {"uFxp_16": 31},
            "value_cache_outputs_ufxp16": 15,
            "float_precision_fallback_component_op_count": len(fallback_ops),
            "float_precision_fallback_component_ops": fallback_ops,
            "not_a_uniform_integer_execution_claim": True,
        },
        "compile": {
            "qairt_version": compile_complete["qairt_version"], "mode": compile_complete["mode"],
            "target": compile_complete["target"], "soc_model": compile_complete["soc_model"],
            "dsp_arch": compile_complete["dsp_arch"], "pd_session": compile_start["pd_session"],
            "input_dlcs": sorted(compile_start["models"], key=lambda item: item["ar"]),
            "context_bytes": context_path.stat().st_size, "context_sha256": EXPECTED["context"],
        },
        "inspection": {
            "utility": "qnn-context-binary-utility", "backend_id": info["backendId"],
            "backend_id_source": "QAIRT 2.49.40 QnnHtpCommon.h: QNN_BACKEND_ID_HTP 6",
            "build_id": info["buildId"], "num_graphs": info["numGraphs"],
            "graphs": {
                name: {
                    "input_count": len(graph["graphInputs"]), "output_count": len(graph["graphOutputs"]),
                    "input_datatypes": dict(Counter(item["info"]["dataType"] for item in graph["graphInputs"])),
                    "output_datatypes": dict(Counter(item["info"]["dataType"] for item in graph["graphOutputs"])),
                }
                for name, graph in sorted(graphs.items())
            },
            "cache_contract_count": len(cache_contracts),
            "cache_contracts": cache_contracts,
            "all_cache_contracts_identical": True,
            "embedded_markers": markers,
        },
        "raw_log_hashes": {
            "conversion": {
                name: {"bytes": (CONVERT_RUN / name).stat().st_size, "sha256": sha256(CONVERT_RUN / name)}
                for name in ("stdout.log", "stderr.log", "aligned-ar1.dlc-info.log", "aligned-ar1.dlc-info.stderr")
            },
            "compile": {
                name: {"bytes": (COMPILE_RUN / name).stat().st_size, "sha256": sha256(COMPILE_RUN / name)}
                for name in ("stdout.log", "stderr.log", "context-info.json", "context-info.stdout.log", "context-info.stderr.log")
            },
        },
        "requested": {
            "qnn_conversion": True, "htp_compilation": True, "phone_access": False,
            "physical_htp_execution": False, "inference": False, "paid_workbench_job": False,
        },
        "next_gate": (
            "After Pi independently reviews this host correction and explicitly transfers phone priority, rebuild "
            "the private runtime bundle/stage around the corrected context and run one locked 16-token physical gate."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
