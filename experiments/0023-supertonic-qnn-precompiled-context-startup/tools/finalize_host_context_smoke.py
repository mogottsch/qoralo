#!/usr/bin/env python3
"""Commit a normalized functional EPContext smoke from ignored host artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

COMPONENTS = ("duration", "text", "vector", "vocoder")
GRAPH_NAMES = {
    "duration": "duration_predictor.onnx",
    "text": "text_encoder.onnx",
    "vector": "vector_estimator-stable-softplus.onnx",
    "vocoder": "vocoder.onnx",
}
EXPECTED_GRAPHS = {
    "duration": "8a1875ef0f6960ca16fc06814509b1c3258e8f50b04a5d590d3ab6db8c775016",
    "text": "769fd1d257674e8624bdea941f7a903d9460051f9845b604cd2c2980f281a8c3",
    "vector": "f2318c54726a034dcc89aa9818a91f1c3db0e3067b9932c7c2dae65957897c7b",
    "vocoder": "35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7",
}
TRANSCRIPT_SHA = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path, relative_to: Path | None = None) -> dict[str, Any]:
    name = path.relative_to(relative_to).as_posix() if relative_to else path.name
    return {"path": name, "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def copy(path: Path, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
    return file_record(destination)


def ort_provider_summary(path: Path) -> dict[str, Any]:
    events = json.loads(path.read_text(encoding="utf-8"))
    node_events = [item for item in events if item.get("cat") == "Node"]
    providers: dict[str, int] = {}
    for item in node_events:
        provider = item.get("args", {}).get("provider", "missing")
        providers[provider] = providers.get(provider, 0) + 1
    return {
        "events": len(events),
        "node_events": len(node_events),
        "provider_node_events": providers,
        "qnn_only_nodes": bool(node_events) and set(providers) == {"QNNExecutionProvider"},
    }


def qnn_root_summary(path: Path) -> dict[str, Any]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    root = [item for item in rows if item["Event Level"] == "ROOT"]
    return {
        "rows": len(rows),
        "root_events": [
            {
                "message": item["Message"],
                "value": int(item["Time"]),
                "unit": item["Unit of Measurement"],
                "timing_source": item["Timing Source"],
                "identifier": item["Event Identifier"],
            }
            for item in root
        ],
        "has_accelerator_execute_cycles": any(
            item["Event Identifier"] == "Accelerator (execute) time (cycles)"
            and int(item["Time"]) > 0
            for item in rows
        ),
        "has_load_binary_event": any("load binary" in item["Event Identifier"] for item in rows),
        "has_finalize_event": any(item["Message"] == "FINALIZE" for item in rows),
    }


def one_component(args: argparse.Namespace, component: str) -> dict[str, Any]:
    generation_dir = args.generation / component
    reload_dir = args.reload / component
    generated = load(generation_dir / "generate-result.json")
    reloaded = load(reload_dir / "reload-result.json")
    source = args.graphs / GRAPH_NAMES[component]
    if sha(source) != EXPECTED_GRAPHS[component]:
        raise SystemExit(f"source graph hash mismatch: {source}")
    if generated["result"] != "passed" or reloaded["result"] != "passed":
        raise SystemExit(f"component did not pass: {component}")
    if not reloaded["source_onnx_absent_from_isolation_root"]:
        raise SystemExit(f"reload was not source-isolated: {component}")
    for artifact in ("descriptor", "external_context_binary"):
        if generated["artifacts"][artifact]["sha256"] != reloaded["artifacts"][artifact]["sha256"]:
            raise SystemExit(f"{component}: {artifact} changed before reload")
    if generated["output"]["sha256"] != reloaded["output"]["sha256"]:
        raise SystemExit(f"{component}: generation/reload outputs differ")

    raw_dir = args.output / "raw"
    profile_dir = args.output / "profiles"
    copied: dict[str, dict[str, Any]] = {}
    copied["generation_result"] = copy(
        generation_dir / "generate-result.json", raw_dir / f"{component}-generation.json"
    )
    copied["reload_result"] = copy(
        reload_dir / "reload-result.json", raw_dir / f"{component}-reload.json"
    )
    generated_ort = next((generation_dir / "profiles").glob("generate_*.json"))
    reload_ort = next((reload_dir / "profiles").glob("reload_*.json"))
    generated_qnn = generation_dir / "profiles/generate.qnn.csv"
    reload_qnn = reload_dir / "profiles/reload.qnn.csv"
    copied["generation_ort_profile"] = copy(
        generated_ort, profile_dir / f"{component}-generation.ort.json"
    )
    copied["generation_qnn_profile"] = copy(
        generated_qnn, profile_dir / f"{component}-generation.qnn.csv"
    )
    copied["reload_ort_profile"] = copy(
        reload_ort, profile_dir / f"{component}-reload.ort.json"
    )
    copied["reload_qnn_profile"] = copy(
        reload_qnn, profile_dir / f"{component}-reload.qnn.csv"
    )

    gen_create = generated["timing"]["session_create_seconds"]
    reload_create = reloaded["timing"]["session_create_seconds"]
    return {
        "source_graph": {
            "name": GRAPH_NAMES[component],
            "bytes": source.stat().st_size,
            "sha256": sha(source),
        },
        "external_context": {
            "descriptor": generated["artifacts"]["descriptor"],
            "binary": generated["artifacts"]["external_context_binary"],
        },
        "functional_checks": {
            "fallback_disabled_generation": generated["configuration"]["session.disable_cpu_ep_fallback"] == "1",
            "fallback_disabled_reload": reloaded["configuration"]["session.disable_cpu_ep_fallback"] == "1",
            "external_non_embedded_generation": generated["configuration"]["ep.context_embed_mode"] == "0",
            "fresh_reload_process": reloaded["fresh_process"],
            "source_onnx_absent_from_reload_mount": reloaded["source_onnx_absent_from_isolation_root"],
            "finite_output": generated["output"]["finite"] and reloaded["output"]["finite"],
            "generation_reload_output_sha256_equal": generated["output"]["sha256"] == reloaded["output"]["sha256"],
        },
        "output": generated["output"],
        "profiles": {
            "generation_ort": ort_provider_summary(generated_ort),
            "generation_qnn": qnn_root_summary(generated_qnn),
            "reload_ort": ort_provider_summary(reload_ort),
            "reload_qnn": qnn_root_summary(reload_qnn),
        },
        "copied_evidence": copied,
        "nonisolated_observed_timings_excluded_from_startup_claim": {
            "source_session_create_seconds": gen_create,
            "context_reload_session_create_seconds": reload_create,
            "source_minus_reload_seconds": gen_create - reload_create,
            "source_over_reload_ratio": gen_create / reload_create,
            "generation_first_run_seconds": generated["timing"]["first_run_seconds"],
            "reload_first_run_seconds": reloaded["timing"]["first_run_seconds"],
        },
    }


def run(args: argparse.Namespace) -> None:
    if sha(args.transcript) != TRANSCRIPT_SHA:
        raise SystemExit("legacy transcript hash mismatch")
    args.output.mkdir(parents=True, exist_ok=True)
    components = {name: one_component(args, name) for name in COMPONENTS}
    all_checks = [
        value
        for item in components.values()
        for value in item["functional_checks"].values()
    ]
    all_profiles = [
        profile["qnn_only_nodes"]
        for item in components.values()
        for key, profile in item["profiles"].items()
        if key.endswith("_ort")
    ]
    result = {
        "schema_version": 1,
        "experiment": "0023-supertonic-qnn-precompiled-context-startup",
        "recorded_date": "2026-08-22",
        "status": "functional_host_context_smoke_passed_timing_excluded",
        "question": "Can the accepted Supertonic all-HTP route generate external QNN contexts and reload them without source ONNX?",
        "answer": "yes_on_host_qnn_htp_for_all_four_components",
        "input": {
            "route": "accepted experiment-0011 stable-Softplus all-HTP route",
            "transcript": file_record(args.transcript),
            "processed_text_length": 239,
            "latent_length": 238,
            "voice": "official public M1 / semantic SID5",
        },
        "runtime": {
            "onnxruntime": "1.27.1 host QNN build",
            "qairt": "2.49.0.260730",
            "backend": "QNN HTP host emulation, soc_model 43",
            "provider_options": {
                "offload_graph_io_quantization": "0",
                "htp_performance_mode": "burst",
                "soc_model": "43",
            },
            "session_options": {
                "session.disable_cpu_ep_fallback": "1",
                "generation": {
                    "ep.context_enable": "1",
                    "ep.context_embed_mode": "0",
                    "ep.context_file_path": "per-component descriptor path",
                },
                "reload": {
                    "ep.context_enable": "not set",
                    "ep.context_file_path": "per-component descriptor path",
                },
            },
        },
        "components": components,
        "aggregate": {
            "components": len(components),
            "all_functional_checks_passed": all(all_checks),
            "all_ort_node_events_qnn_only": all(all_profiles),
            "total_external_context_bytes": sum(
                item["external_context"]["descriptor"]["bytes"]
                + item["external_context"]["binary"]["bytes"]
                for item in components.values()
            ),
        },
        "coordination_and_timing_exclusion": {
            "classification": "functional evidence valid; all timing/resource observations excluded from startup comparison",
            "reason": "The host QNN generation/reload wave overlapped experiment 0017's serialized host QNN run before its owner replied to the coordination request.",
            "overlap_windows_utc": [
                "2026-08-22T10:53Z to 10:54Z initial duration smoke",
                "2026-08-22T10:55:56Z to 11:08:02Z four-component context generation",
                "2026-08-22T11:08:35Z to 11:22:46Z four-component isolated reload/execution",
            ],
            "disclosed_to": ["Jens", "Pi", "Ben"],
            "performance_claim_permitted": False,
            "resource_claim_permitted": False,
            "required_follow_up": "After explicit clearance, run at least three clean fresh-process cold setup measurements per source/context arm with no concurrent QNN/HtpPrepare activity.",
        },
        "claim_boundary": {
            "established": [
                "All four accepted Supertonic graph identities generated external QNN EPContext descriptor/binary pairs on host QNN HTP with ORT CPU fallback disabled.",
                "All four independently reloaded in fresh isolated containers where source ONNX was not mounted.",
                "Every recorded ORT node event was assigned to QNNExecutionProvider and outputs were finite.",
            ],
            "not_established": [
                "isolated setup performance or speedup",
                "physical phone HTP execution",
                "end-to-end context-route WAV validity",
                "three-process cold setup distributions",
            ],
        },
    }
    if not result["aggregate"]["all_functional_checks_passed"]:
        raise SystemExit("functional checks failed")
    if not result["aggregate"]["all_ort_node_events_qnn_only"]:
        raise SystemExit("non-QNN ORT node event found")
    (args.output / "host-context-functional-smoke.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result["aggregate"], indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation", type=Path, required=True)
    parser.add_argument("--reload", type=Path, required=True)
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
