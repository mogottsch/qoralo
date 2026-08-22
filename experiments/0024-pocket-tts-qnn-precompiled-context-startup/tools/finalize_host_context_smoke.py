#!/usr/bin/env python3
"""Aggregate the eight matched source-generation/isolated-reload host smokes."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

ORDER = ("text", "prefill", "bos", "latent", "flow", "decoder12", "decoder6", "decoder1")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation", type=Path, required=True)
    parser.add_argument("--reload", type=Path, required=True)
    parser.add_argument("--graph-inventory", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = load(args.graph_inventory)
    if args.profile_output is not None and args.profile_output.exists():
        shutil.rmtree(args.profile_output)
    components = []
    for name in ORDER:
        generation_path = args.generation / name / "generate-result.json"
        reload_path = args.reload / name / "reload-result.json"
        generation = load(generation_path)
        reload = load(reload_path)
        generate_outputs = [item["sha256"] for item in generation["outputs"]]
        reload_outputs = [item["sha256"] for item in reload["outputs"]]
        valid = (
            generation["result"] == reload["result"] == "passed"
            and generation["provider_events"].get("QNNExecutionProvider") == 1
            and reload["provider_events"].get("QNNExecutionProvider") == 1
            and generation["provider_events"].get("CPUExecutionProvider", 0) == 0
            and reload["provider_events"].get("CPUExecutionProvider", 0) == 0
            and reload["source_onnx_absent_from_isolation_root"]
            and generate_outputs == reload_outputs
        )
        if not valid:
            raise SystemExit(f"host context proof failed for {name}")
        zero_inputs = {key: value for key, value in generation["artifacts"]["inputs"].items()
                       if value.get("elements") == 0}
        if any(item.get("bytes") != 0 or item.get("sha256") != hashlib.sha256(b"").hexdigest()
               for item in zero_inputs.values()):
            raise SystemExit(f"zero-element payload proof failed for {name}")
        committed_profiles: list[dict[str, Any]] = []
        if args.profile_output is not None:
            for mode, source in (("generation", args.generation / name / "profiles"),
                                 ("reload", args.reload / name / "profiles")):
                destination = args.profile_output / mode / name
                destination.mkdir(parents=True, exist_ok=True)
                for profile in sorted(source.iterdir()):
                    target = destination / profile.name
                    shutil.copy2(profile, target)
                    committed_profiles.append({"mode": mode, "path": str(target),
                                               "bytes": target.stat().st_size, "sha256": sha(target)})
        components.append({
            "component": name,
            "committed_profiles": committed_profiles,
            "source_graph": generation["artifacts"]["model_loaded"],
            "descriptor": generation["artifacts"]["descriptor"],
            "external_context_binary": generation["artifacts"]["external_context_binary"],
            "generation": {
                "session_create_seconds": generation["timing"]["session_create_seconds"],
                "first_run_seconds": generation["timing"]["first_run_seconds"],
                "process_to_completed_run_seconds": generation["timing"]["process_to_completed_run_seconds"],
                "provider_events": generation["provider_events"],
                "ort_profile": generation["artifacts"]["ort_profile"],
                "qnn_profile": generation["artifacts"]["qnn_profile"],
                "result_json_sha256": sha(generation_path),
            },
            "isolated_reload": {
                "session_create_seconds": reload["timing"]["session_create_seconds"],
                "first_run_seconds": reload["timing"]["first_run_seconds"],
                "process_to_completed_run_seconds": reload["timing"]["process_to_completed_run_seconds"],
                "source_onnx_absent": True,
                "provider_events": reload["provider_events"],
                "ort_profile": reload["artifacts"]["ort_profile"],
                "qnn_profile": reload["artifacts"]["qnn_profile"],
                "result_json_sha256": sha(reload_path),
            },
            "output_count": len(generate_outputs),
            "output_sha256": generate_outputs,
            "generate_reload_outputs_equal": True,
            "zero_element_inputs": zero_inputs,
        })
    generation_setup = [item["generation"]["session_create_seconds"] for item in components]
    reload_setup = [item["isolated_reload"]["session_create_seconds"] for item in components]
    result = {
        "schema_version": 1,
        "date": "2026-08-22",
        "status": "all_eight_host_context_functional_smokes_passed",
        "route": "pocket-fixed-alba-text64-cache512-canonical-v2-0024-reconstruction-derivative",
        "runtime": {"onnxruntime": "1.27.1", "qairt_qnn": "2.49.0.260730",
                    "provider": "QNNExecutionProvider", "cpu_fallback_disabled": True,
                    "threads": 1, "graph_optimization": "ORT_ENABLE_BASIC"},
        "graph_inventory": {"path": str(args.graph_inventory), "sha256": sha(args.graph_inventory),
                            "exact_0014_hashes_reproduced": inventory["exact_0014_hashes_reproduced"],
                            "documented_derivative": inventory["documented_derivatives_allowed"]},
        "components": components,
        "aggregate": {
            "component_count": len(components),
            "generation_session_create_seconds": generation_setup,
            "generation_session_create_seconds_sum": sum(generation_setup),
            "isolated_reload_session_create_seconds": reload_setup,
            "isolated_reload_session_create_seconds_sum": sum(reload_setup),
            "observed_host_smoke_setup_delta_seconds": sum(generation_setup) - sum(reload_setup),
            "source_graph_bytes_sum": sum(item["source_graph"]["bytes"] for item in components),
            "descriptor_bytes_sum": sum(item["descriptor"]["bytes"] for item in components),
            "external_context_bytes_sum": sum(item["external_context_binary"]["bytes"] for item in components),
            "generation_qnn_provider_events": len(components),
            "generation_cpu_provider_events": 0,
            "reload_qnn_provider_events": len(components),
            "reload_cpu_provider_events": 0,
            "all_outputs_equal": True,
            "all_reloads_source_onnx_absent": True,
        },
        "timing_boundary": {
            "setup": "Immediately before to immediately after one ORT InferenceSession construction in each fresh process.",
            "first_run": "Immediately before to immediately after one session.run; HTP emulation first execution is intentionally separate from setup.",
            "classification": "Functional host smoke with one fresh process per mode/component, not a three-run cold distribution and not physical-phone timing. Context generation is offline cost.",
        },
        "pre_qnn_tooling_attempts": [
            {"component": "text", "result": "launcher_error", "exit_code": 127,
             "reason": "Container used python instead of python3; no QNN session launched; excluded from measurements."},
            {"component": "decoder12", "result": "fixture_validator_error_after_context_emission",
             "reason": "Initial smoke validator rejected declared static zero-length state shapes before session.run. Retry preserved shapes with zero elements/bytes; QNN/provider claims use retry only."},
        ],
        "claim_boundary": "Host QNN provider assignment and external-context reload functionality only. Host HTP emulation is not physical phone proof. No Android E2E, cold timing distribution, warm RTF, physical RPC/cycle/HVX evidence, or new phone WAV is claimed.",
        "pending": {"android_e2e": None, "cold_source_setup_runs": None,
                    "cold_context_setup_runs": None, "warm_rtf": None,
                    "physical_htp_proof": None, "phone_wav": None,
                    "phone_listening_verdict": None,
                    "reason": "Phone unavailable; no phone access attempted."},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["aggregate"], indent=2))


if __name__ == "__main__":
    main()
