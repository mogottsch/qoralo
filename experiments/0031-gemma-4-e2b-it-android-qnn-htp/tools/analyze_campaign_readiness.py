#!/usr/bin/env python3
"""Validate the host-only shared-engine/fresh-dialog canonical campaign plan."""
from __future__ import annotations

import hashlib
import json
import re
import stat
from collections import Counter
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
SDK = Path("/home/moritz/opt/qairt/2.49.40.260810")
STAGE = EXP / ".local/campaign-stage"
OUT = EXP / "results/canonical-campaign-harness-readiness/result.json"
EXPECTED_CONTEXT = "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394"
SOURCE_HASHES = {
    "dialog_cpp": "5365cff503c93f27462831016da8bdc7dd983986b20677153d57f1d5cd886dd4",
    "registry_cpp": "fb4663068fb81709a4063d4cdc5a35634ace6bbbba89edb40ea41a2f12ef19b3",
    "qualla_dialog_cpp": "baa2ff5b37431160b3d6526e009846f80272b75922f8a2ee3de24b476e5f0746",
    "genie_app_docs": "f2d1c839d6508c87be4b5c14d1d6e233606fcbcf5af643884ad1362ddf2e197a",
}
SOURCES = {
    "dialog_cpp": SDK / "examples/Genie/Genie/src/Dialog.cpp",
    "registry_cpp": SDK / "examples/Genie/Genie/src/Registry.cpp",
    "qualla_dialog_cpp": SDK / "examples/Genie/Genie/src/qualla/dialog.cpp",
    "genie_app_docs": SDK / "docs/QAIRT-Docs/Genie/general/tools/genie-app.html",
}
EXPECTED_TIERS = ["short"] * 6 + ["medium"] * 5 + ["long"] * 5
EXPECTED_PROMPTS = {
    "short": (170, "b286f8dda746e8056836a2e71049df866527bee51e368363dd80cfbe27e60e7a"),
    "medium": (594, "8e3c03cb0d1ddce8455306b8b84585ce2ae07c083c4fdbdec1e946e3be56771d"),
    "long": (1929, "450b519d417e29c4239e39aef856db1813d2580cd62e9db9adaae3d94ba8f260"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    for name, path in SOURCES.items():
        if sha256(path) != SOURCE_HASHES[name]:
            raise RuntimeError(f"campaign-isolation source mismatch: {name}")
    dialog_source = SOURCES["dialog_cpp"].read_text(errors="replace")
    registry_source = SOURCES["registry_cpp"].read_text(errors="replace")
    qualla_dialog_source = SOURCES["qualla_dialog_cpp"].read_text(errors="replace")
    docs = SOURCES["genie_app_docs"].read_text(errors="replace")
    source_facts = {
        "shared_htp_config_extracted_to_standalone_registry": (
            "getStandaloneEnginesConfig" in dialog_source and 'contains("shared-engine")' in dialog_source
        ),
        "registry_engine_created_only_when_key_absent": "if (!keyToEngineMap.contains(key))" in registry_source,
        "registry_engine_reference_counted": (
            "incrementUseCount" in registry_source and "decrementUseCount" in registry_source
        ),
        "new_dialog_binds_independent_engine_state": (
            "_engineState[engineRole] = std::make_shared<EngineState>" in qualla_dialog_source
        ),
        "dialog_applies_its_engine_state_before_shared_query": (
            "m_quallaDialog->applyEnginesState()" in dialog_source
        ),
        "genie_app_supports_dialog_create_query_free": all(
            value in docs for value in ("dialog create", "dialog query", "dialog free")
        ),
        "genie_app_supports_profile_per_request": all(
            value in docs for value in ("profile create", "profile save", "profile free")
        ),
    }
    if not all(source_facts.values()):
        raise RuntimeError(f"campaign source proof incomplete: {source_facts}")

    manifest_path = STAGE / "campaign-manifest.json"
    sums_path = STAGE / "SHA256SUMS"
    manifest = json.loads(manifest_path.read_text())
    config = json.loads((STAGE / "gemma4-e2b-htp-cl4096-campaign.json").read_text())
    script_text = (STAGE / "campaign.script").read_text()
    script_lines = script_text.splitlines()
    requests = manifest["requests"]
    if manifest["context_sha256"] != EXPECTED_CONTEXT:
        raise RuntimeError("campaign context identity mismatch")
    if manifest["request_count"] != 16 or [item["tier"] for item in requests] != EXPECTED_TIERS:
        raise RuntimeError("campaign request shape/order mismatch")
    if requests[0]["request_id"] != "first-short-00":
        raise RuntimeError("first-request identity mismatch")
    if Counter(item["tier"] for item in requests) != {"short": 6, "medium": 5, "long": 5}:
        raise RuntimeError("campaign tier count mismatch")
    if manifest["max_new_tokens"] != 2048 or manifest["request_timeout_seconds"] != 1800:
        raise RuntimeError("campaign ceiling/timeout mismatch")
    if not manifest["shared_engine"] or not manifest["keeper_dialog_retains_engine"] or not manifest["one_genie_process"]:
        raise RuntimeError("campaign loaded-route reuse plan mismatch")
    if manifest["request_isolation"] != "fresh_dialog_per_logical_request_with_independent_engine_state":
        raise RuntimeError("campaign request isolation mismatch")
    if manifest["campaign_authorized"] or manifest["adb_used"] or manifest["phone_lock_acquired"]:
        raise RuntimeError("host-only campaign readiness boundary violated")

    dialog = config["dialog"]
    htp = dialog["engine"]["backend"]["QnnHtp"]
    if dialog["max-num-tokens"] != 2048 or dialog["context"]["bos-token"] != -1:
        raise RuntimeError("campaign config token boundary mismatch")
    if not htp["shared-engine"] or not htp["allow-async-init"]:
        raise RuntimeError("campaign config does not enable supported HTP engine sharing")
    context_name = "models/weight_sharing_model_ar128_ar1_cl4096_scl512_1_of_1.serialized.bin"
    if sha256(STAGE / context_name) != EXPECTED_CONTEXT:
        raise RuntimeError("campaign staged context mismatch")

    keeper_create = script_lines.index("dialog create keeper-dialog keeper-config")
    keeper_free = script_lines.index("dialog free keeper-dialog")
    query_lines = [line for line in script_lines if line.startswith("dialog query ")]
    if len(query_lines) != 16 or not keeper_create < min(map(script_lines.index, query_lines)) < keeper_free:
        raise RuntimeError("keeper-dialog lifetime does not bracket every request")
    if any(line.startswith("dialog reset ") for line in script_lines):
        raise RuntimeError("campaign must use fresh dialogs, not unproven reset")
    for item in requests:
        ordinal = item["ordinal"]
        dialog_name = f"dialog-{ordinal:02d}"
        config_name = f"config-{ordinal:02d}"
        profile_name = f"profile-{ordinal:02d}"
        expected = [
            f"profile create {profile_name}",
            f"dialog config create {config_name} gemma4-e2b-htp-cl4096-campaign.json",
            f"dialog create {dialog_name} {config_name}",
            f"dialog setMaxNumTokens {dialog_name} 2048",
            f"dialog query {dialog_name} prompts/{item['tier']}.txt campaign/outputs/{item['request_id']}.txt",
            f"profile save {profile_name} campaign/profiles/{item['request_id']}.json",
            f"dialog free {dialog_name}",
            f"dialog config free {config_name}",
            f"profile free {profile_name}",
        ]
        positions = [script_lines.index(line) for line in expected]
        if positions != sorted(positions) or not keeper_create < positions[0] < positions[-1] < keeper_free:
            raise RuntimeError(f"request lifecycle order mismatch: {item['request_id']}")
        if item["max_new_tokens"] != 2048 or item["input_tokens"] != EXPECTED_PROMPTS[item["tier"]][0]:
            raise RuntimeError(f"request contract mismatch: {item['request_id']}")

    for tier, (tokens, digest) in EXPECTED_PROMPTS.items():
        path = STAGE / f"prompts/{tier}.txt"
        if sha256(path) != digest or tokens + 2048 > 4096:
            raise RuntimeError(f"campaign prompt identity/context fit mismatch: {tier}")

    files = manifest["files"]
    for name, identity in files.items():
        path = STAGE / name
        if path.stat().st_size != identity["bytes"] or sha256(path) != identity["sha256"]:
            raise RuntimeError(f"campaign stage file mismatch: {name}")
    sums = {}
    for line in sums_path.read_text().splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    retained = {
        str(path.relative_to(STAGE)) for path in STAGE.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if set(sums) != retained or any(sha256(STAGE / name) != digest for name, digest in sums.items()):
        raise RuntimeError("campaign stage SHA256SUMS mismatch")
    for path in STAGE.rglob("*"):
        expected_mode = 0o700 if path.is_dir() or path == STAGE / "bin/genie-app" else 0o600
        if stat.S_IMODE(path.stat().st_mode) != expected_mode:
            raise RuntimeError(f"campaign stage mode mismatch: {path}")

    runner_path = EXP / "tools/run_phone_campaign.sh"
    runner = runner_path.read_text()
    runner_facts = {
        "explicit_approval_guard": "CAMPAIGN_APPROVED" in runner,
        "phone_lock_full_lifecycle": "artifacts/locks/phone.lock" in runner and "trap cleanup EXIT" in runner,
        "identity_fail_closed": all(value in runner for value in ("model=SM-S918B", "soc=SM8550", "abi=arm64-v8a")),
        "local_remote_hash_checks": "local-hash-check.txt" in runner and "remote-hash-check.txt" in runner,
        "single_genie_process": runner.count("./bin/genie-app -s campaign.script") == 1,
        "per_request_timeout_monitor": "timed-out-request-ordinal.txt" in runner and "REQUEST_TIMEOUT_SECONDS=1800" in runner,
        "raw_campaign_pull_before_validation": 'adb_cmd pull "$REMOTE/campaign"' in runner,
        "scoped_cleanup": "rm -rf '$REMOTE'" in runner,
    }
    if not all(runner_facts.values()):
        raise RuntimeError(f"campaign runner proof incomplete: {runner_facts}")

    source_provenance = {
        name: {"path": str(path), "bytes": path.stat().st_size, "sha256": SOURCE_HASHES[name]}
        for name, path in SOURCES.items()
    }
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_canonical_campaign_harness_and_fresh_dialog_isolation_plan",
        "status": "canonical_campaign_harness_ready_review_and_phone_approval_required",
        "claim_boundary": (
            "A private campaign stage and runner now encode the exact protocol shape in one genie-app process. A "
            "keeper dialog retains one source-proven Registry-backed shared HTP engine while every logical request "
            "uses a newly created dialog and independent EngineState, then is freed. The plan binds one first short "
            "request plus five warm requests for each tier, exact prompt hashes, 2048 ceilings, per-request profiles "
            "and outputs, timeout monitoring, raw-first capture, and scoped cleanup. All stage hashes and permissions "
            "pass. This is host design/proof only: no campaign is authorized or executed, and no performance "
            "distribution or registry evidence exists."
        ),
        "campaign": {
            "process_count": 1, "loaded_engine_count": 1, "shared_engine": True,
            "keeper_dialog_unqueried": True,
            "request_isolation": manifest["request_isolation"],
            "request_count": len(requests), "tier_order": [item["tier"] for item in requests],
            "tier_counts": dict(Counter(item["tier"] for item in requests)),
            "first_request": requests[0], "warm_requests": requests[1:],
            "max_new_tokens": 2048, "request_timeout_seconds": 1800,
            "model_remap_between_requests": False, "accelerator_recompile_between_requests": False,
        },
        "setup_and_request_timing_plan": {
            "setup_profile": "campaign/setup-profile.json",
            "setup_boundary": "keeper-dialog creation through shared-engine readiness",
            "request_profiles": [item["profile_path"] for item in requests],
            "fresh_dialog_creation_measured_separately_per_request": True,
            "query_timing_recorded_per_request": True,
            "profile_rate_definitions_retained_as_authoritative_runtime_observations": True,
        },
        "failure_isolation": {
            "unique_output_per_request": True, "unique_profile_per_request": True,
            "per_request_timeout_monitor": True, "timeout_seconds": 1800,
            "campaign_stops_process_on_timeout": True, "automatic_retry": False,
            "post_run_validation": "Each request is classified independently; missing/partial output or profile remains error/timeout evidence and never inherits another request's metrics.",
        },
        "host_source_proof": source_facts,
        "host_source_provenance": source_provenance,
        "stage": {
            "private_root": ".local/campaign-stage", "file_count": len(files),
            "logical_bytes": sum(item["bytes"] for item in files.values()),
            "manifest_sha256": sha256(manifest_path), "sha256sums_sha256": sha256(sums_path),
            "all_files_verified": True, "permissions_verified": True,
            "context_sha256": EXPECTED_CONTEXT, "campaign_config_sha256": sha256(STAGE / "gemma4-e2b-htp-cl4096-campaign.json"),
            "campaign_script_sha256": sha256(STAGE / "campaign.script"),
        },
        "runner": {"path": "tools/run_phone_campaign.sh", "sha256": sha256(runner_path), **runner_facts},
        "requested": {
            "adb": False, "phone_lock": False, "campaign_execution": False,
            "physical_htp_execution": False, "performance_publication": False,
        },
        "authorization": {
            "campaign_authorized": False,
            "required_next_action": "Independent review followed by explicit Pi/user campaign approval and phone-priority handoff.",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
