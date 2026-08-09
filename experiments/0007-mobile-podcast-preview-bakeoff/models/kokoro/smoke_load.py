#!/usr/bin/env python3
"""Download pinned files, verify them, and load Kokoro under the resource wrapper."""
from __future__ import annotations

import ctypes.util
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
TRANSCRIPT = EXPERIMENT / "protocol" / "transcript.txt"
EXPECTED_TRANSCRIPT_SHA256 = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
ARTIFACT_ROOT = Path(os.environ.get("KOKORO_ARTIFACT_ROOT", EXPERIMENT / "artifacts" / "kokoro"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> "None":
    raise SystemExit(f"BLOCKED: {message}")


def main() -> None:
    if os.environ.get("KOKORO_GATED_SMOKE") != "1":
        fail("direct model loading is forbidden; run ./smoke-load.sh so task 1's exclusive resource gate is acquired")
    espeak = shutil.which("espeak-ng")
    if not espeak:
        fail("executable 'espeak-ng' is absent; provide a permitted project-local binary on PATH (no apt/sudo)")
    espeak_library = os.environ.get("KOKORO_ESPEAK_LIBRARY") or ctypes.util.find_library("espeak-ng")
    espeak_data = Path(os.environ.get("KOKORO_ESPEAK_DATA", "/usr/share/espeak-ng-data"))
    if not espeak_library:
        fail("libespeak-ng is absent; set KOKORO_ESPEAK_LIBRARY to a permitted project-local shared library")
    if not espeak_data.is_dir():
        fail("eSpeak data is absent; set KOKORO_ESPEAK_DATA to a permitted project-local espeak-ng-data directory")

    transcript_bytes = TRANSCRIPT.read_bytes()
    if hashlib.sha256(transcript_bytes).hexdigest() != EXPECTED_TRANSCRIPT_SHA256:
        fail("the frozen protocol transcript hash changed")

    from huggingface_hub import snapshot_download

    model = PINS["model"]
    snapshot = Path(snapshot_download(
        repo_id=model["repo_id"],
        revision=model["revision"],
        allow_patterns=list(model["files"]),
        local_dir=ARTIFACT_ROOT / "snapshot",
    ))
    verified: dict[str, dict[str, object]] = {}
    for relative, expected in model["files"].items():
        path = snapshot / relative
        actual = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        if actual != expected:
            fail(f"pinned artifact mismatch for {relative}: expected {expected}, got {actual}")
        verified[relative] = actual

    # Avoid the implementation's unpinned lazy-download defaults by supplying all
    # three revision-pinned local files explicitly.
    # misaki 0.9.4 unconditionally chooses espeakng-loader's bundled library.
    # Override its path getters before importing Kokoro so this reproducibly uses
    # the dependency checked above (system-installed here, or explicitly local).
    import espeakng_loader
    espeakng_loader.get_library_path = lambda: espeak_library
    espeakng_loader.get_data_path = lambda: str(espeak_data)

    import torch
    from kokoro import KModel, KPipeline, __version__ as kokoro_version

    if kokoro_version != PINS["implementation"]["version"]:
        fail(f"kokoro version {kokoro_version!r} does not match the pin")
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    loaded_model = KModel(repo_id=model["repo_id"], config=str(snapshot / "config.json"), model=str(snapshot / "kokoro-v1_0.pth")).cpu().eval()
    pipeline = KPipeline(lang_code="a", repo_id=model["repo_id"], model=loaded_model, device="cpu")
    voice = pipeline.load_voice(str(snapshot / "voices" / "af_heart.pt"))
    quiet_pipeline = KPipeline(lang_code="a", repo_id=model["repo_id"], model=False, device="cpu")
    tokens = list(quiet_pipeline(transcript_bytes.decode("utf-8"), voice="af_heart"))
    if not tokens or not all(result.phonemes for result in tokens):
        fail("the pinned transcript did not phonemize")

    try:
        source_revision = subprocess.check_output(
            ["git", "ls-remote", PINS["implementation"]["repository"], "HEAD"],
            text=True, timeout=30,
        ).split()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        source_revision = "not_checked_offline"

    report = {
        "schema_version": 1,
        "status": "passed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resource_gate": {"task": "task-4", "kind": "smoke-load", "policy": "model-resource-policy-v1.json"},
        "model": {"repo_id": model["repo_id"], "revision": model["revision"], "verified_files": verified},
        "implementation": PINS["implementation"] | {"remote_head_observed": source_revision},
        "voice": PINS["voice"] | {"tensor_shape": list(voice.shape)},
        "phonemizer": {
            "espeak_ng": subprocess.check_output([espeak, "--version"], text=True).splitlines()[0],
            "library": espeak_library,
            "data": str(espeak_data),
            "chunks": len(tokens),
        },
        "determinism": {"seed": 0, "torch_deterministic_algorithms": True, "generation_repeat_check": "deferred_to_task_8"},
        "native_output": PINS["native_output"],
        "transcript_sha256": EXPECTED_TRANSCRIPT_SHA256,
    }
    output = ARTIFACT_ROOT / "smoke-load.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "report": str(output), "voice_shape": list(voice.shape)}, sort_keys=True))


if __name__ == "__main__":
    main()
