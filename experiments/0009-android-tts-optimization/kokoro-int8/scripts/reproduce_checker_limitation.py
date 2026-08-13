#!/usr/bin/env python3
"""Reproduce the ONNX checker limitation on both exact source and candidate."""
from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, PROJECT_ROOT, load_json, sha256_file, validate_source, write_json


def checker_error(path: Path) -> dict[str, Any]:
    import onnx

    try:
        onnx.checker.check_model(str(path), full_check=True)
    except onnx.checker.ValidationError as caught:
        message = str(caught)
        required = ("topologically sorted", "/SplitToSequence_output_0", "/SequenceAt", "/Loop")
        if not all(fragment in message for fragment in required):
            raise RuntimeError(f"checker failed differently for {path}: {message}") from caught
        return {"type": type(caught).__name__, "message": message}
    raise RuntimeError(f"checker unexpectedly accepted candidate {path}; review tool drift")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, default=EXPERIMENT_ROOT / "source-manifest.json")
    parser.add_argument("--quantization-report", type=Path, default=EXPERIMENT_ROOT / "reports/quantization-report.json")
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "reports/checker-limitation.json")
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    validate_source(source_root, args.source_manifest, verify_archive=True)
    quantization = load_json(args.quantization_report)
    candidate_record = quantization["candidate"]
    candidate = EXPERIMENT_ROOT / candidate_record["path"]
    if (
        not candidate.is_file()
        or candidate.stat().st_size != candidate_record["bytes"]
        or sha256_file(candidate) != candidate_record["sha256"]
    ):
        raise RuntimeError("selected candidate pin drifted")
    source = source_root / "model.onnx"
    import onnx

    onnx.checker.check_model(str(source), full_check=True)
    candidate_error = checker_error(candidate)

    report = {
        "schema_version": 1,
        "status": "reproduced_quantizer_introduced_topological_order_limitation",
        "tool": {"onnx": importlib.metadata.version("onnx"), "full_check": True},
        "source": {
            "path": source.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": source.stat().st_size,
            "sha256": sha256_file(source),
            "checker_passed": True,
        },
        "candidate": {
            "path": candidate_record["path"],
            "bytes": candidate.stat().st_size,
            "sha256": sha256_file(candidate),
            "error": candidate_error,
        },
        "interpretation": "The exact source passes. ONNX Runtime quantization reorders the outer graph so a SplitToSequence producer follows the Loop that captures it; the checker diagnostic is introduced by quantization and is retained as a structural limitation.",
        "executable_integrity_gate": "Pinned ONNX Runtime CPU session construction/inference plus sherpa-onnx synthesis and full WAV decode all pass for the candidate.",
    }
    write_json(args.output, report)
    print(f"checker limitation reproduced for source and candidate: {args.output}")


if __name__ == "__main__":
    main()
