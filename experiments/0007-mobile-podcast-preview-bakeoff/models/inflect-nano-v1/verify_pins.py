#!/usr/bin/env python3
"""Fail-closed local pins; optionally compare the immutable HF object online."""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

from track import HERE, PINS, PLAN

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
EXACT_REPOSITORY = "owensong/Inflect-Nano-v1"


def validate() -> None:
    identity = PINS["identity"]
    if identity["repository"] != EXACT_REPOSITORY or identity["required_name"] != "Inflect-Nano-v1":
        raise ValueError("only exact owensong/Inflect-Nano-v1 is permitted; v2, aliases, and substitutes are forbidden")
    if not HEX40.fullmatch(identity["revision"]):
        raise ValueError("model revision is not immutable")
    if PINS["implementation"]["source_repository"] != EXACT_REPOSITORY:
        raise ValueError("source is not the exact model repository")
    if PINS["implementation"]["source_revision"] != identity["revision"]:
        raise ValueError("source/model revision mismatch")
    for relative, artifact in PINS["artifacts"]["files"].items():
        if not HEX64.fullmatch(artifact["sha256"]) or artifact["bytes"] < 0:
            raise ValueError(f"unhashed artifact: {relative}")
    if "_v1_" not in PINS["artifacts"]["acoustic_path"] or "_v1_" not in PINS["artifacts"]["vocoder_path"]:
        raise ValueError("weight identity is not explicitly v1")
    frontend = PINS["frontend_assets"]
    if frontend["bert_tokenizer"]["revision"] == "main" or frontend["nltk_data"]["revision"] in ("main", "gh-pages"):
        raise ValueError("frontend assets use moving revisions")
    if frontend["bert_tokenizer"]["license"] != "Apache-2.0":
        raise ValueError("tokenizer license drift")
    for group in frontend.values():
        if not HEX40.fullmatch(group["revision"]):
            raise ValueError("frontend revision is not immutable")
        for artifact in group["files"].values():
            if not HEX64.fullmatch(artifact["sha256"]):
                raise ValueError("frontend asset is not hashed")
    if PINS["voice"]["kind"] != "fixed stock model voice" or PINS["voice"]["cloning_performed"]:
        raise ValueError("voice must be the fixed stock model voice")
    if PINS["voice"]["reference_audio_allowed"] or PINS["voice"]["selectable_voice_input"]:
        raise ValueError("reference or selectable voices are forbidden")
    if PINS["native_output"] != {
        "api_waveform_dtype": "numpy.float32", "channels": 1, "file_format": "WAV",
        "sample_format": "PCM_S16LE", "sample_rate_hz": 24000,
    }:
        raise ValueError("native output contract drift")
    if "--device cpu" not in PINS["implementation"]["cpu_command"]:
        raise ValueError("CPU command drift")
    if PLAN["values"] != [1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5]:
        raise ValueError("length-scale grid drift")
    if PLAN["documented_default"] != PLAN["values"][0] or PLAN["direction"] != "ascending":
        raise ValueError("attempt plan is not default-first and ascending")
    if PLAN["bounds"] != {"minimum": 1.0, "maximum": 1.5} or PLAN["step"] != 0.05:
        raise ValueError("attempt bounds/step drift")
    if PLAN["fixed_controls"] != {"energy_scale": 1.0, "pitch_scale": 1.0}:
        raise ValueError("pitch and energy must remain at defaults")
    lock = HERE / PINS["implementation"]["dependency_lock"]
    from track import sha256
    if sha256(lock) != PINS["implementation"]["dependency_lock_sha256"]:
        raise ValueError("dependency lock drift")
    project = (HERE / "pyproject.toml").read_text(encoding="utf-8")
    for dependency in ("g2p-en==2.1.0", "numba==0.61.0", "numpy==2.1.3", "soundfile==0.13.1", "torch==2.6.0+cpu", "torchaudio==2.6.0+cpu", "transformers==4.48.3"):
        if dependency not in project:
            raise ValueError(f"dependency is not exact: {dependency}")


def online_checks() -> None:
    revision = PINS["identity"]["revision"]
    url = f"https://huggingface.co/api/models/{EXACT_REPOSITORY}/revision/{revision}?blobs=true"
    model = json.load(urllib.request.urlopen(url, timeout=30))
    if model["id"] != EXACT_REPOSITORY or model["sha"] != revision or model.get("gated"):
        raise ValueError("upstream identity/revision/access drift")
    siblings = {item["rfilename"]: item for item in model["siblings"]}
    for relative, expected in PINS["artifacts"]["files"].items():
        remote = siblings[relative]
        if remote["size"] != expected["bytes"]:
            raise ValueError(f"upstream size drift: {relative}")
        if "lfs" in remote and remote["lfs"]["sha256"] != expected["sha256"]:
            raise ValueError(f"upstream LFS hash drift: {relative}")
    tokenizer = PINS["frontend_assets"]["bert_tokenizer"]
    token_model = json.load(urllib.request.urlopen(
        f"https://huggingface.co/api/models/{tokenizer['repository']}/revision/{tokenizer['revision']}?blobs=true", timeout=30
    ))
    if token_model["sha"] != tokenizer["revision"]:
        raise ValueError("tokenizer revision drift")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    validate()
    if args.online:
        online_checks()
    print(json.dumps({"status": "passed", "online": args.online, "repository": EXACT_REPOSITORY}, sort_keys=True))


if __name__ == "__main__":
    main()
