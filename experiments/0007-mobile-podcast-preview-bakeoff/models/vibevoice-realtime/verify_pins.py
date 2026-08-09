#!/usr/bin/env python3
"""Fail closed unless source, weights, voices, config, and environment match pins."""
from __future__ import annotations
import argparse, hashlib, importlib.metadata, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / "pins.json").read_text())
DIRECT = {}
for line in (HERE / "requirements.in").read_text().splitlines():
    if line and not line.startswith("#"):
        name, version = line.split("==", 1); DIRECT[name.lower()] = version
VOICE_HASHES = {
    "en-Carter_man.pt": "a7bfdf1cd4939c22469bcfc6f427ae9c4467b3df46c2c14303a39c294cfc6897",
    "en-Davis_man.pt": "67561d63bfa2153616e4c02fd967007c182593fc53738a6ad94bf5f84e8832ac",
    "en-Emma_woman.pt": "75b15c481e0d848991f1789620aa9929c583ec2c5f701f8152362cf74498bbf8",
    "en-Frank_man.pt": "acaa8f1a4f46a79f8f5660cfb7a3af06ef473389319df7debc07376fdc840e47",
    "en-Grace_woman.pt": "5f0ef02a3f3cace04cf721608b65273879466bb15fe4044e46ec6842190f6bb1",
    "en-Mike_man.pt": "afb64b580fbc6fab09af04572bbbd2b3906ff8ed35a28731a90b8681e47bdc89",
}
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()
def check(condition: bool, message: str) -> None:
    if not condition: raise SystemExit(f"PIN VALIDATION FAILED: {message}")
def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--source", type=Path); p.add_argument("--model", type=Path); p.add_argument("--tokenizer", type=Path); p.add_argument("--environment", type=Path)
    a = p.parse_args(); report = {"source_revision": None, "model_revision": None, "tokenizer_revision": None, "voices": {}, "dependencies": {}}
    if a.source:
        head = subprocess.check_output(["git", "-C", a.source, "rev-parse", "HEAD"], text=True).strip()
        check(head == PINS["source"]["revision"], "source revision differs"); report["source_revision"] = head
        license_text = (a.source / "LICENSE").read_text(); check("MIT License" in license_text and "Copyright (c) 2025 Microsoft" in license_text, "source license differs")
        voices = a.source / "demo/voices/streaming_model"
        actual = {x.name for x in voices.glob("en-*.pt")}; check(actual == set(VOICE_HASHES), "English official voice set differs")
        for name, expected in VOICE_HASHES.items():
            actual_hash = sha256(voices / name); check(actual_hash == expected, f"voice hash differs: {name}"); report["voices"][name] = actual_hash
    if a.model:
        revision = (a.model / ".model-revision").read_text().strip(); check(revision == PINS["model"]["revision"], "model revision marker differs")
        for name, metadata in PINS["model"]["files"].items():
            path = a.model / name; check(path.stat().st_size == metadata["bytes"], f"model file size differs: {name}"); check(sha256(path) == metadata["sha256"], f"model file hash differs: {name}")
        config = json.loads((a.model / "config.json").read_text()); pre = json.loads((a.model / "preprocessor_config.json").read_text())
        check(config["architectures"] == ["VibeVoiceStreamingForConditionalGenerationInference"], "architecture differs")
        check(pre["audio_processor"]["sampling_rate"] == 24000, "native sample rate differs"); report["model_revision"] = revision
    if a.tokenizer:
        revision = (a.tokenizer / ".model-revision").read_text().strip(); check(revision == PINS["tokenizer"]["revision"], "tokenizer revision marker differs")
        for name, metadata in PINS["tokenizer"]["files"].items():
            path = a.tokenizer / name; check(path.stat().st_size == metadata["bytes"], f"tokenizer file size differs: {name}"); check(sha256(path) == metadata["sha256"], f"tokenizer file hash differs: {name}")
        report["tokenizer_revision"] = revision
    if a.environment:
        check(Path(sys.prefix).resolve() == a.environment.resolve(), "inspection is not running inside requested environment")
        for name, expected in DIRECT.items():
            actual = importlib.metadata.version(name); check(actual == expected or (name == "torch" and actual == expected + "+cu128"), f"dependency differs: {name}={actual}"); report["dependencies"][name] = actual
    print(json.dumps(report, indent=2, sort_keys=True))
if __name__ == "__main__": main()
