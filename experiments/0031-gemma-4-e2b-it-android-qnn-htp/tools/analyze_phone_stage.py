#!/usr/bin/env python3
"""Validate the private cache-corrected phone stage without using ADB."""
from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
BUNDLE = EXP / ".local/runtime-bundle"
STAGE = EXP / ".local/phone-stage"
OUT = EXP / "results/position-id-corrected-phone-stage/result.json"
EXPECTED_CONTEXT = "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394"
EXPECTED_SHORT = "b286f8dda746e8056836a2e71049df866527bee51e368363dd80cfbe27e60e7a"
CONTEXT_NAME = "models/weight_sharing_model_ar128_ar1_cl4096_scl512_1_of_1.serialized.bin"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest_path = STAGE / "stage-manifest.json"
    sums_path = STAGE / "SHA256SUMS"
    manifest = json.loads(manifest_path.read_text())
    if manifest["classification"] != "private_phone_stage_preparation_only":
        raise RuntimeError("unexpected stage classification")
    if manifest["corrected_context_sha256"] != EXPECTED_CONTEXT:
        raise RuntimeError("stage is not bound to corrected context")
    if manifest["canonical_short_rendered_sha256"] != EXPECTED_SHORT:
        raise RuntimeError("stage canonical short prompt mismatch")
    if manifest["viability_output_ceiling_tokens"] != 16 or manifest["canonical_campaign"]:
        raise RuntimeError("stage is not the bounded 16-token gate")
    if manifest["adb_used"] or manifest["phone_lock_acquired"]:
        raise RuntimeError("host-only stage preparation boundary violated")
    if not manifest["stage_completeness_check_passed"]:
        raise RuntimeError("runtime stage completeness was not proven")

    files = manifest["files"]
    if files[CONTEXT_NAME]["sha256"] != EXPECTED_CONTEXT:
        raise RuntimeError("staged context identity mismatch")
    required = manifest["required_runtime_files"]
    if len(required) != 8 or any(name not in files for name in required):
        raise RuntimeError("required QnnHtp runtime files missing")
    for name, identity in files.items():
        path = STAGE / name
        if path.stat().st_size != identity["bytes"] or sha256(path) != identity["sha256"]:
            raise RuntimeError(f"stage file mismatch: {name}")

    sums = {}
    for line in sums_path.read_text().splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    retained = {
        str(path.relative_to(STAGE))
        for path in STAGE.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if set(sums) != retained:
        raise RuntimeError("stage SHA256SUMS coverage mismatch")
    for name, digest in sums.items():
        if sha256(STAGE / name) != digest:
            raise RuntimeError(f"stage SHA256SUMS mismatch: {name}")

    if stat.S_IMODE((STAGE / "bin/genie-app").stat().st_mode) != 0o700:
        raise RuntimeError("genie-app mode mismatch")
    for path in STAGE.rglob("*"):
        expected = 0o700 if path.is_dir() else (0o700 if path == STAGE / "bin/genie-app" else 0o600)
        if stat.S_IMODE(path.stat().st_mode) != expected:
            raise RuntimeError(f"stage mode mismatch: {path}")

    bundle_manifest_hash = sha256(BUNDLE / "runtime-manifest.json")
    if manifest["source_bundle_manifest_sha256"] != bundle_manifest_hash:
        raise RuntimeError("stage source bundle mismatch")
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_position_id_corrected_phone_stage_preparation",
        "status": "position_id_binding_corrected_stage_ready_phone_handoff_required",
        "claim_boundary": (
            "The private stage is complete, permission-hardened, and hash-bound to the cache- and positional-name-corrected context, "
            "exact runtime dependencies, canonical short prompt, and 16-token gate. Preparation and validation "
            "used no ADB and did not acquire phone.lock. This is not phone identity, context loading, physical HTP "
            "execution, no-fallback, output, or performance evidence."
        ),
        "stage": {
            "private_root": ".local/phone-stage",
            "file_count": len(files),
            "logical_bytes": sum(item["bytes"] for item in files.values()),
            "stage_manifest_bytes": manifest_path.stat().st_size,
            "stage_manifest_sha256": sha256(manifest_path),
            "sha256sums_bytes": sums_path.stat().st_size,
            "sha256sums_sha256": sha256(sums_path),
            "all_manifest_files_verified": True,
            "sha256sums_complete_and_verified": True,
            "permissions_verified": True,
            "source_bundle_manifest_sha256": bundle_manifest_hash,
            "corrected_context_sha256": EXPECTED_CONTEXT,
            "position_id_binding_corrected": True,
            "canonical_short_rendered_sha256": EXPECTED_SHORT,
            "viability_output_ceiling_tokens": 16,
            "canonical_campaign": False,
            "required_runtime_files": required,
            "required_runtime_completeness": True,
        },
        "authorization_boundary": {
            "expected_serial": "R5CW81PR8SY",
            "adb_used": False,
            "phone_lock_acquired": False,
            "phone_identity_verified": False,
            "phone_run_authorized_now": False,
        },
        "next_gate": (
            "Wait for R5CW81PR8SY to reconnect as device and for Pi to verify identity and explicitly transfer "
            "phone priority; then run exactly one locked 16-token gate, with no retry or campaign."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
