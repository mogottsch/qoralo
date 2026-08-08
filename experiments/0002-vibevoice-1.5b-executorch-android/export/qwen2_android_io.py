#!/usr/bin/env python3
"""Prepare Qwen2 Android inputs and verify chained prefill plus one-token decode."""

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

INPUT_SPECS = {
    "prefill": ("inputs_embeds", "attention_mask", "position_ids", "cache_position"),
    "decode": ("inputs_embeds", "attention_mask", "position_ids", "cache_position"),
}
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


def _validate_control(prefill: dict, decode: dict) -> dict:
    prefill_length = int(prefill["inputs_embeds"].shape[1])
    capacity = int(prefill["attention_mask"].shape[1])
    decode_position = int(decode["cache_position"].item())
    if decode_position != prefill_length:
        raise ValueError(f"decode position {decode_position} != prefill length {prefill_length}")
    if capacity <= decode_position:
        raise ValueError(f"cache capacity {capacity} cannot hold decode position {decode_position}")
    if tuple(decode["attention_mask"].shape) != (1, capacity):
        raise ValueError("decode attention mask does not preserve fixed cache capacity")
    if int(decode["position_ids"].item()) != decode_position:
        raise ValueError("decode position_ids and cache_position differ")
    if not torch.all(decode["attention_mask"][:, : decode_position + 1] == 1):
        raise ValueError("decode attention mask does not cover the valid prefix")
    if torch.count_nonzero(decode["attention_mask"][:, decode_position + 1 :]).item():
        raise ValueError("decode attention mask exposes unused cache capacity")
    if len(prefill["post_cache"]) != 56 or len(decode["pre_cache"]) != 56:
        raise ValueError("normative Qwen2 cache ABI requires 56 tensors")
    for index, (produced, consumed) in enumerate(zip(prefill["post_cache"], decode["pre_cache"])):
        if not torch.equal(produced, consumed):
            raise ValueError(f"fixture cache handoff differs at ABI index {index}")
        if tuple(produced.shape) != (1, 2, capacity, 128):
            raise ValueError(f"cache ABI index {index} has invalid shape {tuple(produced.shape)}")
    return {"prefill_length": prefill_length, "decode_position": decode_position,
            "decode_valid_length": decode_position + 1, "cache_capacity": capacity}


def prepare(fixture_dir: Path, output: Path) -> None:
    fixtures = {
        name: torch.load(fixture_dir / f"{name}.pt", map_location="cpu", weights_only=True)
        for name in INPUT_SPECS
    }
    control = _validate_control(fixtures["prefill"], fixtures["decode"])
    output.mkdir(parents=True, exist_ok=True)
    metadata = {**control, "cache_order": cache_tensor_names(28), "inputs": []}
    # Only four control/data tensors per phase are serialized. In particular,
    # decode.pre_cache is intentionally never written: Android must consume the
    # cache arrays returned by its immediately preceding prefill execution.
    for phase, keys in INPUT_SPECS.items():
        for key in keys:
            tensor = fixtures[phase][key].float() if key == "inputs_embeds" else fixtures[phase][key].long()
            suffix = "f32le" if tensor.dtype == torch.float32 else "i64le"
            filename = f"{phase}-{key.replace('_', '-')}.{suffix}"
            path = output / filename
            write_tensor(path, tensor)
            metadata["inputs"].append({"phase": phase, "name": key, "file": filename,
                                       "shape": list(tensor.shape),
                                       "dtype": str(tensor.dtype).removeprefix("torch."),
                                       "bytes": path.stat().st_size, "sha256": sha256(path)})
    metadata["fixture_cache_serialized"] = False
    (output / "input-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


def _read_outputs(fixture: dict, artifact_dir: Path, prefix: str) -> tuple[torch.Tensor, ...]:
    expected = expected_outputs(fixture)
    return tuple(read_float(artifact_dir / f"{prefix}-output-{i:02d}.f32le", tuple(value.shape))
                 for i, value in enumerate(expected))


def compare(fixture_dir: Path, artifact_dir: Path, device_result: Path,
            repeat_result: Path | None, package_manifest: Path,
            device_properties: Path, preflight: Path, output: Path,
            implementation_commit: str | None) -> int:
    prefill_fixture = torch.load(fixture_dir / "prefill.pt", map_location="cpu", weights_only=True)
    decode_fixture = torch.load(fixture_dir / "decode.pt", map_location="cpu", weights_only=True)
    control = _validate_control(prefill_fixture, decode_fixture)
    prefill_actual = _read_outputs(prefill_fixture, artifact_dir, "prefill")
    decode_actual = _read_outputs(decode_fixture, artifact_dir, "decode")
    prefill_strict = compare_outputs(prefill_actual, expected_outputs(prefill_fixture), 1e-5, 1e-4)
    decode_strict = compare_outputs(decode_actual, expected_outputs(decode_fixture), 1e-5, 1e-4)
    prefill_acceptance = evaluate_acceptance(prefill_strict)
    decode_acceptance = evaluate_acceptance(decode_strict)
    device = json.loads(device_result.read_text())
    repeat = json.loads(repeat_result.read_text()) if repeat_result else None
    package = json.loads(package_manifest.read_text())
    properties = json.loads(device_properties.read_text())
    host_preflight = json.loads(preflight.read_text())
    internal_repeat_equal = bool(device.get("repeat_exact"))
    external_repeat_equal = repeat is None or device.get("decode_ordered_output_sha256") == repeat.get("decode_ordered_output_sha256")
    repeat_equal = internal_repeat_equal and external_repeat_equal
    handoff = device.get("cache_handoff", {})
    handoff_valid = (handoff.get("source") == "android_prefill_outputs"
                     and handoff.get("tensor_count") == 56
                     and handoff.get("prefill_cache_sha256") == handoff.get("decode_input_cache_sha256"))
    passed = (device.get("status") == "passed" and prefill_acceptance["bounded_xnnpack_accepted"]
              and decode_acceptance["bounded_xnnpack_accepted"] and repeat_equal and handoff_valid)
    host_validation = package["host_revalidation"]
    result = {
        "schema_version": 1,
        "status": "passed" if passed else "failed",
        "component": "qwen2_single_token_decode_android_sequential_fp32_xnnpack",
        "source_revision": "6dd49cb7200c0367205a5f1e650244259e9e423d",
        "model_revision": "c00898d257e6b46004e3e2866a47534085fb685a",
        "control": {**control, "logits_checked": True, "positions_checked": True,
                    "masks_checked": True, "valid_length_checked": True,
                    "capacity_checked": True, "fixture_cache_serialized": False},
        "cache_handoff": handoff,
        "cache_order": cache_tensor_names(28),
        "ordered_output_names": list(OUTPUT_NAMES),
        "ordered_output_count": len(OUTPUT_NAMES),
        "prefill_strict": prefill_strict,
        "prefill_accepted_component_specific": prefill_acceptance,
        "strict": decode_strict,
        "accepted_component_specific": decode_acceptance,
        "repeat_hash_equal": repeat_equal,
        "device_result": device,
        "repeat_device_result": repeat,
        "packaging": {"stage_count": package["stage_count"], "total_bytes": package["total_bytes"],
                      "largest_stage_bytes": package["largest_stage_bytes"],
                      "manifest_sha256": sha256(package_manifest),
                      "host_revalidation": host_validation},
        "preflight": host_preflight,
        "device": properties,
        "runtime": device.get("runtime", {"executorch": "1.2.0", "backend": "xnnpack", "precision": "fp32"}),
        "commands": [
            "flock artifacts/locks/heavy-ram.lock bash -lc 'PATH=$PWD/artifacts/venv-executorch-1.2/bin:$PATH artifacts/venv-executorch-1.2/bin/python experiments/0002-vibevoice-1.5b-executorch-android/export/package_qwen2_prefill.py --model artifacts/models/microsoft-VibeVoice-1.5B --fixture-dir artifacts/0002/lane-c/qwen2-fixtures --output artifacts/0002/lane-c/qwen2-prefill-android-package'", 
            "android/run-qwen2-probe.sh",
            "python export/qwen2_android_io.py compare <fixture-dir> <artifact-dir> <device-result> results/qwen2-decode-android.json --package-manifest <manifest> --device-properties <properties> --preflight <preflight>",
        ],
        "implementation_commits": [implementation_commit] if implementation_commit else [],
        "conclusion": ("Galaxy S23 Ultra one-token decode consumed all 56 caches produced by the immediately preceding Android prefill in normative order; logits and updated caches met the bounded FP32 XNNPACK criterion, with unchanged strict metrics retained."
                       if passed else "Android cache chaining, determinism, or the bounded Qwen2 FP32 XNNPACK criterion failed."),
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if passed else 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare"); prep.add_argument("fixture_dir", type=Path); prep.add_argument("output", type=Path)
    check = commands.add_parser("compare")
    check.add_argument("fixture_dir", type=Path); check.add_argument("artifact_dir", type=Path)
    check.add_argument("device_result", type=Path); check.add_argument("output", type=Path)
    check.add_argument("--repeat-result", type=Path); check.add_argument("--package-manifest", type=Path, required=True)
    check.add_argument("--device-properties", type=Path, required=True); check.add_argument("--preflight", type=Path, required=True)
    check.add_argument("--implementation-commit")
    args = parser.parse_args()
    if args.command == "prepare": prepare(args.fixture_dir, args.output); return
    raise SystemExit(compare(args.fixture_dir, args.artifact_dir, args.device_result,
                             args.repeat_result, args.package_manifest, args.device_properties,
                             args.preflight, args.output, args.implementation_commit))


if __name__ == "__main__": main()
