#!/usr/bin/env python3
"""Fail-closed checks for the global Android benchmark registry."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from statistics import median
import re
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REGISTRY_PATH = HERE / "registry.json"
EXPECTED_DEVICE = {"model": "SM-S918B", "soc": "SM8550", "serial": "R5CW81PR8SY", "abi": "arm64-v8a"}
METRIC_FIELDS = ("load_seconds", "cold_rtf", "warm_median_rtf", "proof_run_rtf", "first_post_setup_rtf", "peak_pss_bytes", "peak_vm_hwm_bytes")
STATUSES = {"ran", "partial", "blocked", "deferred", "not_run"}
CANONICAL_V2_SHA256 = "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67"
LEGACY_V1_SHA256 = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
TRANSCRIPT_AUDIT_SOURCE = "experiments/0020-historic-android-benchmark-refresh/results/transcript-provenance-audit.json"
FROZEN_0008_SUPERTONIC_METRICS = {"load_seconds": 0.765107603, "cold_rtf": 0.3854677480612432, "warm_median_rtf": 0.3703028479158501, "proof_run_rtf": None, "first_post_setup_rtf": None, "peak_pss_bytes": 463003648, "peak_vm_hwm_bytes": 531345408}
EXP_0022 = ROOT / "experiments/0022-supertonic-canonical-v2-precompiled-qnn-context"
EXP_0022_RESULT = EXP_0022 / "results/t235-t239-masked-padding-compatibility.json"
EXP_0022_RESULT_SHA256 = "3de896971a64ca5d2833b5421d02e991a75f59922cf6a89c1ac3aa5da21dfc95"
EXP_0017 = ROOT / "experiments/0017-kokoro-onnx-qnn-htp-android"
EXP_0017_RESULT = EXP_0017 / "results/canonical-v2-host-qnn-gate.json"
EXP_0017_RESULT_SHA256 = "3926b2509f426744b14537d4e06898d6e3c9527694a94e0a0c646c9ce1815689"
EXP_0023 = ROOT / "experiments/0023-supertonic-qnn-precompiled-context-startup"
EXP_0023_RESULT = EXP_0023 / "results/phone-campaign/phone-result.json"
EXP_0023_RESULT_SHA256 = "86e4f3011c4f784d10fd7ad178887468383d91c2547651ca41f5fb63e741034a"
EXP_0023_WAV_SHA256 = "47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c"
EXP_0023_IDS = {"0023-supertonic-source-onnx-htp", "0023-supertonic-external-context-htp"}
EXP_0024 = ROOT / "experiments/0024-pocket-tts-qnn-precompiled-context-startup"
EXP_0024_RESULT = EXP_0024 / "results/result.json"
EXP_0024_RESULT_SHA256 = "744d93649ca7fe37a7f75774aec2524717deecf521b2b4a3593c1bed2d0c2dec"
EXP_0024_MANIFEST = EXP_0024 / "results/phone-campaign/evidence-manifest.json"
EXP_0024_MANIFEST_SHA256 = "b69ddc40a4364d8a5c57ce3cc304d7eb3abced81541569a768e78a73a7c801db"
EXP_0024_LISTENING = EXP_0024 / "results/listening-review-2026-08-25.json"
EXP_0024_LISTENING_SHA256 = "863412436bdb76c686c08b17b4710d559481392f80bae95ee705a155d935e60f"
EXP_0024_WAV_SHA256 = {
    "source": "028f8a1e1861f8004619294738d9aa14509b2c3e5e5e626d99113700ab574241",
    "context": "7c3fc41d320e391ed39c10398f9c013d01cba93b9c733d3df546d31a0d006d81",
}
EXP_0024_IDS = {"0024-pocket-reconstruction-source-onnx-htp", "0024-pocket-reconstruction-external-context-htp"}
EXP_0024_COMMIT = "b59601ef66d5d24b6af249ab082291f0c53d4b25"
PRESENTATION_SUPERSESSIONS = {
    "0008-pocket-cpu-t1": "0009-pocket-cpu-t1",
    "0008-kokoro-cpu-t1": "0009-kokoro-cpu-t1",
    "0008-supertonic-cpu-t1": "0009-supertonic-cpu-t1",
    "0014-pocket-alba-fixed-qnn-htp": "0014-pocket-alba-qnn-htp-v2",
}
FROZEN_PRESENTATION_SUPPRESSED_METRICS = {
    "0008-pocket-cpu-t1": {"load_seconds": 0.658703801, "cold_rtf": 0.4358031003580019, "warm_median_rtf": 0.38864718496483114, "proof_run_rtf": None, "first_post_setup_rtf": None, "peak_pss_bytes": 683577344, "peak_vm_hwm_bytes": 751427584},
    "0008-kokoro-cpu-t1": {"load_seconds": 1.303446875, "cold_rtf": 1.187996273027265, "warm_median_rtf": 1.1952115332875515, "proof_run_rtf": None, "first_post_setup_rtf": None, "peak_pss_bytes": 929677312, "peak_vm_hwm_bytes": 995078144},
    "0008-supertonic-cpu-t1": FROZEN_0008_SUPERTONIC_METRICS,
    "0014-pocket-alba-fixed-qnn-htp": {"load_seconds": 58.1983, "cold_rtf": None, "warm_median_rtf": None, "proof_run_rtf": 0.525063, "first_post_setup_rtf": 0.165244, "peak_pss_bytes": None, "peak_vm_hwm_bytes": 2506731520},
}


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main():
    try:
        registry = json.loads(REGISTRY_PATH.read_text())
    except Exception as exc:
        fail(f"cannot parse registry.json: {exc}")
    if registry.get("schema_version") != 1 or registry.get("registry_id") != "android-benchmarks-v1":
        fail("unexpected registry identity")
    if registry.get("device") != EXPECTED_DEVICE:
        fail("canonical device identity changed")
    timeline = registry.get("model_timeline")
    if not isinstance(timeline, list) or not timeline:
        fail("model_timeline must be a non-empty list")
    timeline_models = set()
    for item in timeline:
        if set(item) != {"model", "first_release_date", "date_basis", "source_url"}:
            fail("timeline entry field mismatch")
        if not item["model"].strip() or not item["date_basis"].strip() or not item["source_url"].startswith("https://"):
            fail(f"invalid timeline entry: {item.get('model')}")
        try:
            date.fromisoformat(item["first_release_date"])
        except ValueError:
            fail(f"invalid timeline date: {item.get('first_release_date')}")
        if item["model"] in timeline_models:
            fail(f"duplicate timeline model: {item['model']}")
        timeline_models.add(item["model"])
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("entries must be a non-empty list")
    ids = [e.get("id") for e in entries]
    if len(ids) != len(set(ids)):
        fail("duplicate route id")
    entries_by_id = {e["id"]: e for e in entries}
    seen_experiments = set()
    verified_media = 0
    transcript_counts = {"canonical_v2": 0, "legacy_v1": 0, "noncanonical": 0}
    for e in entries:
        required = ("id", "experiment", "model", "model_identity", "route", "deployment_variant", "quantization", "transcript", "scope", "attempt_status", "technical_execution", "structural_audio", "objective_evidence", "listening_review", "android_attempted", "provider", "precision", "threads", "device", "metrics", "wav", "summary", "limitations", "sources", "missing_reasons")
        missing = [k for k in required if k not in e]
        if missing:
            fail(f"{e.get('id')}: missing keys {missing}")
        limitations = e["limitations"]
        if not isinstance(limitations, list) or any(not isinstance(item, str) or not item.strip() for item in limitations):
            fail(f"{e['id']}: limitations must be a list of non-empty strings")
        if len(limitations) > 1 and all(len(item) == 1 for item in limitations):
            fail(f"{e['id']}: limitations appears to be an exploded character array")
        if not re.fullmatch(r"[0-9]{4}-[a-z0-9-]+", e["id"]):
            fail(f"{e['id']}: invalid id")
        if not re.fullmatch(r"[0-9]{4}", e["experiment"]):
            fail(f"{e['id']}: invalid experiment")
        seen_experiments.add(e["experiment"])
        identity = e["model_identity"]
        if identity is None:
            if "model_identity" not in e["missing_reasons"] and "all" not in e["missing_reasons"]:
                fail(f"{e['id']}: null model identity lacks a missing-evidence reason")
        else:
            if set(identity) != {"name", "url", "revision"} or not identity["name"].strip() or not identity["url"].startswith("https://"):
                fail(f"{e['id']}: invalid model identity")
            if identity["revision"] is not None and not identity["revision"].strip():
                fail(f"{e['id']}: empty model identity revision")
        if e["quantization"] is None and "quantization" not in e["missing_reasons"] and "all" not in e["missing_reasons"]:
            fail(f"{e['id']}: null quantization lacks a missing-evidence reason")
        if e["scope"] not in {"full_e2e", "excluded_non_e2e"}:
            fail(f"{e['id']}: invalid route scope")
        presentation = e.get("presentation")
        expected_supersession = PRESENTATION_SUPERSESSIONS.get(e["id"])
        if expected_supersession is None:
            if presentation is not None:
                fail(f"{e['id']}: unexpected presentation suppression")
        else:
            if not isinstance(presentation, dict) or set(presentation) != {"dashboard_visible", "visibility_reason", "superseded_by"}:
                fail(f"{e['id']}: invalid presentation suppression contract")
            if presentation["dashboard_visible"] is not False or not presentation["visibility_reason"].strip() or presentation["superseded_by"] != expected_supersession:
                fail(f"{e['id']}: presentation supersession mismatch")
            target = entries_by_id.get(expected_supersession)
            if e["scope"] != "full_e2e" or target is None or target["scope"] != "full_e2e":
                fail(f"{e['id']}: presentation suppression changed scope or lacks a full-E2E successor")
        transcript = e["transcript"]
        if e["scope"] == "full_e2e":
            if not isinstance(transcript, dict):
                fail(f"{e['id']}: full-E2E route lacks transcript classification")
            classification = transcript.get("classification")
            if classification not in transcript_counts:
                fail(f"{e['id']}: invalid transcript classification")
            transcript_counts[classification] += 1
            if transcript.get("canonical_v2_sha256") != CANONICAL_V2_SHA256 or transcript.get("canonical_v2_match") != (classification == "canonical_v2"):
                fail(f"{e['id']}: canonical-v2 transcript boundary mismatch")
            if classification == "canonical_v2":
                if transcript.get("sha256") != CANONICAL_V2_SHA256 or transcript.get("bytes") != 226 or transcript.get("trailing_newline") is not False:
                    fail(f"{e['id']}: canonical-v2 classification/hash/byte contract mismatch")
                frontend = transcript.get("effective_frontend")
                frontend_hash = frontend.get("mapped_ids_int32le_sha256") or frontend.get("token_ids_sha256") if isinstance(frontend, dict) else None
                if not isinstance(frontend, dict) or not re.fullmatch(r"[a-f0-9]{64}", frontend_hash or "") or not (ROOT / frontend.get("source", "")).is_file():
                    fail(f"{e['id']}: canonical-v2 route lacks exact effective frontend provenance")
            if classification == "legacy_v1" and (transcript.get("sha256") != LEGACY_V1_SHA256 or transcript.get("bytes") != 230 or transcript.get("trailing_newline") is not False):
                fail(f"{e['id']}: legacy-v1 transcript provenance mismatch")
            if classification == "noncanonical" and transcript.get("sha256") in {CANONICAL_V2_SHA256, LEGACY_V1_SHA256}:
                fail(f"{e['id']}: noncanonical transcript uses a matched hash")
            if classification != "canonical_v2" and transcript.get("effective_frontend") is None and "effective_frontend" not in transcript.get("missing_reasons", {}):
                fail(f"{e['id']}: missing effective frontend provenance lacks a reason")
            for nullable in ("bytes", "trailing_newline"):
                if transcript.get(nullable) is None and nullable not in transcript.get("missing_reasons", {}):
                    fail(f"{e['id']}: null transcript {nullable} lacks a reason")
            audit_source = transcript.get("audit_source", "")
            if not (ROOT / audit_source).is_file():
                fail(f"{e['id']}: transcript classification source is missing")
            expected_0023_audit = "experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/phone-result.json"
            if classification != "canonical_v2" and audit_source != TRANSCRIPT_AUDIT_SOURCE and not (e["id"] in EXP_0023_IDS and audit_source == expected_0023_audit):
                fail(f"{e['id']}: historical transcript audit provenance mismatch")
        elif transcript is None:
            if "transcript" not in e["missing_reasons"]:
                fail(f"{e['id']}: excluded route null transcript lacks a reason")
        else:
            if transcript.get("classification") != "canonical_v2" or transcript.get("sha256") != CANONICAL_V2_SHA256 or transcript.get("bytes") != 226 or transcript.get("trailing_newline") is not False:
                fail(f"{e['id']}: excluded route transcript evidence is invalid")
            frontend = transcript.get("effective_frontend")
            frontend_has_exact_output = isinstance(frontend, dict) and ((frontend.get("token_count") == len(frontend.get("token_ids", [])) and frontend.get("token_count", 0) > 0) or re.fullmatch(r"[a-f0-9]{64}", frontend.get("token_ids_sha256", "") or frontend.get("mapped_ids_int32le_sha256", "")))
            if not frontend_has_exact_output or not (ROOT / frontend.get("source", "")).is_file() or not (ROOT / transcript.get("audit_source", "")).is_file():
                fail(f"{e['id']}: excluded canonical-v2 route lacks exact frontend/classification provenance")
        if e["attempt_status"] not in STATUSES:
            fail(f"{e['id']}: invalid status")
        technical = e["technical_execution"]
        if technical.get("status") != e["attempt_status"] or technical.get("android_attempted") != e["android_attempted"] or technical.get("provider") != e["provider"] or technical.get("threads") != e["threads"]:
            fail(f"{e['id']}: technical execution does not match normalized route fields")
        structural = e["structural_audio"]
        if structural["status"] not in {"valid", "invalid", "unavailable"}:
            fail(f"{e['id']}: invalid structural audio status")
        if e["wav"] is not None and structural["status"] != "valid":
            fail(f"{e['id']}: copied WAV must have structural_audio.status=valid")
        if e["wav"] is None and structural["status"] == "valid":
            fail(f"{e['id']}: structural_audio.status=valid requires a retained WAV")
        if e["wav"] is not None and structural["sample_sha256"] != e["wav"]["sha256"]:
            fail(f"{e['id']}: structural audio hash does not match WAV")
        if structural["status"] == "unavailable" and (structural["basis"] is not None or structural["sample_sha256"] is not None):
            fail(f"{e['id']}: unavailable structural audio cannot carry basis/hash evidence")
        if structural["status"] == "invalid" and (e["wav"] is not None or not isinstance(structural["basis"], str) or not structural["basis"].strip() or not re.fullmatch(r"[a-f0-9]{64}", structural["sample_sha256"] or "")):
            fail(f"{e['id']}: invalid non-WAV structural audio requires an evidence basis and hash")
        objective = e["objective_evidence"]
        if objective["status"] not in {"not_recorded", "descriptive", "pass", "fail"} or not objective["summary"].strip() or any(not isinstance(n, str) or not n.strip() for n in objective["comparison_notes"]):
            fail(f"{e['id']}: invalid objective evidence")
        review = e["listening_review"]
        if review["status"] not in {"not_reviewed", "accepted", "rejected"}:
            fail(f"{e['id']}: invalid listening status")
        if review["status"] == "not_reviewed":
            if review["reviewer"] is not None or review["date"] is not None or review["notes"] is not None:
                fail(f"{e['id']}: not_reviewed cannot carry reviewer/date/notes")
        else:
            if review["reviewer"] != "Moritz" or not review["date"] or not review["notes"] or not review["notes"].strip():
                fail(f"{e['id']}: only an explicit Moritz verdict may set listening status")
        if e["wav"] is not None and review["sample_sha256"] != e["wav"]["sha256"]:
            fail(f"{e['id']}: listening sample hash does not match WAV")
        if e["android_attempted"] and e["device"] != EXPECTED_DEVICE:
            fail(f"{e['id']}: attempted route must identify the authorized device")
        if not e["android_attempted"] and e["device"] is not None:
            fail(f"{e['id']}: non-attempted route must retain device=null")
        if not isinstance(e["metrics"], dict) or set(e["metrics"]) != set(METRIC_FIELDS):
            fail(f"{e['id']}: metric contract mismatch")
        for field, value in e["metrics"].items():
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                fail(f"{e['id']}: invalid metric {field}")
            if value is None and field not in e["missing_reasons"] and "all" not in e["missing_reasons"]:
                fail(f"{e['id']}: null metric {field} lacks a missing-evidence reason")
        if e["metrics"]["warm_median_rtf"] is not None and "One profiled generation only" in " ".join(e["limitations"]):
            fail(f"{e['id']}: a single profiled generation cannot populate warm_median_rtf")
        if e["id"] in FROZEN_PRESENTATION_SUPPRESSED_METRICS and e["metrics"] != FROZEN_PRESENTATION_SUPPRESSED_METRICS[e["id"]]:
            fail(f"{e['id']}: presentation suppression must not alter historical metrics")
        if e["id"] == "0017-kokoro-qnn-host-blocked":
            result_bytes = EXP_0017_RESULT.read_bytes()
            if hashlib.sha256(result_bytes).hexdigest() != EXP_0017_RESULT_SHA256:
                fail(f"{e['id']}: committed terminal evidence hash mismatch")
            source_result = json.loads(result_bytes)
            execution = source_result["execution"]
            eligibility = source_result["eligibility"]
            duration = source_result["outputs"]["duration"]
            audio = source_result["outputs"]["audio"]
            divergence = source_result["divergence"]
            if source_result["status"] != "failed_host_structural_gate_after_18_stage_qnn_pass" or execution["completed_stages"] != 18 or execution["provider_counts"] != {"QNNExecutionProvider": 18} or execution["cpu_provider_node_events"] != 0 or execution["fallback_disabled"] is not True:
                fail(f"{e['id']}: terminal host provider gate mismatch")
            if len(source_result["stages"]) != 18 or any(stage["execution"]["provider_counts"] != {"QNNExecutionProvider": 1} or stage["execution"]["exit_code"] != 0 for stage in source_result["stages"]):
                fail(f"{e['id']}: per-stage QNN execution evidence mismatch")
            if (duration["elements"], duration["sum"], duration["expected_sum"], duration["matches_expected_sum"]) != (235, 605, 602, False):
                fail(f"{e['id']}: duration structural failure mismatch")
            expected_audio = {"elements": 361200, "sha256": "2992f71911b8af233841af4058e8218e8705c987a51643d1d709d96545b60a08", "absolute_peak": 87296.0078125, "rms": 61982.49650008212, "samples_abs_ge_1": 360921}
            if audio["elements"] != expected_audio["elements"] or audio["sha256"] != expected_audio["sha256"] or audio["structural"]["absolute_peak"] != expected_audio["absolute_peak"] or audio["structural"]["rms"] != expected_audio["rms"] or audio["structural"]["samples_abs_ge_1"] != expected_audio["samples_abs_ge_1"] or audio["structural"]["all_finite"] is not True or audio["structural"]["valid"] is not False:
                fail(f"{e['id']}: invalid host float-output boundary mismatch")
            first = divergence["earliest_non_bit_exact_output"]
            material = divergence["earliest_material_contract_divergence"]
            if (first["index"], first["name"]) != (1, "bert") or (material["index"], material["name"], material["output"]) != (4, "duration_alignment", "pred_dur") or divergence["root_cause"] is not None or not divergence["root_cause_reason"]:
                fail(f"{e['id']}: divergence/root-cause boundary mismatch")
            if eligibility["phone_eligible"] is not False or eligibility["provider_gate"] is not True or eligibility["structural_audio_gate"] is not False:
                fail(f"{e['id']}: phone eligibility boundary mismatch")
            if e["scope"] != "excluded_non_e2e" or e["attempt_status"] != "blocked" or e["android_attempted"] or e["device"] is not None or e["provider"] != "QNNExecutionProvider (host staged gate only)":
                fail(f"{e['id']}: host-only excluded-route boundary mismatch")
            if any(value is not None for value in e["metrics"].values()) or e["wav"] is not None or e["objective_evidence"]["status"] != "fail":
                fail(f"{e['id']}: phone-ineligible route cannot carry Android metrics/WAV evidence")
            expected_review = {"status": "not_reviewed", "reviewer": None, "date": None, "notes": None, "sample_sha256": None}
            expected_structural = {"status": "invalid", "basis": "Committed canonical-v2 host float32 output failed the structural audio gate; this ignored tensor is not a retained WAV or listening sample.", "sample_sha256": expected_audio["sha256"]}
            if e["listening_review"] != expected_review or e["structural_audio"] != expected_structural:
                fail(f"{e['id']}: invalid host audio / absent WAV-listening boundary mismatch")
            frontend_source = json.loads((EXP_0017 / "results/canonical-v2-frontend-provenance.json").read_text())
            frontend = e["transcript"]["effective_frontend"]
            tokens = frontend_source["fixed_inputs"]["tensors"]["tokens"]
            if source_result["transcript_sha256"] != CANONICAL_V2_SHA256 or tokens["shape"] != [1, 235] or frontend["token_count"] != 235 or frontend["token_ids_sha256"] != tokens["sha256"]:
                fail(f"{e['id']}: canonical-v2 frontend provenance mismatch")
            required_missing = {"android_attempted", *METRIC_FIELDS, "wav", "physical_rpc_accelerator_cycle_hvx", "listening"}
            if not required_missing.issubset(e["missing_reasons"]):
                fail(f"{e['id']}: terminal host result lacks explicit Android/WAV/listening null reasons")
            preserved_sources = {
                "experiments/0017-kokoro-onnx-qnn-htp-android/results/host-gate-checkpoint.json",
                "experiments/0017-kokoro-onnx-qnn-htp-android/results/staged-host-qnn-feasibility.json",
                "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-cpu-reconstruction-baseline.json",
                "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-host-qnn-interrupted-checkpoint.json",
                "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-native-rerun-1-operator-stopped.json",
                "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-host-qnn-gate.json",
            }
            if not preserved_sources.issubset(e["sources"]):
                fail(f"{e['id']}: historical or terminal 0017 source evidence was dropped")
        if e["id"] == "0014-pocket-alba-fixed-qnn-htp":
            frozen_sha = "2c3901ec39a53596759c1d95381a1d67e4f9ca8886cdf39ac03721863c63eb56"
            frozen_sources = [
                "experiments/0014-pocket-fp-onnx-qnn-htp/results/alba-quality-recovery.json",
                "experiments/0014-pocket-fp-onnx-qnn-htp/results/quality-recovery-listening.json",
                "experiments/0014-pocket-fp-onnx-qnn-htp/results/zero-voice-encoder-root-cause.json",
            ]
            review = e["listening_review"]
            if e["wav"] is None or e["wav"]["sha256"] != frozen_sha or review["status"] != "accepted" or review["reviewer"] != "Moritz" or review["sample_sha256"] != frozen_sha or e["sources"] != frozen_sources:
                fail(f"{e['id']}: presentation suppression must preserve WAV, verdict, and sources")
        if e["id"] == "0019-moss-canonical-v2-qnn-phone-blocked":
            source_blocker = json.loads((ROOT / "experiments/0019-moss-tts-nano-qnn-htp-android/results/fixed-capacity-phone-blocker.json").read_text())
            if e["scope"] != "excluded_non_e2e" or e["attempt_status"] != "blocked" or not e["android_attempted"]:
                fail(f"{e['id']}: phone blocker must remain attempted but excluded/non-E2E")
            if any(value is not None for value in e["metrics"].values()) or e["wav"] is not None or e["listening_review"]["status"] != "not_reviewed":
                fail(f"{e['id']}: pre-session blocker cannot carry benchmark metrics/WAV/listening verdict")
            if source_blocker["exact_blocker"]["phase"] != "QNN backend SetupBackend/CreateDevice before GetCapability assignment" or source_blocker["phone_metrics"]["provider_events"] is not None or source_blocker["phone_metrics"]["physical_rpc_accelerator_cycle_hvx"] is not None:
                fail(f"{e['id']}: exact CreateDevice/provider/physical boundary mismatch")
            if not source_blocker["host"]["cpu_equivalence_passed"] or source_blocker["host"]["contexts_result"] != "four_contexts_generated_and_fail_closed_reloaded":
                fail(f"{e['id']}: bounded host feasibility provenance mismatch")
            frontend = e["transcript"]["effective_frontend"]
            if frontend["token_count"] != source_blocker["canonical_v2"]["token_count"] or frontend["token_ids"] != json.loads((ROOT / frontend["source"]).read_text())["token_ids"]:
                fail(f"{e['id']}: canonical-v2 MOSS frontend provenance mismatch")
        if e["id"] in {"0014-pocket-alba-cpu-v2", "0014-pocket-alba-qnn-htp-v2"}:
            source_result = json.loads((ROOT / "experiments/0014-pocket-fp-onnx-qnn-htp/results/canonical-v2-benchmark.json").read_text())
            is_htp = e["id"] == "0014-pocket-alba-qnn-htp-v2"
            route_result = source_result["physical_qnn_htp"]["benchmark"] if is_htp else source_result["android_cpu"]
            warm_values = route_result["warm"]["rtf"]
            expected_metrics = {
                "load_seconds": route_result["setup"]["seconds"],
                "cold_rtf": route_result["first"]["rtf"],
                "warm_median_rtf": route_result["warm"]["median_rtf"],
                "proof_run_rtf": source_result["physical_qnn_htp"]["profiled_proof"]["result"]["iterations"][0]["rtf"] if is_htp else None,
                "first_post_setup_rtf": route_result["first"]["rtf"],
                "peak_pss_bytes": None,
                "peak_vm_hwm_bytes": route_result["memory"]["max_vm_hwm_kb"] * 1024,
            }
            if e["metrics"] != expected_metrics or len(warm_values) != 5 or median(warm_values) != e["metrics"]["warm_median_rtf"]:
                fail(f"{e['id']}: canonical-v2 first/five-warm campaign mismatch")
            output = route_result["first"]["wav"]
            if output["sha256"] != e["wav"]["sha256"] or output["seconds"] != e["wav"]["duration_seconds"]:
                fail(f"{e['id']}: canonical-v2 Pocket WAV provenance mismatch")
            frontend = e["transcript"]["effective_frontend"]
            if frontend["token_ids_sha256"] != source_result["frontend"]["token_ids_sha256"] or frontend["token_count"] != source_result["frontend"]["token_count"]:
                fail(f"{e['id']}: canonical-v2 Pocket frontend provenance mismatch")
            source_review = source_result["listening"]["physical_qnn_htp" if is_htp else "android_cpu"]
            source_scope = "Exact canonical-v2 fixed-Alba text64/cache512 fallback-disabled physical QNN/HTP WAV only." if is_htp else "Exact canonical-v2 text64/cache512 Android CPU WAV only; HTP requires fresh verdict."
            expected_review = {"status": source_review["verdict"], "reviewer": "Moritz", "date": source_result["date"], "notes": source_review["verbatim"] + ". " + source_scope, "sample_sha256": source_review["sha256"]}
            if e["listening_review"] != expected_review or e["listening_review"]["sample_sha256"] != e["wav"]["sha256"]:
                fail(f"{e['id']}: canonical-v2 Pocket exact-hash listening verdict mismatch")
            if is_htp:
                proof = source_result["physical_qnn_htp"]["profiled_proof"]
                aggregate = proof["aggregate"]
                if aggregate["provider_events"] != {"QNNExecutionProvider": 344} or not aggregate["all_invoked_calls_qnn_only"] or not aggregate["all_physical_event_counts_match_qnn"]:
                    fail(f"{e['id']}: canonical-v2 Pocket physical provider proof mismatch")
                if len({aggregate["rpc_execute_events"], aggregate["accelerator_execute_events"], aggregate["cycle_events"], aggregate["hvx_events"]}) != 1 or aggregate["rpc_execute_events"] != 344:
                    fail(f"{e['id']}: canonical-v2 Pocket physical event counts mismatch")
        if e["id"] == "0021-supertonic-int8-cpu-v2":
            source_result = json.loads((ROOT / "experiments/0021-supertonic-canonical-v2-android-cpu/results/phone-cpu-result.json").read_text())
            source_frontend = json.loads((ROOT / "experiments/0021-supertonic-canonical-v2-android-cpu/results/frontend-provenance.json").read_text())
            warm_values = source_result["measurement"]["warm_rtf_values"]
            expected_metrics = {
                "load_seconds": source_result["route"]["setup_seconds"],
                "cold_rtf": source_result["measurement"]["first"]["rtf"],
                "warm_median_rtf": source_result["measurement"]["warm_median_rtf"],
                "proof_run_rtf": None,
                "first_post_setup_rtf": source_result["measurement"]["first"]["rtf"],
                "peak_pss_bytes": source_result["measurement"]["peak_sampled_pss_bytes"],
                "peak_vm_hwm_bytes": source_result["measurement"]["peak_vm_hwm_bytes"],
            }
            if e["metrics"] != expected_metrics or len(warm_values) != 5 or median(warm_values) != e["metrics"]["warm_median_rtf"]:
                fail(f"{e['id']}: canonical-v2 timing campaign mismatch")
            durations = [source_result["measurement"]["first"]["actual_audio_duration_seconds"]] + [run["actual_audio_duration_seconds"] for run in source_result["measurement"]["warm"]]
            if len(set(durations)) != 1 or source_result["representative_wav"]["sha256"] != e["wav"]["sha256"]:
                fail(f"{e['id']}: canonical-v2 duration/WAV provenance mismatch")
            frontend = e["transcript"]["effective_frontend"]
            if frontend["mapped_ids_int32le_sha256"] != source_frontend["frontend"]["mapped_ids_int32le_sha256"] or frontend["mapped_id_count"] != source_frontend["frontend"]["mapped_id_count"]:
                fail(f"{e['id']}: canonical-v2 frontend mapping mismatch")
            source_review = source_result["representative_wav"]["listening_review"]
            expected_review = {
                "status": source_review["status"], "reviewer": source_review["reviewer"], "date": source_review["date"],
                "notes": source_review["notes"] + ". " + source_review["scope"][0].upper() + source_review["scope"][1:] + ".",
                "sample_sha256": source_review["sample_sha256"],
            }
            if e["listening_review"] != expected_review or e["listening_review"]["sample_sha256"] != e["wav"]["sha256"]:
                fail(f"{e['id']}: canonical-v2 listening review does not match committed exact-hash verdict evidence")
        if e["id"] == "0022-supertonic-t239-padding-blocked":
            result_bytes = EXP_0022_RESULT.read_bytes()
            if hashlib.sha256(result_bytes).hexdigest() != EXP_0022_RESULT_SHA256:
                fail(f"{e['id']}: committed terminal evidence hash mismatch")
            source_result = json.loads(result_bytes)
            policy_path = EXP_0022 / "protocol/padding-compatibility-policy.json"
            policy = json.loads(policy_path.read_text())
            if hashlib.sha256(policy_path.read_bytes()).hexdigest() != source_result["policy"]["sha256"]:
                fail(f"{e['id']}: compatibility policy hash mismatch")
            decision = source_result["decision"]
            if decision["result"] != "failed_joint_constraint_incompatibility" or decision["compatible"] is not False:
                fail(f"{e['id']}: terminal incompatibility decision mismatch")
            if decision["oracle_equivalence_passed"] is not False or decision["frozen_t239_reproduction_passed"] is not True or decision["pad_payload_invariance_passed"] is not True:
                fail(f"{e['id']}: compatibility sub-gate boundary mismatch")
            if decision["required_action"] != "stop_before_runner_implementation_context_generation_output_or_phone_access":
                fail(f"{e['id']}: fail-closed stop boundary mismatch")
            comparison = source_result["comparisons"]["dynamic_t235_oracle_vs_dynamic_t239_masked"]
            limits = policy["oracle_equivalence_limits"]
            if comparison["duration"]["max_abs"] <= limits["duration_max_abs_lte"]:
                fail(f"{e['id']}: duration incompatibility is not preserved")
            text_comparison = comparison["text_embedding_semantic_prefix"]
            if text_comparison["max_abs"] <= limits["text_embedding_semantic_prefix_max_abs_lte"] or text_comparison["rmse"] <= limits["text_embedding_semantic_prefix_rmse_lte"] or text_comparison["cosine"] >= limits["text_embedding_semantic_prefix_cosine_gte"]:
                fail(f"{e['id']}: semantic-prefix incompatibility is not preserved")
            if e["scope"] != "excluded_non_e2e" or e["attempt_status"] != "blocked" or e["android_attempted"] or e["provider"] is not None or e["precision"] is not None or e["threads"] is not None or e["device"] is not None:
                fail(f"{e['id']}: stopped pre-run route execution boundary mismatch")
            if any(value is not None for value in e["metrics"].values()) or e["wav"] is not None:
                fail(f"{e['id']}: stopped pre-run route cannot carry metrics or WAV evidence")
            expected_review = {"status": "not_reviewed", "reviewer": None, "date": None, "notes": None, "sample_sha256": None}
            if e["listening_review"] != expected_review or e["structural_audio"] != {"status": "unavailable", "basis": None, "sample_sha256": None}:
                fail(f"{e['id']}: absent audio/listening boundary mismatch")
            if e["objective_evidence"]["status"] != "fail":
                fail(f"{e['id']}: terminal objective gate failure is not represented")
            semantic_ids = source_result["canonical_input"]["semantic_text_ids"]
            frontend = e["transcript"]["effective_frontend"]
            if semantic_ids["shape"] != [1, 235] or frontend["token_count"] != 235 or frontend["token_ids_sha256"] != semantic_ids["sha256"]:
                fail(f"{e['id']}: canonical T235 frontend provenance mismatch")
            required_missing = {"android_attempted", "provider", "precision", "threads", *METRIC_FIELDS, "wav", "physical_rpc_accelerator_cycle_hvx", "listening"}
            if not required_missing.issubset(e["missing_reasons"]):
                fail(f"{e['id']}: terminal negative result lacks exhaustive null reasons")
        if e["id"] in EXP_0023_IDS:
            result_bytes = EXP_0023_RESULT.read_bytes()
            if hashlib.sha256(result_bytes).hexdigest() != EXP_0023_RESULT_SHA256:
                fail(f"{e['id']}: committed phone result hash mismatch")
            source_result = json.loads(result_bytes)
            arm = "source" if e["id"] == "0023-supertonic-source-onnx-htp" else "context"
            setup = source_result["setup"][arm]
            e2e = source_result["e2e"][arm]
            proof = source_result["physical_proof"]
            expected_setup_values = {"source": [22.1599, 21.6129, 20.9571], "context": [0.785324, 0.496524, 0.497816]}[arm]
            if source_result["status"] != "phone_campaign_passed" or source_result["execution"]["all_nine_runner_processes_exit_zero"] is not True:
                fail(f"{e['id']}: completed phone campaign status mismatch")
            if setup["sequence_values_seconds"] != expected_setup_values or len(setup["runs"]) != 3:
                fail(f"{e['id']}: fresh-process setup distribution mismatch")
            comparison = source_result["setup_comparison"]
            expected_comparison = {"source_median_seconds": 21.6129, "context_median_seconds": 0.497816, "source_minus_context_median_seconds": 21.115084, "source_over_context_median_ratio": 43.415438635961884, "context_setup_reduction_percent": 97.69667189502566}
            if any(comparison[key] != value for key, value in expected_comparison.items()):
                fail(f"{e['id']}: matched setup comparison mismatch")
            expected_setup_pss = {"source": [1354060, 1354631, 1341123], "context": [162649, 162301, 162340]}[arm]
            observed_setup_pss = [run["sampled_memory"]["peak_sampled_pss_kb"] for run in setup["runs"]]
            pss_range = f"{min(expected_setup_pss):,}–{max(expected_setup_pss):,} KiB"
            if observed_setup_pss != expected_setup_pss or pss_range not in e["summary"]:
                fail(f"{e['id']}: setup-only PSS evidence mismatch")
            contract = json.loads((EXP_0023 / "protocol/experiment-contract.json").read_text())
            expected_graphs = {"duration": "8a1875ef0f6960ca16fc06814509b1c3258e8f50b04a5d590d3ab6db8c775016", "text": "769fd1d257674e8624bdea941f7a903d9460051f9845b604cd2c2980f281a8c3", "vector_stable_softplus": "f2318c54726a034dcc89aa9818a91f1c3db0e3067b9932c7c2dae65957897c7b", "vocoder": "35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7"}
            runtime = contract["runtime"]
            if contract["graphs"] != {**expected_graphs, "matching_rule": contract["graphs"]["matching_rule"]} or "experiment 0011" not in contract["scope"]["baseline_route"] or contract["scope"]["input"] != "experiment 0011 legacy 230-byte transcript, processed T239":
                fail(f"{e['id']}: exact graph/input lineage mismatch")
            if runtime["onnxruntime"] != "1.27.1" or runtime["qairt"] != "2.49.0.260730" or runtime["android_libonnxruntime"]["sha256"] != "643c6f6fd3d2b375ca8f2407a1695acaf55320b8e947adc4284665640fdc3ae9" or runtime["session.disable_cpu_ep_fallback"] != "1":
                fail(f"{e['id']}: matched runtime lineage mismatch")
            proof_rtf = None if arm == "source" else proof["runner"]["rtf"][0]
            expected_metrics = {
                "load_seconds": setup["median_seconds"],
                "cold_rtf": e2e["first"]["rtf"],
                "warm_median_rtf": e2e["warm"]["median_rtf"],
                "proof_run_rtf": proof_rtf,
                "first_post_setup_rtf": e2e["first"]["rtf"],
                "peak_pss_bytes": e2e["sampled_memory"]["peak_sampled_pss_kb"] * 1024,
                "peak_vm_hwm_bytes": e2e["sampled_memory"]["peak_observed_vmhwm_kb"] * 1024,
            }
            if e["metrics"] != expected_metrics or len(e2e["warm"]["rtf"]) != 5 or median(e2e["warm"]["rtf"]) != e["metrics"]["warm_median_rtf"]:
                fail(f"{e['id']}: setup/first/five-warm metric provenance mismatch")
            if e["scope"] != "full_e2e" or e["attempt_status"] != "ran" or not e["android_attempted"] or e["device"] != EXPECTED_DEVICE:
                fail(f"{e['id']}: completed physical-phone route boundary mismatch")
            if e["transcript"]["classification"] != "legacy_v1" or e["transcript"]["sha256"] != LEGACY_V1_SHA256 or e["transcript"]["canonical_v2_match"] is not False:
                fail(f"{e['id']}: pragmatic legacy-v1 boundary mismatch")
            source_sample = EXP_0023 / "samples/supertonic-stable-softplus-qnn-context.wav"
            if e2e["runner"]["runs"] != 6 or e2e["wav"]["sha256"] != EXP_0023_WAV_SHA256 or e["wav"]["sha256"] != EXP_0023_WAV_SHA256 or hashlib.sha256(source_sample.read_bytes()).hexdigest() != EXP_0023_WAV_SHA256:
                fail(f"{e['id']}: six-run/WAV provenance mismatch")
            accepted_0011 = entries_by_id["0011-supertonic-all-htp"]["listening_review"]
            if accepted_0011["status"] != "accepted" or accepted_0011["sample_sha256"] != EXP_0023_WAV_SHA256 or e["listening_review"]["status"] != "accepted" or e["listening_review"]["reviewer"] != "Moritz" or e["listening_review"]["sample_sha256"] != EXP_0023_WAV_SHA256:
                fail(f"{e['id']}: exact-hash historical listening verdict mismatch")
            if source_result["source_vs_context_raw_comparison"] != {"byte_identical": True, "cosine": 1.0, "elements": 729746, "interpretation": "descriptive only; no numerical acceptance gate", "max_abs": 0.0, "rmse": 0.0}:
                fail(f"{e['id']}: matched-arm byte identity boundary mismatch")
            if source_result["context_source_unavailable_gate"] != "passed" or source_result["cleanup"] != {"phone_lock_release_verified_nonblocking": True, "remote_cleanup_exit_code": 0, "remote_root_absence_verified": True} or source_result["parser_incident"]["phone_rerun"] is not False:
                fail(f"{e['id']}: source-absence, cleanup, or offline-parser boundary mismatch")
            if arm == "context":
                if not proof["physical_qnn_htp_proven"] or not proof["fallback_disabled"] or not proof["source_onnx_unavailable"] or not proof["excluded_from_setup_and_e2e_timing"]:
                    fail(f"{e['id']}: context physical-proof boundary mismatch")
                if any(profile["providers"] != ["QNNExecutionProvider"] for profile in proof["ort_profiles"]):
                    fail(f"{e['id']}: context ORT profile is not QNN-only")
                if any(set(profile["hvx_thread_values"]) != {4} or profile["rpc_events"] <= 0 or profile["accelerator_us_events"] <= 0 or profile["accelerator_cycle_events"] <= 0 for profile in proof["qnn_profiles"]):
                    fail(f"{e['id']}: context physical RPC/accelerator/cycle/HVX evidence mismatch")
            elif "proof_run_rtf" not in e["missing_reasons"]:
                fail(f"{e['id']}: absent source-arm proof run lacks a reason")
        if e["id"] in EXP_0024_IDS:
            result_bytes = EXP_0024_RESULT.read_bytes()
            if hashlib.sha256(result_bytes).hexdigest() != EXP_0024_RESULT_SHA256:
                fail(f"{e['id']}: committed phone result hash mismatch")
            if hashlib.sha256(EXP_0024_MANIFEST.read_bytes()).hexdigest() != EXP_0024_MANIFEST_SHA256:
                fail(f"{e['id']}: evidence manifest hash mismatch")
            source_result = json.loads(result_bytes)
            evidence_manifest = json.loads(EXP_0024_MANIFEST.read_text())
            listening_bytes = EXP_0024_LISTENING.read_bytes()
            if hashlib.sha256(listening_bytes).hexdigest() != EXP_0024_LISTENING_SHA256:
                fail(f"{e['id']}: exact-hash listening evidence mismatch")
            listening_evidence = json.loads(listening_bytes)
            listening_by_route = {review["route_id"]: review for review in listening_evidence["reviews"]}
            arm = "source" if e["id"] == "0024-pocket-reconstruction-source-onnx-htp" else "context"
            peer = "0024-pocket-reconstruction-external-context-htp" if arm == "source" else "0024-pocket-reconstruction-source-onnx-htp"
            comparison = source_result["comparison"]
            arm_result = comparison[arm]
            proof = source_result["physical_proof"][arm]
            if source_result["status"] != "complete" or source_result["route"] != "pocket-fixed-alba-text64-cache512-canonical-v2-0024-reconstruction-derivative":
                fail(f"{e['id']}: completed reconstruction-derivative status mismatch")
            inventory = source_result["graph_inventory"]["evidence"]
            if inventory["exact_0014_hashes_reproduced"] is not False or inventory["documented_derivatives_allowed"] is not True or any(item["exact_0014_hash_match"] for item in inventory["graphs"].values()):
                fail(f"{e['id']}: 0024 derivative was relabeled as exact 0014 graphs")
            expected_setup = {"source": [27.0767, 23.8668, 28.6125], "context": [0.729463, 1.26412, 1.01122]}[arm]
            expected_first = {"source": [0.172432, 0.167197, 0.182052], "context": [0.167568, 0.16733, 0.165802]}[arm]
            expected_warm_median = {"source": 0.168605, "context": 0.164032}[arm]
            expected_proof_rtf = proof["result"]["iterations"][0]["rtf"]
            if arm_result["setup_seconds"] != expected_setup or len(arm_result["runs"]) != 3 or median(expected_setup) != arm_result["setup_median_seconds"]:
                fail(f"{e['id']}: three-process setup distribution mismatch")
            if arm_result["first_rtf"] != expected_first or median(expected_first) != arm_result["first_rtf_median"]:
                fail(f"{e['id']}: first-generation distribution mismatch")
            if len(arm_result["warm_rtf"]) != 15 or median(arm_result["warm_rtf"]) != arm_result["warm_rtf_median_pooled"] or arm_result["warm_rtf_median_pooled"] != expected_warm_median:
                fail(f"{e['id']}: pooled 15-warm distribution mismatch")
            if any(len(run["warm"]["runs"]) != 5 or run["warm"]["count"] != 5 or run["provider"] != "QNNExecutionProvider" or run["cpu_fallback"] is not False or run["determinism"]["state_reset"]["flow_cache"] != "fresh from immutable packed Alba for every iteration" for run in arm_result["run_evidence"]):
                fail(f"{e['id']}: per-process first/five-warm reset contract mismatch")
            expected_metrics = {
                "load_seconds": arm_result["setup_median_seconds"],
                "cold_rtf": arm_result["first_rtf_median"],
                "warm_median_rtf": arm_result["warm_rtf_median_pooled"],
                "proof_run_rtf": expected_proof_rtf,
                "first_post_setup_rtf": None,
                "peak_pss_bytes": None,
                "peak_vm_hwm_bytes": arm_result["max_vm_hwm_kb"] * 1024,
            }
            if e["metrics"] != expected_metrics:
                fail(f"{e['id']}: normalized setup/RTF/VmHWM metrics mismatch")
            setup_expected = {
                "observed_setup_delta_seconds_source_minus_context": 26.065479999999997,
                "speedup_ratio_source_over_context": 26.776270247819465,
                "observed_setup_reduction_percent": 96.26534991339418,
                "minimum_speedup_gate": None,
            }
            if any(comparison[key] != value for key, value in setup_expected.items()):
                fail(f"{e['id']}: matched setup comparison mismatch")
            matched = e.get("matched_comparison")
            if not isinstance(matched, dict) or matched["source_commit"] != EXP_0024_COMMIT or matched["arm"] != arm or matched["peer_route_id"] != peer:
                fail(f"{e['id']}: matched comparison provenance mismatch")
            if matched["source_setup_seconds"] != comparison["source"]["setup_seconds"] or matched["context_setup_seconds"] != comparison["context"]["setup_seconds"] or matched["source_first_rtf"] != comparison["source"]["first_rtf"] or matched["context_first_rtf"] != comparison["context"]["first_rtf"] or matched["source_warm_rtf"] != comparison["source"]["warm_rtf"] or matched["context_warm_rtf"] != comparison["context"]["warm_rtf"]:
                fail(f"{e['id']}: matched comparison distributions mismatch")
            if matched["source_minus_context_median_seconds"] != setup_expected["observed_setup_delta_seconds_source_minus_context"] or matched["source_over_context_median_ratio"] != setup_expected["speedup_ratio_source_over_context"] or matched["context_setup_reduction_percent"] != setup_expected["observed_setup_reduction_percent"] or matched["minimum_speedup_gate"] is not None or matched["offline_context_generation_included"] is not False or matched["proof_runs_excluded_from_benchmark_metrics"] is not True:
                fail(f"{e['id']}: matched comparison boundary mismatch")
            output = source_result["output_comparison"]
            expected_output = {
                "byte_identical": output["byte_identical_between_arms"],
                "equal_length": output["equal_length"],
                "correlation": output["correlation"],
                "snr_db_source_over_difference": output["snr_db_source_over_difference"],
                "interpretation": "descriptive numerical comparison only; both byte-distinct WAVs have independent exact-hash accepted listening reviews",
            }
            if matched["output_comparison"] != expected_output or output["source_listening"]["status"] != "not_reviewed" or output["context_listening"]["status"] != "not_reviewed":
                fail(f"{e['id']}: descriptive output/listening boundary mismatch")
            aggregate = proof["aggregate"]
            if proof["cpu_fallback_disabled"] is not True or aggregate["provider_events"] != {"QNNExecutionProvider": 344} or not aggregate["all_invoked_calls_qnn_only"] or not aggregate["all_physical_event_counts_match_qnn"]:
                fail(f"{e['id']}: fallback-disabled physical provider proof mismatch")
            if len({aggregate["rpc_execute_events"], aggregate["accelerator_execute_events"], aggregate["cycle_events"], aggregate["hvx_events"]}) != 1 or aggregate["rpc_execute_events"] != 344 or aggregate["hvx_thread_sum"] != 1376:
                fail(f"{e['id']}: physical RPC/accelerator/cycle/HVX counts mismatch")
            expected_cycles = {"source": 3989277125, "context": 3998683560}[arm]
            if aggregate["accelerator_cycles"] != expected_cycles or proof["safety"]["runner_exit"] != 0 or proof["safety"]["cleanup_exit"] != 0 or proof["safety"]["cleanup_verified"] is not True:
                fail(f"{e['id']}: physical cycle/safety evidence mismatch")
            if (arm == "context") != (proof["source_onnx_unavailable"] is True) or (arm == "context") != all(run["source_onnx_unavailable"] is True for run in arm_result["run_evidence"]):
                fail(f"{e['id']}: source-ONNX availability boundary mismatch")
            source_wav = EXP_0024 / f"results/phone-campaign/{arm}.wav"
            if e["wav"]["sha256"] != EXP_0024_WAV_SHA256[arm] or hashlib.sha256(source_wav.read_bytes()).hexdigest() != EXP_0024_WAV_SHA256[arm] or proof["wav"]["sha256"] != EXP_0024_WAV_SHA256[arm]:
                fail(f"{e['id']}: retained WAV provenance mismatch")
            source_review = listening_by_route.get(e["id"])
            if source_review is None or source_review["status"] != "accepted" or source_review["wav_sha256"] != EXP_0024_WAV_SHA256[arm]:
                fail(f"{e['id']}: owning exact-hash listening record mismatch")
            note_scope = "source-ONNX" if arm == "source" else "external-EPContext"
            peer_scope = "context" if arm == "source" else "source"
            expected_review = {
                "status": "accepted",
                "reviewer": listening_evidence["reviewer"],
                "date": listening_evidence["review_date"],
                "notes": f"{listening_evidence['verbatim']} Independent exact-hash verdict for the distinct 0024 {note_scope} phone WAV; no transfer to the {peer_scope} WAV, host output, another hash, or the Pocket TTS family.",
                "sample_sha256": EXP_0024_WAV_SHA256[arm],
            }
            if e["listening_review"] != expected_review or e["objective_evidence"]["status"] != "descriptive":
                fail(f"{e['id']}: exact-hash listening/objective boundary mismatch")
            history = source_result["campaign_history"]
            cleanup = history["pending_root_cleanup_resume"]
            if history["interrupted_run_excluded"] is not True or history["interruption_checkpoint"]["interruption"]["measurement_included"] is not False or cleanup["tri_state_status"] != "verified_absent" or not cleanup["transport_revalidated"] or not cleanup["device_identity_revalidated"] or not cleanup["phone_lock_released"]:
                fail(f"{e['id']}: excluded-disconnect or cleanup-closure boundary mismatch")
            if evidence_manifest["result"]["sha256"] != EXP_0024_RESULT_SHA256 or evidence_manifest["validation"] != {"source_cold_processes": 3, "context_cold_processes": 3, "profiled_proofs": ["source", "context"], "profile_files_per_proof": 24, "pending_remote_root_cleanup": "verified_absent", "source_listening": "not_reviewed", "context_listening": "not_reviewed"}:
                fail(f"{e['id']}: hash-bound evidence manifest boundary mismatch")
            if e["scope"] != "full_e2e" or e["attempt_status"] != "ran" or not e["android_attempted"] or e["device"] != EXPECTED_DEVICE:
                fail(f"{e['id']}: completed physical-phone route boundary mismatch")
            if e["transcript"]["classification"] != "canonical_v2" or e["transcript"]["effective_frontend"]["token_ids_sha256"] != "56d50c958627be19a7f2c86dde68a537a80f3f6d9087c16f55fde58c4d117c82":
                fail(f"{e['id']}: canonical-v2 frontend boundary mismatch")
            if "first_post_setup_rtf" not in e["missing_reasons"] or "peak_pss_bytes" not in e["missing_reasons"]:
                fail(f"{e['id']}: aggregate-first/PSS null reasons missing")
        remeasurements = e.get("remeasurements", [])
        if e["id"] == "0008-supertonic-cpu-t1":
            if e["metrics"] != FROZEN_0008_SUPERTONIC_METRICS or e["wav"] is not None:
                fail("0008-supertonic-cpu-t1: frozen original metrics/WAV provenance was overwritten")
            if len(remeasurements) != 1:
                fail("0008-supertonic-cpu-t1: expected exactly one provenance-tracked remeasurement")
        elif remeasurements:
            fail(f"{e['id']}: unexpected remeasurement without a validated frozen baseline")
        for refresh in remeasurements:
            if refresh["original_snapshot"]["metrics"] != e["metrics"] or refresh["original_snapshot"]["wav"] != e["wav"]:
                fail(f"{e['id']}: nested remeasurement does not preserve the frozen original snapshot")
            if refresh["source_commit"] != "b717b74b1866b578f02f96e6962563c7567b6e00" or refresh["experiment"] != "0020":
                fail(f"{e['id']}: unexpected remeasurement provenance")
            transcript = refresh["contract"].get("transcript", {})
            if transcript.get("classification") != "legacy_v1" or transcript.get("sha256") != "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f":
                fail(f"{e['id']}: historical refresh transcript must remain exact legacy v1")
            if transcript.get("canonical_v2_sha256") != "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67":
                fail(f"{e['id']}: canonical-v2 comparison boundary is missing")
            warm_values = refresh["warm_rtf_values"]
            if len(warm_values) != 3 or abs(median(warm_values) - refresh["metrics"]["warm_median_rtf"]) > 1e-15:
                fail(f"{e['id']}: exact historical three-warm median mismatch")
            if "does not satisfy" not in refresh["contract"].get("current_global_contract_status", ""):
                fail(f"{e['id']}: newer five-warm protocol boundary is missing")
            run_warm = [run["rtf"] for run in refresh["runs"] if run["state"] == "warm"]
            if run_warm != warm_values or len(refresh["runs"]) != 4:
                fail(f"{e['id']}: nested cold/warm run evidence mismatch")
            review = refresh["listening_review"]
            source_refresh = json.loads((ROOT / refresh["sources"][0]).read_text())
            source_review = source_refresh["representative_wav"]["listening_review"]
            expected_review = {
                "status": source_review["status"], "reviewer": source_review["reviewer"], "date": source_review["date"],
                "notes": source_review["notes"] + ". " + source_review["scope"][0].upper() + source_review["scope"][1:] + ".",
                "sample_sha256": source_review["sample_sha256"],
            }
            if review != expected_review or review["sample_sha256"] != refresh["representative_wav"]["sha256"]:
                fail(f"{e['id']}: refresh listening status/hash mismatch")
            for source in refresh["sources"]:
                if not (ROOT / source).exists():
                    fail(f"{e['id']}: refresh source path missing: {source}")
            rwav = refresh["representative_wav"]
            rpath = HERE / rwav["path"]
            if not rpath.is_file() or hashlib.sha256(rpath.read_bytes()).hexdigest() != rwav["sha256"]:
                fail(f"{e['id']}: refresh representative WAV missing/hash mismatch")
            with wave.open(str(rpath), "rb") as f:
                if rpath.stat().st_size != rwav["bytes"] or f.getframerate() != rwav["sample_rate_hz"] or f.getnchannels() != rwav["channels"] or f.getsampwidth() != 2 or abs(f.getnframes() / f.getframerate() - rwav["duration_seconds"]) > 1e-9:
                    fail(f"{e['id']}: refresh representative WAV header mismatch")
            if rwav.get("verified") is not True:
                fail(f"{e['id']}: refresh representative WAV is not marked verified")
            verified_media += 1
        if e["id"] == "0008-supertonic-cpu-t1":
            refresh_wav = e["remeasurements"][0]["representative_wav"]
            experiment_page = ROOT / "docs/experiments/0020-historic-android-benchmark-refresh/index.html"
            expected_src = f'../../android-benchmarks/{refresh_wav["path"]}'
            if not experiment_page.is_file() or f'src="{expected_src}"' not in experiment_page.read_text():
                fail(f"{e['id']}: suppressed row must preserve 0020 experiment-page access to retained refresh audio")
        wav = e["wav"]
        if wav is None:
            if "wav" not in e["missing_reasons"] and "all" not in e["missing_reasons"]:
                fail(f"{e['id']}: null WAV lacks a missing-evidence reason")
        else:
            for key in ("path", "sha256", "bytes", "sample_rate_hz", "channels", "duration_seconds", "verified"):
                if key not in wav:
                    fail(f"{e['id']}: WAV missing {key}")
            if wav["verified"] is not True:
                fail(f"{e['id']}: copied WAV is not marked verified")
            path = HERE / wav["path"]
            if not path.is_file():
                fail(f"{e['id']}: WAV does not exist: {path}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != wav["sha256"]:
                fail(f"{e['id']}: WAV SHA-256 mismatch")
            with wave.open(str(path), "rb") as f:
                if path.stat().st_size != wav["bytes"]:
                    fail(f"{e['id']}: WAV byte count mismatch")
                if f.getframerate() != wav["sample_rate_hz"] or f.getnchannels() != wav["channels"] or f.getsampwidth() != 2:
                    fail(f"{e['id']}: WAV format mismatch (expected declared rate/channels and PCM16 sample width)")
                if abs(f.getnframes() / f.getframerate() - wav["duration_seconds"]) > 1e-9:
                    fail(f"{e['id']}: WAV duration mismatch")
            verified_media += 1
        for source in e["sources"]:
            if not (ROOT / source).exists():
                fail(f"{e['id']}: source path missing: {source}")
    if transcript_counts["legacy_v1"] != 19 or transcript_counts["noncanonical"] != 9 or transcript_counts["canonical_v2"] < 1:
        fail(f"visible transcript classification baseline drifted: {transcript_counts}")
    report = HERE / "missing-fields.md"
    if not report.is_file() or "null" not in report.read_text():
        fail("missing-fields.md is absent or does not explain null semantics")
    if (HERE / "index.html").read_bytes() != (HERE / "dashboard.html").read_bytes():
        fail("generated index.html and dashboard.html differ")
    required_dashboard_fragments = (
        '>Setup</button>',
        'data-metric="load_seconds"',
        'id="routes-scroll" tabindex="0" role="region"',
        'id="routes-fullscreen" aria-controls="routes-panel" aria-pressed="false"',
        'requestFullscreen',
        'fullscreenchange',
        "sortTable(7,'ascending',false)",
        'More columns are available horizontally',
        'Vertical scrolling stays with the page.',
        'id="routes-sticky-header"',
        "window.addEventListener('scroll',scheduleStickyHeader",
    )
    prohibited_dashboard_fragments = (
        'id="routes-scroll-start"',
        'id="routes-scroll-end"',
        'id="routes-scroll-cue"',
        'max-height:min(72vh,760px)',
        '>Evidence summary</button>',
    )
    for page_name in ("index.html", "dashboard.html"):
        page = HERE / page_name
        if not page.is_file():
            fail(f"missing generated page: {page_name}")
        page_text = page.read_text()
        for fragment in required_dashboard_fragments:
            if fragment not in page_text:
                fail(f"{page_name}: required sortable/scroll/fullscreen UI is missing {fragment!r}")
        for fragment in prohibited_dashboard_fragments:
            if fragment in page_text:
                fail(f"{page_name}: removed nested-scroll UI leaked into the generated dashboard: {fragment!r}")
        for item in timeline:
            if item["model"] not in page_text or item["first_release_date"] not in page_text or item["source_url"] not in page_text:
                fail(f"{page_name}: timeline entry missing for {item['model']}")
        for e in entries:
            marker = f'data-route-id="{e["id"]}"'
            row_match = re.search(rf'<tr {re.escape(marker)}>.*?</tr>', page_text)
            row_html = row_match.group(0) if row_match else None
            dashboard_visible = e["scope"] == "full_e2e" and e.get("presentation", {}).get("dashboard_visible", True)
            if dashboard_visible and (page_text.count(marker) != 1 or row_html is None):
                fail(f"{page_name}: visible full-E2E route {e['id']} is missing or duplicated")
            if not dashboard_visible and marker in page_text:
                fail(f"{page_name}: hidden route {e['id']} leaked into presentation")
            if dashboard_visible:
                if len(re.findall(r'<td(?:\s|>)', row_html)) != 10:
                    fail(f"{page_name}: {e['id']} visible route must have exactly ten presentation cells")
                setup_match = re.search(r'<td data-metric="load_seconds" data-sort="([^"]*)" title="[^"]*">(.*?)</td>', row_html)
                if setup_match is None:
                    fail(f"{page_name}: {e['id']} setup cell is missing")
                refresh = e.get("remeasurements", [])[-1] if e.get("remeasurements") else None
                setup_value = (refresh["metrics"] if refresh else e["metrics"])["load_seconds"]
                expected_sort = "" if setup_value is None else str(setup_value)
                if setup_match.group(1) != expected_sort:
                    fail(f"{page_name}: {e['id']} setup sort value does not match metrics.load_seconds")
                route_text = f'{e["route"]} {e.get("deployment_variant") or ""}'.lower()
                expected_semantics = "context load / reload" if "external epcontext" in route_text or "external context" in route_text else "source compile / setup" if "source-onnx" in route_text or "source onnx" in route_text else "route setup / load"
                if expected_semantics not in setup_match.group(2):
                    fail(f"{page_name}: {e['id']} setup semantics label mismatch")
                if setup_value is None and not setup_match.group(2).startswith("—"):
                    fail(f"{page_name}: {e['id']} unavailable setup was not rendered as unavailable")
            identity = e["model_identity"]
            if dashboard_visible and identity is not None and identity["url"] not in page_text:
                fail(f"{page_name}: {e['id']} model source link is missing")
            refresh = e.get("remeasurements", [])[-1] if e.get("remeasurements") else None
            display_wav = refresh["representative_wav"] if refresh else e["wav"]
            display_review = refresh["listening_review"] if refresh else e["listening_review"]
            if not dashboard_visible:
                anchor = f"audio-{e['id']}"
                review_anchor = f"needs-{e['id']}"
                if f'href="#{anchor}"' in page_text or f'id="{anchor}"' in page_text or f'id="{review_anchor}"' in page_text:
                    fail(f"{page_name}: hidden route {e['id']} leaked into audio presentation")
                if e.get("presentation") is not None and display_wav is not None and f'src="{display_wav["path"]}"' in page_text:
                    fail(f"{page_name}: presentation-suppressed route {e['id']} retained a compact audio player")
                continue
            if display_wav is None:
                if row_html is not None and 'class="listening-link"' in row_html:
                    fail(f"{page_name}: {e['id']} listening status links without retained audio")
                continue
            anchor = f"audio-{e['id']}"
            expected_listening_link = f'class="listening-link" href="#{anchor}" aria-label="'
            if row_html is None or expected_listening_link not in row_html:
                fail(f"{page_name}: {e['id']} listening-status badge does not accessibly target its player")
            if f'id="{anchor}"' not in page_text:
                fail(f"{page_name}: {e['id']} player anchor is missing")
            review_anchor = f"needs-{e['id']}"
            if display_review["status"] == "not_reviewed":
                if f'id="{review_anchor}"' not in page_text:
                    fail(f"{page_name}: unreviewed sample {e['id']} missing from Needs review")
            elif f'id="{review_anchor}"' in page_text:
                fail(f"{page_name}: reviewed sample {e['id']} leaked into Needs review")
            if f'src="{display_wav["path"]}"' not in page_text:
                fail(f"{page_name}: {e['id']} embedded audio source is missing")
    print(f"PASS: {len(entries)} routes across {len(seen_experiments)} experiments; {verified_media} verified Android WAVs")


if __name__ == "__main__":
    main()
