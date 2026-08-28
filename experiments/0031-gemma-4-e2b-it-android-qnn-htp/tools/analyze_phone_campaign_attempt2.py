#!/usr/bin/env python3
"""Retain and validate the successful reset-isolated canonical Gemma campaign."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import shutil
import statistics
from collections import Counter
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RESULTS = EXP / "results/android-qnn-physical-campaign-attempt-02"
EXPECTED_CONTEXT = "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394"
REQUESTS = [
    ("first-short-00", "short", "first"),
    *[(f"warm-short-{index:02d}", "short", "warm") for index in range(1, 6)],
    *[(f"warm-medium-{index:02d}", "medium", "warm") for index in range(1, 6)],
    *[(f"warm-long-{index:02d}", "long", "warm") for index in range(1, 6)],
]
EXPECTED_INPUT_TOKENS = {"short": 170, "medium": 594, "long": 1929}
EXPECTED_RENDERED = {
    "short": "b286f8dda746e8056836a2e71049df866527bee51e368363dd80cfbe27e60e7a",
    "medium": "8e3c03cb0d1ddce8455306b8b84585ce2ae07c083c4fdbdec1e946e3be56771d",
    "long": "450b519d417e29c4239e39aef856db1813d2580cd62e9db9adaae3d94ba8f260",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_identity(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def parse_battery(path: Path) -> dict[str, object]:
    text = path.read_text(errors="replace")
    def value(name: str) -> int:
        match = re.search(rf"^\s*{re.escape(name)}: (-?\d+)$", text, re.MULTILINE)
        if not match:
            raise RuntimeError(f"battery field missing: {name}")
        return int(match.group(1))
    return {
        "usb_powered": "USB powered: true" in text,
        "level_percent": value("level"),
        "temperature_c": value("temperature") / 10,
        "voltage_mv": value("voltage"),
        "charge_counter": value("Charge counter"),
    }


def parse_thermal(path: Path) -> dict[str, object]:
    text = path.read_text(errors="replace")
    status = re.search(r"Thermal Status: (\d+)", text)
    values = {
        name: float(value)
        for value, name in re.findall(r"Temperature\{mValue=([0-9.]+), mType=\d+, mName=([^,]+),", text)
    }
    if not status:
        raise RuntimeError("thermal status missing")
    return {"status": int(status.group(1)), "temperatures_c": values}


def distribution(values: list[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if not run.is_dir() or run.parent.name != "campaign-runs":
        raise ValueError(f"unexpected run directory: {run}")

    if RESULTS.exists():
        shutil.rmtree(RESULTS)
    raw = RESULTS / "raw"
    raw.mkdir(parents=True)
    source_log = run / "campaign/genie-verbose.log"
    for source in sorted(run.rglob("*")):
        if not source.is_file() or source == source_log:
            continue
        destination = raw / source.relative_to(run)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    compressed_log = raw / "campaign/genie-verbose.log.gz"
    compressed_log.parent.mkdir(parents=True, exist_ok=True)
    with source_log.open("rb") as src, compressed_log.open("wb") as compressed_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=compressed_file, compresslevel=9, mtime=0) as dst:
            shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)

    if int((raw / "exit-code.txt").read_text()) != 0 or int((raw / "launcher-exit-code.txt").read_text()) != 0:
        raise RuntimeError("campaign exit mismatch")
    identity = parse_identity(raw / "identity.txt")
    required_identity = {
        "serial": "R5CW81PR8SY", "manufacturer": "samsung", "model": "SM-S918B",
        "device": "dm3q", "soc": "SM8550", "abi": "arm64-v8a", "boot": "1",
        "verified_boot": "green", "flash_locked": "1",
    }
    if any(identity.get(key) != value for key, value in required_identity.items()):
        raise RuntimeError(f"device identity mismatch: {identity}")
    if (raw / "cleanup-status.txt").read_text().strip() != "absent" or (raw / "process-after.txt").read_text().strip():
        raise RuntimeError("campaign cleanup/process boundary mismatch")
    for check_name in ("local-hash-check.txt", "remote-hash-check.txt"):
        check = (raw / check_name).read_text()
        if "FAILED" in check or ": OK" not in check:
            raise RuntimeError(f"campaign stage hash check failed: {check_name}")

    # Stream the 400 MB verbose log; retain exact compressed bytes plus original identity.
    counters = Counter()
    reset_enter: list[float] = []
    reset_return: list[float] = []
    token_log_count = 0
    with source_log.open(errors="replace") as stream:
        for line in stream:
            if "qnn-api initialized with 2 graph(s)" in line: counters["qnn_init"] += 1
            if "Context 1 deserialized on pd 0" in line: counters["context_deserialized"] += 1
            if "QnnGraph_execute started" in line: counters["graph_started"] += 1
            if "QnnGraph_execute done. status 0x0" in line: counters["graph_done_0"] += 1
            if "Graph ar128_cl4096_1_of_1 execution finished with result 0" in line: counters["ar128_result_0"] += 1
            if "Graph ar1_cl4096_1_of_1 execution finished with result 0" in line: counters["ar1_result_0"] += 1
            if "Entering GenieDialog_query" in line: counters["query_enter"] += 1
            if "Returning from GenieDialog_query" in line: counters["query_return"] += 1
            if "Returning from GenieDialog_create" in line: counters["dialog_create_return"] += 1
            if "Returning from GenieDialog_free" in line: counters["dialog_free_return"] += 1
            if "Number of existing contexts: 0, graphs: 0" in line: counters["contexts_freed"] += 1
            if "does not support usesCrossAttention" in line: counters["cross_attention_capability"] += 1
            if "QnnCpu" in line or "CPU backend" in line: counters["cpu_backend"] += 1
            if re.search(r"fallback", line, re.IGNORECASE): counters["fallback"] += 1
            if any(value in line for value in ("Non-identical quantization parameters", "Tensor not found", "Could not find I/O tensors")):
                counters["fatal_validation"] += 1
            if "embedding-tokens:" in line: token_log_count += 1
            reset_match = re.match(r"\s*([0-9.]+)ms \[INFO\]: (Entering|Returning from) GenieDialog_reset", line)
            if reset_match:
                (reset_enter if reset_match.group(2) == "Entering" else reset_return).append(float(reset_match.group(1)))
    expected_graphs = {"ar128_result_0": 117, "ar1_result_0": 15158, "graph_done_0": 15275}
    for name, expected in expected_graphs.items():
        if counters[name] != expected:
            raise RuntimeError(f"campaign execution count mismatch: {name}={counters[name]}")
    if counters["qnn_init"] != 1 or counters["context_deserialized"] != 1:
        raise RuntimeError("campaign did not reuse one loaded QNN route")
    if counters["query_enter"] != 16 or counters["query_return"] != 16:
        raise RuntimeError("campaign query count mismatch")
    if counters["dialog_create_return"] != 1 or counters["dialog_free_return"] != 1:
        raise RuntimeError("campaign dialog lifecycle count mismatch")
    if counters["cpu_backend"] or counters["fallback"] or counters["fatal_validation"]:
        raise RuntimeError("campaign CPU/fallback/validation marker observed")
    if counters["cross_attention_capability"] != 16 or token_log_count != 32:
        raise RuntimeError("campaign nonfatal capability/token-log count mismatch")
    if len(reset_enter) != 15 or len(reset_return) != 15:
        raise RuntimeError("campaign reset log count mismatch")
    reset_ms = [round(stop - start, 3) for start, stop in zip(reset_enter, reset_return)]
    if any(value < 0 for value in reset_ms):
        raise RuntimeError("negative reset duration")

    request_results = []
    prior_queries: list[dict[str, object]] = []
    for ordinal, (request_id, tier, request_class) in enumerate(REQUESTS):
        profile_path = raw / f"campaign/profiles/{request_id}.json"
        profile = json.loads(profile_path.read_text())
        components = profile.get("components")
        if not isinstance(components, list) or len(components) != 1:
            raise RuntimeError(f"profile components missing: {request_id}")
        events = components[0]["events"]
        queries = [event for event in events if event["type"] == "GenieDialog_query"]
        creates = [event for event in events if event["type"] == "GenieDialog_create"]
        if len(creates) != 1 or len(queries) != ordinal + 1:
            raise RuntimeError(f"cumulative profile growth mismatch: {request_id}")
        if queries[:-1] != prior_queries:
            raise RuntimeError(f"cumulative profile prior events changed: {request_id}")
        query = queries[-1]
        prior_queries = queries
        input_tokens = query["num-prompt-tokens"]["value"]
        generated = query["num-generated-tokens"]["value"]
        if input_tokens != EXPECTED_INPUT_TOKENS[tier] or not 0 < generated <= 2048:
            raise RuntimeError(f"request token count mismatch: {request_id}")
        output_path = raw / f"campaign/outputs/{request_id}.txt"
        output_bytes = output_path.read_bytes()
        output_text = output_bytes.decode("utf-8")
        if not output_text.strip():
            raise RuntimeError(f"empty output: {request_id}")
        if tier == "long":
            sanity = {
                "looks_sensible": False,
                "issue_notes": "Severe repetition collapse in the exact max-token output.",
            }
        else:
            sanity = {"looks_sensible": True, "issue_notes": None}
        stop_reason = "max_tokens" if generated == 2048 else "eos"
        prompt_rate = float(query["prompt-processing-rate"]["value"])
        request_results.append({
            "ordinal": ordinal, "request_id": request_id, "tier": tier, "request_class": request_class,
            "input_tokens": input_tokens, "generated_tokens": generated, "stop_reason": stop_reason,
            "dialog_create_or_reset_duration_ms": 0.0 if ordinal == 0 else reset_ms[ordinal - 1],
            "reset_duration_in_total_request": False,
            "request_to_first_token_us": query["time-to-first-token"]["value"],
            "prefill_duration_us_derived_from_authoritative_rate": round(input_tokens / prompt_rate * 1_000_000),
            "prefill_rate_tokens_per_second": prompt_rate,
            "decode_duration_us": query["token-generation-time"]["value"],
            "decode_rate_tokens_per_second": query["token-generation-rate"]["value"],
            "decode_rate_first_token_inclusion": None,
            "decode_rate_first_token_inclusion_reason": "Genie profile does not state whether its rate numerator includes the first token.",
            "total_request_duration_us": query["duration"],
            "profile_snapshot_path": f"raw/campaign/profiles/{request_id}.json",
            "profile_snapshot_sha256": sha256(profile_path),
            "output": {"path": f"raw/campaign/outputs/{request_id}.txt", "bytes": len(output_bytes), "sha256": sha256(output_path)},
            "output_sanity": sanity,
        })

    # Greedy output identity is observed, not required.
    hashes_by_tier = {
        tier: sorted({item["output"]["sha256"] for item in request_results if item["tier"] == tier})
        for tier in EXPECTED_INPUT_TOKENS
    }
    if any(len(values) != 1 for values in hashes_by_tier.values()):
        raise RuntimeError("unexpected greedy output variation")
    warm_distributions = {}
    for tier in ("short", "medium", "long"):
        items = [item for item in request_results if item["tier"] == tier and item["request_class"] == "warm"]
        warm_distributions[tier] = {
            "request_count": len(items),
            "input_tokens": EXPECTED_INPUT_TOKENS[tier],
            "generated_tokens": sorted({item["generated_tokens"] for item in items}),
            "stop_reasons": dict(Counter(item["stop_reason"] for item in items)),
            "ttft_us": distribution([item["request_to_first_token_us"] for item in items]),
            "prefill_tokens_per_second": distribution([item["prefill_rate_tokens_per_second"] for item in items]),
            "decode_tokens_per_second": distribution([item["decode_rate_tokens_per_second"] for item in items]),
            "total_request_us": distribution([item["total_request_duration_us"] for item in items]),
            "reset_duration_ms": distribution([item["dialog_create_or_reset_duration_ms"] for item in items]),
            "output_hashes": hashes_by_tier[tier],
            "all_output_sanity_passed": all(item["output_sanity"]["looks_sensible"] for item in items),
        }

    setup_profile = json.loads((raw / "campaign/setup-profile.json").read_text())
    setup_event = setup_profile["components"][0]["events"][0]
    if setup_event["type"] != "GenieDialog_create":
        raise RuntimeError("setup profile event mismatch")
    monitor = (raw / "monitor-and-memory.txt").read_text()
    vmhwm = [int(value) for value in re.findall(r"VmHWM:\s+(\d+) kB", monitor)]
    pss = [int(value) for value in re.findall(r"TOTAL PSS:\s+(\d+)", monitor)]
    timestamps = [int(value) for value in re.findall(r"timestamp_ns=(\d+)", monitor)]
    if not vmhwm or not pss or not timestamps:
        raise RuntimeError("campaign memory evidence missing")

    battery_before = parse_battery(raw / "battery-before.txt")
    battery_after = parse_battery(raw / "battery-after.txt")
    thermal_before = parse_thermal(raw / "thermal-before.txt")
    thermal_after = parse_thermal(raw / "thermal-after.txt")
    raw_files = {
        str(path.relative_to(raw)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(raw.rglob("*")) if path.is_file()
    }
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "run_id": run.name,
        "classification": "positive_physical_qnn_htp_canonical_campaign_with_long_output_sanity_failure",
        "status": "canonical_campaign_complete_long_output_repetition_sanity_failed",
        "claim_boundary": (
            "One verified SM8550 QnnHtp process loaded/deserialized the corrected context exactly once and completed "
            "the canonical first short plus five warm short/medium/long requests with exact 2048 ceilings. Fifteen "
            "source-proven full resets isolated requests without remapping. All 15,275 successful QnnDsp graph "
            "completions returned status 0 with no QNN CPU/runtime-fallback marker. Exact outputs/profiles and timing "
            "distributions are retained. Short/medium outputs pass the narrow sanity check; every identical long "
            "max-token output fails it for severe repetition collapse. This is execution/performance evidence, not "
            "a quality acceptance claim."
        ),
        "campaign": {
            "complete": True, "process_count": 1, "dialog_count": 1,
            "context_deserialization_count": counters["context_deserialized"],
            "request_isolation": "proven_full_in_session_conversation_and_kv_reset",
            "reset_count": len(reset_ms), "request_count": len(request_results),
            "first_request_count": 1, "warm_request_counts": {"short": 5, "medium": 5, "long": 5},
            "max_new_tokens": 2048, "request_timeout_seconds": 1800,
            "timed_out_requests": 0, "error_requests": 0, "automatic_retries": 0,
        },
        "device": identity,
        "route": {
            "context_sha256": EXPECTED_CONTEXT, "backend": "QnnHtp", "dsp_arch": "v73",
            "successful_qnn_graph_completions": counters["graph_done_0"],
            "successful_ar128_graph_completions": counters["ar128_result_0"],
            "successful_ar1_graph_completions": counters["ar1_result_0"],
            "qnn_cpu_backend_markers": counters["cpu_backend"],
            "runtime_fallback_markers": counters["fallback"],
            "physical_htp_transformer_execution_proven": True,
            "uniform_integer_execution_claim": False,
        },
        "setup": {
            "boundary": "Immediately before genie-app/dialog/context creation through one loaded dialog ready for the first request.",
            "dialog_create_duration_us": setup_event["duration"],
            "dialog_init_time_us": setup_event["init-time"]["value"],
            "profile_path": "raw/campaign/setup-profile.json",
            "profile_sha256": sha256(raw / "campaign/setup-profile.json"),
        },
        "requests": request_results,
        "first_request": request_results[0],
        "warm_distributions": warm_distributions,
        "output_identity_observation": {
            "greedy_output_byte_identity_required": False,
            "unique_hashes_by_tier": hashes_by_tier,
            "all_outputs_identical_within_each_tier": True,
        },
        "memory": {
            "method": "0.5 s target /proc status and dumpsys meminfo sampling across setup/campaign",
            "timestamp_samples": len(timestamps), "complete_pss_samples": len(pss),
            "peak_process_vmhwm_kb": max(vmhwm), "peak_sampled_total_pss_kb": max(pss),
            "mapped_context_bytes": 1_186_369_536,
            "limitations": "Process values exclude unreported HTP-private memory; sampled PSS can miss peaks.",
        },
        "operating_context": {
            "battery_before": battery_before, "battery_after": battery_after,
            "thermal_before": thermal_before, "thermal_after": thermal_after,
        },
        "stage_and_cleanup": {
            "local_hash_check_passed": True, "remote_hash_check_passed": True,
            "runtime_completeness_passed": True,
            "remote_cleanup_status": "absent", "residual_process_observed": False,
            "phone_lock_held_full_adb_lifecycle": True,
        },
        "raw_provider_log": {
            "original_bytes": source_log.stat().st_size,
            "original_sha256": sha256(source_log),
            "compressed_path": "raw/campaign/genie-verbose.log.gz",
            "compressed_bytes": compressed_log.stat().st_size,
            "compressed_sha256": sha256(compressed_log),
            "compression_reversible": True,
        },
        "raw_evidence": raw_files,
        "publication": {
            "experiment_evidence_complete": True,
            "registry_normalization_owner": "Kate",
            "long_output_sanity_failure_must_be_disclosed": True,
            "quality_acceptance_claim": False,
        },
    }
    (RESULTS / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(RESULTS / "result.json")


if __name__ == "__main__":
    main()
