#!/usr/bin/env python3
"""Fail-closed official Kokoro checkpoint, code, and voice verification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
from kokoro import KModel

from kokoro_contract import sha256_file

PINS = {
    "model": (327_212_226, "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"),
    "config": (2_351, "5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f"),
    "voice": (523_425, "0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff"),
}


def verify_file(path: Path, name: str) -> None:
    size, digest = PINS[name]
    if not path.is_file() or path.is_symlink() or path.stat().st_size != size or sha256_file(path) != digest:
        raise RuntimeError(f"{name} pin mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--voice", type=Path, required=True)
    parser.add_argument("--voice-raw", type=Path, required=True)
    parser.add_argument("--sherpa-voices", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in ("model", "config", "voice"):
        verify_file(getattr(args, name), name)
    checkpoint = torch.load(args.model, map_location="cpu", weights_only=True)
    model = KModel(repo_id="not-used", model=str(args.model), config=str(args.config), disable_complex=False).cpu().eval()
    groups = {}
    matched_total = 0
    extras_total = 0
    for group, source_state in checkpoint.items():
        loaded = getattr(model, group).state_dict()
        matched = 0
        expected_names = set()
        for source_name, source_value in source_state.items():
            target_name = source_name.removeprefix("module.")
            expected_names.add(target_name)
            target_value = loaded.get(target_name)
            if target_value is None or source_value.dtype != target_value.dtype or tuple(source_value.shape) != tuple(target_value.shape) or not torch.equal(source_value, target_value):
                raise RuntimeError(f"loaded checkpoint tensor differs: {group}.{source_name}")
            matched += 1
        extras = sorted(set(loaded) - expected_names)
        for name in extras:
            value = loaded[name]
            if name.endswith(".norm.weight"):
                expected = torch.ones_like(value)
            elif name.endswith(".norm.bias"):
                expected = torch.zeros_like(value)
            else:
                raise RuntimeError(f"unexpected non-checkpoint model state: {group}.{name}")
            if not torch.equal(value, expected):
                raise RuntimeError(f"unexpected default state value: {group}.{name}")
        matched_total += matched
        extras_total += len(extras)
        groups[group] = {"checkpoint_tensors": len(source_state), "exact_matches": matched, "code_default_affine_instance_norm_state": len(extras)}
    if matched_total != 548 or extras_total != 140:
        raise RuntimeError(f"state count drift: matched={matched_total}, extras={extras_total}")

    voice = torch.load(args.voice, map_location="cpu", weights_only=True)
    if tuple(voice.shape) != (510, 1, 256) or voice.dtype != torch.float32 or not voice.is_contiguous():
        raise RuntimeError("voice tensor contract drift")
    raw = voice.numpy().tobytes()
    if args.voice_raw.read_bytes() != raw:
        raise RuntimeError("lossless voice raw serialization differs")
    all_voices = args.sherpa_voices.read_bytes()
    block = len(raw)
    if all_voices[3 * block : 4 * block] != raw:
        raise RuntimeError("pinned sherpa SID-3 corroborating voice block differs")

    package_root = Path(__import__("kokoro").__file__).parent
    source_files = {}
    for name in ("model.py", "modules.py", "istftnet.py", "custom_stft.py", "pipeline.py"):
        path = package_root / name
        source_files[name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    document = {
        "schema_version": 1,
        "status": "passed",
        "official_revision": "f3ff3571791e39611d31c381e3a41a3af07b4987",
        "model": {"bytes": args.model.stat().st_size, "sha256": sha256_file(args.model)},
        "config": {"bytes": args.config.stat().st_size, "sha256": sha256_file(args.config)},
        "voice": {"bytes": args.voice.stat().st_size, "sha256": sha256_file(args.voice), "shape": list(voice.shape), "dtype": str(voice.dtype)},
        "checkpoint": {"groups": groups, "exact_loaded_checkpoint_tensors": matched_total, "code_default_affine_instance_norm_tensors": extras_total, "all_checkpoint_tensors_exact": True},
        "voice_transform": {"raw_bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(), "official_pt_lossless_match": True, "sherpa_sid_3_block_lossless_match": True},
        "kokoro_0_9_4_source_files": source_files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
