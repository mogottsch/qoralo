#!/usr/bin/env python3
"""Fail-closed Kitten Mini 0.8 provenance checks, optionally against upstream."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
PLAN = json.loads((HERE / "attempt-plan.json").read_text(encoding="utf-8"))
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(pins: dict | None = None, plan: dict | None = None, *, check_lock: bool = True) -> None:
    pins = PINS if pins is None else pins
    plan = PLAN if plan is None else plan
    model, implementation, voice = pins["model"], pins["implementation"], pins["voice"]
    assert model["repo_id"] == "KittenML/kitten-tts-mini-0.8"
    assert model["name"] == "Kitten TTS Mini" and model["version"] == "0.8"
    assert model["parameter_class"] == "80M"
    assert not any(word in model["repo_id"].lower() for word in ("nano", "micro"))
    assert HEX40.fullmatch(model["revision"])
    assert implementation["release_tag"] == "0.8"
    assert implementation["declared_release_version"] == "0.8.0"
    assert implementation["release_asset"] == "kittentts-0.8.0-py3-none-any.whl"
    assert "/download/0.8/" in implementation["release_asset_url"]
    assert HEX40.fullmatch(implementation["revision"])
    assert HEX64.fullmatch(implementation["release_asset_sha256"])
    if check_lock:
        assert sha256(HERE / implementation["dependency_lock"]) == implementation["dependency_lock_sha256"]
    for artifact in model["files"].values():
        assert artifact["bytes"] > 0 and HEX64.fullmatch(artifact["sha256"])
    assert voice["display_id"] == "Jasper" and voice["asset_key"] == "expr-voice-2-m"
    assert HEX64.fullmatch(voice["array_c_order_sha256"])
    assert voice["reference_audio_used"] is False and voice["cloning_performed"] is False
    assert pins["native_output"]["sample_rate_hz"] == 24000
    assert pins["execution"] == {
        "device": "cpu", "runtime": "onnxruntime CPUExecutionProvider", "network_during_generation": False
    }
    assert plan["committed_before_full_generation"] is True
    assert plan["model_repo_id"] == model["repo_id"] and plan["model_revision"] == model["revision"]
    assert plan["attempts"] == [
        {"ordinal": 1, "id": "default", "speed": 1.0, "uses_documented_default": True},
        {"ordinal": 2, "id": "speed-0.95", "speed": 0.95, "uses_documented_default": False},
        {"ordinal": 3, "id": "speed-0.90", "speed": 0.9, "uses_documented_default": False},
    ]
    assert plan["grid"] == {
        "direction": "decreasing", "step": 0.05, "endpoints": [1.0, 0.9],
        "bounded_values": [1.0, 0.95, 0.9],
    }
    assert plan["run_workflow"]["runs"] == ["primary", "repeat-1"]
    assert plan["run_workflow"]["order"] == "ordered_primary_attempts_then_one_accepted_attempt_repeat"
    assert plan["documentation"]["documented_numeric_bounds"] is None
    assert plan["documentation"]["documented_direction_for_longer_output"] == "decrease speed"
    assert plan["short_default_outcome"] == "continue_to_next_precommitted_attempt"
    assert plan["short_final_outcome"] == "terminal_protocol_blocker"


def online_checks() -> None:
    model = PINS["model"]
    response = json.load(urllib.request.urlopen(
        f"https://huggingface.co/api/models/{model['repo_id']}/revision/{model['revision']}?blobs=true", timeout=30
    ))
    assert response["sha"] == model["revision"]
    siblings = {item["rfilename"]: item for item in response["siblings"]}
    for path, expected in model["files"].items():
        remote = siblings[path]
        assert remote["size"] == expected["bytes"]
        if "lfs" in remote:
            assert remote["lfs"]["sha256"] == expected["sha256"]
    implementation = PINS["implementation"]
    tag = json.load(urllib.request.urlopen(
        "https://api.github.com/repos/KittenML/KittenTTS/git/ref/tags/0.8", timeout=30
    ))
    assert tag["object"]["sha"] == implementation["revision"]
    release = json.load(urllib.request.urlopen(
        "https://api.github.com/repos/KittenML/KittenTTS/releases/tags/0.8", timeout=30
    ))
    asset = next(item for item in release["assets"] if item["name"] == implementation["release_asset"])
    assert asset["size"] == implementation["release_asset_bytes"]
    assert asset["digest"] == "sha256:" + implementation["release_asset_sha256"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    validate()
    if args.online:
        online_checks()
    print(json.dumps({"status": "passed", "online": args.online}, sort_keys=True))


if __name__ == "__main__":
    main()
