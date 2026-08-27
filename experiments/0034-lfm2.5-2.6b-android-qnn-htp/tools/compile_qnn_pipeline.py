#!/usr/bin/env python3
"""Compile every static LFM2 pipeline part in isolated fail-closed processes."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parts-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    experiment = Path(__file__).resolve().parents[1]
    worker = experiment / "tools/compile_qnn_part.py"
    manifest = json.loads((args.parts_dir / "manifest.json").read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started_ns = time.time_ns()
    completed = []

    for index, part in enumerate(manifest["parts"], 1):
        name = part["name"]
        output = args.output_dir / name
        result_path = output / "result.json"
        if result_path.exists() and json.loads(result_path.read_text()).get("success"):
            result = json.loads(result_path.read_text())
            status = "reused"
        else:
            output.mkdir(parents=True, exist_ok=True)
            log_path = output / "compile.log"
            with log_path.open("wb") as log:
                process = subprocess.run(
                    [
                        str(args.python),
                        str(worker),
                        "--model",
                        str(args.parts_dir / part["path"]),
                        "--output-dir",
                        str(output),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            if not result_path.exists():
                raise RuntimeError(f"worker produced no result for {name}; see {log_path}")
            result = json.loads(result_path.read_text())
            if process.returncode or not result.get("success"):
                raise RuntimeError(f"QNN compilation failed for {name}; see {log_path}")
            status = "compiled"
        completed.append(
            {
                "name": name,
                "kind": part["kind"],
                "status": status,
                "context_model": result["context_model"],
                "context_binary": result["context_binary"],
                "framework_op_trace": result["framework_op_trace"],
                "session_create_seconds": result["session_create_seconds"],
                "session_disable_cpu_ep_fallback": result["session_disable_cpu_ep_fallback"],
            }
        )
        print(f"[{index}/{len(manifest['parts'])}] {name}: {status}", flush=True)

    summary = {
        "schema_version": 1,
        "classification": "host_aot_compilation_not_physical_android_execution",
        "source_manifest": str(args.parts_dir / "manifest.json"),
        "onnxruntime": "1.26.0",
        "onnxruntime_qnn": "2.5.0",
        "qnn_runtime": "2.49.40 bundled by onnxruntime-qnn 2.5.0 host package",
        "target": {"soc_model": 43, "chipset": "SM8550", "htp_arch": 73},
        "fallback_policy": "session.disable_cpu_ep_fallback=1 for every part",
        "block_quant_weight_optimization": True,
        "all_parts_compiled": True,
        "part_count": len(completed),
        "started_ns": started_ns,
        "stopped_ns": time.time_ns(),
        "parts": completed,
        "claim_boundary": "Target-specific host AOT and framework-op mapping only. Physical HTP execution still requires the authorized Android phone.",
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(args.output_dir / "summary.json")


if __name__ == "__main__":
    main()
