#!/usr/bin/env python3
"""Fail closed on local provenance; optionally compare all pins with official APIs."""
from __future__ import annotations
import argparse, json, re, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
PLAN = json.loads((HERE / "speed-attempts.json").read_text(encoding="utf-8"))
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def validate() -> None:
    model, implementation, voice = PINS["model"], PINS["implementation"], PINS["voice"]
    assert PINS["candidate"] == "D"
    assert model["repo_id"] == "Supertone/supertonic-3" and HEX40.fullmatch(model["revision"])
    assert model["gated"] is False and model["credentials_required"] is False
    assert model["license_acceptance"] == "none"
    assert implementation["repository"] == "https://github.com/supertone-inc/supertonic-py.git"
    assert HEX40.fullmatch(implementation["revision"])
    assert implementation["version"] == "1.3.1" and HEX64.fullmatch(implementation["wheel_sha256"])
    required = {"LICENSE", "config.json", "onnx/duration_predictor.onnx", "onnx/text_encoder.onnx", "onnx/tts.json", "onnx/unicode_indexer.json", "onnx/vector_estimator.onnx", "onnx/vocoder.onnx", "voice_styles/M1.json"}
    assert set(model["files"]) == required
    assert all(item["bytes"] > 0 and HEX64.fullmatch(item["sha256"]) for item in model["files"].values())
    assert voice == voice | {"id": "M1", "kind": "repository bundled stock voice", "artifact": "voice_styles/M1.json", "personal_or_cloned_input_used": False, "custom_voice_allowed": False}
    attempts = PLAN["attempts"]
    assert attempts[0] == {"index": 0, "argument": "omitted", "effective_speed": 1.05}
    assert [x["effective_speed"] for x in attempts] == [1.05, 1.0, .95, .9, .85, .8, .75, .7]
    assert PLAN["direction"] == "descending" and PLAN["step"] == .05 and PLAN["endpoint"] == .7
    assert PINS["runtime"]["execution_provider"] == "CPUExecutionProvider"
    assert PINS["native_output"]["sample_rate_hz"] == 44100


def online_checks() -> None:
    model = PINS["model"]
    data = json.load(urllib.request.urlopen(f"https://huggingface.co/api/models/{model['repo_id']}/revision/{model['revision']}?blobs=true", timeout=30))
    assert data["sha"] == model["revision"]
    siblings = {x["rfilename"]: x for x in data["siblings"]}
    for path, expected in model["files"].items():
        remote = siblings[path]
        assert remote["size"] == expected["bytes"]
        if "lfs" in remote:
            assert remote["lfs"]["sha256"] == expected["sha256"]
    impl = PINS["implementation"]
    commit = json.load(urllib.request.urlopen(f"https://api.github.com/repos/supertone-inc/supertonic-py/commits/{impl['revision']}", timeout=30))
    assert commit["sha"] == impl["revision"]
    package = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/supertonic/{impl['version']}/json", timeout=30))
    wheel = next(x for x in package["urls"] if x["filename"] == impl["wheel"])
    assert wheel["size"] == impl["wheel_bytes"] and wheel["digests"]["sha256"] == impl["wheel_sha256"]


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--online", action="store_true"); args = parser.parse_args()
    validate()
    if args.online: online_checks()
    print(json.dumps({"status": "passed", "online": args.online}, sort_keys=True))

if __name__ == "__main__": main()
