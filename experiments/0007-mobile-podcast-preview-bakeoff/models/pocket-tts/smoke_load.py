#!/usr/bin/env python3
"""Fail-closed Pocket TTS stock-voice load; must be invoked through smoke_load.sh."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
ARTIFACT_ROOT = Path(
    os.environ.get("POCKET_TTS_ARTIFACT_ROOT", EXPERIMENT / "artifacts/setup/pocket-tts")
)
SOURCE = ARTIFACT_ROOT / "source"

sys.path.insert(0, str(EXPERIMENT / "tools"))
import protocol  # noqa: E402


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"Pocket TTS smoke refused: {message}")


def main() -> None:
    if os.environ.get("PREVIEW_RESOURCE_GRANT_KIND") != "smoke-load":
        fail("missing smoke-load resource-grant marker; use ./smoke_load.sh")
    if protocol.protocol_reference() != PINS["protocol"]:
        fail("shared preview protocol revision drift")

    try:
        revision = subprocess.check_output(
            ["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(SOURCE), "status", "--porcelain", "--untracked-files=no"],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        fail("pinned source is absent; run ./setup.sh")
    if revision != PINS["source"]["revision"] or dirty:
        fail("source revision or tracked tree drift")

    # Import only after provenance checks. The source checkout's frozen venv is
    # selected by smoke_load.sh, so this must resolve to the pinned checkout.
    from pocket_tts import TTSModel

    import pocket_tts

    package_path = Path(pocket_tts.__file__).resolve()
    if SOURCE.resolve() not in package_path.parents:
        fail(f"package did not load from pinned checkout: {package_path}")

    model = TTSModel.load_model(language=PINS["generation"]["language"], temp=0.3)
    if model.sample_rate != PINS["native_output"]["sample_rate_hz"]:
        fail("native sample-rate drift")
    # This is the official precomputed stock state. It does not read or encode
    # source audio, and works with the public no-voice-cloning weight fallback.
    state = model.get_state_for_audio_prompt(PINS["voice"]["name"])
    if not isinstance(state, dict) or not state:
        fail("stock voice state was empty")

    evidence = {
        "status": "passed",
        "source_revision": revision,
        "model_repository": PINS["weights"]["stock_voice_repository"],
        "model_revision": PINS["weights"]["stock_voice_model_revision"],
        "voice_repository_revision": PINS["weights"]["stock_voice_revision"],
        "voice": PINS["voice"]["name"],
        "cloning_performed": False,
        "sample_rate_hz": model.sample_rate,
        "voice_state_entries": len(state),
        "protocol": PINS["protocol"],
    }
    output = ARTIFACT_ROOT / "smoke-load.json"
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
