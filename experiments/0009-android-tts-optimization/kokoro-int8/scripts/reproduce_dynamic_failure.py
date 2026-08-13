#!/usr/bin/env python3
"""Reproduce and retain the rejected default dynamic-QInt8 CPU failure."""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, load_json, sha256_file, validate_source, write_json
from quantize import verify_toolchain


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=EXPERIMENT_ROOT / "generated" / "model.dynamic-default.qint8.onnx",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=EXPERIMENT_ROOT / "reports" / "dynamic-qint8-failure.json",
    )
    parser.add_argument("--source-manifest", type=Path, default=EXPERIMENT_ROOT / "source-manifest.json")
    parser.add_argument("--toolchain-lock", type=Path, default=EXPERIMENT_ROOT / "toolchain.lock.json")
    parser.add_argument("--wheel-dir", type=Path, default=EXPERIMENT_ROOT / ".cache" / "wheels")
    parser.add_argument("--espeak-bin", type=Path, default=Path("/usr/bin/espeak-ng"))
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    source = validate_source(source_root, args.source_manifest, verify_archive=True)
    tools = verify_toolchain(args.toolchain_lock, args.wheel_dir, args.espeak_bin)

    import onnxruntime as ort
    from onnxruntime.quantization import QuantType, quantize_dynamic

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    temporary.unlink(missing_ok=True)
    started = time.perf_counter()
    quantize_dynamic(
        str(source_root / "model.onnx"),
        str(temporary),
        per_channel=True,
        weight_type=QuantType.QInt8,
    )
    quantization_seconds = time.perf_counter() - started
    temporary.replace(args.output)

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    error: dict[str, Any]
    try:
        ort.InferenceSession(str(args.output), options, providers=["CPUExecutionProvider"])
    except Exception as caught:
        message = str(caught)
        if "NOT_IMPLEMENTED" not in message or "ConvInteger(10)" not in message:
            raise RuntimeError(f"dynamic candidate failed differently than pinned evidence: {message}") from caught
        error = {"type": type(caught).__name__, "message": message}
    else:
        raise RuntimeError("dynamic candidate unexpectedly became CPU-loadable; review runtime drift before proceeding")

    report = {
        "schema_version": 1,
        "status": "reproduced_rejected_cpu_incompatible",
        "purpose": "Retain the failed dynamic-QInt8 attempt; it is not the selected candidate.",
        "source": source,
        "method": {
            "api": "onnxruntime.quantization.quantize_dynamic",
            "op_types_to_quantize": "onnxruntime_1.22.1_default_eligible_operators",
            "weight_type": "QInt8",
            "per_channel": True,
        },
        "tools": tools,
        "output": {
            "path": args.output.resolve().relative_to(EXPERIMENT_ROOT).as_posix(),
            "bytes": args.output.stat().st_size,
            "sha256": sha256_file(args.output),
        },
        "cpu_probe": {
            "runtime": f"onnxruntime {ort.__version__}",
            "requested_providers": ["CPUExecutionProvider"],
            "num_threads": 1,
            "session_constructed": False,
            "error": error,
        },
        "timing_context_only": {
            "quantization_seconds": quantization_seconds,
            "not_android_evidence": True,
        },
        "resolution": "Reject dynamic QInt8. Use the selected calibrated static S8S8 QDQ mixed-precision candidate.",
    }
    write_json(args.report, report)
    print(f"reproduced expected CPU incompatibility: {args.report}")
    print(f"rejected model: {report['output']['bytes']} bytes, {report['output']['sha256']}")


if __name__ == "__main__":
    main()
