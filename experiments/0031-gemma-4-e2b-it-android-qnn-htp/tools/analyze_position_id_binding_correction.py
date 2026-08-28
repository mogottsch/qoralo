#!/usr/bin/env python3
"""Validate the host-side positional input rename, reconversion, and rebuilt HTP context."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
CONVERT_RUN = EXP / ".local/qairt-2.49.40-cache-aligned-v6-run"
COMPILE_RUN = EXP / ".local/qairt-2.49.40-context-cache-aligned-v6-run"
OUT = EXP / "results/qairt-2.49.40-position-id-binding-correction/result.json"
EXPECTED_DLCS = {
    1: (2_356_847_508, "f080cce522588baadcea38444b480038198918cd8a580dee1026591d638aa044"),
    128: (2_356_851_164, "23a27a84529990adeda07b9b81cc0dd7d360b396d48233e37170f4e62a2c0759"),
}
EXPECTED_CONTEXT = (1_186_369_536, "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394")
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


def events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(errors="replace").splitlines() if line.startswith("{")]


def tensor_map(items: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {item["info"]["name"]: item["info"] for item in items}


def signature(info: dict[str, object]) -> tuple[object, object]:
    return info["dataType"], info["quantizeParams"]


def markers(path: Path, values: list[bytes]) -> dict[str, bool]:
    found = {value.decode(): False for value in values}
    tail = b""
    overlap = max(map(len, values)) - 1
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            data = tail + chunk
            for value in values:
                if value in data:
                    found[value.decode()] = True
            tail = data[-overlap:]
    return found


def parse_dlc_io(ar: int) -> dict[str, object]:
    text = (CONVERT_RUN / f"ar{ar}.dlc-info.log").read_text(errors="replace")
    input_section = text.split("Input Name", 1)[1].split("Output Name", 1)[0]
    output_section = text.split("Output Name", 1)[1].split("Total parameters:", 1)[0]

    def rows(section: str, heading: str) -> list[list[str]]:
        result = []
        for line in section.splitlines():
            if line.startswith("|"):
                fields = [value.strip() for value in line.strip("|").split("|")]
                if len(fields) >= 3 and fields[0] not in ("", heading):
                    result.append(fields)
        return result

    inputs = rows(input_section, "Input Name")
    outputs = rows(output_section, "Output Name")
    if len(inputs) != 38 or len(outputs) != 31:
        raise RuntimeError(f"AR{ar} DLC IO count mismatch")
    positional = [row[0] for row in inputs if "position_ids" in row[0]]
    expected_positional = ["swa_position_ids_cos", "swa_position_ids_sin", "position_ids_cos", "position_ids_sin"]
    if positional != expected_positional or any("position_ids_global" in row[0] for row in inputs):
        raise RuntimeError(f"AR{ar} DLC positional inputs mismatch: {positional}")
    output_types = dict(Counter(row[2] for row in outputs))
    if output_types != {"uFxp_16": 31}:
        raise RuntimeError(f"AR{ar} DLC output datatype mismatch: {output_types}")
    if "Total parameters: 2280676608" not in text:
        raise RuntimeError(f"AR{ar} parameter count mismatch")
    return {
        "input_count": len(inputs), "output_count": len(outputs),
        "positional_inputs": positional, "output_datatypes": output_types,
        "parameters": 2_280_676_608,
    }


def main() -> None:
    conversion_events = events(CONVERT_RUN / "stdout.log")
    if [item.get("event") for item in conversion_events] != [
        "position_id_aligned_conversion_start", "position_id_aligned_conversion_complete"
    ]:
        raise RuntimeError("unexpected position-ID conversion events")
    conversion_start, conversion_complete = conversion_events
    if conversion_start["phone_access"] or not conversion_start["rename_is_numerically_identity"]:
        raise RuntimeError("position-ID conversion boundary mismatch")
    variants = {item["ar"]: item for item in conversion_start["variants"]}
    converted = {item["ar"]: item for item in conversion_complete["converted_models"]}
    for ar in (1, 128):
        if variants[ar]["input_renames"] != RENAMES or not variants[ar]["onnx_checker_passed"]:
            raise RuntimeError(f"AR{ar} rename evidence mismatch")
        expected_bytes, expected_hash = EXPECTED_DLCS[ar]
        if converted[ar]["bytes"] != expected_bytes or converted[ar]["sha256"] != expected_hash:
            raise RuntimeError(f"AR{ar} DLC identity mismatch")
    dlc_inspection = {str(ar): parse_dlc_io(ar) for ar in (1, 128)}

    compile_events = events(COMPILE_RUN / "stdout.log")
    if [item.get("event") for item in compile_events] != [
        "cache_aligned_htp_compile_start", "cache_aligned_htp_compile_complete"
    ]:
        raise RuntimeError("unexpected position-ID compile events")
    compile_start, compile_complete = compile_events
    compile_inputs = {item["ar"]: item["dlc_sha256"] for item in compile_start["models"]}
    if compile_inputs != {ar: EXPECTED_DLCS[ar][1] for ar in (1, 128)}:
        raise RuntimeError("compile inputs mismatch")
    context_path = Path(compile_complete["context"]["path"])
    if context_path.stat().st_size != EXPECTED_CONTEXT[0] or sha256(context_path) != EXPECTED_CONTEXT[1]:
        raise RuntimeError("position-ID-aligned context identity mismatch")

    metadata_path = COMPILE_RUN / "context-info.json"
    metadata = json.loads(metadata_path.read_text())
    info = metadata["info"]
    if info["backendId"] != 6 or info["numGraphs"] != 2:
        raise RuntimeError("context is not the expected two-graph HTP artifact")
    graphs = {item["info"]["graphName"]: item["info"] for item in info["graphs"]}
    if set(graphs) != {"ar1_cl4096_1_of_1", "ar128_cl4096_1_of_1"}:
        raise RuntimeError("context graph names mismatch")
    graph_summaries = {}
    maps = {}
    for name, graph in graphs.items():
        inputs = tensor_map(graph["graphInputs"])
        outputs = tensor_map(graph["graphOutputs"])
        positional = [key for key in inputs if "position_ids" in key]
        if set(positional) != {"swa_position_ids_cos", "swa_position_ids_sin", "position_ids_cos", "position_ids_sin"}:
            raise RuntimeError(f"{name} context positional inputs mismatch: {positional}")
        if any("position_ids_global" in key for key in inputs):
            raise RuntimeError(f"{name} retains old global positional names")
        if Counter(item["dataType"] for item in outputs.values()) != {"QNN_DATATYPE_UFIXED_POINT_16": 31}:
            raise RuntimeError(f"{name} output datatype mismatch")
        graph_summaries[name] = {
            "input_count": len(inputs), "output_count": len(outputs),
            "positional_inputs": positional,
            "input_datatypes": dict(Counter(item["dataType"] for item in inputs.values())),
            "output_datatypes": dict(Counter(item["dataType"] for item in outputs.values())),
        }
        maps[name] = (inputs, outputs)

    ar1_inputs, ar1_outputs = maps["ar1_cl4096_1_of_1"]
    ar128_inputs, ar128_outputs = maps["ar128_cl4096_1_of_1"]
    cache_contracts = []
    for output_name in sorted(name for name in ar1_outputs if "_value_" in name):
        input_name = output_name[:-4] + "_in"
        signatures = [
            signature(ar1_inputs[input_name]), signature(ar1_outputs[output_name]),
            signature(ar128_inputs[input_name]), signature(ar128_outputs[output_name]),
        ]
        if not all(value == signatures[0] for value in signatures):
            raise RuntimeError(f"cache correction regressed: {output_name}")
        cache_contracts.append(output_name[:-4])
    if len(cache_contracts) != 15:
        raise RuntimeError("cache contract count mismatch")

    embedded = markers(context_path, [
        b"soc_type=SM8550", b"arch=73", b"native_hmx_a16w4=true",
        b"ar1_cl4096_1_of_1", b"ar128_cl4096_1_of_1",
    ])
    if not all(embedded.values()):
        raise RuntimeError("context target markers missing")

    config = json.loads((EXP / ".local/runtime-bundle/gemma4-e2b-htp-cl4096-greedy.json").read_text())
    positional_config = config["dialog"]["engine"]["model"]["positional-encoding"]
    if len(positional_config) != 2 or "prefix" in positional_config[0] or positional_config[1].get("prefix") != "swa_":
        raise RuntimeError("Genie positional configuration mismatch")

    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_position_id_binding_correction_and_sm8550_recompile",
        "status": "position_id_binding_corrected_recompiled_stage_rebuild_required",
        "claim_boundary": (
            "Both AR variants were numerically unchanged except for renaming the global RoPE input symbols from "
            "position_ids_global_cos/sin to the exact position_ids_cos/sin names searched by the unprefixed Genie "
            "positional configuration. Both full DLCs retain 2,280,676,608 parameters and 31 uFxp16 outputs. "
            "Official metadata for the rebuilt two-graph QNN HTP SM8550/v73 context confirms the corrected names "
            "and all 15 four-way cache signatures remain identical. This is host conversion/AOT inspection only, "
            "not physical dialog creation, graph execution, no-fallback, output, or performance evidence."
        ),
        "correction": {
            "kind": "ONNX graph-input and activation-encoding symbol rename",
            "renames": RENAMES,
            "numerically_identity": True,
            "checkpoint_modified": False,
            "ar1_value_cache_qdq_boundary_preserved": True,
            "variants": sorted(variants.values(), key=lambda item: item["ar"]),
        },
        "conversion": {
            "qairt_version": conversion_start["qairt_version"],
            "target": conversion_start["target"],
            "models": sorted(converted.values(), key=lambda item: item["ar"]),
            "dlc_inspection": dlc_inspection,
        },
        "compile": {
            "mode": compile_complete["mode"], "target": compile_complete["target"],
            "soc_model": compile_complete["soc_model"], "dsp_arch": compile_complete["dsp_arch"],
            "pd_session": compile_start["pd_session"], "context_bytes": EXPECTED_CONTEXT[0],
            "context_sha256": EXPECTED_CONTEXT[1],
        },
        "inspection": {
            "utility": "qnn-context-binary-utility", "backend_id": info["backendId"],
            "build_id": info["buildId"], "num_graphs": info["numGraphs"],
            "graphs": dict(sorted(graph_summaries.items())),
            "old_global_positional_input_count": 0,
            "genie_default_global_inputs_present_in_both_graphs": True,
            "swa_prefixed_inputs_present_in_both_graphs": True,
            "cache_contract_count": len(cache_contracts),
            "all_cache_contracts_still_identical": True,
            "embedded_markers": embedded,
        },
        "config_binding": {
            "global_entry_has_no_prefix": True,
            "global_context_inputs": ["position_ids_cos", "position_ids_sin"],
            "swa_prefix": "swa_",
            "swa_context_inputs": ["swa_position_ids_cos", "swa_position_ids_sin"],
            "host_name_set_match": True,
        },
        "raw_log_hashes": {
            "conversion": {
                name: {"bytes": (CONVERT_RUN / name).stat().st_size, "sha256": sha256(CONVERT_RUN / name)}
                for name in ("stdout.log", "stderr.log", "ar1.dlc-info.log", "ar1.dlc-info.stderr", "ar128.dlc-info.log", "ar128.dlc-info.stderr")
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
        "next_gate": "Rebuild and hash the private runtime bundle/stage around this context before requesting any phone handoff.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
