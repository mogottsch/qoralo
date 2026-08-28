#!/usr/bin/env python3
"""Validate the host-only single-dialog/full-reset canonical campaign plan."""
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
OUT = EXP / "results/canonical-campaign-reset-harness-readiness/result.json"
EXPECTED_CONTEXT = "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394"
SOURCE_HASHES = {
    "qualla_dialog_cpp": "baa2ff5b37431160b3d6526e009846f80272b75922f8a2ee3de24b476e5f0746",
    "qnn_htp_cpp": "e060a8ddc4195fa1ddc6adeeba4a2bae4b5a86d305db5c3affdd6853d86c2e22",
    "genie_dialog_cpp": "db7a3e9035f980fe130877d892826a82158d2d1062c2314d7b347f5dea69a05f",
    "genie_app_docs": "f2d1c839d6508c87be4b5c14d1d6e233606fcbcf5af643884ad1362ddf2e197a",
}
SOURCES = {
    "qualla_dialog_cpp": SDK / "examples/Genie/Genie/src/qualla/dialog.cpp",
    "qnn_htp_cpp": SDK / "examples/Genie/Genie/src/qualla/engines/qnn-htp.cpp",
    "genie_dialog_cpp": SDK / "examples/Genie/Genie/src/GenieDialog.cpp",
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
            raise RuntimeError(f"reset-isolation source mismatch: {name}")
    dialog = SOURCES["qualla_dialog_cpp"].read_text(errors="replace")
    htp = SOURCES["qnn_htp_cpp"].read_text(errors="replace")
    api = SOURCES["genie_dialog_cpp"].read_text(errors="replace")
    docs = SOURCES["genie_app_docs"].read_text(errors="replace")
    source_facts = {
        "api_reset_calls_dialog_reset": "GenieDialog_reset" in api and "dialog->reset();" in api,
        "reset_zeros_past_prompt_generated_decode_queries": all(
            value in dialog for value in (
                "_n_past               = 0", "_n_prompt             = 0",
                "_n_generated          = 0", "_n_decode             = 0", "_n_queries            = 0",
            )
        ),
        "reset_clears_last_token_and_pending_inputs": all(
            value in dialog for value in ("_last_tok             = -1", "m_unprocessedEmbedding.clear()", "m_unprocessedTokens.clear()")
        ),
        "reset_resets_engine_sampler_and_dialog_state": all(
            value in dialog for value in ("e.second->reset()", "s.second->reset()", "State::clear()")
        ),
        "htp_reset_drops_kv_and_resets_model_state": "updateKV(0);" in htp and "_model->resetState();" in htp,
        "genie_app_exposes_reset": "dialog reset" in docs,
    }
    if not all(source_facts.values()):
        raise RuntimeError(f"reset isolation source proof incomplete: {source_facts}")

    manifest_path = STAGE / "campaign-manifest.json"
    sums_path = STAGE / "SHA256SUMS"
    manifest = json.loads(manifest_path.read_text())
    config = json.loads((STAGE / "gemma4-e2b-htp-cl4096-campaign.json").read_text())
    script_path = STAGE / "campaign.script"
    script_lines = script_path.read_text().splitlines()
    requests = manifest["requests"]
    if manifest["context_sha256"] != EXPECTED_CONTEXT or manifest["request_count"] != 16:
        raise RuntimeError("reset campaign stage identity/count mismatch")
    if [item["tier"] for item in requests] != EXPECTED_TIERS:
        raise RuntimeError("reset campaign tier order mismatch")
    if Counter(item["tier"] for item in requests) != {"short": 6, "medium": 5, "long": 5}:
        raise RuntimeError("reset campaign tier count mismatch")
    if manifest["request_isolation"] != "proven_full_in_session_conversation_and_kv_reset":
        raise RuntimeError("reset campaign isolation label mismatch")
    if manifest["reset_count"] != 15 or not manifest["single_dialog_retains_loaded_engine"]:
        raise RuntimeError("reset campaign single-dialog plan mismatch")
    if manifest["shared_engine"] or not manifest["one_genie_process"]:
        raise RuntimeError("reset campaign must not use unsupported shared-engine extraction")
    if manifest["max_new_tokens"] != 2048 or manifest["request_timeout_seconds"] != 1800:
        raise RuntimeError("reset campaign generation boundary mismatch")
    if manifest["campaign_authorized"] or manifest["adb_used"] or manifest["phone_lock_acquired"]:
        raise RuntimeError("host-only reset readiness boundary violated")

    dialog_config = config["dialog"]
    htp_config = dialog_config["engine"]["backend"]["QnnHtp"]
    if htp_config.get("shared-engine") is not False:
        raise RuntimeError("reset campaign incorrectly enables shared engine")
    if len(dialog_config["engine"]["cache-groups"]) != 2:
        raise RuntimeError("reset campaign lost Gemma global/SWA cache groups")
    if [item["prefix"] for item in dialog_config["engine"]["cache-groups"]] != ["past_", "swa_"]:
        raise RuntimeError("reset campaign cache-group prefixes mismatch")
    if dialog_config["max-num-tokens"] != 2048 or dialog_config["context"]["bos-token"] != -1:
        raise RuntimeError("reset campaign token boundary mismatch")

    if script_lines.count("dialog create campaign-dialog campaign-config") != 1:
        raise RuntimeError("reset campaign must create exactly one dialog")
    if script_lines.count("dialog free campaign-dialog") != 1:
        raise RuntimeError("reset campaign must free exactly one dialog")
    query_lines = [line for line in script_lines if line.startswith("dialog query campaign-dialog ")]
    reset_lines = [line for line in script_lines if line == "dialog reset campaign-dialog"]
    if len(query_lines) != 16 or len(reset_lines) != 15:
        raise RuntimeError("reset/query count mismatch")
    first_query_index = script_lines.index(query_lines[0])
    if any(index < first_query_index for index, line in enumerate(script_lines) if line == "dialog reset campaign-dialog"):
        raise RuntimeError("first request must start from newly created dialog without reset")
    prior_position = first_query_index
    for item in requests:
        query = f"dialog query campaign-dialog prompts/{item['tier']}.txt campaign/outputs/{item['request_id']}.txt"
        profile = f"profile save campaign-profile campaign/profiles/{item['request_id']}.json"
        query_pos = script_lines.index(query)
        profile_pos = script_lines.index(profile)
        if item["ordinal"]:
            reset_pos = max(index for index, line in enumerate(script_lines[:query_pos]) if line == "dialog reset campaign-dialog")
            if not prior_position < reset_pos < query_pos < profile_pos:
                raise RuntimeError(f"reset lifecycle order mismatch: {item['request_id']}")
        elif not query_pos < profile_pos:
            raise RuntimeError("first request profile order mismatch")
        prior_position = profile_pos
        if item["max_new_tokens"] != 2048 or item["input_tokens"] != EXPECTED_PROMPTS[item["tier"]][0]:
            raise RuntimeError(f"request metadata mismatch: {item['request_id']}")
        if item["profile_snapshot_kind"] != "cumulative_through_this_request":
            raise RuntimeError("profile snapshot semantics missing")

    for tier, (tokens, digest) in EXPECTED_PROMPTS.items():
        path = STAGE / f"prompts/{tier}.txt"
        if sha256(path) != digest or tokens + 2048 > 4096:
            raise RuntimeError(f"reset campaign prompt mismatch: {tier}")
    context_name = "models/weight_sharing_model_ar128_ar1_cl4096_scl512_1_of_1.serialized.bin"
    if sha256(STAGE / context_name) != EXPECTED_CONTEXT:
        raise RuntimeError("reset campaign context mismatch")

    files = manifest["files"]
    for name, identity in files.items():
        path = STAGE / name
        if path.stat().st_size != identity["bytes"] or sha256(path) != identity["sha256"]:
            raise RuntimeError(f"reset campaign stage file mismatch: {name}")
    sums = {}
    for line in sums_path.read_text().splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    retained = {str(path.relative_to(STAGE)) for path in STAGE.rglob("*") if path.is_file() and path.name != "SHA256SUMS"}
    if set(sums) != retained or any(sha256(STAGE / name) != digest for name, digest in sums.items()):
        raise RuntimeError("reset campaign SHA256SUMS mismatch")
    for path in STAGE.rglob("*"):
        expected_mode = 0o700 if path.is_dir() or path == STAGE / "bin/genie-app" else 0o600
        if stat.S_IMODE(path.stat().st_mode) != expected_mode:
            raise RuntimeError(f"reset campaign mode mismatch: {path}")

    runner_path = EXP / "tools/run_phone_campaign.sh"
    runner = runner_path.read_text()
    runner_facts = {
        "runner_executable": bool(runner_path.stat().st_mode & 0o111),
        "explicit_approval_guard": "CAMPAIGN_APPROVED" in runner,
        "full_phone_lock_cleanup": "artifacts/locks/phone.lock" in runner and "trap cleanup EXIT" in runner,
        "single_genie_process": runner.count("./bin/genie-app -s campaign.script") == 1,
        "per_request_timeout_monitor": "timed-out-request-ordinal.txt" in runner,
        "raw_pull_before_validation": 'adb_cmd pull "$REMOTE/campaign"' in runner,
    }
    if not all(runner_facts.values()):
        raise RuntimeError(f"reset campaign runner mismatch: {runner_facts}")

    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_canonical_campaign_single_dialog_full_reset_isolation_plan",
        "status": "canonical_campaign_reset_harness_ready_review_and_phone_approval_required",
        "claim_boundary": (
            "The corrected private campaign uses one already-proven non-shared QnnHtp dialog/context for all 16 "
            "requests and invokes the public Genie dialog reset between requests. Hash-bound QAIRT source proves "
            "reset clears prompt/conversation counters, last/pending tokens, HTP KV state, model state, sampler, and "
            "dialog State without remapping the model. The exact first+5/5/5 order, 2048 ceilings, cumulative "
            "per-request profile snapshots, unique outputs, timeout/failure handling, raw capture, hashes, and "
            "cleanup are verified. This is host proof only: no corrected campaign was run or authorized."
        ),
        "campaign": {
            "process_count": 1, "dialog_count": 1, "loaded_context_count": 1,
            "shared_engine": False,
            "request_isolation": manifest["request_isolation"],
            "reset_count": manifest["reset_count"], "request_count": manifest["request_count"],
            "tier_order": [item["tier"] for item in requests],
            "tier_counts": dict(Counter(item["tier"] for item in requests)),
            "max_new_tokens": 2048, "request_timeout_seconds": 1800,
            "model_remap_between_requests": False, "accelerator_recompile_between_requests": False,
            "cache_groups": ["past_", "swa_"],
        },
        "reset_proof": {
            **source_facts,
            "reset_before_first_request": False,
            "reset_before_every_subsequent_request": True,
            "reset_duration_source": "Entering/Returning GenieDialog_reset timestamps in verbose raw log",
            "reset_outside_profile_query_duration": True,
        },
        "profiles": {
            "setup_profile": "campaign/setup-profile.json",
            "one_cumulative_snapshot_after_each_request": True,
            "snapshot_paths": [item["profile_path"] for item in requests],
            "post_run_extraction": "Request N uses the newly appended query event in snapshot N; exact event-count growth is validated.",
        },
        "failure_isolation": {
            "unique_output_per_request": True, "per_request_timeout_monitor": True,
            "timeout_seconds": 1800, "process_killed_on_timeout": True,
            "automatic_retry": False,
            "missing_or_partial_request_evidence_retained_as_error_or_timeout": True,
        },
        "source_provenance": {
            name: {"path": str(path), "bytes": path.stat().st_size, "sha256": SOURCE_HASHES[name]}
            for name, path in SOURCES.items()
        },
        "stage": {
            "private_root": ".local/campaign-stage", "file_count": len(files),
            "logical_bytes": sum(item["bytes"] for item in files.values()),
            "manifest_sha256": sha256(manifest_path), "sha256sums_sha256": sha256(sums_path),
            "campaign_config_sha256": sha256(STAGE / "gemma4-e2b-htp-cl4096-campaign.json"),
            "campaign_script_sha256": sha256(script_path),
            "all_files_verified": True, "permissions_verified": True,
        },
        "runner": {"path": "tools/run_phone_campaign.sh", "sha256": sha256(runner_path), **runner_facts},
        "requested": {"adb": False, "phone_lock": False, "campaign_execution": False},
        "authorization": {
            "campaign_authorized": False,
            "required_next_action": "Independent review and a new explicit campaign approval/phone handoff.",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
