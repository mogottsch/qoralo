#!/usr/bin/env python3
"""Shared fail-closed provenance and attempt-plan helpers for Inflect-Nano-v1."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
PLAN = json.loads((HERE / "attempt-plan.json").read_text(encoding="utf-8"))
ARTIFACT_ROOT = EXPERIMENT / "artifacts" / "inflect-nano-v1"
SNAPSHOT = ARTIFACT_ROOT / "snapshot"
TOKENIZER = ARTIFACT_ROOT / "bert-base-uncased"
NLTK_DATA = ARTIFACT_ROOT / "nltk_data"
TRANSCRIPT = EXPERIMENT / "protocol" / "transcript.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_snapshot(snapshot: Path = SNAPSHOT) -> dict[str, dict[str, object]]:
    verified: dict[str, dict[str, object]] = {}
    for relative, expected in PINS["artifacts"]["files"].items():
        path = snapshot / relative
        if not path.is_file():
            raise RuntimeError(f"pinned Inflect-Nano-v1 artifact is absent: {relative}")
        actual = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        if actual != expected:
            raise RuntimeError(f"pinned Inflect-Nano-v1 artifact drift: {relative}")
        verified[relative] = actual
    return verified


def verify_frontend_assets() -> None:
    for root, files in (
        (TOKENIZER, PINS["frontend_assets"]["bert_tokenizer"]["files"]),
        (NLTK_DATA, PINS["frontend_assets"]["nltk_data"]["files"]),
    ):
        for relative, expected in files.items():
            path = root / relative
            actual = {"bytes": path.stat().st_size, "sha256": sha256(path)} if path.is_file() else None
            expected_shape = {"bytes": expected["bytes"], "sha256": expected["sha256"]}
            if actual != expected_shape:
                raise RuntimeError(f"pinned frontend asset drift: {relative}")


def install_local_tokenizer_resolution() -> None:
    """Keep upstream's bert-base-uncased choice but force its pinned local object."""
    verify_frontend_assets()
    from transformers import AutoTokenizer
    original = AutoTokenizer.from_pretrained

    def pinned(name: str, *args: object, **kwargs: object):
        if name != PINS["frontend_assets"]["bert_tokenizer"]["upstream_alias"]:
            raise RuntimeError(f"unexpected frontend model request: {name}")
        return original(str(TOKENIZER), local_files_only=True)

    AutoTokenizer.from_pretrained = pinned


def frozen_transcript() -> str:
    data = TRANSCRIPT.read_bytes()
    if hashlib.sha256(data).hexdigest() != PINS["protocol"]["transcript_sha256"]:
        raise RuntimeError("protocol-v2 transcript drift")
    return data.decode("utf-8")


def attempt_value(index: int) -> float:
    values = PLAN["values"]
    if index < 0 or index >= len(values):
        raise ValueError(f"attempt index must be between 0 and {len(values) - 1}")
    return float(values[index])


def attempt_directory(root: Path, index: int, *, repeat: bool = False) -> Path:
    value = attempt_value(index)
    suffix = "-repeat" if repeat else ""
    return root / f"attempt-{index:02d}-length-scale-{value:.2f}{suffix}"
