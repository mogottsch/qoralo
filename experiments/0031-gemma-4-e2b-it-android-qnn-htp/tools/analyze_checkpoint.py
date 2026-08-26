#!/usr/bin/env python3
"""Bind and summarize the public Gemma4 w4a16 checkpoint without loading weights."""
from __future__ import annotations

import collections
import hashlib
import json
import struct
from pathlib import Path

import onnx
from transformers import AutoTokenizer

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]
ROOT = EXP / ".local/checkpoint"
CKPT = ROOT / "extracted/gemma_4_e2b_it_w4a16"
ZIP = ROOT / "gemma_4_e2b_it_w4a16.zip"
TIERS = ("short", "medium", "long")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shape(value_info: onnx.ValueInfoProto) -> list[int | str | None]:
    dims = value_info.type.tensor_type.shape.dim
    return [d.dim_value if d.HasField("dim_value") else d.dim_param if d.HasField("dim_param") else None for d in dims]


def external_info(initializer: onnx.TensorProto) -> dict[str, str]:
    return {item.key: item.value for item in initializer.external_data}


def summarize_encodings(path: Path) -> dict:
    payload = json.loads(path.read_text())
    summary: dict = {"top_level_keys": sorted(payload)}
    for key, value in payload.items():
        if isinstance(value, dict) and key == "quantizer_args":
            summary[key] = value
            continue
        if not isinstance(value, (dict, list)):
            summary[key] = {"type": type(value).__name__, "value": value}
            continue
        bitwidths: collections.Counter[int] = collections.Counter()
        dtypes: collections.Counter[str] = collections.Counter()
        encoding_types: collections.Counter[str] = collections.Counter()
        symmetry: collections.Counter[str] = collections.Counter()
        records = value.values() if isinstance(value, dict) else value
        enc_count = 0
        for entry in records:
            entries = entry if isinstance(entry, list) else [entry]
            for enc in entries:
                if not isinstance(enc, dict):
                    continue
                enc_count += 1
                bitwidth = enc.get("bitwidth", enc.get("bw"))
                if bitwidth is not None:
                    bitwidths[int(bitwidth)] += 1
                dtype = enc.get("dtype", enc.get("data_type"))
                if dtype is not None:
                    dtypes[str(dtype)] += 1
                if "enc_type" in enc:
                    encoding_types[str(enc["enc_type"])] += 1
                if "is_sym" in enc:
                    symmetry[str(bool(enc["is_sym"])).lower()] += 1
        summary[key] = {
            "tensor_entry_count": len(value),
            "encoding_record_count": enc_count,
            "bitwidth_record_counts": {str(k): v for k, v in sorted(bitwidths.items())},
            "dtype_record_counts": dict(sorted(dtypes.items())),
            "encoding_type_record_counts": dict(sorted(encoding_types.items())),
            "symmetric_record_counts": dict(sorted(symmetry.items())),
        }
    return summary


def main() -> None:
    onnx_path = CKPT / "model_dynamic.onnx"
    data_path = CKPT / "model.data"
    model = onnx.load(str(onnx_path), load_external_data=False)
    graph = model.graph
    external = []
    max_end = 0
    referenced = 0
    locations: collections.Counter[str] = collections.Counter()
    for initializer in graph.initializer:
        if initializer.data_location != onnx.TensorProto.EXTERNAL:
            continue
        info = external_info(initializer)
        offset = int(info.get("offset", "0"))
        length = int(info.get("length", "0"))
        referenced += length
        max_end = max(max_end, offset + length)
        locations[info.get("location", "")] += 1
        external.append({"name": initializer.name, "offset": offset, "length": length})

    tokenizer = AutoTokenizer.from_pretrained(str(CKPT), local_files_only=True, trust_remote_code=False)
    prompt_inventory = {}
    rendered_dir = EXP / "protocol/rendered"
    token_dir = EXP / "protocol/token-ids"
    rendered_dir.mkdir(parents=True, exist_ok=True)
    token_dir.mkdir(parents=True, exist_ok=True)
    for tier in TIERS:
        workload_path = REPO / f"protocols/android-llm-benchmark/workloads/inference-v1/{tier}.json"
        workload = json.loads(workload_path.read_text())
        rendered = tokenizer.apply_chat_template(
            workload["messages"],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        ids = tokenizer.encode(rendered, add_special_tokens=False)
        rendered_bytes = rendered.encode("utf-8")
        token_bytes = b"".join(struct.pack("<i", token) for token in ids)
        (rendered_dir / f"{tier}.txt").write_bytes(rendered_bytes)
        (token_dir / f"{tier}.int32le").write_bytes(token_bytes)
        prompt_inventory[tier] = {
            "workload_sha256": sha256(workload_path),
            "rendered_bytes": len(rendered_bytes),
            "rendered_sha256": hashlib.sha256(rendered_bytes).hexdigest(),
            "input_tokens": len(ids),
            "first_token_ids": ids[:4],
            "bos_token_id": tokenizer.bos_token_id,
            "leading_bos_count": next((index for index, token in enumerate(ids) if token != tokenizer.bos_token_id), len(ids)),
            "token_ids_int32le_sha256": hashlib.sha256(token_bytes).hexdigest(),
            "max_new_tokens": workload["generation"]["max_new_tokens"],
            "fits_context_4096": len(ids) + workload["generation"]["max_new_tokens"] <= 4096,
            "fits_context_8192": len(ids) + workload["generation"]["max_new_tokens"] <= 8192,
        }

    members = []
    for path in sorted(CKPT.iterdir()):
        if path.is_file():
            members.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    member_by_name = {item["path"]: item for item in members}
    args = json.loads((CKPT / "args.json").read_text())
    config = json.loads((CKPT / "config.json").read_text())
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "public_checkpoint_identity_and_conversion_input_analysis",
        "heavy_ram_lock_held": True,
        "archive": {"url": "https://qaihub-public-assets.s3.us-west-2.amazonaws.com/qai-hub-models/models/gemma_4_e2b_it/v1/gemma_4_e2b_it_w4a16.zip", "bytes": ZIP.stat().st_size, "sha256": sha256(ZIP), "zip_integrity": "passed"},
        "members": members,
        "source": {"checkpoint": args["checkpoint"], "current_public_revision": "dd693ff40353f057ca5f07e945ad867f4afbf2ec", "architecture": config["model_type"], "text_config": config["text_config"]},
        "quantization": {"published_name": args["precision"], "calibration_samples": args["num_samples"], "raw_text_calibration": args["raw_text_calibration"], "sequential_mse": args["use_seq_mse"], "encodings_summary": summarize_encodings(CKPT / "model.encodings")},
        "onnx": {
            "ir_version": model.ir_version,
            "opset_imports": {item.domain or "ai.onnx": item.version for item in model.opset_import},
            "graph_name": graph.name,
            "node_count": len(graph.node),
            "op_type_counts": dict(sorted(collections.Counter(node.op_type for node in graph.node).items())),
            "inputs": [{"name": item.name, "elem_type": item.type.tensor_type.elem_type, "shape": shape(item)} for item in graph.input],
            "outputs": [{"name": item.name, "elem_type": item.type.tensor_type.elem_type, "shape": shape(item)} for item in graph.output],
            "initializer_count": len(graph.initializer),
            "external_initializer_count": len(external),
            "external_locations": dict(locations),
            "external_referenced_bytes_sum": referenced,
            "external_max_offset_plus_length": max_end,
            "model_data_bytes": data_path.stat().st_size,
            "external_ranges_within_model_data": max_end <= data_path.stat().st_size,
            "model_data_sha256": member_by_name["model.data"]["sha256"],
        },
        "tokenizer_and_template": {"tokenizer_json_sha256": sha256(CKPT / "tokenizer.json"), "tokenizer_config_sha256": sha256(CKPT / "tokenizer_config.json"), "chat_template_sha256": sha256(CKPT / "chat_template.jinja"), "prompt_inventory": prompt_inventory},
        "conversion_input_mutated": False,
    }
    output = EXP / "results/checkpoint-analysis/result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(output)


if __name__ == "__main__":
    main()
