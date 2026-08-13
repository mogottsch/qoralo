#!/usr/bin/env python3
"""Generate and validate the shared host-only deployment integration evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

EXPERIMENT = Path(__file__).resolve().parents[1]
TRANSCRIPT_HASH = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
VARIANTS = {
    "pocket": "sherpa-onnx-pocket-tts-int8-2026-01-26",
    "kokoro": "kokoro-multi-lang-v1_0",
    "supertonic_3": "sherpa-onnx-supertonic-3-tts-int8-2026-05-11",
}
DESCRIPTORS = {
    "pocket": EXPERIMENT / "models/pocket/android-descriptor.json",
    "kokoro": EXPERIMENT / "models/kokoro/benchmark-descriptor.json",
    "supertonic_3": EXPERIMENT / "models/supertonic-3/android-descriptor.json",
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object required: {path}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and path.as_posix() == value and not ({".", ".."} & set(path.parts))


def inventory_rows(candidate: str) -> list[dict[str, Any]]:
    if candidate == "pocket":
        rows = load(EXPERIMENT / "models/pocket/model.json")["deployed_files"]
    elif candidate == "kokoro":
        rows = load(EXPERIMENT / "models/kokoro/deployed-inventory.json")["files"]
    else:
        rows = load(EXPERIMENT / "models/supertonic-3/inventory.json")["files"]
    normalized = [{"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]} for row in rows]
    if [row["path"] for row in normalized] != sorted(row["path"] for row in normalized):
        raise ValueError(f"{candidate} inventory is not sorted")
    if len({row["path"] for row in normalized}) != len(normalized):
        raise ValueError(f"{candidate} inventory contains duplicate paths")
    for row in normalized:
        if not safe_path(row["path"]) or not isinstance(row["bytes"], int) or row["bytes"] < 0 or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError(f"invalid {candidate} inventory row: {row!r}")
    return normalized


def make_pocket_descriptor() -> dict[str, Any]:
    model = load(EXPERIMENT / "models/pocket/model.json")
    config_rel = "models/pocket/sherpa-config.json"
    files = {"protocol/transcript.txt": TRANSCRIPT_HASH, config_rel: digest(EXPERIMENT / config_rel)}
    files.update({f"models/pocket/{row['path']}": row["sha256"] for row in inventory_rows("pocket")})
    voice = model["voice"]
    return {
        "schema_version": 1,
        "candidate": "pocket",
        "deployment_variant": VARIANTS["pocket"],
        "archive_sha256": model["archive"]["sha256"],
        "transcript": "protocol/transcript.txt",
        "transcript_sha256": TRANSCRIPT_HASH,
        "sherpa_config_path": config_rel,
        "provider": "cpu",
        "num_threads": 1,
        "warm_runs": 3,
        "speaker_id": 0,
        "language": "en",
        "storage": "app_specific_external_files",
        "requested_voice": voice["requested_voice"],
        "actual_reference": f"models/pocket/{voice['actual_reference']}",
        "actual_reference_sha256": voice["actual_reference_sha256"],
        "voice_match": voice["voice_match"],
        "files": dict(sorted(files.items())),
    }


def validate_descriptor(candidate: str, value: dict[str, Any]) -> None:
    required = {"schema_version", "candidate", "deployment_variant", "transcript", "transcript_sha256", "sherpa_config_path", "provider", "num_threads", "warm_runs", "speaker_id", "language", "storage", "files"}
    if not required <= value.keys():
        raise ValueError(f"{candidate} descriptor missing {sorted(required - value.keys())}")
    if value["schema_version"] != 1 or value["candidate"] != candidate or value["deployment_variant"] != VARIANTS[candidate]:
        raise ValueError(f"{candidate} identity drift")
    if value["provider"] != "cpu" or value["num_threads"] != 1 or value["warm_runs"] < 3:
        raise ValueError(f"{candidate} canonical runtime drift")
    if value["storage"] != "app_specific_external_files" or not str(value["language"]).lower().startswith("en"):
        raise ValueError(f"{candidate} storage/language drift")
    if value["transcript"] != "protocol/transcript.txt" or value["transcript_sha256"] != TRANSCRIPT_HASH:
        raise ValueError(f"{candidate} transcript drift")
    files = value["files"]
    if not isinstance(files, dict) or files.get(value["transcript"]) != TRANSCRIPT_HASH or files.get(value["sherpa_config_path"]) != digest(EXPERIMENT / value["sherpa_config_path"]):
        raise ValueError(f"{candidate} config/transcript is not pinned")
    prefix = "supertonic-3" if candidate == "supertonic_3" else candidate
    expected = {f"models/{prefix}/{row['path']}": row["sha256"] for row in inventory_rows(candidate)}
    for path, expected_hash in expected.items():
        if files.get(path) != expected_hash:
            raise ValueError(f"{candidate} deployed pin missing/drifted: {path}")
    extra = set(files) - set(expected) - {value["transcript"], value["sherpa_config_path"]}
    if extra:
        raise ValueError(f"{candidate} unaccounted deployed pins: {sorted(extra)}")
    for path, sha256 in files.items():
        if not safe_path(path) or not re.fullmatch(r"[0-9a-f]{64}", str(sha256)):
            raise ValueError(f"{candidate} unsafe path or hash: {path}")
    if candidate == "pocket" and (value.get("requested_voice") != "Alba" or value.get("voice_match") is not False or not value.get("actual_reference", "").endswith("/bria.wav")):
        raise ValueError("Pocket voice mismatch must remain explicit")
    if candidate == "kokoro" and (value["speaker_id"] != 3 or value.get("speaker") != "af_heart"):
        raise ValueError("Kokoro SID provenance drift")
    if candidate == "supertonic_3" and (value["speaker_id"] != 5 or value.get("voice") != "M1"):
        raise ValueError("Supertonic M1 provenance drift")


def generate() -> tuple[dict[str, Any], dict[str, Any]]:
    pocket = make_pocket_descriptor()
    DESCRIPTORS["pocket"].write_text(json.dumps(pocket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Add the common harness field while retaining the model-local provenance spelling.
    kokoro = load(DESCRIPTORS["kokoro"])
    kokoro["model_storage"] = "app_specific_external_files"
    kokoro["storage"] = "app_specific_external_files"
    DESCRIPTORS["kokoro"].write_text(json.dumps(kokoro, indent=2) + "\n", encoding="utf-8")

    models = []
    for candidate, path in DESCRIPTORS.items():
        descriptor = load(path)
        validate_descriptor(candidate, descriptor)
        rows = inventory_rows(candidate)
        deployed = sum(row["bytes"] for row in rows)
        models.append({
            "candidate": candidate,
            "deployment_variant": VARIANTS[candidate],
            "descriptor": path.relative_to(EXPERIMENT).as_posix(),
            "descriptor_sha256": digest(path),
            "inventory_file_count": len(rows),
            "deployed_bytes": deployed,
            "required_free_bytes": deployed * 2,
        })
    total = sum(model["deployed_bytes"] for model in models)
    aggregate = {
        "schema_version": 1,
        "storage_formula": "required_free_bytes = 2 * verified_deployed_bytes; APK bytes are added by the runner before applying the same 2x safety allowance",
        "models": models,
        "aggregate_deployed_bytes": total,
        "aggregate_required_free_bytes": total * 2,
    }
    readiness = {
        "schema_version": 1,
        "scope": "host_only_no_android_performance_claim",
        "android_device_measurement": "pending",
        "models": [
            {"candidate": "pocket", "status": "ready_with_declared_voice_mismatch", "voice_provenance": "Alba absent; pinned packaged Bria fallback", "blocked": False},
            {"candidate": "kokoro", "status": "ready", "voice_provenance": "pinned v1.0 metadata proves SID 3 is af_heart", "blocked": False},
            {"candidate": "supertonic_3", "status": "ready", "voice_provenance": "pinned deterministic conversion proof maps SID 5 to M1", "blocked": False},
        ],
        "all_unblocked_descriptors_conform": True,
    }
    return aggregate, readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated committed evidence differs")
    args = parser.parse_args()
    aggregate_path = EXPERIMENT / "integration/aggregate-inventory.json"
    readiness_path = EXPERIMENT / "integration/host-readiness.json"
    old = (aggregate_path.read_bytes() if aggregate_path.exists() else None, readiness_path.read_bytes() if readiness_path.exists() else None)
    aggregate, readiness = generate()
    outputs = (json.dumps(aggregate, indent=2, sort_keys=True) + "\n", json.dumps(readiness, indent=2, sort_keys=True) + "\n")
    if args.check:
        expected = tuple(x.encode() for x in outputs)
        if old != expected:
            raise SystemExit("generated integration evidence is stale; run tools/integration_gate.py")
    else:
        aggregate_path.parent.mkdir(parents=True, exist_ok=True)
        aggregate_path.write_text(outputs[0], encoding="utf-8")
        readiness_path.write_text(outputs[1], encoding="utf-8")
    print(f"validated {len(DESCRIPTORS)} descriptors; aggregate deployed bytes={aggregate['aggregate_deployed_bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
