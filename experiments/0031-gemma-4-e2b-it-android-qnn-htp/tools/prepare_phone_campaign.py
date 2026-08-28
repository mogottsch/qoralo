#!/usr/bin/env python3
"""Prepare the private one-process, shared-engine canonical campaign stage without ADB."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
BUNDLE = EXP / ".local/runtime-bundle"
STAGE = EXP / ".local/campaign-stage"
EXPECTED_CONTEXT = "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394"
CONTEXT_NAME = "models/weight_sharing_model_ar128_ar1_cl4096_scl512_1_of_1.serialized.bin"
WORKLOADS = [
    ("first-short-00", "short"),
    *[(f"warm-short-{index:02d}", "short") for index in range(1, 6)],
    *[(f"warm-medium-{index:02d}", "medium") for index in range(1, 6)],
    *[(f"warm-long-{index:02d}", "long") for index in range(1, 6)],
]
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


def link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def main() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True, mode=0o700)
    for source in sorted(path for path in BUNDLE.rglob("*") if path.is_file()):
        if source.name in {"build.stdout.log", "build.stderr.log"}:
            continue
        link_or_copy(source, STAGE / source.relative_to(BUNDLE))
    for tier, (_, expected_hash) in EXPECTED_PROMPTS.items():
        source = EXP / f"protocol/rendered/{tier}.txt"
        if sha256(source) != expected_hash:
            raise RuntimeError(f"canonical rendered {tier} identity mismatch")
        link_or_copy(source, STAGE / f"prompts/{tier}.txt")

    config = json.loads((BUNDLE / "gemma4-e2b-htp-cl4096-greedy.json").read_text())
    dialog = config["dialog"]
    dialog["max-num-tokens"] = 2048
    dialog["context"]["bos-token"] = -1
    dialog["engine"]["backend"]["QnnHtp"]["shared-engine"] = True
    campaign_config = STAGE / "gemma4-e2b-htp-cl4096-campaign.json"
    campaign_config.write_text(json.dumps(config, indent=2) + "\n")

    lines = [
        "log create campaign-log verbose campaign/genie-verbose.log",
        "profile create setup-profile",
        "dialog config create keeper-config gemma4-e2b-htp-cl4096-campaign.json",
        "dialog config bind profile keeper-config setup-profile",
        "dialog config bind log keeper-config campaign-log",
        "dialog create keeper-dialog keeper-config",
        "profile save setup-profile campaign/setup-profile.json",
    ]
    requests = []
    for ordinal, (request_id, tier) in enumerate(WORKLOADS):
        dialog_name = f"dialog-{ordinal:02d}"
        config_name = f"config-{ordinal:02d}"
        profile_name = f"profile-{ordinal:02d}"
        lines.extend([
            f"profile create {profile_name}",
            f"dialog config create {config_name} gemma4-e2b-htp-cl4096-campaign.json",
            f"dialog config bind profile {config_name} {profile_name}",
            f"dialog config bind log {config_name} campaign-log",
            f"dialog create {dialog_name} {config_name}",
            f"dialog setMaxNumTokens {dialog_name} 2048",
            f"dialog query {dialog_name} prompts/{tier}.txt campaign/outputs/{request_id}.txt",
            f"dialog getValue {dialog_name} GENIE_DIALOG_PARAM_CONTEXT_OCCUPANCY",
            f"profile save {profile_name} campaign/profiles/{request_id}.json",
            f"dialog free {dialog_name}",
            f"dialog config free {config_name}",
            f"profile free {profile_name}",
        ])
        requests.append({
            "ordinal": ordinal, "request_id": request_id, "tier": tier,
            "prompt_path": f"prompts/{tier}.txt",
            "output_path": f"campaign/outputs/{request_id}.txt",
            "profile_path": f"campaign/profiles/{request_id}.json",
            "max_new_tokens": 2048,
            "input_tokens": EXPECTED_PROMPTS[tier][0],
        })
    lines.extend([
        "dialog free keeper-dialog",
        "dialog config free keeper-config",
        "profile free setup-profile",
        "log free campaign-log",
        "exit",
    ])
    script_path = STAGE / "campaign.script"
    script_path.write_text("\n".join(lines) + "\n")

    if sha256(STAGE / CONTEXT_NAME) != EXPECTED_CONTEXT:
        raise RuntimeError("campaign stage context mismatch")
    files = {}
    for path in sorted(item for item in STAGE.rglob("*") if item.is_file()):
        if path.name in {"SHA256SUMS", "campaign-manifest.json"}:
            continue
        files[str(path.relative_to(STAGE))] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "schema_version": 1,
        "classification": "private_canonical_campaign_stage_preparation_only",
        "source_bundle_manifest_sha256": sha256(BUNDLE / "runtime-manifest.json"),
        "context_sha256": EXPECTED_CONTEXT,
        "shared_engine": True,
        "keeper_dialog_retains_engine": True,
        "request_isolation": "fresh_dialog_per_logical_request_with_independent_engine_state",
        "one_genie_process": True,
        "model_remap_between_requests": False,
        "max_new_tokens": 2048,
        "request_timeout_seconds": 1800,
        "request_count": len(requests),
        "requests": requests,
        "canonical_campaign": True,
        "campaign_authorized": False,
        "adb_used": False,
        "phone_lock_acquired": False,
        "files": files,
    }
    manifest_path = STAGE / "campaign-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with (STAGE / "SHA256SUMS").open("w") as out:
        for path in sorted(item for item in STAGE.rglob("*") if item.is_file() and item.name != "SHA256SUMS"):
            out.write(f"{sha256(path)}  {path.relative_to(STAGE)}\n")
    (STAGE / "bin/genie-app").chmod(0o700)
    for path in STAGE.rglob("*"):
        if path.is_dir():
            path.chmod(0o700)
        elif path != STAGE / "bin/genie-app":
            path.chmod(0o600)
    print(STAGE)


if __name__ == "__main__":
    main()
