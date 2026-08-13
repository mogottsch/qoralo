#!/usr/bin/env python3
"""Validate the completed thread sweep and build deterministic measured reports."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
RESULTS = ROOT / "results"
sys.path.insert(0, str(ROOT / "tools"))
import run_sweep  # noqa: E402

REPORT_JSON = RESULTS / "measured-thread-sweep.json"
REPORT_MD = RESULTS / "measured-thread-sweep.md"
HANDOFF = ROOT / "WORKER_HANDOFF.md"
MIB = 1024 * 1024


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical_status(status: str | None) -> str:
    if status is None:
        return "UNAVAILABLE"
    if status == "STATUS_0":
        return "NONE"
    if status.startswith("STATUS_") and status.removeprefix("STATUS_").isdigit():
        level = int(status.removeprefix("STATUS_"))
        names = ["NONE", "LIGHT", "MODERATE", "SEVERE", "CRITICAL", "EMERGENCY", "SHUTDOWN"]
        return names[level] if level < len(names) else status
    return status


def file_evidence(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(), f"missing or linked evidence: {path}")
    return {
        "path": path.relative_to(REPO).as_posix(),
        "sha256": digest(path),
        "bytes": path.stat().st_size,
    }


def verify_pointer(pointer: dict) -> dict:
    path = REPO / pointer["path"]
    observed = file_evidence(path)
    require(observed["sha256"] == pointer["sha256"], f"hash drift: {pointer['path']}")
    require(observed["bytes"] == pointer["bytes"], f"size drift: {pointer['path']}")
    return observed


def memory_summary(result: dict) -> dict:
    memories = [result["load_memory"], *(row["memory"] for row in result["runs"])]
    return {
        "maximum_boundary_pss_bytes": max(int(row["pss_bytes"]) for row in memories),
        "maximum_boundary_rss_bytes": max(int(row["rss_bytes"]) for row in memories),
        "maximum_sampled_peak_pss_bytes": max(int(row["sampled_peak_pss_bytes"]) for row in memories),
        "maximum_sampled_peak_rss_bytes": max(int(row["sampled_peak_rss_bytes"]) for row in memories),
        "maximum_process_vm_hwm_bytes": max(int(row["vm_hwm_bytes"]) for row in memories),
        "vm_hwm_semantics": "cumulative_process_lifetime",
    }


def comparison_class(percent: float) -> str:
    magnitude = abs(percent)
    if magnitude < 5:
        return "inconclusive_below_5_percent"
    if magnitude < 10:
        return "inconclusive_5_to_below_10_percent"
    return "directional_at_or_above_10_percent"


def build() -> tuple[dict, str, str]:
    receipt_path = RESULTS / "campaign-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("status") == "complete", "campaign is not complete")
    require(receipt.get("success_count") == 9 and receipt.get("failure_count") == 0, "campaign is not 9/9 successful")
    require(len(receipt.get("runs", [])) == 9, "campaign does not have nine configurations")

    raw_ledger_evidence = verify_pointer(receipt["raw_ledger"])
    raw_ledger = json.loads((REPO / receipt["raw_ledger"]["path"]).read_text(encoding="utf-8"))
    published_without_pointer = dict(receipt)
    published_without_pointer.pop("raw_ledger")
    require(published_without_pointer == raw_ledger, "published receipt differs from its raw ledger")

    plan = json.loads(run_sweep.PLAN_PATH.read_text(encoding="utf-8"))
    order = run_sweep.flatten_order(plan)
    require(receipt["order"] == order, "receipt order differs from active plan")
    require(receipt["active_plan_sha256"] == digest(run_sweep.PLAN_PATH), "active plan hash drift")
    amendment = plan["protocol_amendments"][0]
    require(receipt["plan_sha256"] == amendment["supersedes_plan_sha256"], "registered plan hash drift")
    require(receipt["descriptor_manifest_sha256"] == digest(run_sweep.DESCRIPTOR_MANIFEST), "manifest hash drift")
    require(all(value is False for value in receipt["prohibitions_observed"].values()), "a prohibited action was recorded")

    raw_dir = REPO / receipt["raw_campaign_path"]
    require(raw_dir.is_dir() and raw_dir.resolve().is_relative_to((REPO / "artifacts/0009/thread-sweep/campaigns").resolve()), "unsafe raw campaign path")
    verification_pointer = receipt["resume_events"][-1]["verification_evidence"]
    resume_verification_evidence = verify_pointer(verification_pointer)
    resume_verification = json.loads((REPO / verification_pointer["path"]).read_text(encoding="utf-8"))
    require(resume_verification["original_completed_run_count"] == 6, "resume did not verify the original six runs")
    require(resume_verification["verified_wav_count"] == 24, "resume did not verify 24 original WAVs")
    require(resume_verification["verified_telemetry_file_count"] == 6, "resume did not verify six original telemetry files")
    interruption_state_evidence = verify_pointer(receipt["interruption_before_sequence_7"]["pre_state"]["raw_evidence"])
    interrupted_dir = REPO / receipt["interruption_before_sequence_7"]["empty_allocated_run_path"]
    require(interrupted_dir.is_dir() and not any(interrupted_dir.iterdir()), "interrupted pre-synthesis run directory is not empty")

    state_evidence: list[dict] = []
    for state in receipt["device_states"]:
        state_evidence.append(verify_pointer(state["raw_evidence"]))

    configurations: list[dict] = []
    validations: list[dict] = []
    for index, ledger_run in enumerate(receipt["runs"]):
        expected = {**order[index], "sequence": index + 1}
        checked = run_sweep.verify_completed_run(ledger_run, raw_dir, expected)
        validations.append(checked)
        run_dir = REPO / ledger_run["raw_run_path"]
        result = json.loads((run_dir / "device-result.json").read_text(encoding="utf-8"))
        measured_runs: list[dict] = []
        for device_run, wav in zip(result["runs"], checked["wavs"], strict=True):
            measured_runs.append({
                "kind": device_run["state"],
                "synthesis_wall_seconds": int(device_run["synthesis_nanos"]) / 1e9,
                "rtf": float(device_run["rtf"]),
                "first_non_empty_callback_seconds": int(device_run["first_callback_nanos"]) / 1e9,
                "sample_count": int(device_run["sample_count"]),
                "sample_rate_hz": int(device_run["sample_rate"]),
                "audio_duration_seconds": float(device_run["duration_seconds"]),
                "memory": device_run["memory"],
                "wav": wav,
                "device_audio_validation": device_run["audio_validation"],
            })
        warm = [row for row in measured_runs if row["kind"] == "warm"]
        warm_median = statistics.median(row["rtf"] for row in warm)
        require(abs(warm_median - float(result["warm_median_rtf"])) <= 1e-12, "warm median drift")
        observed_raw_statuses = [
            ledger_run.get("android_thermal_status_pre"),
            *checked["thermal_gate_statuses"],
            *checked["telemetry_statuses"],
            ledger_run.get("android_thermal_status_post"),
        ]
        raw_counts = collections.Counter(status or "UNAVAILABLE" for status in observed_raw_statuses)
        canonical_counts = collections.Counter(canonical_status(status) for status in observed_raw_statuses)
        candidate = ledger_run["candidate"]
        configurations.append({
            "sequence": index + 1,
            "configuration_id": ledger_run["configuration_id"],
            "candidate": candidate,
            "threads": int(ledger_run["threads"]),
            "block": int(ledger_run["block"]),
            "position_in_block": int(ledger_run["position_in_block"]),
            "deployment_variant": plan["candidates"][candidate]["deployment_variant"],
            "voice": {
                "requested": plan["candidates"][candidate]["requested_voice"],
                "actual": plan["candidates"][candidate]["actual_voice"],
                "speaker_id": plan["candidates"][candidate]["speaker_id"],
                "voice_match": plan["candidates"][candidate]["voice_match"],
            },
            "policy_phase": "registered_NONE_only" if index < 6 else "amended_NONE_or_LIGHT",
            "load_wall_seconds": int(result["load_nanos"]) / 1e9,
            "load_memory": result["load_memory"],
            "cold_rtf": measured_runs[0]["rtf"],
            "warm_median_rtf": warm_median,
            "warm_rtf_values": [row["rtf"] for row in warm],
            "warm_median_callback_seconds": statistics.median(row["first_non_empty_callback_seconds"] for row in warm),
            "memory_summary": memory_summary(result),
            "runs": measured_runs,
            "thermal": {
                "android_status_pre": ledger_run.get("android_thermal_status_pre"),
                "gate_statuses": checked["thermal_gate_statuses"],
                "telemetry_statuses": checked["telemetry_statuses"],
                "android_status_post": ledger_run.get("android_thermal_status_post"),
                "raw_status_counts": dict(sorted(raw_counts.items())),
                "canonical_status_counts": dict(sorted(canonical_counts.items())),
                "battery_temperature_c_pre": ledger_run.get("battery_temperature_c_pre"),
                "battery_temperature_c_post": ledger_run.get("battery_temperature_c_post"),
            },
            "descriptor_sha256": ledger_run["descriptor_sha256"],
            "raw_run_path": ledger_run["raw_run_path"],
            "host_run_sha256": checked["host_run_sha256"],
            "telemetry_sha256": checked["telemetry_sha256"],
        })

    require(sum(len(row["runs"]) for row in configurations) == 36, "expected 36 measured WAV runs")
    require(sum(row["wav_count"] for row in validations) == 36, "expected 36 independently validated WAVs")
    require(len(validations) == 9 and all(row["telemetry_sample_count"] > 0 for row in validations), "expected nine valid telemetry streams")

    comparisons: list[dict] = []
    for candidate in plan["candidates"]:
        rows = sorted((row for row in configurations if row["candidate"] == candidate), key=lambda row: row["threads"])
        require([row["threads"] for row in rows] == [1, 2, 4], f"incomplete thread matrix: {candidate}")
        baseline = rows[0]["warm_median_rtf"]
        values = []
        for row in rows:
            percent = (row["warm_median_rtf"] / baseline - 1.0) * 100.0
            values.append({
                "threads": row["threads"],
                "warm_median_rtf": row["warm_median_rtf"],
                "change_vs_one_thread_percent": percent,
                "speedup_vs_one_thread": baseline / row["warm_median_rtf"],
                "classification": "baseline" if row["threads"] == 1 else comparison_class(percent),
            })
        best = min(rows, key=lambda row: row["warm_median_rtf"])
        comparisons.append({
            "candidate": candidate,
            "one_thread_warm_median_rtf": baseline,
            "observations": values,
            "best_observed_threads": best["threads"],
            "best_observed_warm_median_rtf": best["warm_median_rtf"],
            "interpretation": (
                "Observed direction only. Differences below 5-10% are inconclusive; "
                "the policy change at sequence 7 and lack of replicated campaigns limit causal attribution."
            ),
        })

    staged_report_path = RESULTS / "staged-hash-verification.json"
    staged_report = json.loads(staged_report_path.read_text(encoding="utf-8"))
    require(staged_report["summary"] == {"all_match": True, "expected_file_count": 401, "mismatch_count": 0, "verified_match_count": 401}, "staged inventory validation failed")
    staged_raw_evidence = verify_pointer(staged_report["raw_evidence"])

    report = {
        "schema_version": 1,
        "experiment": "0009-android-tts-optimization/thread-sweep",
        "report_kind": "measured_physical_android_thread_sweep",
        "generated_from_completed_at_utc": receipt["ended_at_utc"],
        "status": "measured_complete",
        "no_estimated_cells": True,
        "campaign_id": receipt["sweep_id"],
        "device": receipt["device"],
        "runtime": plan["runtime"],
        "measurement_protocol": plan["measurement"],
        "transcript": plan["transcript"],
        "registered_order": order,
        "thermal_policy_history": receipt["thermal_policy_history"],
        "protocol_amendment": receipt["protocol_amendments"][0],
        "interruption_before_sequence_7": receipt["interruption_before_sequence_7"],
        "configurations": configurations,
        "thread_comparisons": comparisons,
        "interpretation_rules": {
            "below_5_percent": "inconclusive",
            "from_5_to_below_10_percent": "inconclusive",
            "at_or_above_10_percent": "directional only, not inferential replication",
            "required_disclosure": "Differences below 5-10% are inconclusive.",
        },
        "limitations": [
            "The eligibility policy changed after sequence 6: sequences 1-6 required NONE; sequences 7-9 accepted NONE or LIGHT and waited only at MODERATE or higher.",
            "The campaign was intentionally interrupted before sequence 7 synthesis and later resumed after hash/ledger verification; the gap is preserved as provenance.",
            "This is one balanced, rotated campaign rather than replicated randomized campaigns. Thermal status and order remain possible confounders.",
            "Pocket used the packaged Bria reference, not the requested Alba voice.",
            "Listening evaluation was not performed.",
        ],
        "validation": {
            "status": "passed",
            "configuration_count": 9,
            "successful_configuration_count": 9,
            "wav_count": 36,
            "independently_decoded_wav_count": 36,
            "valid_non_silent_unclipped_wav_count": 36,
            "telemetry_file_count": 9,
            "valid_nonempty_telemetry_file_count": 9,
            "telemetry_sample_count": sum(row["telemetry_sample_count"] for row in validations),
            "device_state_evidence_count": len(state_evidence) + 1,
            "staged_file_count": 401,
            "staged_file_hash_match_count": 401,
            "all_host_run_evidence_hashes_match": True,
            "all_wav_hashes_match": True,
            "all_result_medians_recomputed": True,
            "all_statuses_recorded": True,
            "per_configuration": validations,
        },
        "provenance": {
            "registered_plan_sha256": receipt["plan_sha256"],
            "active_amended_plan_sha256": receipt["active_plan_sha256"],
            "descriptor_manifest_sha256": receipt["descriptor_manifest_sha256"],
            "apk_sha256": receipt["apk"]["installed_sha256"],
            "raw_ledger": raw_ledger_evidence,
            "published_campaign_receipt": file_evidence(receipt_path),
            "resume_verification": resume_verification_evidence,
            "interruption_pre_state": interruption_state_evidence,
            "device_states": state_evidence,
            "staged_inventory": staged_raw_evidence,
            "git_commit_before_results": receipt["host"]["git_commit_before_results"],
            "prohibitions_observed": receipt["prohibitions_observed"],
        },
    }
    markdown = render_markdown(report)
    handoff = render_handoff(report)
    return report, markdown, handoff


def f(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def render_markdown(report: dict) -> str:
    lines = [
        "# Measured Android CPU thread sweep",
        "",
        f"**Status:** 9/9 configurations succeeded; 36/36 WAVs and 9/9 telemetry streams independently validated.",
        "",
        "These are observed physical-phone measurements, not estimates. **Differences below 5–10% are inconclusive.** Values at or above 10% are directional only because this is a single rotated campaign and the thermal policy changed mid-campaign.",
        "",
        "## Observed results",
        "",
        "| Seq | Candidate | Threads | Load (s) | Cold RTF | Warm median RTF | Warm callback median (s) | Peak sampled PSS (MiB) | Peak sampled RSS (MiB) | Thermal pre → gate → post |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["configurations"]:
        gate = ",".join(row["thermal"]["gate_statuses"])
        memory = row["memory_summary"]
        lines.append(
            f"| {row['sequence']} | {row['candidate']} | {row['threads']} | {f(row['load_wall_seconds'])} | "
            f"{f(row['cold_rtf'])} | {f(row['warm_median_rtf'])} | {f(row['warm_median_callback_seconds'])} | "
            f"{f(memory['maximum_sampled_peak_pss_bytes'] / MIB, 1)} | {f(memory['maximum_sampled_peak_rss_bytes'] / MIB, 1)} | "
            f"{canonical_status(row['thermal']['android_status_pre'])} → {canonical_status(gate)} → {canonical_status(row['thermal']['android_status_post'])} |"
        )
    lines += ["", "## Thread comparison", ""]
    for comparison in report["thread_comparisons"]:
        observations = {row["threads"]: row for row in comparison["observations"]}
        best = comparison["best_observed_threads"]
        lines.append(f"### {comparison['candidate']}")
        lines.append("")
        lines.append(
            f"Observed warm median RTF: 1 thread {f(observations[1]['warm_median_rtf'])}, "
            f"2 threads {f(observations[2]['warm_median_rtf'])} ({observations[2]['change_vs_one_thread_percent']:+.1f}%), "
            f"4 threads {f(observations[4]['warm_median_rtf'])} ({observations[4]['change_vs_one_thread_percent']:+.1f}%). "
            f"The lowest observed value was at {best} thread{'s' if best != 1 else ''}."
        )
        lines.append("")
        lines.append(f"Interpretation labels: 2 threads `{observations[2]['classification']}`; 4 threads `{observations[4]['classification']}`.")
        lines.append("")
    lines += [
        "## Protocol amendment and interruption",
        "",
        "Sequences 1–6 used the registered NONE-only thermal gate and the original 30/60-second passive stabilization. The prior runner was intentionally interrupted while waiting at LIGHT before sequence 7 synthesis. Its orphan pre-state and empty allocated run directory remain retained and hash-addressed.",
        "",
        "After Moritz's explicit authorization, sequences 7–9 treated NONE and LIGHT as eligible, waited only at MODERATE or higher, and used no fixed passive sleeps. All three resumed synthesis gates observed LIGHT (`STATUS_1`). No device setting, thermal policy, or CPU setting was changed.",
        "",
        "This mid-campaign change is a real comparability limitation, especially for configurations 7–9. It is not normalized away.",
        "",
        "## Validation and provenance",
        "",
        f"- 36/36 retained WAVs: SHA-256 matched, canonical mono PCM16 decoded completely, frame/rate/duration agreed, and audio was non-silent and unclipped.",
        f"- 9/9 telemetry JSONL files: non-empty and structurally valid ({report['validation']['telemetry_sample_count']} samples total); every parsed Android thermal status is retained per configuration.",
        "- 9/9 host evidence manifests and all files they pin matched SHA-256; warm medians were recomputed.",
        "- 401/401 staged deployment files and all nine descriptors matched their registered hashes before resume.",
        f"- Raw ledger: `{report['provenance']['raw_ledger']['path']}` (`{report['provenance']['raw_ledger']['sha256']}`).",
        f"- Resume verification: `{report['provenance']['resume_verification']['path']}` (`{report['provenance']['resume_verification']['sha256']}`).",
        "- No root, system tuning, QNN/QAIRT, proprietary SDK, or text splitting was used. Listening was not performed.",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def render_handoff(report: dict) -> str:
    best = {row["candidate"]: row["best_observed_threads"] for row in report["thread_comparisons"]}
    return f"""# Worker handoff: Android thread sweep

## Completion

- Campaign `{report['campaign_id']}` is complete: **9/9 configurations succeeded**.
- **36/36 WAVs** and **9/9 telemetry files** passed independent retained-artifact validation.
- Best observed warm-median RTF thread counts were Pocket `{best['pocket']}`, Kokoro `{best['kokoro']}`, and Supertonic 3 `{best['supertonic_3']}`. These are observations, not tuning recommendations.
- Machine report: `results/measured-thread-sweep.json`
- Human report: `results/measured-thread-sweep.md`
- Campaign receipt: `results/campaign-receipt.json`

## Required interpretation

**Differences below 5–10% are inconclusive.** Even changes at or above 10% are directional here: there is only one rotated campaign, and the gate changed after sequence 6. Sequences 1–6 required Android thermal status NONE. Following Moritz's explicit authorization, sequences 7–9 accepted NONE and LIGHT, waited only at MODERATE or higher, and had no fixed passive sleeps.

The interrupted sequence-7 attempt never began synthesis. Its raw pre-state and empty allocated run directory are preserved in the receipt. Resume verification hash-checked the ledger, all six completed runs (24 WAVs and six telemetry streams), the installed APK, 401 staged files, and nine descriptors before executing only sequences 7–9 in the registered order under the public phone lock. No phone setting was changed.

## Revalidation

```bash
python3 experiments/0009-android-tts-optimization/thread-sweep/tools/generate_descriptors.py --check
python3 -m unittest discover -s experiments/0009-android-tts-optimization/thread-sweep/tests -p 'test_*.py' -v
python3 experiments/0009-android-tts-optimization/thread-sweep/tools/build_report.py --check
```

Raw artifacts remain ignored under `{report['provenance']['raw_ledger']['path'].removesuffix('/ledger.json')}` and are hash-addressed by the receipt/report. No commit or push was made.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate artifacts and require reports to be current")
    args = parser.parse_args()
    report, markdown, handoff = build()
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    expected = {REPORT_JSON: json_text, REPORT_MD: markdown, HANDOFF: handoff}
    if args.check:
        for path, content in expected.items():
            require(path.is_file(), f"missing generated report: {path}")
            require(path.read_text(encoding="utf-8") == content, f"stale generated report: {path}")
        print("9 configurations, 36 WAVs, 9 telemetry streams, hashes, metrics, and reports: valid")
        return 0
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".incoming")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
