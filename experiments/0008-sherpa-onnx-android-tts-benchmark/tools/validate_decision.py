#!/usr/bin/env python3
"""Validate the published decision against normalized manifests and retained evidence."""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
REPO = EXPERIMENT.parents[1]
sys.path.insert(0, str(HERE))
from host_wav import validate_file  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: {actual!r} != {expected!r}")


def verify_evidence(manifest: dict, label: str) -> None:
    evidence = manifest.get("evidence", manifest.get("raw_evidence", []))
    if isinstance(evidence, dict):
        return
    for item in evidence:
        relative = item.get("relative_path")
        if not relative:
            continue
        path = REPO / relative
        if not path.is_file():
            raise ValueError(f"{label}: retained artifact missing: {relative}")
        exact(path.stat().st_size, item["byte_count"], f"{label} {relative} size")
        exact(digest(path), item["sha256"], f"{label} {relative} SHA-256")


def verify_campaign(published: dict) -> None:
    path = EXPERIMENT / published["manifest"]
    exact(digest(path), published["manifest_sha256"], f"{published['candidate_id']} manifest SHA-256")
    source = json.loads(path.read_text())
    exact(source["candidate_id"], published["candidate_id"], "candidate id")
    exact(source["provider"], "cpu", "provider")
    exact(source["threads"], 1, "canonical thread count")
    exact(source["metrics"]["load_wall_seconds"]["value"], published["load_wall_seconds"], "load")
    exact(source["metrics"]["warm_median_rtf"]["value"], published["warm_median_rtf"], "warm median")
    exact(statistics.median(run["rtf"]["value"] for run in source["runs"] if run["kind"] == "warm"), published["warm_median_rtf"], "recomputed median")
    source_runs = source["runs"]
    published_runs = [published["cold"], *published["warm"]]
    exact(len(source_runs), 4, "run count")
    for index, (run, summary) in enumerate(zip(source_runs, published_runs)):
        for source_key, summary_key in (("synthesis_wall_seconds", "wall_seconds"), ("audio_duration_seconds", "audio_seconds"), ("rtf", "rtf"), ("first_non_empty_callback_seconds", "callback_seconds")):
            exact(run[source_key]["value"], summary[summary_key], f"run {index} {summary_key}")
        if run["audio_validation"] != "valid":
            raise ValueError(f"run {index} is not marked valid")
        evidence = next(item for item in source["evidence"] if item["sha256"] == run["wav_sha256"])
        wav = REPO / evidence["relative_path"]
        report = validate_file(wav, run["wav_sha256"])
        exact(report.frames, run["sample_count"]["value"], f"run {index} frames")
        exact(report.sample_rate_hz, run["sample_rate_hz"]["value"], f"run {index} sample rate")
        if abs(report.duration_seconds - run["audio_duration_seconds"]["value"]) > 1e-12:
            raise ValueError(f"run {index} duration drift")
    verify_evidence(source, published["candidate_id"])


def verify_two_thread(published: dict) -> None:
    path = EXPERIMENT / published["manifest"]
    exact(digest(path), published["manifest_sha256"], "two-thread manifest SHA-256")
    source = json.loads(path.read_text())
    exact(source["threads"], 2, "optional thread count")
    exact(source["metrics"]["warm_median_rtf"]["value"], published["warm_median_rtf"], "two-thread median")
    exact(statistics.median(run["rtf"]["value"] for run in source["runs"] if run["kind"] == "warm"), published["warm_median_rtf"], "two-thread recomputed median")
    verify_evidence(source, "kokoro two-thread")
    for run in source["runs"]:
        evidence = next(item for item in source["evidence"] if item["sha256"] == run["wav_sha256"])
        validate_file(REPO / evidence["relative_path"], run["wav_sha256"])


def main() -> int:
    decision = json.loads((EXPERIMENT / "results/measured-decision.json").read_text())
    exact([item["candidate_id"] for item in decision["canonical_one_thread"]], ["pocket", "kokoro", "supertonic_3"], "fixed order")
    exact(decision["historical_only"], ["vibevoice_realtime_0_5b", "inflect_nano_v1", "kitten_tts_mini_80m_v0_8"], "historical-only candidates")
    preflight = EXPERIMENT / decision["measured_on"]["preflight_manifest"]
    exact(digest(preflight), decision["measured_on"]["preflight_manifest_sha256"], "preflight SHA-256")
    for campaign in decision["canonical_one_thread"]:
        verify_campaign(campaign)
    exact(len(decision["optional_two_thread"]), 1, "optional campaign count")
    verify_two_thread(decision["optional_two_thread"][0])
    for relative in ("results/pocket/native-crash.failure.json", "results/kokoro/native-crash.failure.json"):
        verify_evidence(json.loads((EXPERIMENT / relative).read_text()), relative)
    print("measured decision, 16 WAVs, manifests, and retained artifact hashes: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
