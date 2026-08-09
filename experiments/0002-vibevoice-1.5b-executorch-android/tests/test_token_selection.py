#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVA_SOURCE = ROOT / "android/app/src/main/java/dev/moket/vibevoiceprobe/TokenSelector.java"
JAVA_TEST = ROOT / "tests/java/dev/moket/vibevoiceprobe/TokenSelectorTest.java"
MANIFEST = ROOT / "fixtures/token-selection-manifest.json"


def test_native_token_selector(tmp_path: Path) -> None:
    subprocess.run(["javac", "-d", str(tmp_path), str(JAVA_SOURCE), str(JAVA_TEST)], check=True)
    completed = subprocess.run(
        ["java", "-cp", str(tmp_path), "dev.moket.vibevoiceprobe.TokenSelectorTest"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert completed.stdout.strip() == "TokenSelectorTest: passed"


def test_manifest_locks_pytorch_sequence_and_settings() -> None:
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["provenance"]["seed"] == 42
    assert manifest["settings"]["do_sample"] is False
    assert manifest["settings"]["rng_consumed"] is False
    assert manifest["settings"]["seed_reset_verified"] is True
    assert manifest["allowed_ids"] == [151643, 151652, 151653, 151654]
    assert [row["selected_id"] for row in manifest["steps"]] == manifest["locked_sequence"]
    assert manifest["locked_sequence"][-1] == manifest["tokens"]["eos"]
    assert manifest["steps"][-1]["terminates"] is True
