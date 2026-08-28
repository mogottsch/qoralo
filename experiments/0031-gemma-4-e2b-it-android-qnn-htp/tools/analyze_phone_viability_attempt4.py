#!/usr/bin/env python3
"""Retain and classify the first successful physical Gemma inference gate (attempt 04)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RESULTS = EXP / "results/android-qnn-physical-viability-attempt-04"
EXPECTED_CONTEXT = "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394"
EXPECTED_SHORT_RENDERED = "b286f8dda746e8056836a2e71049df866527bee51e368363dd80cfbe27e60e7a"
EXPECTED_SHORT_TOKENS = "31a85f9c813266bbbb3505a04a226a9b184882b636cc2f6f67193a6b1eb2ad78"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_identity(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if not run.is_dir() or run.parent.name != "phone-runs":
        raise ValueError(f"unexpected run directory: {run}")

    if RESULTS.exists():
        shutil.rmtree(RESULTS)
    raw = RESULTS / "raw"
    raw.mkdir(parents=True)
    retain = [
        "adb-state.txt", "identity.txt", "battery-before.txt", "battery-before.stderr",
        "battery-after.txt", "battery-after.stderr", "thermal-before.txt", "thermal-before.stderr",
        "thermal-after.txt", "thermal-after.stderr", "storage-before.txt", "local-hash-check.txt",
        "remote-hash-check.txt", "remote-hash-check.stderr", "runtime-completeness.txt", "push.txt",
        "runner.stdout", "runner.stderr", "memory-samples.txt", "memory-samples.stderr", "exit-code.txt",
        "launcher.stdout", "launcher.stderr", "launcher-exit-code.txt", "genie-verbose.log",
        "viability-output.txt", "viability-profile.json", "pull-viability-output.txt.txt",
        "pull-viability-profile.json.txt", "pull-genie-verbose.log.txt", "process-after.txt",
        "cleanup.stdout", "cleanup.stderr", "cleanup-status.txt",
    ]
    for name in retain:
        source = run / name
        if source.exists():
            shutil.copy2(source, raw / name)

    exit_code = int((raw / "exit-code.txt").read_text().strip())
    launcher_exit = int((raw / "launcher-exit-code.txt").read_text().strip())
    stderr = (raw / "runner.stderr").read_text(errors="replace")
    stdout = (raw / "runner.stdout").read_text(errors="replace")
    log = (raw / "genie-verbose.log").read_text(errors="replace")
    cleanup = (raw / "cleanup-status.txt").read_text().strip()
    identity = parse_identity(raw / "identity.txt")
    required_identity = {
        "serial": "R5CW81PR8SY", "manufacturer": "samsung", "model": "SM-S918B",
        "device": "dm3q", "soc": "SM8550", "abi": "arm64-v8a", "boot": "1",
        "verified_boot": "green", "flash_locked": "1",
    }
    if any(identity.get(key) != value for key, value in required_identity.items()):
        raise RuntimeError(f"device identity mismatch: {identity}")

    stage_result = json.loads((EXP / "results/position-id-corrected-phone-stage/result.json").read_text())
    if stage_result["stage"]["corrected_context_sha256"] != EXPECTED_CONTEXT:
        raise RuntimeError("durable position-ID-corrected stage identity mismatch")
    physical = {
        "backend_extension_loaded": (
            "Backend extensions lib path : libQnnHtpNetRunExtensions.so" in log
            and "Unable to load backend extensions" not in stderr
        ),
        "both_graphs_initialized": "qnn-api initialized with 2 graph(s)" in log,
        "physical_soc_detected": "Detected Snapdragon SOC SM8550" in log,
        "htp_provider_initialized": "HTP: initialization completed successfully" in log,
        "qnn_htp_backend_created": "QnnBackend_create done successfully" in log,
        "qnn_device_created": "QnnDevice_create done" in log,
        "v73_stub_loaded": "libQnnHtpV73Stub.so" in log,
        "qnn_stub_connection_established": "First connection to QNN stub established" in log,
        "context_deserialized": "Context 1 deserialized on pd 0" in log,
        "weight_sharing_context_detected": "prepared with Weight Sharing enabled" in log,
        "ar128_graph_switched_and_executed": (
            "Graph ar128_cl4096_1_of_1 switch successful" in log
            and log.count("Graph ar128_cl4096_1_of_1 execution finished with result 0") == 2
        ),
        "ar1_graph_switched_and_executed": (
            "Graph ar1_cl4096_1_of_1 switch successful" in log
            and log.count("Graph ar1_cl4096_1_of_1 execution finished with result 0") == 15
        ),
    }
    if not all(physical.values()):
        raise RuntimeError(f"missing physical execution evidence: {physical}")
    if log.count("QnnGraph_execute done. status 0x0") != 17:
        raise RuntimeError("unexpected successful QNN graph execution count")
    if re.search(r"QnnCpu|CPU backend", log, re.IGNORECASE) or re.search(r"fallback", log, re.IGNORECASE):
        raise RuntimeError("CPU backend or runtime fallback marker observed")
    if any(value in log or value in stderr for value in (
        "Non-identical quantization parameters", "Model Validation Errors found",
        "Tensor not found: position_ids", "Could not find I/O tensors in loaded graphs",
    )):
        raise RuntimeError("a previously fixed validation blocker reappeared")
    if "Returning from GenieDialog_query" not in log or "Context Occupancy: 186" not in stdout:
        raise RuntimeError("dialog/query completion evidence missing")

    profile = json.loads((raw / "viability-profile.json").read_text())
    components = profile.get("components")
    if not isinstance(components, list) or len(components) != 1:
        raise RuntimeError("missing Genie profile components")
    events = {item["type"]: item for item in components[0]["events"]}
    create = events["GenieDialog_create"]
    query = events["GenieDialog_query"]
    expected_profile = {
        "num-prompt-tokens": 171,
        "num-generated-tokens": 16,
    }
    for field, expected in expected_profile.items():
        if query[field]["value"] != expected:
            raise RuntimeError(f"profile {field} mismatch")

    output_path = raw / "viability-output.txt"
    output_bytes = output_path.read_bytes()
    output_text = output_bytes.decode("utf-8")
    if not output_text.strip():
        raise RuntimeError("empty physical output")

    token_path = EXP / "protocol/token-ids/short.int32le"
    rendered_path = EXP / "protocol/rendered/short.txt"
    if sha256(rendered_path) != EXPECTED_SHORT_RENDERED or sha256(token_path) != EXPECTED_SHORT_TOKENS:
        raise RuntimeError("bound canonical short rendering/token identity mismatch")
    token_data = token_path.read_bytes()
    expected_tokens = list(struct.unpack(f"<{len(token_data) // 4}i", token_data))
    logged_lines = [line for line in log.splitlines() if "embedding-tokens:" in line]
    if len(logged_lines) != 2:
        raise RuntimeError("unexpected embedding-token log count")
    logged_prefixes = []
    for line in logged_lines:
        values = [int(value) for value in re.findall(r"\d+", line.split("embedding-tokens:", 1)[1])]
        if len(values) < 3 or values[:2] != [2, 2] or values[1:] != expected_tokens[: len(values) - 1]:
            raise RuntimeError("runtime token prefix does not prove one extra BOS")
        logged_prefixes.append(values)
    if len(expected_tokens) != 170 or query["num-prompt-tokens"]["value"] != len(expected_tokens) + 1:
        raise RuntimeError("effective prompt token delta mismatch")

    if exit_code != 0 or launcher_exit != 0 or cleanup != "absent":
        raise RuntimeError("successful gate exit/cleanup mismatch")
    if (raw / "process-after.txt").read_text().strip():
        raise RuntimeError("residual process observed")
    completeness = (raw / "runtime-completeness.txt").read_text().splitlines()
    if len(completeness) != 8 or "lib/libQnnHtpNetRunExtensions.so" not in completeness:
        raise RuntimeError("runtime completeness proof mismatch")
    for check_name in ("local-hash-check.txt", "remote-hash-check.txt"):
        check = (raw / check_name).read_text()
        if "FAILED" in check or ": OK" not in check:
            raise RuntimeError(f"stage hash check failed: {check_name}")

    memory_text = (raw / "memory-samples.txt").read_text()
    vmhwm = [int(value) for value in re.findall(r"VmHWM:\s+(\d+) kB", memory_text)]
    pss = [int(value) for value in re.findall(r"TOTAL PSS:\s+(\d+)", memory_text)]
    timestamps = [int(value) for value in re.findall(r"timestamp_ns=(\d+)", memory_text)]
    if not vmhwm or not pss or len(timestamps) != 5:
        raise RuntimeError("memory observations missing")

    raw_files = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(raw.iterdir()) if path.is_file()
    }
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "run_id": run.name,
        "classification": "positive_physical_qnn_htp_bounded_inference_with_effective_prompt_bos_mismatch",
        "status": "physical_qnn_htp_inference_positive_canonical_campaign_blocked_on_extra_bos",
        "claim_boundary": (
            "The verified SM8550 phone loaded the exact position-ID-corrected context through QnnHtp, physically "
            "executed two successful AR128 prompt graph calls and fifteen successful AR1 decode graph calls on "
            "QnnDsp/HTP, and returned a coherent 16-token UTF-8 output. No QNN CPU backend or runtime fallback marker "
            "appears. This proves bounded physical transformer inference, not a canonical campaign: Genie processed "
            "171 prompt tokens and the runtime log begins [2,2,...], proving one automatic BOS was prepended to the "
            "bound 170-token, single-BOS rendering. Campaign metrics/publication remain blocked until the effective "
            "prompt identity is corrected and separately authorized."
        ),
        "gate": {
            "bounded_viability_only": True, "canonical_campaign": False, "max_new_tokens": 16,
            "phone_lock_held_full_adb_lifecycle": True, "attempt": 4,
            "context_sha256": EXPECTED_CONTEXT, "further_retry_performed": False,
        },
        "device": identity,
        "stage": {
            "local_hash_check_passed": True, "remote_hash_check_passed": True,
            "runtime_completeness_files": completeness, "remote_cleanup_status": cleanup,
            "residual_process_observed": False,
        },
        "physical_provider_and_execution_evidence": physical,
        "execution": {
            "successful_qnn_graph_executions": 17,
            "successful_ar128_graph_executions": 2,
            "successful_ar1_graph_executions": 15,
            "qnn_graph_execute_success_status": "0x0",
            "qnn_cpu_backend_markers": 0,
            "runtime_fallback_markers": 0,
            "physical_htp_transformer_execution_proven": True,
            "uniform_integer_execution_claim": False,
            "nonfatal_uses_cross_attention_capability_log": "qnn-htp-engine does not support usesCrossAttention",
        },
        "prompt_identity": {
            "canonical_short_rendered_sha256": EXPECTED_SHORT_RENDERED,
            "bound_single_bos_token_count": len(expected_tokens),
            "bound_token_ids_int32le_sha256": EXPECTED_SHORT_TOKENS,
            "runtime_profile_prompt_tokens": query["num-prompt-tokens"]["value"],
            "runtime_logged_prefix": logged_prefixes[0],
            "runtime_token_log_truncated_by_logger": True,
            "logged_prefix_after_extra_bos_matches_bound_token_prefix": True,
            "effective_extra_leading_bos_count": 1,
            "canonical_effective_prompt_identity_passed": False,
        },
        "outcome": {
            "exit_code": exit_code, "result": "bounded_physical_inference_succeeded",
            "dialog_created": True, "graph_execution_observed": True,
            "output_created": True, "generated_tokens": query["num-generated-tokens"]["value"],
            "stop_reason": "max_tokens", "context_occupancy": 186,
            "output": {"path": "raw/viability-output.txt", "bytes": len(output_bytes), "sha256": sha256(output_path)},
            "output_sanity": {"looks_sensible": True, "issue_notes": None},
        },
        "profile_observations": {
            "scope": "bounded viability only; not canonical campaign metrics",
            "dialog_create_duration_us": create["duration"],
            "dialog_init_time_us": create["init-time"]["value"],
            "query_duration_us": query["duration"],
            "runtime_prompt_tokens": query["num-prompt-tokens"]["value"],
            "prompt_processing_rate_tokens_per_second": query["prompt-processing-rate"]["value"],
            "time_to_first_token_us": query["time-to-first-token"]["value"],
            "generated_tokens": query["num-generated-tokens"]["value"],
            "token_generation_rate_tokens_per_second": query["token-generation-rate"]["value"],
            "token_generation_time_us": query["token-generation-time"]["value"],
            "decode_rate_first_token_inclusion": None,
            "decode_rate_first_token_inclusion_reason": "Genie profile does not state whether its rate numerator includes the first token.",
        },
        "memory_observations": {
            "sample_count": len(timestamps), "method": "0.5 s target shell sampling of /proc status and dumpsys meminfo",
            "actual_intervals_ms": [round((right - left) / 1_000_000, 3) for left, right in zip(timestamps, timestamps[1:])],
            "peak_process_vmhwm_kb": max(vmhwm), "peak_sampled_total_pss_kb": max(pss),
            "limitations": "Process observations exclude unreported HTP-private memory and sparse sampling can miss peaks.",
        },
        "exact_unblock": (
            "Host-correct the automatic extra BOS without rewriting canonical workload bytes, prove the runtime-effective "
            "token sequence equals the bound single-BOS 170-token sequence, rebuild/hash the stage, and obtain a new "
            "explicit handoff before any campaign or retry."
        ),
        "raw_evidence": raw_files,
    }
    (RESULTS / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(RESULTS / "result.json")


if __name__ == "__main__":
    main()
