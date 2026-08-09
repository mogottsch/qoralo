#!/usr/bin/env python3
"""Capture the pinned VibeVoice PyTorch masking and greedy token decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import torch

from fixture_utils import repo_root

SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"
TOKENIZER_REVISION = "8faed761d45a263340a0528343f099c05c9a4323"
VOCABULARY_SIZE = 151936
TOKENS = {
    "eos": 151643,
    "speech_start": 151652,
    "speech_end": 151653,
    "speech_diffusion": 151654,
}
LOCKED_SEQUENCE = [151652, 151654, 151654, 151653, 151643]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def tensor_sha256(value: torch.Tensor) -> str:
    return sha256_bytes(value.detach().cpu().contiguous().numpy().tobytes())


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "artifacts/0002/lane-c/token-selection")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(Path(__file__))
    source = root / "artifacts/source/microsoft-vibevoice"
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != SOURCE_REVISION:
        raise SystemExit(f"Expected source {SOURCE_REVISION}, got {revision}")

    # Import the processor from the exact pinned implementation. Its operation is
    # scores + a -Inf mask followed by torch.argmax when do_sample=False.
    import sys
    sys.path.insert(0, str(source))
    from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceTokenConstraintProcessor

    allowed = [TOKENS[name] for name in ("speech_start", "speech_end", "speech_diffusion", "eos")]
    processor = VibeVoiceTokenConstraintProcessor(allowed, device=torch.device("cpu"))

    def capture_sequence() -> list[dict[str, object]]:
        rows = []
        for step, selected in enumerate(LOCKED_SEQUENCE):
            logits = torch.full((1, VOCABULARY_SIZE), -1000.0, dtype=torch.float32)
            # A disallowed distractor proves masking. The step-zero allowed-token
            # tie proves torch.argmax's first/lowest vocabulary index rule.
            logits[0, 7] = 1_000_000.0
            logits[0, selected] = 5.0
            if step == 0:
                logits[0, TOKENS["speech_end"]] = 5.0
            if step == 2:
                logits[0, TOKENS["speech_diffusion"]] = -103.0
                logits[0, TOKENS["eos"]] = -104.0
            scores = processor(torch.zeros((1, 1), dtype=torch.long), logits)
            decision = int(torch.argmax(scores, dim=-1).item())
            if decision != selected:
                raise SystemExit(f"Step {step}: expected {selected}, got {decision}")
            rows.append({
                "step": step,
                "selected_id": decision,
                "logits_sha256": tensor_sha256(logits),
                "masked_scores_sha256": tensor_sha256(scores),
                "terminates": decision == TOKENS["eos"],
            })
        return rows

    torch.manual_seed(args.seed)
    rows = capture_sequence()
    torch.manual_seed(args.seed)
    reset_rows = capture_sequence()
    if reset_rows != rows:
        raise SystemExit("Token decisions or hashes changed after resetting the pinned seed")

    args.output.mkdir(parents=True, exist_ok=True)
    capture = {
        "schema_version": 1,
        "component": "token_selection",
        "provenance": {
            "source_revision": SOURCE_REVISION,
            "model_revision": MODEL_REVISION,
            "tokenizer": "Qwen/Qwen2.5-1.5B",
            "tokenizer_revision": TOKENIZER_REVISION,
            "seed": args.seed,
            "dtype": "float32",
        },
        "settings": {
            "do_sample": False,
            "algorithm": "mask disallowed IDs with -Inf, then torch.argmax",
            "temperature": None,
            "top_k": None,
            "top_p": None,
            "rng_consumed": False,
            "seed_reset_verified": True,
            "tie_rule": "lowest vocabulary ID (first index)",
        },
        "vocabulary_size": VOCABULARY_SIZE,
        "tokens": TOKENS,
        "allowed_ids": sorted(allowed),
        "locked_sequence": LOCKED_SEQUENCE,
        "steps": rows,
        "termination": {"eos_id": TOKENS["eos"], "capacity": "controller max-length budget"},
    }
    encoded = json.dumps(capture, sort_keys=True, separators=(",", ":")).encode()
    capture["capture_sha256"] = sha256_bytes(encoded)
    (args.output / "capture.json").write_text(json.dumps(capture, indent=2) + "\n")
    print(json.dumps(capture, indent=2))


if __name__ == "__main__":
    main()
