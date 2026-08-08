#!/usr/bin/env python3
"""Capture two chained real semantic-encoder calls from locked decoder audio."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import torch

from fixture_utils import repo_root, snapshot_cache, tensor_metadata
from semantic_encoder import load_semantic_encoder, semantic_cache_names

SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "artifacts/source/microsoft-vibevoice")
    parser.add_argument("--model", type=Path, default=root / "artifacts/models/microsoft-VibeVoice-1.5B")
    parser.add_argument("--decoder-fixtures", type=Path, default=root / "artifacts/0002/acoustic-decoder-fixtures")
    parser.add_argument("--output", type=Path, default=root / "artifacts/0002/lane-b/semantic-encoder/capture-1")
    parser.add_argument("--repeat-of", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    revision = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    if revision != SOURCE_REVISION:
        raise SystemExit(f"Expected source {SOURCE_REVISION}, got {revision}")
    sys.path.insert(0, str(args.source.resolve()))
    from vibevoice.modular.modular_vibevoice_tokenizer import VibeVoiceTokenizerStreamingCache

    encoder = load_semantic_encoder(args.model.resolve())
    names = semantic_cache_names(encoder)
    cache = VibeVoiceTokenizerStreamingCache()
    calls: list[dict[str, object]] = []
    prior_post: dict[str, torch.Tensor] | None = None
    with torch.no_grad():
        for call_index in range(2):
            decoder_fixture = args.decoder_fixtures / f"call_{call_index:03d}.pt"
            decoded = torch.load(decoder_fixture, map_location="cpu", weights_only=True)
            audio = decoded["pcm"].float().contiguous()
            pre_cache, _ = snapshot_cache(encoder, cache)
            if call_index == 1:
                assert prior_post is not None
                if pre_cache.keys() != prior_post.keys() or any(
                    not torch.equal(pre_cache[key], prior_post[key]) for key in pre_cache
                ):
                    raise SystemExit("Call two did not receive call-one eager cache state")
            features = encoder(
                audio, cache=cache, sample_indices=torch.zeros(1, dtype=torch.int64), use_cache=True
            ).permute(0, 2, 1).contiguous()
            post_cache, entries = snapshot_cache(encoder, cache)
            calls.append({"audio": audio, "features": features, "pre_cache": pre_cache, "post_cache": post_cache})
            prior_post = post_cache
            if tuple(features.shape) != (1, 1, 128):
                raise SystemExit(f"Unexpected semantic output shape: {tuple(features.shape)}")
            if [entry["module"] for entry in entries] != list(names):
                raise SystemExit("Runtime cache order differs from lexical ABI")

    args.output.mkdir(parents=True, exist_ok=True)
    fixture = {"calls": calls, "cache_names": list(names)}
    fixture_path = args.output / "fixture.pt"
    torch.save(fixture, fixture_path)
    repeat_match = None
    if args.repeat_of:
        prior = torch.load(args.repeat_of, map_location="cpu", weights_only=True)
        repeat_match = True
        for index in range(2):
            for section in ("audio", "features"):
                repeat_match &= torch.equal(calls[index][section], prior["calls"][index][section])
            for section in ("pre_cache", "post_cache"):
                current = calls[index][section]
                old = prior["calls"][index][section]
                repeat_match &= current.keys() == old.keys() and all(torch.equal(current[k], old[k]) for k in current)
        if not repeat_match:
            raise SystemExit("Repeat capture tensor hashes differ")
    manifest = {
        "schema_version": 1,
        "component": "semantic_audio_encoder",
        "provenance": {
            "source_revision": SOURCE_REVISION,
            "model_revision": MODEL_REVISION,
            "model_index_sha256": sha256(args.model / "model.safetensors.index.json"),
            "input_source": "real chained call_000/call_001 acoustic decoder PCM from seed-42 locked generation",
        },
        "cache_order": list(names),
        "calls": [
            {
                "index": index,
                "audio": tensor_metadata(call["audio"]),
                "features": tensor_metadata(call["features"]),
                "pre_cache": {key: tensor_metadata(value) for key, value in call["pre_cache"].items()},
                "post_cache": {key: tensor_metadata(value) for key, value in call["post_cache"].items()},
            }
            for index, call in enumerate(calls)
        ],
        "chaining": {"call_2_pre_cache_equals_call_1_post_cache": True},
        "repeat": {"compared_to": str(args.repeat_of) if args.repeat_of else None, "all_tensor_hashes_match": repeat_match},
        "capture": {"wall_seconds": time.perf_counter() - started, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
