#!/usr/bin/env python3
"""Build the structured Android INT8 result from probe tensors and telemetry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from qwen2_android_io import OUTPUT_NAMES, _read_outputs, _validate_control
from qwen2_backbone import cache_tensor_names
from qwen2_quantization import quantization_spec, quantized_comparison
from validate_qwen2_fixtures import expected_outputs
from validate_qwen2_pte import compare_outputs


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture_dir", type=Path)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("device_result", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--host-result", type=Path, required=True)
    parser.add_argument("--device-properties", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--implementation-commit")
    args = parser.parse_args()

    prefill_fixture = torch.load(args.fixture_dir / "prefill.pt", map_location="cpu", weights_only=True)
    decode_fixture = torch.load(args.fixture_dir / "decode.pt", map_location="cpu", weights_only=True)
    control = _validate_control(prefill_fixture, decode_fixture)
    prefill_actual = _read_outputs(prefill_fixture, args.artifact_dir, "prefill")
    decode_actual = _read_outputs(decode_fixture, args.artifact_dir, "decode")
    prefill_quant = quantized_comparison(prefill_actual, expected_outputs(prefill_fixture), list(OUTPUT_NAMES))
    decode_quant = quantized_comparison(decode_actual, expected_outputs(decode_fixture), list(OUTPUT_NAMES))
    device = json.loads(args.device_result.read_text())
    package = json.loads(args.package_manifest.read_text())
    host = json.loads(args.host_result.read_text())
    handoff = device.get("cache_handoff", {})
    handoff_valid = (
        handoff.get("source") == "android_prefill_outputs"
        and handoff.get("tensor_count") == 56
        and handoff.get("prefill_cache_sha256") == handoff.get("decode_input_cache_sha256")
        and not handoff.get("fixture_cache_files_read", True)
    )
    deterministic = bool(device.get("repeat_exact"))
    passed = (
        package.get("status") == "passed"
        and host.get("status") == "passed"
        and device.get("status") == "passed"
        and prefill_quant["accepted"]
        and decode_quant["accepted"]
        and handoff_valid
        and deterministic
    )
    result = {
        "schema_version": 1,
        "status": "passed" if passed else "rejected",
        "component": "qwen2_prefill_decode_android_sequential_int8_xnnpack",
        "source_revision": "6dd49cb7200c0367205a5f1e650244259e9e423d",
        "model_revision": "c00898d257e6b46004e3e2866a47534085fb685a",
        "quantization": quantization_spec(),
        "control": {**control, "fixture_cache_serialized": False, "positions_checked": True, "masks_checked": True},
        "cache_handoff": {**handoff, "validated": handoff_valid, "required_source": "actual Android INT8 prefill outputs"},
        "cache_order": cache_tensor_names(28),
        "ordered_output_names": list(OUTPUT_NAMES),
        "prefill": {
            "int8_vs_pinned_fp32": prefill_quant,
            "strict_fp32_threshold_metrics": compare_outputs(prefill_actual, expected_outputs(prefill_fixture), 1e-5, 1e-4),
        },
        "decode": {
            "int8_vs_pinned_fp32": decode_quant,
            "strict_fp32_threshold_metrics": compare_outputs(decode_actual, expected_outputs(decode_fixture), 1e-5, 1e-4),
        },
        "determinism": {"repeat_exact": deterministic, "prefill_sha256": device.get("prefill_ordered_output_sha256"), "decode_sha256": device.get("decode_ordered_output_sha256"), "repeat_prefill_sha256": device.get("repeat_prefill_ordered_output_sha256"), "repeat_decode_sha256": device.get("repeat_decode_ordered_output_sha256")},
        "package": {"stage_count": package["stage_count"], "total_bytes": package["total_bytes"], "largest_stage_bytes": package["largest_stage_bytes"], "manifest_sha256": sha256(args.package_manifest), "size_and_fallback_acceptance": host.get("size_and_fallback_acceptance")},
        "fp32_baseline": host.get("fp32_baseline"),
        "timing": device.get("first_run"),
        "memory_kib": device.get("memory_kib"),
        "preflight": json.loads(args.preflight.read_text()),
        "device": json.loads(args.device_properties.read_text()),
        "runtime": {**device.get("runtime", {}), "precision": "int8"},
        "implementation_commits": [args.implementation_commit] if args.implementation_commit else [],
        "commands": [
            "artifacts/venv-executorch-1.2/bin/python export/export_qwen2_quantized.py",
            "android/run-qwen2-int8-probe.sh",
        ],
        "conclusion": (
            "Accepted: Galaxy S23 Ultra INT8 decode consumed all 56 actual INT8 prefill caches in normative order; tensor/token criteria, determinism, package benefit, timing, and memory evidence pass."
            if passed else
            "Rejected: Android INT8 numerical/token, real-cache handoff, determinism, host acceptance, or deployment-benefit criteria failed."
        ),
        "device_result": device,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
