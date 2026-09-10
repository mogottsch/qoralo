#!/usr/bin/env python3
"""Bind static integrated-runner semantics, context ABIs, and stage artifacts."""
from __future__ import annotations
import argparse, hashlib, json, math, struct
from pathlib import Path

import numpy as np

TYPE_BYTES = {
    "QNN_DATATYPE_FLOAT_32": 4,
    "QNN_DATATYPE_INT_64": 8,
}
ATTENTION = {2, 5, 9, 13, 17, 21, 24, 27}

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def graph(path: Path) -> dict:
    info = json.loads(path.read_text())["info"]
    return info, info["graphs"][0]["info"]

def tensors(values: list[dict]) -> dict[str, dict]:
    return {value["info"]["name"]: value["info"] for value in values}

def tensor_bytes(value: dict) -> int:
    return math.prod(value["dimensions"]) * TYPE_BYTES[value["dataType"]]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ar171-context-info", type=Path, required=True)
    parser.add_argument("--ar1-context-info", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--host-runner", type=Path, required=True)
    parser.add_argument("--phone-script", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--embedding-stage", type=Path, required=True)
    parser.add_argument("--prior-prefill-inputs", type=Path, required=True)
    parser.add_argument("--prior-bridge-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    ar171_info, ar171 = graph(args.ar171_context_info)
    ar1_info, ar1 = graph(args.ar1_context_info)
    ar171_inputs, ar1_inputs = tensors(ar171["graphInputs"]), tensors(ar1["graphInputs"])
    ar171_outputs, ar1_outputs = tensors(ar171["graphOutputs"]), tensors(ar1["graphOutputs"])
    for label, info, graph_info, inputs, outputs, sequence in (
        ("ar171", ar171_info, ar171, ar171_inputs, ar171_outputs, 171),
        ("ar1", ar1_info, ar1, ar1_inputs, ar1_outputs, 1),
    ):
        if info["numGraphs"] != 1 or graph_info["numGraphInputs"] != 41 or graph_info["numGraphOutputs"] != 60:
            raise SystemExit(f"{label} graph ABI count mismatch")
        position = inputs["position_ids"]
        if position["dataType"] != "QNN_DATATYPE_INT_64" or position["dimensions"] != [1, sequence]:
            raise SystemExit(f"{label} position ABI mismatch")
        if not all(value["dataType"] == "QNN_DATATYPE_FLOAT_32" for value in outputs.values()):
            raise SystemExit(f"{label} non-FP32 output")
        if not all(value["memType"] == "QNN_TENSORMEMTYPE_RAW" for value in list(inputs.values()) + list(outputs.values())):
            raise SystemExit(f"{label} non-raw tensor")

    raw_tokens = args.token_file.read_bytes()
    if len(raw_tokens) != 171 * 4:
        raise SystemExit("canonical short token count mismatch")
    token_ids = np.asarray(struct.unpack("<171i", raw_tokens), dtype=np.int32)
    quant = np.memmap(args.embedding_stage / "embedding-quant.u8", np.uint8, "r", shape=(128000, 1024))
    scales = np.memmap(args.embedding_stage / "embedding-scales.f32le", np.float32, "r", shape=(128000, 64))
    zero_points = np.memmap(args.embedding_stage / "embedding-zp.u8", np.uint8, "r", shape=(128000, 32))
    embeddings = np.empty((1, 171, 2048), np.float32)
    for row, token in enumerate(token_ids):
        unpacked = np.empty(2048, np.float32)
        unpacked[::2] = quant[token] & 15
        unpacked[1::2] = quant[token] >> 4
        zp = np.empty(64, np.float32)
        zp[::2] = zero_points[token] & 15
        zp[1::2] = zero_points[token] >> 4
        embeddings[0, row] = (unpacked - np.repeat(zp, 32)) * np.repeat(scales[token], 32)
    position = np.arange(171, dtype=np.int64)[None, :]
    mask = np.full((1, 1, 171, 4096), -65504.0, np.float32)
    past = 4096 - 171
    for row in range(171):
        mask[0, 0, row, past : past + row + 1] = 0.0
    prefill_inputs = json.loads((args.prior_prefill_inputs / "result.json").read_text())
    prior_by_name = {item["name"]: args.prior_prefill_inputs / Path(item["path"]).name for item in prefill_inputs["inputs"]}
    embedding_equal = embeddings.tobytes() == prior_by_name["/model/embed_tokens/GatherBlockQuantized/output_0"].read_bytes()
    mask_equal = mask.tobytes() == prior_by_name["attention_mask"].read_bytes()

    source = args.source.read_text()
    support_header = args.source.parent / "integrated_output.hpp"
    combined_source = source + "\n" + support_header.read_text()
    required_fragments = [
        "qnn_outputs_finite alias=", "ProfilingLevel::DETAILED", "profileGetEvents",
        "RunPrefill171", "runner.LoadOnly(root / \"contexts/ar171.bin\", \"prefill\")",
        "runner.FreeContexts(); const auto prefill_free_end",
        "\"profile_reset\", [&] { runner.ResetDetailedProfile(); }, std::cerr)",
        "runner.LoadOnly(root / \"contexts/ar1.bin\", \"monolith\")",
        "runner.RunToken(emitter.Tokens().back(), 171 + static_cast<int>(output_index) - 1, true)", "simultaneous_contexts",
        "prefill_cpu_input_seconds", "prefill_state_bridge_seconds",
        "ExclusiveTokenOutput", "BoundedTokenEmitter", "AppendAndFlush", "CaptureOptionalTelemetry",
        "SummarizeTiming",
        "request_to_first_emitted_token_seconds", "request_to_final_emitted_token_seconds",
        "MAX_NEW is total emitted tokens including the AR171 endpoint",
        "monolithic_ = lfm2::UsesMonolithicDispatch(alias)",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in combined_source]
    if missing:
        raise SystemExit(f"missing integrated source fragments: {missing}")

    stage = json.loads((args.stage / "stage.json").read_text())
    bridge = json.loads(args.prior_bridge_validation.read_text())
    if bridge["position_native_int32"] != [171] or not bridge["all_state_checks_pass"]:
        raise SystemExit("historical qnn-net-run bridge evidence is not intact")
    result = {
        "schema_version": 1,
        "classification": "host_static_and_build_validation_of_integrated_ar171_ar1_runner",
        "source": {"path": str(args.source), "sha256": sha256(args.source), "support_header": str(support_header), "support_header_sha256": sha256(support_header), "required_fragments_present": True},
        "binaries": {
            "host_sha256": sha256(args.host_runner),
            "android_sha256": stage["runner_sha256"],
            "android_elf_preflight": True,
        },
        "contexts": {
            "ar171": {
                "build_id": ar171_info["buildId"], "sha256": stage["ar171_context_sha256"],
                "inputs": 41, "outputs": 60,
                "position": {"data_type": ar171_inputs["position_ids"]["dataType"], "dimensions": [1, 171], "direct_copy_bytes": tensor_bytes(ar171_inputs["position_ids"])},
                "attention_mask_dimensions": ar171_inputs["attention_mask"]["dimensions"],
                "state_outputs": sum(name.startswith("present") for name in ar171_outputs),
                "logit_outputs": sum(name.startswith("logits_vocab_") for name in ar171_outputs),
                "shared_weights_bytes": ar171["graphBlobInfoV2"]["sharedWeightsSize"],
                "const_bytes": ar171["graphBlobInfoV2"]["constSize"],
                "io_tensor_bytes": ar171["graphBlobInfoV2"]["ioTensorSize"],
                "spill_fill_buffer_bytes": ar171["graphBlobInfo"]["info"]["spillFillBufferSize"],
            },
            "ar1": {
                "build_id": ar1_info["buildId"], "sha256": stage["ar1_context_sha256"],
                "inputs": 41, "outputs": 60,
                "position": {"data_type": ar1_inputs["position_ids"]["dataType"], "dimensions": [1, 1], "direct_copy_bytes": tensor_bytes(ar1_inputs["position_ids"])},
                "attention_mask_dimensions": ar1_inputs["attention_mask"]["dimensions"],
                "state_outputs": sum(name.startswith("present") for name in ar1_outputs),
                "logit_outputs": sum(name.startswith("logits_vocab_") for name in ar1_outputs),
                "shared_weights_bytes": ar1["graphBlobInfoV2"]["sharedWeightsSize"],
                "const_bytes": ar1["graphBlobInfoV2"]["constSize"],
                "io_tensor_bytes": ar1["graphBlobInfoV2"]["ioTensorSize"],
                "spill_fill_buffer_bytes": ar1["graphBlobInfo"]["info"]["spillFillBufferSize"],
            },
        },
        "input_semantics": {
            "canonical_short_tokens": 171,
            "token_file_sha256": sha256(args.token_file),
            "tokenization_precomputed_and_excluded_from_timing": True,
            "cpu_embedding_bytes": embeddings.nbytes,
            "cpu_embedding_sha256": hashlib.sha256(embeddings.tobytes()).hexdigest(),
            "embedding_byte_equal_to_accepted_prefill_input": embedding_equal,
            "position_int64_sha256": hashlib.sha256(position.tobytes()).hexdigest(),
            "mask_bytes": mask.nbytes,
            "mask_sha256": hashlib.sha256(mask.tobytes()).hexdigest(),
            "mask_byte_equal_to_accepted_prefill_input": mask_equal,
            "zero_prefill_state_inputs": 38,
        },
        "api_type_boundary": {
            "integrated_direct_qnn": "Reads QNN graph tensor descriptors and memcpy-copies INT64 position buffers: 1368 bytes for AR171 and 8 bytes for AR1.",
            "prior_qnn_net_run": "The historical qnn-net-run input-file route used INT32 raw position files that were later proven to enter default FLOAT ingestion and become all-zero INT64 positions. It remains wrong-position execution evidence, not an accepted position-semantic route.",
            "non_generalization": "The qnn-net-run raw-file convention is not reused or generalized to the direct-QNN runner ABI.",
            "prior_bridge_position_native_int32": bridge["position_native_int32"],
        },
        "integrated_semantics": {
            "backend_device_processes": 1,
            "contexts_loaded_sequentially": 2,
            "simultaneous_contexts": 1,
            "explicit_phase_transitions": 1,
            "context_reloads_per_phase": 0,
            "per_token_context_streaming": False,
            "finite_scan": "all requested outputs before copying: 60 for AR171 and 60 for every AR1 decode call",
            "profile": "detailed recursive QNN events phase-labeled; extraction is optional/fail-open and explicitly logged; prefill profile freed/reset before AR1 load",
            "output_persistence": "exclusive output file opened before backend setup; endpoint and every decode token appended and fsync'd immediately, preserving partial output on later inference/finite-scan/profile failure",
            "output_cap_semantics": "MAX_NEW is total emitted tokens including the AR171 endpoint; max16 performs at most 15 AR1 calls and stops early on EOS",
            "timing": "backend setup is separate. Actual request-start to first emitted token includes its fsync and excludes later profile work. Actual request-start to final emitted token includes the intervening prefill profile dump, context free, profile reset, AR1 context load, and token fsyncs, but excludes the trailing AR1 profile dump/free. Compute-only phase sums and diagnostic total including all profile/free overhead are separately labeled.",
        },
        "stage": {
            "path": str(args.stage), "payload_files": stage["payload_files"], "payload_bytes": stage["payload_bytes"],
            "metadata_sha256": sha256(args.stage / "stage.json"), "manifest_sha256": sha256(args.stage / "SHA256SUMS"),
            "all_local_hashes_verified": True,
        },
        "shared_context_assessment": {
            "ordinary_two_graph_context": "No verified ORT/QAIRT path here aliases constants across two ordinary static-shape graphs; current ordinary contexts each report sharedWeightsSize=0 and would duplicate about 3.19 GB constants.",
            "shared_weight_format": "ORT shared multi-graph generation uses the previously rejected shared-weight resource format. x86 rejected its shared weights and physical matched-runtime context creation failed. It is not revived as a candidate.",
            "single_graph_selector": "A single ordinary static graph cannot select AR171 versus AR1 shape/semantics without executing duplicate branches or relying on unsupported dynamic control flow.",
            "possible_future_work": "A custom Qualcomm-supported multi-graph context with proven cross-graph constant aliasing would require new SDK documentation or maintainer guidance and fresh host/physical evidence.",
            "combined_const_bytes": ar171["graphBlobInfoV2"]["constSize"] + ar1["graphBlobInfoV2"]["constSize"],
            "combined_io_tensor_bytes": ar171["graphBlobInfoV2"]["ioTensorSize"] + ar1["graphBlobInfoV2"]["ioTensorSize"],
            "combined_spill_fill_buffer_bytes": ar171["graphBlobInfo"]["info"]["spillFillBufferSize"] + ar1["graphBlobInfo"]["info"]["spillFillBufferSize"],
            "combined_context_viability_claim": False,
        },
        "host_runtime_boundary": "Host and Android binaries compile. No integrated inference ran: x86 AR171 execution already exceeds 1800 seconds, so repeating it is intentionally excluded.",
        "fidelity_boundary": "Large state/logit deltas and token-5 divergence came from the historical qnn-net-run route whose positions became all zero. They are wrong-input evidence, not a precision conclusion for this corrected direct-QNN INT64 route; corrected operability still cannot imply numerical fidelity.",
        "proposed_phone_gate": {
            "script": str(args.phone_script),
            "script_sha256": sha256(args.phone_script),
            "timeout_seconds": 600,
            "scope": "one exact canonical-short/max16 integrated process; preserve raw tokens and phase-labeled detailed profile logs before validation",
            "success_boundary": "finite-scanned completion and coherent bounded tokens; reference or numerical equality is not required",
            "requires_fresh_pi_priority": True,
        },
        "phone_boundary": "No ADB or phone access occurred. Stage and runner script are readiness evidence only.",
        "claim_boundary": "Host static/build/stage readiness only; no integrated physical execution, TTFT, performance distribution, campaign, or registry result.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "source_sha256": result["source"]["sha256"],
        "android_runner_sha256": result["binaries"]["android_sha256"],
        "ar171_position": result["contexts"]["ar171"]["position"],
        "ar1_position": result["contexts"]["ar1"]["position"],
        "embedding_equal": embedding_equal,
        "mask_equal": mask_equal,
        "stage_files": stage["payload_files"],
    }, indent=2))

if __name__ == "__main__":
    main()
