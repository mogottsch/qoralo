#!/usr/bin/env python3
"""Fail-closed checks for the global Android benchmark registry."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REGISTRY_PATH = HERE / "registry.json"
EXPECTED_DEVICE = {"model": "SM-S918B", "soc": "SM8550", "serial": "R5CW81PR8SY", "abi": "arm64-v8a"}
METRIC_FIELDS = ("load_seconds", "cold_rtf", "warm_median_rtf", "peak_pss_bytes", "peak_vm_hwm_bytes")
STATUSES = {"success", "partial", "rejected", "blocked", "deferred", "not_run"}


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
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        fail("entries must be a non-empty list")
    ids = [e.get("id") for e in entries]
    if len(ids) != len(set(ids)):
        fail("duplicate route id")
    seen_experiments = set()
    verified_media = 0
    for e in entries:
        required = ("id", "experiment", "model", "route", "deployment_variant", "attempt_status", "android_attempted", "provider", "precision", "threads", "device", "metrics", "wav", "summary", "limitations", "sources", "missing_reasons")
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
        if e["attempt_status"] not in STATUSES:
            fail(f"{e['id']}: invalid status")
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
        for e in entries:
            if e["wav"] is None:
                continue
            anchor = f"audio-{e['id']}"
            if f'href="#{anchor}"' not in page_text:
                fail(f"{page_name}: {e['id']} table link does not target its player")
            if f'id="{anchor}"' not in page_text:
                fail(f"{page_name}: {e['id']} player anchor is missing")
            if f'src="{e["wav"]["path"]}"' not in page_text:
                fail(f"{page_name}: {e['id']} embedded audio source is missing")
    print(f"PASS: {len(entries)} routes across {len(seen_experiments)} experiments; {verified_media} verified Android WAVs")


if __name__ == "__main__":
    main()
