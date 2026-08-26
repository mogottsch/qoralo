#!/usr/bin/env python3
"""Copy runner evidence into a committed, hash-bound experiment result."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def token_ids_sha256(ids: list[int]) -> str:
    payload = b"".join(struct.pack("<i", value) for value in ids)
    return sha256_bytes(payload)


def finalize(input_dir: Path, output_dir: Path, scope: str, looks_sensible: bool | None,
             issue_notes: str | None = None) -> dict:
    raw_path = input_dir / "runner-result.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "outputs").mkdir(exist_ok=True)
    (output_dir / "rendered").mkdir(exist_ok=True)

    if looks_sensible is True and issue_notes is not None:
        raise ValueError("sensible output cannot carry issue notes")
    if looks_sensible is False and not issue_notes:
        raise ValueError("non-sensible output requires issue notes")
    if looks_sensible is None and issue_notes is not None:
        raise ValueError("unchecked output cannot carry issue notes")

    result = raw
    result["scope"] = scope
    result["source_runner_result_sha256"] = sha256_file(raw_path)
    result["host_is_android_evidence"] = False if scope.startswith("host_") else None
    if "route" in result and result["route"].get("model_path"):
        result["route"]["model_path"] = ".local/model/" + Path(
            result["route"]["model_path"]
        ).name

    for tier, prompt in result["prompts"].items():
        source = input_dir / prompt["rendered_relative_path"]
        destination = output_dir / "rendered" / f"{tier}.txt"
        shutil.copyfile(source, destination)
        prompt["rendered_path"] = f"rendered/{tier}.txt"
        prompt["rendered_sha256"] = sha256_file(destination)
        prompt["token_ids_int32le_sha256"] = token_ids_sha256(prompt.pop("token_ids"))
        prompt.pop("rendered_relative_path", None)

    for run in result["runs"]:
        source = input_dir / run["output_relative_path"]
        destination = output_dir / "outputs" / f"{run['id']}.txt"
        shutil.copyfile(source, destination)
        run["output"] = {
            "path": f"outputs/{run['id']}.txt",
            "sha256": sha256_file(destination),
            "bytes": destination.stat().st_size,
        }
        run["output_sanity"] = {
            "looks_sensible": looks_sensible,
            "issue_notes": issue_notes,
        }
        run["emitted_token_ids_int32le_sha256"] = token_ids_sha256(
            run.pop("emitted_token_ids")
        )
        run.pop("output_relative_path", None)

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--scope",
        choices=[
            "host_smoke",
            "host_reset_diagnostic",
            "android_smoke",
            "android_campaign",
            "android_reset_diagnostic",
        ],
        required=True,
    )
    parser.add_argument("--looks-sensible", choices=["true", "false", "null"], default="null")
    parser.add_argument("--issue-notes")
    args = parser.parse_args()
    status = {"true": True, "false": False, "null": None}[args.looks_sensible]
    result = finalize(args.input_dir, args.output_dir, args.scope, status, args.issue_notes)
    target = args.output_dir / "result.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
