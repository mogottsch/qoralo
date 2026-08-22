#!/usr/bin/env python3
"""Validate and summarize the ignored source/context Android stage packages."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def records(stage: Path) -> dict[str, dict[str, Any]]:
    return {str(path.relative_to(stage)): {"bytes": path.stat().st_size, "sha256": sha(path)}
            for path in sorted(stage.rglob("*")) if path.is_file()}


def parse_manifest(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text().splitlines():
        digest, relative = line.split(maxsplit=1)
        result[relative.removeprefix("./")] = digest
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-stage", type=Path, required=True)
    parser.add_argument("--context-stage", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--context-manifest", type=Path, required=True)
    parser.add_argument("--graph-inventory", type=Path, required=True)
    parser.add_argument("--host-context-evidence", type=Path, required=True)
    parser.add_argument("--readelf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = records(args.source_stage)
    context = records(args.context_stage)
    source_manifest = parse_manifest(args.source_manifest)
    context_manifest = parse_manifest(args.context_manifest)
    if {key: value["sha256"] for key, value in source.items()} != source_manifest:
        raise SystemExit("source stage manifest mismatch")
    if {key: value["sha256"] for key, value in context.items()} != context_manifest:
        raise SystemExit("context stage manifest mismatch")

    graph_inventory = json.loads(args.graph_inventory.read_text())["graphs"]
    expected_graphs = {f"model/{name}": value["sha256"] for name, value in graph_inventory.items()}
    actual_source_graphs = {name: value["sha256"] for name, value in source.items() if name.endswith(".onnx")}
    if actual_source_graphs != expected_graphs:
        raise SystemExit("source stage graph mismatch")

    host = json.loads(args.host_context_evidence.read_text())
    expected_context: dict[str, str] = {}
    for component in host["components"]:
        expected_context[f"model/{component['descriptor']['path']}"] = component["descriptor"]["sha256"]
        expected_context[f"model/{component['external_context_binary']['path']}"] = component["external_context_binary"]["sha256"]
    actual_context = {name: value["sha256"] for name, value in context.items()
                      if name.startswith("model/")}
    if actual_context != expected_context:
        raise SystemExit("context stage descriptor/binary mismatch")
    descriptors = {name: value for name, value in context.items() if name.endswith(".onnx")}
    if len(descriptors) != 8 or any(value["bytes"] >= 65536 for value in descriptors.values()):
        raise SystemExit("context source-absence package gate failed")
    if any(value["sha256"] in {item["sha256"] for item in graph_inventory.values()}
           for value in descriptors.values()):
        raise SystemExit("context package contains a source graph")

    common_names = sorted((set(source) & set(context)) - {name for name in source if name.startswith("model/")})
    if any(source[name] != context[name] for name in common_names):
        raise SystemExit("common runner/runtime/assets differ between arms")
    runner = args.source_stage / "pocket_context_benchmark_runner"
    readelf = subprocess.check_output([str(args.readelf), "-d", str(runner)], text=True)
    needed = [line.split("[")[1].split("]")[0] for line in readelf.splitlines() if "(NEEDED)" in line]
    expected_needed = ["libonnxruntime.so", "libc++_shared.so", "libm.so", "libdl.so", "libc.so"]
    if needed != expected_needed:
        raise SystemExit(f"unexpected runner linkage: {needed}")

    result = {
        "schema_version": 1,
        "date": "2026-08-22",
        "status": "source_and_context_android_stages_prepared_no_phone_access",
        "route": "pocket-fixed-alba-text64-cache512-canonical-v2-0024-reconstruction-derivative",
        "source_stage": {
            "manifest_sha256": sha(args.source_manifest),
            "file_count": len(source), "file_bytes_sum": sum(value["bytes"] for value in source.values()),
            "model_file_count": sum(name.startswith("model/") for name in source),
            "source_onnx_count": len(actual_source_graphs), "files": source,
        },
        "context_stage": {
            "manifest_sha256": sha(args.context_manifest),
            "file_count": len(context), "file_bytes_sum": sum(value["bytes"] for value in context.values()),
            "model_file_count": sum(name.startswith("model/") for name in context),
            "descriptor_count": len(descriptors),
            "external_binary_count": sum(name.endswith("_qnn.bin") for name in context),
            "source_onnx_absent": True, "files": context,
        },
        "matched_common_files": {name: source[name] for name in common_names},
        "runner": {
            "sha256": sha(runner), "bytes": runner.stat().st_size,
            "target": "ELF64 AArch64 PIE, Android API 27, NDK r26c",
            "needed": needed,
            "source_sha256": sha(Path(__file__).with_name("pocket_context_benchmark_runner.cc")),
        },
        "gates": {
            "source_graphs_match_documented_derivative_inventory": True,
            "context_descriptors_and_binaries_match_host_evidence": True,
            "context_stage_has_only_small_descriptors_no_source_graphs": True,
            "runner_runtime_assets_identical_between_arms": True,
            "manifest_recomputed_equal": True,
        },
        "phone": {"attempted": False, "phone_lock_acquired": False, "adb_invoked": False,
                  "reason": "Stage preparation only; device unavailable and 0023 retains first future phone window."},
        "portability": {"host_preparation_blocker": None,
                        "physical_context_load_status": None,
                        "boundary": "Host-generated QNN context portability and complete E2E remain unproven until the exact authorized phone returns."},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"source": {key: result["source_stage"][key] for key in ("manifest_sha256", "file_count", "file_bytes_sum")},
                      "context": {key: result["context_stage"][key] for key in ("manifest_sha256", "file_count", "file_bytes_sum")},
                      "runner": result["runner"]}, indent=2))


if __name__ == "__main__":
    main()
