#!/usr/bin/env python3
"""Validate pulled 0023 phone evidence before scoped cleanup."""

from __future__ import annotations

import argparse
import array
import csv
import hashlib
import json
import math
import statistics
import wave
from pathlib import Path
from typing import Any

HISTORICAL_ACCEPTED_WAV = "47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c"
EXPECTED_FRAMES = 729746
EXPECTED_RATE = 44100


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def parse_memory(path: Path) -> dict[str, int]:
    values = {}
    for line in path.read_text().splitlines():
        key, value = line.split("=", 1)
        values[key] = int(value)
    if values.get("runner_exit_code") != 0:
        raise SystemExit(f"runner failed per {path}")
    return values


def setup_summary(root: Path, arm: str) -> dict[str, Any]:
    runs = []
    for index in (1, 2, 3):
        directory = root / f"{arm}-setup-{index}"
        result = load_json(directory / "stdout.json")
        if result["result"] != "passed" or result["arm"] != arm or result["action"] != "setup":
            raise SystemExit(f"invalid setup result: {directory}")
        memory = parse_memory(directory / "memory.txt")
        runs.append(
            {
                "run_index": index,
                "session_create_seconds": result["session_create_seconds"],
                "process_entry_to_ready_seconds": result["process_entry_to_ready_seconds"],
                "max_rss_at_ready_kb": result["max_rss_at_ready_kb"],
                "sampled_memory": memory,
                "raw_result": file_record(directory / "stdout.json"),
            }
        )
    sequence = [item["session_create_seconds"]["sequence"] for item in runs]
    return {
        "runs": runs,
        "sequence_values_seconds": sequence,
        "median_seconds": statistics.median(sequence),
        "minimum_seconds": min(sequence),
        "maximum_seconds": max(sequence),
        "population_stddev_seconds": statistics.pstdev(sequence),
    }


def validate_wav(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as stream:
        info = {
            "channels": stream.getnchannels(),
            "sample_width_bytes": stream.getsampwidth(),
            "sample_rate_hz": stream.getframerate(),
            "frames": stream.getnframes(),
            "compression": stream.getcomptype(),
        }
    if info != {
        "channels": 1,
        "sample_width_bytes": 2,
        "sample_rate_hz": EXPECTED_RATE,
        "frames": EXPECTED_FRAMES,
        "compression": "NONE",
    }:
        raise SystemExit(f"invalid WAV structure {path}: {info}")
    info.update(
        duration_seconds=EXPECTED_FRAMES / EXPECTED_RATE,
        bytes=path.stat().st_size,
        sha256=sha(path),
    )
    return info


def e2e_summary(root: Path, arm: str) -> dict[str, Any]:
    directory = root / f"{arm}-e2e"
    result = load_json(directory / "stdout.json")
    if result["result"] != "passed" or result["arm"] != arm or result["action"] != "e2e":
        raise SystemExit(f"invalid E2E result: {directory}")
    if result["runs"] != 6 or len(result["run_total_seconds"]) != 6 or len(result["rtf"]) != 6:
        raise SystemExit(f"invalid run count: {directory}")
    raw = directory / "output.raw"
    wav = directory / "output.wav"
    if raw.stat().st_size != EXPECTED_FRAMES * 4:
        raise SystemExit(f"invalid raw size: {raw}")
    wav_info = validate_wav(wav)
    verdict = (
        {
            "status": "accepted",
            "reason": "byte-identical SHA-256 to Moritz-accepted experiment-0011 all-HTP WAV",
            "historical_hash": HISTORICAL_ACCEPTED_WAV,
        }
        if wav_info["sha256"] == HISTORICAL_ACCEPTED_WAV
        else {
            "status": "not_reviewed",
            "reason": "new byte-different WAV requires Moritz's exact-hash listening verdict",
            "historical_hash": HISTORICAL_ACCEPTED_WAV,
        }
    )
    return {
        "runner": result,
        "sampled_memory": parse_memory(directory / "memory.txt"),
        "raw": file_record(raw),
        "wav": wav_info,
        "listening": verdict,
        "first": {
            "seconds": result["run_total_seconds"][0],
            "rtf": result["rtf"][0],
        },
        "warm": {
            "seconds": result["run_total_seconds"][1:],
            "rtf": result["rtf"][1:],
            "median_seconds": statistics.median(result["run_total_seconds"][1:]),
            "median_rtf": statistics.median(result["rtf"][1:]),
        },
    }


def compare_raw(left: Path, right: Path) -> dict[str, Any]:
    a = array.array("f")
    b = array.array("f")
    with left.open("rb") as stream:
        a.fromfile(stream, EXPECTED_FRAMES)
    with right.open("rb") as stream:
        b.fromfile(stream, EXPECTED_FRAMES)
    sum_sq = 0.0
    sum_a2 = 0.0
    sum_b2 = 0.0
    dot = 0.0
    max_abs = 0.0
    for x, y in zip(a, b):
        delta = float(x) - float(y)
        absolute = abs(delta)
        max_abs = max(max_abs, absolute)
        sum_sq += delta * delta
        sum_a2 += float(x) * float(x)
        sum_b2 += float(y) * float(y)
        dot += float(x) * float(y)
    return {
        "elements": len(a),
        "byte_identical": left.read_bytes() == right.read_bytes(),
        "max_abs": max_abs,
        "rmse": math.sqrt(sum_sq / len(a)),
        "cosine": dot / math.sqrt(sum_a2 * sum_b2),
        "interpretation": "descriptive only; no numerical acceptance gate",
    }


def physical_proof(root: Path) -> dict[str, Any]:
    directory = root / "context-proof"
    result = load_json(directory / "stdout.json")
    if result["result"] != "passed" or result["arm"] != "context" or result["action"] != "proof":
        raise SystemExit("invalid context proof result")
    profiles = directory / "profiles"
    ort_profiles = sorted(profiles.glob("*.json"))
    qnn_profiles = sorted(profiles.glob("*.qnn.csv"))
    if len(ort_profiles) != 4 or len(qnn_profiles) != 4:
        raise SystemExit(f"expected four ORT and QNN profiles, got {len(ort_profiles)} / {len(qnn_profiles)}")
    ort_records = []
    for path in ort_profiles:
        events = json.loads(path.read_text())
        node_events = [item for item in events if item.get("cat") == "Node"]
        providers = {item.get("args", {}).get("provider") for item in node_events}
        if not node_events or providers != {"QNNExecutionProvider"}:
            raise SystemExit(f"provider proof failed: {path}: {providers}")
        ort_records.append({**file_record(path), "node_events": len(node_events), "providers": sorted(providers)})
    qnn_records = []
    required = (
        "RPC (execute) time",
        "QNN accelerator (execute) time",
        "Accelerator (execute) time (cycles)",
        "Number of HVX threads used",
    )
    for path in qnn_profiles:
        rows = list(csv.DictReader(path.open()))
        identifiers = [row["Event Identifier"] for row in rows]
        for term in required:
            if not any(term in identifier for identifier in identifiers):
                raise SystemExit(f"missing {term}: {path}")
        hvx = [int(row["Time"]) for row in rows if row["Event Identifier"] == "Number of HVX threads used"]
        if not hvx or set(hvx) != {4}:
            raise SystemExit(f"HVX proof failed: {path}: {hvx}")
        qnn_records.append(
            {
                **file_record(path),
                "hvx_thread_values": hvx,
                "rpc_events": sum("RPC (execute) time" in item for item in identifiers),
                "accelerator_us_events": sum("QNN accelerator (execute) time" in item for item in identifiers),
                "accelerator_cycle_events": sum("Accelerator (execute) time (cycles)" in item for item in identifiers),
            }
        )
    return {
        "runner": result,
        "sampled_memory": parse_memory(directory / "memory.txt"),
        "ort_profiles": ort_records,
        "qnn_profiles": qnn_records,
        "fallback_disabled": result["fallback_disabled"],
        "source_onnx_unavailable": True,
        "physical_qnn_htp_proven": True,
        "excluded_from_setup_and_e2e_timing": True,
    }


def run(args: argparse.Namespace) -> None:
    evidence = args.campaign / "device-evidence"
    source_setup = setup_summary(evidence, "source")
    context_setup = setup_summary(evidence, "context")
    source_e2e = e2e_summary(evidence, "source")
    context_e2e = e2e_summary(evidence, "context")
    proof = physical_proof(evidence)
    delta = source_setup["median_seconds"] - context_setup["median_seconds"]
    result = {
        "schema_version": 1,
        "experiment": "0023-supertonic-qnn-precompiled-context-startup",
        "status": "phone_campaign_pulled_and_validated_cleanup_pending",
        "setup": {"source": source_setup, "context": context_setup},
        "setup_comparison": {
            "source_median_seconds": source_setup["median_seconds"],
            "context_median_seconds": context_setup["median_seconds"],
            "source_minus_context_median_seconds": delta,
            "source_over_context_median_ratio": source_setup["median_seconds"] / context_setup["median_seconds"],
            "context_setup_reduction_percent": delta / source_setup["median_seconds"] * 100.0,
        },
        "e2e": {"source": source_e2e, "context": context_e2e},
        "source_vs_context_raw_comparison": compare_raw(
            evidence / "source-e2e/output.raw", evidence / "context-e2e/output.raw"
        ),
        "physical_proof": proof,
        "structural_wav_valid": True,
        "context_source_unavailable_gate": (args.campaign / "context-source-unavailable-gate.txt").read_text().strip(),
        "cleanup": "pending outer shell trap",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"setup_comparison": result["setup_comparison"], "structural_wav_valid": True}, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
