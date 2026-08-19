#!/usr/bin/env python3
"""Fail-closed checks for the global Android benchmark registry."""
from __future__ import annotations

import hashlib
import json
from datetime import date
import re
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REGISTRY_PATH = HERE / "registry.json"
EXPECTED_DEVICE = {"model": "SM-S918B", "soc": "SM8550", "serial": "R5CW81PR8SY", "abi": "arm64-v8a"}
METRIC_FIELDS = ("load_seconds", "cold_rtf", "warm_median_rtf", "peak_pss_bytes", "peak_vm_hwm_bytes")
STATUSES = {"ran", "partial", "blocked", "deferred", "not_run"}


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
    seen_experiments = set()
    verified_media = 0
    for e in entries:
        required = ("id", "experiment", "model", "model_identity", "route", "deployment_variant", "quantization", "scope", "attempt_status", "technical_execution", "structural_audio", "objective_evidence", "listening_review", "android_attempted", "provider", "precision", "threads", "device", "metrics", "wav", "summary", "limitations", "sources", "missing_reasons")
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
        if e["wav"] is None and structural["status"] != "unavailable":
            fail(f"{e['id']}: missing WAV must have structural_audio.status=unavailable")
        if e["wav"] is not None and structural["sample_sha256"] != e["wav"]["sha256"]:
            fail(f"{e['id']}: structural audio hash does not match WAV")
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
                if f.getframerate() != wav["sample_rate_hz"] or f.getnchannels() != wav["channels"]:
                    fail(f"{e['id']}: WAV format mismatch")
                if abs(f.getnframes() / f.getframerate() - wav["duration_seconds"]) > 1e-9:
                    fail(f"{e['id']}: WAV duration mismatch")
            verified_media += 1
        for source in e["sources"]:
            if not (ROOT / source).exists():
                fail(f"{e['id']}: source path missing: {source}")
    report = HERE / "missing-fields.md"
    if not report.is_file() or "null" not in report.read_text():
        fail("missing-fields.md is absent or does not explain null semantics")
    for page_name in ("index.html", "dashboard.html"):
        page = HERE / page_name
        if not page.is_file():
            fail(f"missing generated page: {page_name}")
        page_text = page.read_text()
        for item in timeline:
            if item["model"] not in page_text or item["first_release_date"] not in page_text or item["source_url"] not in page_text:
                fail(f"{page_name}: timeline entry missing for {item['model']}")
        for e in entries:
            marker = f'data-route-id="{e["id"]}"'
            if e["scope"] == "full_e2e" and page_text.count(marker) != 1:
                fail(f"{page_name}: full E2E route {e['id']} is missing or duplicated")
            if e["scope"] == "excluded_non_e2e" and marker in page_text:
                fail(f"{page_name}: non-E2E route {e['id']} leaked into presentation")
            identity = e["model_identity"]
            if e["scope"] == "full_e2e" and identity is not None and identity["url"] not in page_text:
                fail(f"{page_name}: {e['id']} model source link is missing")
            if e["wav"] is None:
                continue
            anchor = f"audio-{e['id']}"
            if f'href="#{anchor}"' not in page_text:
                fail(f"{page_name}: {e['id']} table link does not target its player")
            if f'id="{anchor}"' not in page_text:
                fail(f"{page_name}: {e['id']} player anchor is missing")
            review_anchor = f"needs-{e['id']}"
            if e["scope"] == "full_e2e" and e["listening_review"]["status"] == "not_reviewed":
                if f'id="{review_anchor}"' not in page_text:
                    fail(f"{page_name}: unreviewed sample {e['id']} missing from Needs review")
            elif f'id="{review_anchor}"' in page_text:
                fail(f"{page_name}: reviewed/non-E2E sample {e['id']} leaked into Needs review")
            if f'src="{e["wav"]["path"]}"' not in page_text:
                fail(f"{page_name}: {e['id']} embedded audio source is missing")
    print(f"PASS: {len(entries)} routes across {len(seen_experiments)} experiments; {verified_media} verified Android WAVs")


if __name__ == "__main__":
    main()
