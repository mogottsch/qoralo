#!/usr/bin/env python3
"""Generate the nine thread-sweep descriptors from immutable experiment 0008 inputs.

The descriptor bytes are copied verbatim except for the single ``num_threads``
integer.  ``--check`` is fail-closed and does not rewrite committed evidence.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

SWEEP_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = SWEEP_ROOT / "protocol" / "sweep-plan.json"
DESCRIPTOR_DIR = SWEEP_ROOT / "descriptors"
THREADS = (1, 2, 4)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def resolve_from_plan(value: str) -> Path:
    return (PLAN_PATH.parent / value).resolve()


def generated_payload(source: bytes, threads: int) -> bytes:
    pattern = re.compile(rb'("num_threads"\s*:\s*)1(?=\s*[,}])')
    payload, count = pattern.subn(lambda match: match.group(1) + str(threads).encode("ascii"), source)
    if count != 1:
        raise ValueError(f"source descriptor must contain exactly one num_threads=1 field; found {count}")
    return payload


def build_outputs() -> tuple[dict[Path, bytes], dict]:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    transcript = resolve_from_plan(plan["transcript"]["source"])
    if sha256_file(transcript) != plan["transcript"]["sha256"]:
        raise ValueError("frozen transcript hash drift")
    if transcript.stat().st_size != plan["transcript"]["byte_count"]:
        raise ValueError("frozen transcript byte count drift")
    if transcript.read_bytes().endswith(b"\n") != plan["transcript"]["trailing_newline"]:
        raise ValueError("frozen transcript newline contract drift")

    outputs: dict[Path, bytes] = {}
    rows: list[dict] = []
    for candidate, candidate_spec in plan["candidates"].items():
        source_path = resolve_from_plan(candidate_spec["source_descriptor"])
        source = source_path.read_bytes()
        source_hash = sha256_bytes(source)
        if source_hash != candidate_spec["source_descriptor_sha256"]:
            raise ValueError(f"source descriptor hash drift for {candidate}")
        source_json = json.loads(source)
        if source_json.get("candidate") != candidate:
            raise ValueError(f"candidate mismatch in source descriptor for {candidate}")
        if source_json.get("provider") != "cpu" or source_json.get("num_threads") != 1:
            raise ValueError(f"source descriptor is not the pinned one-thread CPU deployment for {candidate}")
        if source_json.get("warm_runs") != 3:
            raise ValueError(f"source descriptor warm-run count drift for {candidate}")
        if source_json.get("transcript_sha256") != plan["transcript"]["sha256"]:
            raise ValueError(f"source descriptor transcript drift for {candidate}")

        for threads in THREADS:
            payload = generated_payload(source, threads)
            parsed = json.loads(payload)
            expected = copy.deepcopy(source_json)
            expected["num_threads"] = threads
            if parsed != expected:
                raise ValueError(f"generated descriptor changed fields other than num_threads for {candidate}/{threads}")
            relative = Path(f"{candidate}-t{threads}.json")
            outputs[DESCRIPTOR_DIR / relative] = payload
            rows.append({
                "candidate": candidate,
                "threads": threads,
                "path": relative.as_posix(),
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "source_path": candidate_spec["source_descriptor"],
                "source_sha256": source_hash,
                "semantic_change_from_source": {"num_threads": {"from": 1, "to": threads}},
            })

    manifest = {
        "schema_version": 1,
        "generator": "tools/generate_descriptors.py",
        "generator_rule": "Source bytes are preserved except for the single num_threads integer.",
        "transcript_sha256": plan["transcript"]["sha256"],
        "provider": "cpu",
        "descriptors": rows,
    }
    manifest_payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    outputs[DESCRIPTOR_DIR / "manifest.json"] = manifest_payload
    return outputs, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify committed outputs without rewriting them")
    args = parser.parse_args()
    outputs, _ = build_outputs()
    failures: list[str] = []
    for path, expected in outputs.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != expected:
                failures.append(str(path.relative_to(SWEEP_ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    if failures:
        raise SystemExit("descriptor drift: " + ", ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
