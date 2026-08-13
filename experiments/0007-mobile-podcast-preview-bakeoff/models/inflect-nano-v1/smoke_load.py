#!/usr/bin/env python3
"""Gated CPU-only weight and frozen-frontend smoke load; performs no synthesis."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from track import NLTK_DATA, PINS, SNAPSHOT, frozen_transcript, install_local_tokenizer_resolution, verify_snapshot


def fail(message: str) -> "None":
    raise SystemExit(f"BLOCKED: {message}")


def main() -> None:
    if os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "model-load":
        fail("use smoke-load.sh; direct or ungated model loading is forbidden")
    if os.environ.get("PREVIEW_RESOURCE_GRANT_TASK") != "task-3-inflect-smoke":
        fail("unexpected resource-grant task")
    verified = verify_snapshot()
    os.environ["NLTK_DATA"] = str(NLTK_DATA)
    sys.path[:0] = [str(SNAPSHOT), str(SNAPSHOT / "third_party" / "tiny_tts_frontend")]
    install_local_tokenizer_resolution()
    import torch
    from inference import load_acoustic, load_vocoder, text_to_tokens

    if torch.cuda.is_available() and os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        fail("CUDA must be hidden for the CPU track")
    device = torch.device("cpu")
    acoustic, speakers, acoustic_parameters = load_acoustic(SNAPSHOT / PINS["artifacts"]["acoustic_path"], device)
    vocoder, vocoder_parameters = load_vocoder(SNAPSHOT / PINS["artifacts"]["vocoder_path"], device)
    tokens = text_to_tokens(frozen_transcript())
    if not all(tensor.numel() for tensor in tokens):
        fail("vendored pinned frontend returned empty tokens")
    if set(speakers) != {PINS["voice"]["id"]}:
        fail("fixed stock voice identity drift")
    report = {
        "schema_version": 1,
        "status": "passed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repository": PINS["identity"]["repository"],
        "revision": PINS["identity"]["revision"],
        "device": str(device),
        "sample_rate_hz": PINS["native_output"]["sample_rate_hz"],
        "voice": PINS["voice"],
        "parameters": {"acoustic": acoustic_parameters, "vocoder": vocoder_parameters},
        "frontend_token_count": int(tokens[0].numel()),
        "verified_file_count": len(verified),
        "synthesis_performed": False,
    }
    output = SNAPSHOT.parent / "smoke-load.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
