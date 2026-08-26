#!/usr/bin/env python3
"""Fail-closed validation for the separate Android LLM benchmark registry."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REGISTRY_PATH = HERE / "registry.json"
SCHEMA_PATH = HERE / "schema.json"
EXPECTED_DEVICE = {
    "model": "SM-S918B",
    "soc": "SM8550",
    "serial": "R5CW81PR8SY",
    "abi": "arm64-v8a",
}
EXPECTED_TIERS = ("short", "medium", "long")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_file(relative: str, label: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        fail(f"{label}: path escapes repository: {relative}")
    if not path.is_file():
        fail(f"{label}: missing file: {relative}")
    return path


def close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-9)


def required_null_reason(container: dict, value, key: str, label: str) -> None:
    if value is None and not container.get(key, "").strip():
        fail(f"{label}: null {key} lacks an explicit missing reason")


def validate_workload(registry: dict) -> tuple[dict, dict[str, str], dict[str, int]]:
    contract_info = registry["benchmark_contract"]
    contract_path = repository_file(contract_info["path"], "benchmark contract")
    if sha256(contract_path) != contract_info["sha256"]:
        fail("benchmark contract SHA-256 does not match registry")
    contract = load_json(contract_path)
    if contract.get("contract_id") != "android-llm-inference-v1":
        fail("unexpected benchmark contract identity")

    manifest_path = repository_file(contract_info["workload_manifest"], "workload manifest")
    manifest: dict[str, str] = {}
    for number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split()
        if len(parts) != 2 or len(parts[0]) != 64:
            fail(f"workload manifest line {number} is invalid")
        digest, name = parts
        if name in manifest:
            fail(f"duplicate workload manifest entry: {name}")
        manifest[name] = digest
    if set(manifest) != {f"{tier}.json" for tier in EXPECTED_TIERS}:
        fail("workload manifest must contain exactly short.json, medium.json, and long.json")

    workload_dir = manifest_path.parent
    message_bytes: dict[str, int] = {}
    for tier in EXPECTED_TIERS:
        path = workload_dir / f"{tier}.json"
        if sha256(path) != manifest[path.name]:
            fail(f"workload hash mismatch: {path.name}")
        workload = load_json(path)
        if set(workload) != {"schema_version", "workload_id", "tier", "messages", "generation"}:
            fail(f"{path.name}: unexpected workload fields")
        if workload["schema_version"] != 1 or workload["workload_id"] != contract["contract_id"] or workload["tier"] != tier:
            fail(f"{path.name}: workload identity mismatch")
        if workload["generation"] != contract["generation"]:
            fail(f"{path.name}: generation settings differ from contract")
        messages = workload["messages"]
        if not isinstance(messages, list) or [m.get("role") for m in messages] != ["system", "user"]:
            fail(f"{path.name}: messages must be exactly system then user")
        if any(set(m) != {"role", "content"} or not isinstance(m["content"], str) or not m["content"] for m in messages):
            fail(f"{path.name}: invalid message content")
        message_bytes[tier] = sum(len(m["content"].encode("utf-8")) for m in messages)
    return contract, manifest, message_bytes


def validate_rate(run: dict, field: str, numerator: int, seconds_field: str, label: str) -> None:
    rate = run["throughput"][field]
    seconds = run["timing"][seconds_field]
    reasons = run["missing_reasons"]
    required_null_reason(reasons, rate, f"throughput.{field}", label)
    required_null_reason(reasons, seconds, f"timing.{seconds_field}", label)
    if rate is None or seconds is None:
        return
    if seconds <= 0:
        fail(f"{label}: {seconds_field} must be positive when throughput is reported")
    expected = numerator / seconds
    if not close(rate, expected):
        fail(f"{label}: {field} {rate} != {numerator}/{seconds} ({expected})")


def aggregate_values(runs: list[dict], tier: str, path: tuple[str, str]) -> list[float]:
    section, field = path
    return [r[section][field] for r in runs if r["phase"] == "loaded_route" and r["tier"] == tier and r[section][field] is not None]


def validate_entry(entry: dict, manifest: dict[str, str], message_bytes: dict[str, int], all_ids: set[str]) -> None:
    label = entry["id"]
    if label in all_ids:
        fail(f"duplicate route id: {label}")
    all_ids.add(label)

    if entry["device"] != EXPECTED_DEVICE:
        fail(f"{label}: every registry row must identify the canonical Android device")

    for source in entry["sources"]:
        repository_file(source, f"{label} source")

    for tier in EXPECTED_TIERS:
        workload = entry["workloads"][tier]
        expected_path = f"protocols/android-llm-benchmark/workloads/inference-v1/{tier}.json"
        if workload["tier"] != tier or workload["path"] != expected_path:
            fail(f"{label}: {tier} workload path/tier mismatch")
        if workload["sha256"] != manifest[f"{tier}.json"]:
            fail(f"{label}: {tier} workload SHA-256 mismatch")
        if workload["input_bytes"] != message_bytes[tier]:
            fail(f"{label}: {tier} canonical message-byte count mismatch")
        if workload["input_tokens"] + workload["max_new_tokens"] > workload["context_limit_tokens"]:
            fail(f"{label}: {tier} prompt plus output ceiling exceeds context limit")

    runs = entry["runs"]
    run_ids: set[str] = set()
    for run in runs:
        run_label = f"{label}/{run['id']}"
        if run["id"] in run_ids:
            fail(f"{label}: duplicate run id {run['id']}")
        run_ids.add(run["id"])
        expected_tokens = entry["workloads"][run["tier"]]["input_tokens"]
        if run["input_tokens"] != expected_tokens:
            fail(f"{run_label}: input token count differs from route workload")

        output = run["output"]
        output_path = repository_file(output["path"], f"{run_label} output")
        if output_path.stat().st_size != output["bytes"] or sha256(output_path) != output["sha256"]:
            fail(f"{run_label}: raw output bytes/hash mismatch")

        reasons = run["missing_reasons"]
        isolation = run["request_isolation"]
        required_null_reason(
            reasons,
            isolation["reset_or_session_creation_seconds"],
            "request_isolation.reset_or_session_creation_seconds",
            run_label,
        )
        if run["phase"] == "loaded_route" and not isolation["loaded_model_runtime_route_reused"]:
            fail(f"{run_label}: loaded-route request must retain the loaded model/runtime route")
        for field, value in run["timing"].items():
            required_null_reason(reasons, value, f"timing.{field}", run_label)
        prefill_numerator = run["input_tokens"]
        validate_rate(run, "prefill_tokens_per_second", prefill_numerator, "prefill_seconds", run_label)

        includes_first = run["throughput"]["decode_first_token_included"]
        decode_rate = run["throughput"]["decode_tokens_per_second"]
        required_null_reason(reasons, includes_first, "throughput.decode_first_token_included", run_label)
        if decode_rate is not None and includes_first is None:
            fail(f"{run_label}: decode rate requires first-token inclusion semantics")
        decode_numerator = run["output_tokens"] if includes_first else max(run["output_tokens"] - 1, 0)
        validate_rate(run, "decode_tokens_per_second", decode_numerator, "decode_seconds", run_label)

    if entry["attempt_status"] == "ran":
        first = [r for r in runs if r["phase"] == "first"]
        if len(first) != 1 or first[0]["tier"] != "short":
            fail(f"{label}: ran route requires exactly one short first request")
        for tier in EXPECTED_TIERS:
            count = sum(r["phase"] == "loaded_route" and r["tier"] == tier for r in runs)
            if count < 5:
                fail(f"{label}: ran route requires at least five loaded-route {tier} requests")

    aggregate_map = {
        "median_request_to_first_token_seconds": ("timing", "request_to_first_token_seconds"),
        "median_prefill_tokens_per_second": ("throughput", "prefill_tokens_per_second"),
        "median_decode_tokens_per_second": ("throughput", "decode_tokens_per_second"),
        "median_total_seconds": ("timing", "total_seconds"),
    }
    for tier in EXPECTED_TIERS:
        agg = entry["aggregates"]["by_tier"][tier]
        actual_count = sum(r["phase"] == "loaded_route" and r["tier"] == tier for r in runs)
        if agg["loaded_route_count"] != actual_count:
            fail(f"{label}: {tier} aggregate count mismatch")
        for aggregate_field, raw_path in aggregate_map.items():
            values = aggregate_values(runs, tier, raw_path)
            reported = agg[aggregate_field]
            if not values:
                if reported is not None:
                    fail(f"{label}: {tier} {aggregate_field} must be null without raw values")
            elif reported is None or not close(reported, statistics.median(values)):
                fail(f"{label}: {tier} {aggregate_field} does not match raw median")

    required_null_reason(entry["missing_reasons"], entry["setup"]["seconds"], "setup.seconds", label)
    required_null_reason(entry["missing_reasons"], entry["memory"]["peak_pss_bytes"], "memory.peak_pss_bytes", label)
    required_null_reason(entry["missing_reasons"], entry["memory"]["peak_vm_hwm_bytes"], "memory.peak_vm_hwm_bytes", label)
    required_null_reason(entry["missing_reasons"], entry["memory"]["sampling_interval_seconds"], "memory.sampling_interval_seconds", label)


def main() -> None:
    registry = load_json(REGISTRY_PATH)
    schema = load_json(SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(registry),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "<root>"
        fail(f"schema violation at {location}: {first.message}")
    if registry["canonical_device"] != EXPECTED_DEVICE:
        fail("canonical device identity changed")

    _contract, manifest, message_bytes = validate_workload(registry)
    ids: set[str] = set()
    for entry in registry["entries"]:
        validate_entry(entry, manifest, message_bytes, ids)

    print(
        f"PASS: {len(registry['entries'])} Android LLM registry entries; "
        "schema, protocol hashes, outputs, sanity boundaries, campaign counts, and aggregates valid"
    )


if __name__ == "__main__":
    main()
