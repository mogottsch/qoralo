#!/usr/bin/env python3
"""Create a deterministic inventory for tracked package files and ignored evidence."""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, load_json, sha256_file, write_json

EXCLUDED_DIRECTORY_NAMES = {".cache", ".venv", ".pytest_cache", "__pycache__"}


def role(path: Path) -> str:
    value = path.relative_to(EXPERIMENT_ROOT).as_posix()
    if value == "generated/model.static-qdq-s8s8-generator-fp32.onnx":
        return "selected_mixed_s8s8_candidate"
    if value == "generated/model.static-qdq-s8s8.onnx":
        return "bit_exact_rebuild_of_selected_candidate"
    if value == "generated/trial-generator-fp32-s8s8.onnx":
        return "historical_bit_exact_selected_recipe_trial"
    if value == "generated/model.dynamic-default.qint8.onnx":
        return "rejected_cpu_incompatible_dynamic_candidate"
    if value == "generated/screening/full-eligible-s8s8.onnx":
        return "rejected_full_eligible_static_screening_candidate"
    if value in {
        "generated/screening/linear-only-s8s8.onnx",
        "generated/trial-linear-s8s8.onnx",
    }:
        return "non_selected_linear_only_static_screening_candidate"
    if value == "generated/blind/kokoro-int8-listening.zip":
        return "blind_listening_artifact_for_moritz"
    if value == "generated/blind/answer-key.json":
        return "secret_answer_key_keep_from_listener"
    if value == "generated/blind/seed.hex":
        return "secret_blinding_seed_keep_from_listener"
    if value.startswith("generated/audio/fp32/"):
        return "selected_gate_fp32_wav"
    if value.startswith("generated/audio/int8/"):
        return "selected_gate_int8_wav"
    if value.startswith("generated/screening/") and value.endswith(".wav"):
        return "screening_wav"
    if "trial-" in value and value.endswith(".wav"):
        return "historical_screening_wav"
    if value.startswith("generated/") and value.endswith(".log"):
        return "retained_execution_log"
    if value.startswith("generated/"):
        return "retained_historical_or_intermediate_evidence"
    if value.startswith("reports/"):
        return "committable_report"
    if value.startswith("scripts/"):
        return "reproduction_code"
    if value.startswith("tests/"):
        return "focused_test"
    if value.startswith("screening/"):
        return "screening_recipe"
    if value.endswith(".md"):
        return "documentation"
    return "committable_input_or_lock"


def media_type(path: Path) -> str:
    return {
        ".onnx": "application/onnx",
        ".wav": "audio/wav-pcm16-mono-24000hz",
        ".zip": "application/zip",
        ".json": "application/json",
        ".md": "text/markdown",
        ".py": "text/x-python",
        ".sh": "text/x-shellscript",
        ".log": "text/plain",
        ".lock": "text/plain",
        ".hex": "text/plain",
    }.get(path.suffix, "application/octet-stream")


def discover(output: Path) -> list[Path]:
    values: list[Path] = []
    for path in EXPERIMENT_ROOT.rglob("*"):
        relative = path.relative_to(EXPERIMENT_ROOT)
        if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts):
            continue
        if path == output:
            continue
        if path.is_symlink():
            raise RuntimeError(f"package contains an unexpected symlink: {path}")
        if path.is_file() and path.suffix != ".pyc":
            values.append(path)
    return sorted(values, key=lambda item: item.relative_to(EXPERIMENT_ROOT).as_posix())


def entry(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(EXPERIMENT_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "role": role(path),
        "media_type": media_type(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "package-manifest.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != EXPERIMENT_ROOT:
        raise RuntimeError("package manifest must live at the experiment root")

    paths = discover(output)
    entries = [entry(path) for path in paths]
    generated = [item for item in entries if item["path"].startswith("generated/")]
    committable = [item for item in entries if not item["path"].startswith("generated/")]
    aliases: dict[str, list[str]] = defaultdict(list)
    for item in entries:
        aliases[item["sha256"]].append(item["path"])
    duplicate_groups = [
        {"sha256": digest, "paths": sorted(values)}
        for digest, values in sorted(aliases.items())
        if len(values) > 1
    ]

    quantization = load_json(EXPERIMENT_ROOT / "reports/quantization-report.json")
    blind = load_json(EXPERIMENT_ROOT / "reports/blind-package.json")
    gate = load_json(EXPERIMENT_ROOT / "reports/quality-gate.json")
    report = {
        "schema_version": 1,
        "status": gate["quality_gate"]["overall_status"],
        "scope": "Complete Kokoro INT8 host quantization-quality package inventory",
        "selected_candidate": {
            "path": quantization["candidate"]["path"],
            "bytes": quantization["candidate"]["bytes"],
            "sha256": quantization["candidate"]["sha256"],
        },
        "blind_listening_artifact": blind["package"],
        "inventory_policy": {
            "generated_directory_is_gitignored": True,
            "every_current_generated_regular_file_is_hash_pinned_below": True,
            "cache_and_virtual_environment_excluded": [".cache/", ".venv/", ".pytest_cache/", "__pycache__/", "*.pyc"],
            "manifest_excludes_itself": True,
            "clean_checkout_note": "Ignored artifacts can be absent in a clean checkout; restore only bytes matching this manifest or regenerate a new hash-addressed evidence set.",
        },
        "counts": {
            "committable_file_count_excluding_manifest": len(committable),
            "generated_evidence_file_count": len(generated),
            "generated_evidence_bytes": sum(item["bytes"] for item in generated),
        },
        "committable_files": committable,
        "generated_evidence": generated,
        "identical_content_aliases": duplicate_groups,
    }
    write_json(output, report)
    print(
        f"package manifest: {output} "
        f"({len(committable)} committable, {len(generated)} generated files)"
    )


if __name__ == "__main__":
    main()
