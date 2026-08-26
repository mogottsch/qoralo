#!/usr/bin/env python3
"""Bind rendered prompts to the deployed GGUF tokenizer with llama-tokenize."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokenize", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--rendered-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    inventory: dict[str, dict[str, object]] = {}
    for tier in ("short", "medium", "long"):
        prompt = args.rendered_dir / f"{tier}.txt"
        completed = subprocess.run(
            [
                str(args.tokenize),
                "--model", str(args.model),
                "--file", str(prompt),
                "--ids",
                "--no-bos",
                "--log-disable",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        ids = json.loads(completed.stdout)
        if not isinstance(ids, list) or not all(isinstance(value, int) for value in ids):
            raise ValueError(f"unexpected token output for {tier}")
        packed = struct.pack(f"<{len(ids)}i", *ids)
        prompt_bytes = prompt.read_bytes()
        inventory[tier] = {
            "rendered_bytes": len(prompt_bytes),
            "rendered_sha256": sha256(prompt_bytes),
            "input_tokens": len(ids),
            "token_ids_int32le_sha256": sha256(packed),
            "first_token_id": ids[0],
            "last_token_id": ids[-1],
        }
    args.output.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
