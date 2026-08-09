#!/usr/bin/env python3
"""Fail-closed local pin checks; optionally verify immutable revisions online."""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def validate() -> None:
    assert PINS["schema_version"] == 1
    assert HEX40.fullmatch(PINS["model"]["revision"])
    assert HEX40.fullmatch(PINS["implementation"]["revision"])
    assert HEX64.fullmatch(PINS["implementation"]["wheel_sha256"])
    assert PINS["model"]["repo_id"] == "hexgrad/Kokoro-82M"
    assert PINS["implementation"]["package"] == "kokoro"
    # Keep voice identity tied to an exact repository object rather than merely
    # trusting a prose name.
    voice = PINS["voice"]
    voice_path = f"voices/{voice['id']}.pt"
    assert voice_path in PINS["model"]["files"]
    assert HEX64.fullmatch(PINS["model"]["files"][voice_path]["sha256"])
    assert voice["kind"] == "repository stock voice"
    assert voice["personal_or_cloned_input_used"] is False
    assert PINS["native_output"]["sample_rate_hz"] == 24000


def online_checks() -> None:
    revision = PINS["model"]["revision"]
    model = json.load(urllib.request.urlopen(
        f"https://huggingface.co/api/models/{PINS['model']['repo_id']}/revision/{revision}?blobs=true", timeout=30
    ))
    assert model["sha"] == revision, (model["sha"], revision)
    siblings = {item["rfilename"]: item for item in model["siblings"]}
    for path, expected in PINS["model"]["files"].items():
        remote = siblings[path]
        assert remote["size"] == expected["bytes"]
        if "lfs" in remote:
            assert remote["lfs"]["sha256"] == expected["sha256"]
    source_revision = PINS["implementation"]["revision"]
    source = json.load(urllib.request.urlopen(
        f"https://api.github.com/repos/hexgrad/kokoro/commits/{source_revision}", timeout=30
    ))
    assert source["sha"] == source_revision, (source["sha"], source_revision)
    package = json.load(urllib.request.urlopen("https://pypi.org/pypi/kokoro/json", timeout=30))
    release = package["releases"][PINS["implementation"]["version"]]
    wheel = next(item for item in release if item["filename"] == PINS["implementation"]["wheel"])
    assert wheel["digests"]["sha256"] == PINS["implementation"]["wheel_sha256"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true", help="also compare pins with upstream APIs/remotes")
    args = parser.parse_args()
    validate()
    if args.online:
        online_checks()
    print(json.dumps({"status": "passed", "online": args.online}, sort_keys=True))


if __name__ == "__main__":
    main()
