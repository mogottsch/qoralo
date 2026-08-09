#!/usr/bin/env python3
"""Fail-closed shared protocol and result provenance checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "protocol" / "preview-protocol-v2.json"
PREVIEW_REVISION_RESET_TASKS = ("task-6", "task-7", "task-8", "task-16", "task-17", "task-18")


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_protocol(path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    path = Path(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    transcript = path.parent.joinpath(manifest["transcript_path"]).read_bytes()
    actual = hashlib.sha256(transcript).hexdigest()
    if actual != manifest["transcript_sha256"]:
        raise ValueError(f"transcript SHA-256 drift: {actual}")
    text = transcript.decode(manifest["transcript_encoding"])
    if len(text.split()) != manifest["transcript_word_count"] or not 35 <= len(text.split()) <= 45:
        raise ValueError("transcript word count drift")
    if transcript.endswith(b"\n") != manifest["transcript_trailing_newline"]:
        raise ValueError("transcript trailing-newline drift")
    return manifest


def protocol_fingerprint(manifest: dict[str, Any]) -> str:
    """Hash every normative manifest field; $schema is non-normative."""
    return canonical_sha256({k: v for k, v in manifest.items() if k != "$schema"})


def protocol_reference(path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    p = load_protocol(path)
    return {"protocol_id": p["protocol_id"], "protocol_version": p["protocol_version"], "transcript_sha256": p["transcript_sha256"], "protocol_fingerprint": protocol_fingerprint(p)}


def validate_successor(previous: dict[str, Any], candidate: dict[str, Any]) -> None:
    if previous["protocol_id"] != candidate["protocol_id"]:
        raise ValueError("protocol_id cannot change within this protocol line")
    old_version, new_version = previous["protocol_version"], candidate["protocol_version"]
    transcript_changed = previous["transcript_sha256"] != candidate["transcript_sha256"]
    normative_changed = protocol_fingerprint(previous) != protocol_fingerprint(candidate)
    if transcript_changed and new_version <= old_version:
        raise ValueError("a transcript byte or punctuation change requires a higher protocol version")
    if normative_changed and new_version <= old_version:
        raise ValueError("any normative protocol change requires a higher protocol version")
    if new_version < old_version:
        raise ValueError("protocol version cannot decrease")


def revision_invalidation_tasks() -> tuple[str, ...]:
    """Frozen parent cascade; intentionally excludes the unrelated task-9 capture."""
    return PREVIEW_REVISION_RESET_TASKS


def validate_result_protocol(result: dict[str, Any], path: str | Path = DEFAULT_MANIFEST) -> None:
    expected = protocol_reference(path)
    actual = result.get("protocol")
    if actual != expected:
        raise ValueError(f"preview protocol mismatch; prior preview is invalid: got {actual!r}, expected {expected!r}")
