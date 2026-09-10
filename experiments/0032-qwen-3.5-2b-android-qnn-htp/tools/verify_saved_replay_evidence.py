#!/usr/bin/env python3
"""Verify saved replay evidence. Never loads the model/PT2 graph or executes it.

Default verification needs only Git-retained data. --include-local also recovers
all positional tensors from the explicitly LOCAL-ONLY compressed archive.
--tensor-values checks those small saved output tensors with torch, not a model.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(directory: Path, include_local: bool = False, tensor_values: bool = False) -> dict:
    directory = directory.resolve()
    experiment = directory.parents[1]
    manifest = json.loads((directory / "compression-manifest.json").read_text())
    journal_bytes = (directory / "raw/progress.jsonl").read_bytes()
    rows = [json.loads(line) for line in journal_bytes.splitlines()]
    result = json.loads((directory / "raw/result.json").read_text())
    input_bytes = (experiment / "protocol/token-ids/short.int32le").read_bytes()
    if sha(input_bytes) != "dcfd3c24cb3f8a370f91b38c9720d7e3dd5c623d491fed70ded3726ec49048f4":
        raise ValueError("Canonical short input identity mismatch")
    ids = struct.unpack("<174i", input_bytes)
    if result["status"] != "completed" or result["evaluated_tokens"] != 174 or result["state_updates_completed"] != 174:
        raise ValueError("Replay is not complete")
    if len(rows) != 174 or sha(journal_bytes) != result["progress_artifact"]["sha256"]:
        raise ValueError("Journal count/hash mismatch")
    positions = {entry["position"]: entry for entry in manifest["files"] if "position" in entry}
    if len(positions) != 174 or len([e for e in manifest["files"] if "position" in e]) != 174:
        raise ValueError("Position manifest is incomplete or duplicated")
    for i, row in enumerate(rows):
        entry = positions[i]
        if row["position"] != i or row["input_token"] != ids[i] or entry["input_token"] != ids[i]:
            raise ValueError(f"Position/input mismatch at {i}")
        if (row["artifact"]["sha256"], row["artifact"]["bytes"]) != (entry["raw_sha256"], entry["raw_bytes"]):
            raise ValueError(f"Raw tensor binding mismatch at {i}")
        if not row["logits"]["finite"] or row["logits"]["argmax"] != entry["argmax"]:
            raise ValueError(f"Logit observation mismatch at {i}")
    torch = None
    if tensor_values:
        import torch
        torch.set_num_threads(1)
    recovered = tensor_checks = 0
    for entry in manifest["files"]:
        if "compressed_path" in entry:
            path = directory / entry["compressed_path"]
        elif include_local:
            path = experiment / entry["compressed_local_path"]
        else:
            continue
        compressed = path.read_bytes()
        if len(compressed) != entry["compressed_bytes"] or sha(compressed) != entry["compressed_sha256"]:
            raise ValueError(f"Compressed bytes/hash mismatch: {path}")
        raw = subprocess.check_output(["zstd", "-q", "-dc", str(path)])
        if len(raw) != entry["raw_bytes"] or sha(raw) != entry["raw_sha256"]:
            raise ValueError(f"Raw recovery mismatch: {path}")
        recovered += 1
        if tensor_values and "position" in entry:
            values = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
            observed = rows[entry["position"]]["logits"]
            if list(values.shape) != observed["shape"] or not bool(torch.isfinite(values).all()):
                raise ValueError("Tensor shape/finiteness mismatch")
            values = values.float().reshape(-1)
            if int(values.argmax()) != observed["argmax"]:
                raise ValueError("Tensor-derived argmax mismatch")
            if int((values == values.max()).sum()) != observed["max_count"]:
                raise ValueError("Tensor-derived maximum tie count mismatch")
            top_values = torch.topk(values, min(10, values.numel())).values.tolist()
            if (observed["top_logits"] != top_values
                    or len(observed["top_ids"]) != len(top_values)
                    or len(set(observed["top_ids"])) != len(top_values)):
                raise ValueError("Tensor-derived top-k ranking/length mismatch")
            if float(values.min()) != observed["min"] or float(values.max()) != observed["max"]:
                raise ValueError("Tensor-derived logit range mismatch")
            for token, value in zip(observed["top_ids"], observed["top_logits"]):
                if float(values[token]) != value:
                    raise ValueError("Tensor-derived top logit mismatch")
            tensor_checks += 1
        if entry.get("compressed_path") == "raw/final-logits.pt.zst":
            if entry["raw_sha256"] != result["final_logits_artifact"]["sha256"]:
                raise ValueError("Final tensor binding mismatch")
            if entry["raw_sha256"] != positions[173]["raw_sha256"]:
                raise ValueError("Final tensor bytes differ from position 173")
            if result["final_logits"] != rows[173]["logits"]:
                raise ValueError("Final summary differs from position 173")
    return {
        "journal_positions_verified": 174,
        "raw_recoveries_verified": recovered,
        "positional_tensors_numerically_checked": tensor_checks,
        "local_positional_bytes_checked": include_local,
        "model_archive_loaded_or_executed": False,
        "limitation": None if include_local else "Intermediate tensor bytes are LOCAL-ONLY; Git hashes alone cannot recover or numerically recheck them.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--include-local", action="store_true")
    parser.add_argument("--tensor-values", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.directory, args.include_local, args.tensor_values), indent=2))


if __name__ == "__main__":
    main()
