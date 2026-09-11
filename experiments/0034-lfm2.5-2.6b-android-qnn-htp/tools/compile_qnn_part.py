#!/usr/bin/env python3
"""Compile one static LFM2 pipeline part for SM8550/v73 with fail-closed QNN EP."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import traceback
from pathlib import Path

import onnxruntime as ort
import onnxruntime_qnn as qnn


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trace_dir = args.output_dir / "trace"
    trace_dir.mkdir(exist_ok=True)
    context_model = args.output_dir / "context.onnx"
    registration = "QNNExecutionProvider"
    result: dict[str, object] = {
        "schema_version": 1,
        "model": args.model.name,
        "model_bytes": args.model.stat().st_size,
        "model_sha256": sha256(args.model),
        "onnxruntime": ort.__version__,
        "onnxruntime_qnn": qnn.__version__,
        "target": {"soc_model": "43", "chipset": "SM8550", "htp_arch": "73"},
        "started_ns": time.time_ns(),
        "ort_intra_op_threads": args.threads,
        "ort_inter_op_threads": 1,
        "prepare_only": True,
        "graph_execution_requested": False,
    }
    exit_code = 0
    try:
        ort.register_execution_provider_library(registration, qnn.get_library_path())
        devices = [item for item in ort.get_ep_devices() if item.ep_name == registration]
        if not devices:
            raise RuntimeError("QNN EP device not found")
        options = ort.SessionOptions()
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.intra_op_num_threads = args.threads
        options.inter_op_num_threads = 1
        options.log_severity_level = 2
        options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        options.add_session_config_entry("ep.context_enable", "1")
        options.add_session_config_entry("ep.context_file_path", str(context_model))
        provider_options = {
            "backend_path": qnn.get_qnn_htp_path(),
            "soc_model": "43",
            "htp_arch": "73",
            "enable_htp_prepare_only": "1",
            "enable_block_quant_weight_optimization": "1",
            "enable_framework_op_trace": "1",
            "framework_op_trace_dir": str(trace_dir),
            "enable_htp_fp16_precision": "1",
            "htp_graph_finalization_optimization_mode": "1",
        }
        result["provider_options"] = provider_options
        options.add_provider_for_devices(devices, provider_options)
        started = time.perf_counter_ns()
        session = ort.InferenceSession(str(args.model), sess_options=options)
        stopped = time.perf_counter_ns()
        result["session_create_seconds"] = (stopped - started) / 1e9
        result["session_disable_cpu_ep_fallback"] = True
        result["providers_reported"] = session.get_providers()
        del session
        binary = args.output_dir / "context_qnn.bin"
        trace = trace_dir / "qnn_op_trace.json"
        for label, path in (("context_model", context_model), ("context_binary", binary), ("framework_op_trace", trace)):
            if not path.is_file():
                raise RuntimeError(f"missing {label}: {path}")
            result[label] = {"path": str(path.relative_to(args.output_dir)), "bytes": path.stat().st_size, "sha256": sha256(path)}
        result["success"] = True
    except Exception as error:
        exit_code = 1
        result.update(
            {
                "success": False,
                "exception_type": type(error).__name__,
                "exception": str(error),
            }
        )
        traceback.print_exc()
    finally:
        result["stopped_ns"] = time.time_ns()
        try:
            ort.unregister_execution_provider_library(registration)
        except Exception:
            pass
        (args.output_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
