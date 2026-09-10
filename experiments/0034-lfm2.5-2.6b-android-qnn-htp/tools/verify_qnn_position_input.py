#!/usr/bin/env python3
"""Fail-closed preflight for qnn-net-run position input file semantics."""
from __future__ import annotations
import argparse, hashlib, json, shlex
from pathlib import Path
import numpy as np

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(path: Path, mode: str, start: int, count: int, command: str) -> dict[str, object]:
    if start < 0 or count < 1:
        raise ValueError("start must be nonnegative and count positive")
    arguments = shlex.split(command)
    use_native = "--use_native_input_files" in arguments
    targeted = "--native_input_tensor_names" in arguments
    if mode == "default-float32":
        if use_native or targeted:
            raise ValueError("default-float32 file paired with native-input flag")
        dtype = np.dtype("<f4")
        required_flag = "none"
    elif mode == "native-int64":
        if not (use_native or targeted):
            raise ValueError("native-int64 file requires --use_native_input_files or --native_input_tensor_names")
        dtype = np.dtype("<i8")
        required_flag = "--use_native_input_files or --native_input_tensor_names"
    else:
        raise ValueError(f"unsupported mode: {mode}")
    expected_bytes = count * dtype.itemsize
    if path.stat().st_size != expected_bytes:
        raise ValueError(f"position file size {path.stat().st_size} != {expected_bytes} for {mode}")
    values = np.fromfile(path, dtype=dtype)
    expected = np.arange(start, start + count, dtype=dtype)
    if not np.array_equal(values, expected):
        mismatch = int(np.flatnonzero(values != expected)[0]) if np.any(values != expected) else -1
        raise ValueError(f"position values mismatch at index {mismatch}: got {values[mismatch]!r}, expected {expected[mismatch]!r}")
    return {
        "schema_version": 1,
        "classification": "qnn_net_run_position_input_preflight",
        "path": str(path),
        "sha256": sha256(path),
        "mode": mode,
        "graph_tensor_data_type": "QNN_DATATYPE_INT_64",
        "file_data_type": str(dtype),
        "bytes": path.stat().st_size,
        "expected_start": start,
        "expected_count": count,
        "first_values": values[: min(4, count)].tolist(),
        "last_values": values[max(0, count - 4):].tolist(),
        "native_flag_required": required_flag,
        "command": command,
        "passed": True,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--mode", choices=("default-float32", "native-int64"), required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.file, args.mode, args.start, args.count, args.command)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")

if __name__ == "__main__":
    main()
