#!/usr/bin/env python3
"""Deterministic shared Kokoro v1.0 frontend and artifact helpers.

The frontend is a small, fail-closed transcription of sherpa-onnx v1.13.5's
KokoroMultiLangLexicon lexicon branch for the experiment's ASCII English
contract. It resolves real text against the pinned Misaki-derived lexicon at
runtime; it never loads frozen token IDs or a neural intermediate fixture.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PUNCTUATION = frozenset(";:,.!?—…\"()“”")
SENTENCE_END = frozenset(".!?;")
ASCII_PARTS = re.compile(r"[A-Za-z0-9']+|[^\sA-Za-z0-9']")


class ContractError(RuntimeError):
    """Raised when an input drifts outside the frozen deployment contract."""


@dataclass(frozen=True)
class FrontendResult:
    normalized_text: str
    parts: tuple[str, ...]
    segments: tuple[tuple[int, ...], ...]
    style_indices: tuple[int, ...]
    lexicon_words: tuple[str, ...]
    punctuation: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_tokens(path: Path) -> tuple[dict[str, int], dict[int, str]]:
    token_to_id: dict[str, int] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw:
            raise ContractError(f"empty token line {number}")
        fields = raw.strip().split()
        if len(fields) == 1:
            token, value = " ", fields[0]
        elif len(fields) == 2:
            token, value = fields
        else:
            raise ContractError(f"malformed token line {number}: {raw!r}")
        index = int(value)
        if token in token_to_id:
            raise ContractError(f"duplicate token {token!r}")
        token_to_id[token] = index
    id_to_token = {value: key for key, value in token_to_id.items()}
    if len(id_to_token) != len(token_to_id):
        raise ContractError("token IDs are not unique")
    if token_to_id.get(" ") != 16:
        raise ContractError("space token drift")
    return token_to_id, id_to_token


def load_lexicon(path: Path, token_to_id: dict[str, int]) -> dict[str, tuple[int, ...]]:
    lexicon: dict[str, tuple[int, ...]] = {}
    with path.open(encoding="utf-8") as stream:
        for number, raw in enumerate(stream, 1):
            fields = raw.strip().split()
            if len(fields) < 2:
                raise ContractError(f"malformed lexicon line {number}")
            word, phones = fields[0].lower(), fields[1:]
            if word in lexicon:  # sherpa-onnx keeps the first pronunciation.
                continue
            try:
                ids = tuple(token_to_id[phone] for phone in phones)
            except KeyError as exc:
                raise ContractError(
                    f"unknown phone {exc.args[0]!r} at lexicon line {number}"
                ) from exc
            lexicon[word] = ids
    return lexicon


def frontend(text: str, tokens_path: Path, lexicon_path: Path) -> FrontendResult:
    """Convert text to padded model token segments via the real pinned lexicon.

    This mirrors the relevant v1.13.5 C++ behavior: ASCII words are lowercased,
    each lexicon pronunciation is followed by a space token, punctuation is a
    separate token, and .!?; terminates a segment. OOV fallback is deliberately
    fail-closed because the frozen transcript is required to have full coverage.
    """
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized or normalized != text:
        raise ContractError("text must already be non-empty and whitespace-normalized")
    token_to_id, _ = load_tokens(tokens_path)
    lexicon = load_lexicon(lexicon_path, token_to_id)
    parts = tuple(ASCII_PARTS.findall(normalized))
    if "".join(parts).replace(" ", "") != normalized.replace(" ", ""):
        raise ContractError("frontend lexer did not cover the complete text")

    segments: list[tuple[int, ...]] = []
    current: list[int] = [0]
    words: list[str] = []
    punctuation: list[str] = []
    for raw in parts:
        part = raw.lower()
        if part in PUNCTUATION:
            punctuation.append(part)
            try:
                current.append(token_to_id[part])
            except KeyError as exc:
                raise ContractError(f"punctuation token unavailable: {part!r}") from exc
            if part in SENTENCE_END:
                current.append(0)
                segments.append(tuple(current))
                current = [0]
            continue
        if not re.fullmatch(r"[a-z0-9']+", part):
            raise ContractError(f"unsupported frontend part: {raw!r}")
        if part not in lexicon:
            raise ContractError(f"selected text is not fully covered by lexicon: {part!r}")
        words.append(part)
        current.extend(lexicon[part])
        current.append(token_to_id[" "])
    if len(current) > 1:
        current.append(0)
        segments.append(tuple(current))
    if not segments:
        raise ContractError("frontend produced no segment")
    for segment in segments:
        if segment[0] != 0 or segment[-1] != 0:
            raise ContractError("padding contract violated")
        if len(segment) - 2 >= 510:
            raise ContractError("voice style index is outside the official pack")
    return FrontendResult(
        normalized_text=normalized,
        parts=parts,
        segments=tuple(segments),
        style_indices=tuple(len(segment) - 2 for segment in segments),
        lexicon_words=tuple(words),
        punctuation=tuple(punctuation),
    )


def validate_audio(samples: Iterable[float], sample_rate: int = 24_000) -> dict[str, object]:
    values = list(float(x) for x in samples)
    if sample_rate != 24_000:
        raise ContractError(f"sample-rate drift: {sample_rate}")
    if len(values) < 2_400:
        raise ContractError("audio is shorter than 0.1 second")
    if not all(math.isfinite(x) for x in values):
        raise ContractError("audio contains non-finite values")
    peak = max(abs(x) for x in values)
    rms = math.sqrt(sum(x * x for x in values) / len(values))
    clipped = sum(abs(x) >= 1.0 for x in values)
    valid = peak >= 0.0001 and peak < 1.0 and rms >= 0.00001 and clipped == 0
    return {
        "valid": valid,
        "sample_count": len(values),
        "sample_rate_hz": sample_rate,
        "duration_seconds": len(values) / sample_rate,
        "all_finite": True,
        "absolute_peak": peak,
        "rms": rms,
        "clipped_float_samples": clipped,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--tokens", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = frontend(
        args.text.read_text(encoding="utf-8"), args.tokens, args.lexicon
    )
    document = {
        "normalized_text": result.normalized_text,
        "parts": list(result.parts),
        "segments": [list(x) for x in result.segments],
        "style_indices": list(result.style_indices),
        "lexicon_words": list(result.lexicon_words),
        "punctuation": list(result.punctuation),
    }
    payload = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
