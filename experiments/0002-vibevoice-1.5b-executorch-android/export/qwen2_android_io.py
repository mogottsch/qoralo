#!/usr/bin/env python3
"""Prepare Qwen2 prefill raw tensors and compare all 58 ordered Android outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from diagnose_qwen2 import evaluate_acceptance
from qwen2_backbone import cache_tensor_names
from validate_qwen2_fixtures import expected_outputs
from validate_qwen2_pte import compare_outputs

INPUTS = ("inputs-embeds.f32le", "attention-mask.i64le", "position-ids.i64le", "cache-position.i64le")
OUTPUT_NAMES = ("last_hidden_state", "next_token_logits", *cache_tensor_names(28))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_tensor(path: Path, tensor: torch.Tensor) -> None:
    path.write_bytes(tensor.detach().cpu().contiguous().numpy().tobytes())


def read_float(path: Path, shape: tuple[int, ...]) -> torch.Tensor:
    expected = torch.empty(shape, dtype=torch.float32).numel()
    data = torch.frombuffer(bytearray(path.read_bytes()), dtype=torch.float32)
    if data.numel() != expected:
        raise ValueError(f"{path}: expected {expected} floats, got {data.numel()}")
    return data.reshape(shape).clone()


def prepare(fixture_dir: Path, output: Path) -> None:
    fixture = torch.load(fixture_dir / "prefill.pt", map_location="cpu", weights_only=True)
    output.mkdir(parents=True, exist_ok=True)
    tensors = (fixture["inputs_embeds"].float(), fixture["attention_mask"].long(),
               fixture["position_ids"].long(), fixture["cache_position"].long())
    metadata = {"prefill_length": int(tensors[0].shape[1]), "cache_capacity": int(tensors[1].shape[1]), "inputs": []}
    for name, tensor in zip(INPUTS, tensors):
        path = output / name
        write_tensor(path, tensor)
        metadata["inputs"].append({"file": name, "shape": list(tensor.shape),
                                   "dtype": str(tensor.dtype).removeprefix("torch."),
                                   "bytes": path.stat().st_size, "sha256": sha256(path)})
    (output / "input-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


def compare(fixture_dir: Path, artifact_dir: Path, device_result: Path,
            repeat_result: Path | None, package_manifest: Path,
            device_properties: Path, preflight: Path, output: Path,
            implementation_commit: str | None) -> int:
    fixture = torch.load(fixture_dir / "prefill.pt", map_location="cpu", weights_only=True)
    expected = expected_outputs(fixture)
    actual = tuple(read_float(artifact_dir / f"output-{i:02d}.f32le", tuple(value.shape))
                   for i, value in enumerate(expected))
    strict = compare_outputs(actual, expected, 1e-5, 1e-4)
    acceptance = evaluate_acceptance(strict)
    device = json.loads(device_result.read_text())
    repeat = json.loads(repeat_result.read_text()) if repeat_result else None
    package = json.loads(package_manifest.read_text())
    properties = json.loads(device_properties.read_text())
    host_preflight = json.loads(preflight.read_text())
    internal_repeat_equal = bool(device.get("repeat_exact"))
    external_repeat_equal = repeat is None or device.get("ordered_output_sha256") == repeat.get("ordered_output_sha256")
    repeat_equal = internal_repeat_equal and external_repeat_equal
    passed = device.get("status") == "passed" and acceptance["bounded_xnnpack_accepted"] and repeat_equal
    result = {
        "schema_version": 1,
        "status": "passed" if passed else "failed",
        "component": "qwen2_prefill_android_sequential_fp32_xnnpack",
        "source_revision": "6dd49cb7200c0367205a5f1e650244259e9e423d",
        "model_revision": "c00898d257e6b46004e3e2866a47534085fb685a",
        "packaging": {
            "rationale": package["packaging_rationale"],
            "graph_boundaries": package["graph_boundaries"],
            "stage_count": package["stage_count"],
            "total_bytes": package["total_bytes"],
            "largest_stage_bytes": package["largest_stage_bytes"],
            "manifest_sha256": sha256(package_manifest),
            "host_revalidation": package["host_revalidation"],
        },
        "output_order": list(OUTPUT_NAMES),
        "ordered_output_count": len(OUTPUT_NAMES),
        "strict": strict,
        "accepted_component_specific": acceptance,
        "repeat_hash_equal": repeat_equal,
        "device_result": device,
        "repeat_device_result": repeat,
        "preflight": host_preflight,
        "device": properties,
        "runtime": device.get("runtime", {"executorch": "1.2.0", "backend": "xnnpack", "precision": "fp32"}),
        "commands": [
            "flock artifacts/locks/heavy-ram.lock .venv/bin/python export/package_qwen2_prefill.py --model artifacts/models/VibeVoice-1.5B --fixture-dir artifacts/0002/lane-c/qwen2-fixtures --output artifacts/0002/lane-c/qwen2-prefill-android-package",
            "android/run-qwen2-probe.sh",
            "python export/qwen2_android_io.py compare <fixture-dir> <artifact-dir> <device-result> results/qwen2-prefill-android.json --package-manifest <manifest> --device-properties <properties> --preflight <preflight>",
        ],
        "implementation_commits": [implementation_commit] if implementation_commit else [],
        "conclusion": (
            "The 30-stage sequential FP32 package completed prefill on the Galaxy S23 Ultra, "
            "preserved the ordered logits plus 56-cache ABI, and met the bounded Qwen2 FP32 "
            "XNNPACK criterion while the unchanged strict tolerance remains reported."
            if passed else
            "Android execution or the bounded Qwen2 FP32 XNNPACK acceptance criterion failed."
        ),
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if passed else 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("fixture_dir", type=Path); prep.add_argument("output", type=Path)
    check = commands.add_parser("compare")
    check.add_argument("fixture_dir", type=Path); check.add_argument("artifact_dir", type=Path)
    check.add_argument("device_result", type=Path); check.add_argument("output", type=Path)
    check.add_argument("--repeat-result", type=Path)
    check.add_argument("--package-manifest", type=Path, required=True)
    check.add_argument("--device-properties", type=Path, required=True)
    check.add_argument("--preflight", type=Path, required=True)
    check.add_argument("--implementation-commit")
    args = parser.parse_args()
    if args.command == "prepare": prepare(args.fixture_dir, args.output); return
    raise SystemExit(compare(args.fixture_dir, args.artifact_dir, args.device_result,
                             args.repeat_result, args.package_manifest,
                             args.device_properties, args.preflight, args.output,
                             args.implementation_commit))


if __name__ == "__main__": main()
