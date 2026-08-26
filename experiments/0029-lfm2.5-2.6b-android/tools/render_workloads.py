#!/usr/bin/env python3
"""Render the canonical two-message workload with LFM2.5's pinned native template."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render(messages: list[dict[str, str]]) -> bytes:
    if [message.get("role") for message in messages] != ["system", "user"]:
        raise ValueError("this locked renderer accepts exactly system + user")
    system = messages[0]["content"]
    user = messages[1]["content"]
    # Exact reachable specialization of LiquidAI's pinned chat_template.jinja:
    # no tools, add_generation_prompt=true. LFM2.5 always starts with <think>.
    text = (
        "<|startoftext|><|im_start|>system\n"
        + system
        + "<|im_end|>\n<|im_start|>user\n"
        + user
        + "<|im_end|>\n<|im_start|>assistant\n<think>"
    )
    return text.encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, object]] = {}
    for tier in ("short", "medium", "long"):
        source = args.workload_dir / f"{tier}.json"
        workload_bytes = source.read_bytes()
        workload = json.loads(workload_bytes)
        rendered = render(workload["messages"])
        target = args.output_dir / f"{tier}.txt"
        target.write_bytes(rendered)
        manifest[tier] = {
            "canonical_workload_sha256": sha256(workload_bytes),
            "rendered_path": target.name,
            "rendered_bytes": len(rendered),
            "rendered_sha256": sha256(rendered),
        }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
