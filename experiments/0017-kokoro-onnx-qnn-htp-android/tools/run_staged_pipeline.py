#!/usr/bin/env python3
"""Run every Kokoro stage in a separate process and pass raw tensors explicitly."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_pipeline_input(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("pipeline input must be tensor-name=path")
    name, path = value.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError("pipeline input must be tensor-name=path")
    return name, Path(path)


def tensor_spec(contract: dict[str, object], path: Path) -> str:
    shape = ",".join(str(item) for item in contract["shape"])
    return f"{contract['name']}|{contract['dtype']}|{shape}|{path}"


def safe_tensor_filename(stage_index: int, output_index: int, contract: dict[str, object]) -> str:
    suffix = "f32" if contract["dtype"] == "float32" else "i64"
    name_hash = hashlib.sha256(str(contract["name"]).encode()).hexdigest()[:12]
    return f"{stage_index:02d}-{output_index:02d}-{name_hash}.{suffix}"


def write_checkpoint(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provider", choices=("cpu", "qnn"), required=True)
    parser.add_argument("--backend", type=Path)
    parser.add_argument("--optimization", choices=("disabled", "basic", "all"), default="disabled")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--pipeline-input", action="append", default=[], type=parse_pipeline_input)
    args = parser.parse_args()
    if args.provider == "qnn" and args.backend is None:
        parser.error("--provider qnn requires --backend")
    if args.runs <= 0:
        parser.error("--runs must be positive")

    manifest = json.loads(args.manifest.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tensor_dir = args.output_dir / "tensors"
    log_dir = args.output_dir / "logs"
    profile_dir = args.output_dir / "profiles"
    for directory in (tensor_dir, log_dir, profile_dir):
        directory.mkdir(parents=True, exist_ok=True)

    tensor_paths: dict[str, Path] = dict(args.pipeline_input)
    expected_pipeline_inputs = {item["name"] for item in manifest["pipeline_inputs"]}
    if set(tensor_paths) != expected_pipeline_inputs:
        raise RuntimeError(
            f"pipeline input names mismatch: expected {sorted(expected_pipeline_inputs)}, "
            f"got {sorted(tensor_paths)}"
        )
    for name, path in tensor_paths.items():
        if not path.is_file():
            raise RuntimeError(f"missing pipeline input {name}: {path}")

    record: dict[str, object] = {
        "schema_version": 1,
        "status": "running",
        "manifest": {
            "path": str(args.manifest),
            "bytes": args.manifest.stat().st_size,
            "sha256": sha256(args.manifest),
            "source_graph_sha256": manifest["source"]["sha256"],
        },
        "runner": {
            "path": str(args.runner),
            "bytes": args.runner.stat().st_size,
            "sha256": sha256(args.runner),
        },
        "provider": args.provider,
        "backend": str(args.backend) if args.backend else None,
        "optimization": args.optimization,
        "runs_per_stage": args.runs,
        "separate_process_per_stage": True,
        "pipeline_inputs": {
            name: {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for name, path in sorted(tensor_paths.items())
        },
        "stages": [],
    }
    checkpoint = args.output_dir / "pipeline-checkpoint.json"
    write_checkpoint(checkpoint, record)

    for stage in manifest["stages"]:
        index = int(stage["index"])
        name = str(stage["name"])
        model_path = Path(stage["model"]["path"])
        if not model_path.is_absolute():
            model_path = args.repo_root / model_path
        expected_model_sha = stage["model"]["sha256"]
        actual_model_sha = sha256(model_path)
        if actual_model_sha != expected_model_sha:
            raise RuntimeError(
                f"stage model hash mismatch for {name}: {actual_model_sha}"
            )

        output_paths: dict[str, Path] = {}
        command = [
            str(args.runner),
            "--model",
            str(model_path),
            "--stage",
            name,
            "--provider",
            args.provider,
            "--optimization",
            args.optimization,
            "--runs",
            str(args.runs),
            "--profile-prefix",
            str(profile_dir / f"{index:02d}-{name}"),
        ]
        if args.backend:
            command.extend(("--backend", str(args.backend)))
        for contract in stage["inputs"]:
            tensor_name = str(contract["name"])
            if tensor_name not in tensor_paths:
                raise RuntimeError(f"{name}: unavailable input tensor {tensor_name}")
            command.extend(("--input-spec", tensor_spec(contract, tensor_paths[tensor_name])))
        for output_index, contract in enumerate(stage["outputs"], start=1):
            path = tensor_dir / safe_tensor_filename(index, output_index, contract)
            output_paths[str(contract["name"])] = path
            command.extend(("--output-spec", tensor_spec(contract, path)))

        stdout_path = log_dir / f"{index:02d}-{name}.stdout.json"
        stderr_path = log_dir / f"{index:02d}-{name}.stderr.log"
        start = time.monotonic()
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, check=False)
        wall_seconds = time.monotonic() - start
        stage_record: dict[str, object] = {
            "index": index,
            "name": name,
            "model_sha256": actual_model_sha,
            "command": command,
            "exit_code": result.returncode,
            "wall_seconds": wall_seconds,
            "stdout": {
                "path": str(stdout_path),
                "bytes": stdout_path.stat().st_size,
                "sha256": sha256(stdout_path),
            },
            "stderr": {
                "path": str(stderr_path),
                "bytes": stderr_path.stat().st_size,
                "sha256": sha256(stderr_path),
            },
        }
        if result.returncode == 0:
            runtime = json.loads(stdout_path.read_text())
            if runtime.get("status") != "passed" or runtime.get("stage") != name:
                raise RuntimeError(f"{name}: runner JSON contract failed")
            output_records = {}
            for tensor_name, path in output_paths.items():
                if not path.is_file():
                    raise RuntimeError(f"{name}: missing output {tensor_name}")
                tensor_paths[tensor_name] = path
                output_records[tensor_name] = {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            stage_record["runtime"] = runtime
            stage_record["outputs"] = output_records
            stage_record["profile_files"] = [
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
                for path in sorted(profile_dir.glob(f"{index:02d}-{name}*"))
                if path.is_file()
            ]
        record["stages"].append(stage_record)
        if result.returncode != 0:
            record["status"] = "failed"
            record["failed_stage"] = name
            record["failed_stage_index"] = index
            write_checkpoint(checkpoint, record)
            return result.returncode
        write_checkpoint(checkpoint, record)

    pipeline_outputs = {}
    for contract in manifest["pipeline_outputs"]:
        name = str(contract["name"])
        path = tensor_paths[name]
        pipeline_outputs[name] = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    record["pipeline_outputs"] = pipeline_outputs
    record["status"] = "passed"
    record["completed_stages"] = len(record["stages"])
    write_checkpoint(checkpoint, record)
    print(json.dumps({"status": "passed", "stages": len(record["stages"]), "outputs": pipeline_outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
