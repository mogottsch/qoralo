#!/usr/bin/env python3
"""Build and validate the private listening page without staging audio."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
RESULTS = EXP / "results"
PROTOCOL_PATH = EXP / "protocol/preview-protocol-v2.json"
TRANSCRIPT_PATH = EXP / "protocol/transcript.txt"
SCHEMA_PATH = HERE / "bakeoff-manifest.schema.json"
MANIFEST_PATH = HERE / "bakeoff-manifest.json"
REPORT_PATH = REPO / "docs/candidate-decision-report.json"
REPORT_SCHEMA_PATH = REPO / "docs/candidate-decision-report.schema.json"
CANDIDATES = {
    "realtime": ("Candidate A", "a", "VibeVoice Realtime 0.5B", "realtime-preview.json"),
    "pocket": ("Candidate B", "b", "Pocket TTS 100M", "pocket-preview.json"),
    "kokoro": ("Candidate C", "c", "Kokoro 82M", "kokoro-preview.json"),
    "supertonic-3": ("Candidate D", "d", "Supertone/supertonic-3", "supertonic-3-preview.json"),
    "inflect-nano-v1": ("Candidate E", "e", "owensong/Inflect-Nano-v1", "inflect-nano-v1-preview.json"),
    "kitten-tts-mini-0.8": ("Candidate F", "f", "KittenML/kitten-tts-mini-0.8", "kitten-tts-mini-0.8-preview.json"),
}
LABELS = {model: values[0] for model, values in CANDIDATES.items()}
SLUGS = {model: values[1] for model, values in CANDIDATES.items()}
DISPLAY_NAMES = {model: values[2] for model, values in CANDIDATES.items()}
RESULT_FILES = {model: RESULTS / values[3] for model, values in CANDIDATES.items()}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(relative: str) -> Path:
    return EXP / relative


def seed_record(result: dict) -> dict:
    determinism = result["provenance"].get("determinism", {})
    value = result["provenance"].get("seed", determinism.get("global_torch_seed", determinism.get("torch_manual_seed", 0)))
    return {
        "value": value,
        "support": result["provenance"].get("seed_support", "Seeded immediately before generation; see determinism evidence."),
        "determinism": determinism,
    }


def artifact(result: dict, kind: str, model: str) -> dict | None:
    record = result.get(kind)
    if record is None:
        return None
    slug = SLUGS[model]
    if kind == "raw":
        has_carrier = "derivation_carrier_path" in record
        source = record.get("derivation_carrier_path", record["artifact_path"])
        source_hash = record.get("derivation_carrier_sha256", record["sha256"])
        fmt = "WAV PCM_F32LE" if has_carrier else record["output_format"]
    else:
        source, source_hash = record["artifact_path"], record["sha256"]
        fmt = record["sample_format"]
    source_path = repo_path(source)
    if not source_path.is_file():
        raise ValueError(f"missing audio artifact: {source}")
    if sha256(source_path) != source_hash:
        raise ValueError(f"artifact hash mismatch: {source}")
    return {
        "source_path": source,
        "published_url": f"audio/candidate-{slug}-{kind}.wav",
        "sha256": source_hash,
        "duration_seconds": record["duration_seconds"],
        "sample_rate_hz": record["sample_rate_hz"],
        "channels": record["channels"],
        "format": fmt,
    }


def derivation(result: dict) -> tuple[dict, list[str]]:
    normalized = result.get("normalized")
    if not normalized:
        return {"applied": False, "reason": result.get("blocker")}, []
    metadata = load(repo_path(normalized["derivation_metadata_path"]))
    steps = [
        "decode native audio to float64",
        "arithmetic-mean mono conversion when needed",
        "deterministic polyphase resampling to 24000 Hz when needed",
        f"zero-crossing exact-window trim [{metadata['trim_start']}, {metadata['trim_end']})",
        "240-sample sine-squared boundary fades",
        f"gain {metadata['gain_db']:.12g} dB toward -20 LUFS with -1 dBFS ceiling",
        "deterministic TPDF dither using NumPy PCG64 seed 0",
        "quantize to mono PCM_S16LE",
    ]
    return {"applied": True, "metadata_path": normalized["derivation_metadata_path"], "metadata": metadata, "steps": steps}, result["provenance"].get("derivation_command", result["command"])


def build_manifest(result_files: dict[str, Path] | None = None) -> dict:
    protocol = load(PROTOCOL_PATH)
    transcript = TRANSCRIPT_PATH.read_text(encoding="utf-8")
    transcript_hash = hashlib.sha256(transcript.encode()).hexdigest()
    if transcript_hash != protocol["transcript_sha256"]:
        raise ValueError("transcript does not match protocol")
    candidates = []
    fingerprints = set()
    paths = result_files or RESULT_FILES
    missing = [str(paths[model]) for model in CANDIDATES if not paths[model].is_file()]
    if missing:
        raise ValueError(f"six-candidate publication evidence is incomplete: {missing}")
    for model in CANDIDATES:
        result_path = paths[model]
        result = load(result_path)
        fingerprints.add(result["protocol"]["protocol_fingerprint"])
        transforms, derivation_command = derivation(result)
        raw = result["raw"]
        candidates.append({
            "label": LABELS[model],
            "model": model,
            "display_name": DISPLAY_NAMES[model],
            "status": result["status"],
            "seed": seed_record(result),
            "voice": result["voice"],
            "revisions": {"source": result["provenance"]["source_revision"], "model": result["provenance"]["model_revision"]},
            "commands": {"generation": result["command"], "derivation": derivation_command},
            "native": {
                "format": raw["output_format"], "sample_rate_hz": raw["sample_rate_hz"], "channels": raw["channels"],
                "sha256": raw["sha256"], "duration_seconds": raw["duration_seconds"],
                "sample_count": raw.get("sample_count"), "byte_count": raw.get("byte_count", raw.get("bytes")),
            },
            "raw": artifact(result, "raw", model),
            "normalized": artifact(result, "normalized", model),
            "transformations": transforms,
            "forbidden_transformations_used": result["forbidden_transformations_used"],
            "blocker": result.get("blocker"),
            "result_path": str(result_path.relative_to(REPO)),
        })
    if len(fingerprints) != 1:
        raise ValueError("preview protocol fingerprints disagree")
    return {
        "schema_version": 1,
        "transcript": {"text": transcript, "sha256": transcript_hash, "word_count": len(transcript.split())},
        "protocol": {
            "id": protocol["protocol_id"], "version": protocol["protocol_version"],
            "fingerprint": fingerprints.pop(), "manifest_path": str(PROTOCOL_PATH.relative_to(REPO)),
            "transformations": protocol["audio"],
        },
        "anonymization": {"page_labels": list(LABELS.values()), "identity_disclosure": "explicit_reveal_only"},
        "candidates": candidates,
    }


def validate_manifest(manifest: dict) -> None:
    try:
        import jsonschema
    except ImportError as error:
        raise SystemExit("install requirements-protocol.txt (jsonschema is required)") from error
    jsonschema.Draft202012Validator(load(SCHEMA_PATH)).validate(manifest)
    if hashlib.sha256(manifest["transcript"]["text"].encode()).hexdigest() != manifest["transcript"]["sha256"]:
        raise ValueError("manifest transcript hash is inconsistent")
    if {c["model"] for c in manifest["candidates"]} != set(LABELS):
        raise ValueError("manifest must contain each model exactly once")
    for candidate in manifest["candidates"]:
        result = load(REPO / candidate["result_path"])
        if result["protocol"]["transcript_sha256"] != manifest["transcript"]["sha256"]:
            raise ValueError(f"{candidate['model']}: transcript hash mismatch")
        if result["protocol"]["protocol_fingerprint"] != manifest["protocol"]["fingerprint"]:
            raise ValueError(f"{candidate['model']}: protocol fingerprint mismatch")
        if result["raw"]["sha256"] != candidate["native"]["sha256"]:
            raise ValueError(f"{candidate['model']}: native hash mismatch")
        if candidate["status"] == "accepted" and candidate["normalized"] is None:
            raise ValueError(f"{candidate['model']}: accepted result lacks normalized audio")
        if candidate["status"] == "blocked" and (candidate["normalized"] is not None or not candidate["blocker"]):
            raise ValueError(f"{candidate['model']}: blocked result is inconsistent")


def decision_report() -> dict:
    report = load(REPORT_PATH)
    try:
        import jsonschema
    except ImportError as error:
        raise SystemExit("install requirements-protocol.txt (jsonschema is required)") from error
    jsonschema.Draft202012Validator(load(REPORT_SCHEMA_PATH)).validate(report)
    listening_status = report["subjective_listening"]["status"]
    if listening_status not in {"pending_user_review", "recorded_user_review"}:
        raise ValueError("unsupported subjective listening status")
    if listening_status == "recorded_user_review":
        review_path = REPO / report["subjective_listening"]["evidence"]
        if not review_path.is_file():
            raise ValueError("recorded user listening evidence is missing")
    if len(report["candidate_decisions"]) != 5:
        raise ValueError("exactly five user decisions are permitted")
    evidence_records = list(report["host_quality_evidence"])
    evidence_records.append(report["android_measurements"]["vibevoice_1_5b_four_call"])
    evidence_records.append(report["estimates"]["realtime_0_5b"])
    evidence_records.append(report["historical_evidence"])
    evidence_records.append(report["historical_evidence"]["prefix_supplement"])
    for record in evidence_records:
        path = REPO / record["evidence"]
        if not path.is_file():
            raise ValueError(f"decision evidence missing: {record['evidence']}")
        if sha256(path) != record["evidence_sha256"]:
            raise ValueError(f"decision evidence hash mismatch: {record['evidence']}")
    if report["historical_evidence"]["completed_steps"] != 39 or report["historical_evidence"]["total_steps"] != 39:
        raise ValueError("historical 39/39 evidence must remain preserved")
    return report


def crew_snapshot() -> dict:
    task_dir = REPO / ".pi/messenger/crew/tasks"
    task_paths = sorted(task_dir.glob("task-*.json"), key=lambda path: int(path.stem.split("-")[1]))
    tasks = []
    for path in task_paths:
        task = load(path)
        tasks.append({key: task.get(key) for key in ("id", "title", "status", "depends_on", "attempt_count", "started_at", "completed_at", "blocked_reason", "summary")})
    ids = {task["id"] for task in tasks}
    if not tasks or any(set(task["depends_on"] or []) - ids for task in tasks):
        raise ValueError("Crew DAG is incomplete or has dangling dependencies")
    return {"schema_version": 1, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tasks": tasks}


def build(output: Path, manifest: dict | None = None) -> None:
    write_canonical_manifest = manifest is None
    manifest = manifest or build_manifest()
    validate_manifest(manifest)
    if write_canonical_manifest:
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    audio = output / "audio"
    audio.mkdir(exist_ok=True)
    for candidate in manifest["candidates"]:
        for kind in ("raw", "normalized"):
            record = candidate[kind]
            if record:
                shutil.copyfile(repo_path(record["source_path"]), output / record["published_url"])
    snapshot = crew_snapshot()
    report = decision_report()
    (output / "bakeoff-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (output / "crew-tasks.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    (output / "candidate-decision-report.json").write_text(json.dumps(report, indent=2) + "\n")
    template = (HERE / "index.template.html").read_text()
    # This is the complete initial-page data contract. In particular, do not add
    # model keys, names, provenance, report summaries, or Crew task titles here.
    page_data = {
        "transcript": manifest["transcript"],
        "protocol": {"version": manifest["protocol"]["version"]},
        "candidates": [{
            "label": candidate["label"], "slug": SLUGS[candidate["model"]], "status": candidate["status"],
            "raw_url": candidate["raw"]["published_url"],
            "normalized_url": candidate["normalized"]["published_url"] if candidate["normalized"] else None,
        } for candidate in manifest["candidates"]],
    }
    embedded_page_data = json.dumps(page_data, separators=(",", ":")).replace("</", "<\\/")
    (output / "index.html").write_text(template.replace("__BAKEOFF_JSON__", embedded_page_data))
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=REPO, text=True, capture_output=True, check=True).stdout.splitlines()
    forbidden = [path for path in staged if path.endswith((".wav", ".flac", ".mp3", ".m4a")) or "/artifacts/" in path]
    if forbidden:
        raise ValueError(f"staged-path audit failed: {forbidden}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=EXP / "artifacts/publication-build")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        validate_manifest(build_manifest())
    else:
        build(args.output.resolve())


if __name__ == "__main__":
    main()
