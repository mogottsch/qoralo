#!/usr/bin/env python3
"""Inventory Qwen3.5-2B QNN/HTP support without downloading model weights."""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

from transformers import AutoTokenizer

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]
TOKENIZER = EXP / ".local/tokenizer"
QAIRT = Path("/home/moritz/opt/qairt/2.49.0.260730")
QAIHM = EXP / ".local/ai-hub-models"
TIERS = ("short", "medium", "long")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    builder_path = QAIRT / "lib/python/qairt/gen_ai_api/builders/qwen/builder.py"
    factory_path = QAIRT / "lib/python/qairt/gen_ai_api/gen_ai_builder_factory.py"
    support_table_path = QAIRT / "lib/python/qti/aisw/converters/gguf_builder/utils.py"
    example_path = QAIRT / "examples/Genie/configs/qwen3-5/qwen3-5-4b-htp.json"
    builder_text = builder_path.read_text()
    support_text = support_table_path.read_text()
    model_types_match = re.search(r"MODEL_TYPE_TO_ARCH\s*=\s*\{(.*?)\}\n\n", support_text, re.S)
    gguf_types = sorted(set(re.findall(r'"([a-zA-Z0-9_]+)"\s*:', model_types_match.group(1)))) if model_types_match else []
    config = json.loads((TOKENIZER / "config.json").read_text())
    text = config["text_config"]
    example = json.loads(example_path.read_text())

    tokenizer = AutoTokenizer.from_pretrained(str(TOKENIZER), local_files_only=True, trust_remote_code=False)
    prompt_inventory = {}
    for tier in TIERS:
        workload_path = REPO / f"protocols/android-llm-benchmark/workloads/inference-v1/{tier}.json"
        workload = json.loads(workload_path.read_text())
        rendered = tokenizer.apply_chat_template(workload["messages"], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        ids = tokenizer.encode(rendered, add_special_tokens=False)
        rendered_bytes = rendered.encode()
        token_bytes = b"".join(struct.pack("<i", value) for value in ids)
        (EXP / f"protocol/rendered/{tier}.txt").write_bytes(rendered_bytes)
        (EXP / f"protocol/token-ids/{tier}.int32le").write_bytes(token_bytes)
        prompt_inventory[tier] = {
            "workload_sha256": sha256(workload_path),
            "rendered_bytes": len(rendered_bytes),
            "rendered_sha256": hashlib.sha256(rendered_bytes).hexdigest(),
            "input_tokens": len(ids),
            "token_ids_int32le_sha256": hashlib.sha256(token_bytes).hexdigest(),
            "max_new_tokens": workload["generation"]["max_new_tokens"],
            "fits_context_4096": len(ids) + workload["generation"]["max_new_tokens"] <= 4096,
        }

    stub_files = sorted(
        path.name for path in (QAIHM / "src/qai_hub_models/models/qwen3_5_2b").iterdir() if path.is_file()
    )
    result = {
        "schema_version": 1,
        "experiment": "0032-qwen-3.5-2b-android-qnn-htp",
        "classification": "negative_phone_independent_qnn_htp_feasibility",
        "model": {
            "source": "Qwen/Qwen3.5-2B",
            "revision": "15852e8c16360a2fea060d615a32b45270f8a8fc",
            "architecture": config["architectures"][0],
            "model_type": config["model_type"],
            "text_layers": text["num_hidden_layers"],
            "hidden_size": text["hidden_size"],
            "head_dim": text["head_dim"],
            "full_attention_kv_heads": text["num_key_value_heads"],
            "full_attention_kv_width": text["num_key_value_heads"] * text["head_dim"],
            "linear_key_heads": text["linear_num_key_heads"],
            "linear_key_head_dim": text["linear_key_head_dim"],
            "linear_key_width": text["linear_num_key_heads"] * text["linear_key_head_dim"],
            "native_context": text["max_position_embeddings"],
        },
        "public_qualcomm_release": {
            "repository": "qualcomm/Qwen3.5-2B",
            "revision": "bd885dfceb1a1f45564aef4cd69e183085ea9a24",
            "qai_hub_models_version": "v0.61.0",
            "qai_hub_models_commit": "5975a79b55b40f5cbc61f3ac5e52abe47d9d8bd5",
            "published_runtime": "GENIEX_LLAMACPP",
            "published_precision": "q4_0",
            "published_artifact": {
                "repository": "unsloth/Qwen3.5-2B-GGUF",
                "revision": "f6d5376be1edb4d416d56da11e5397a961aca8ae",
                "filename": "Qwen3.5-2B-Q4_0.gguf",
                "bytes": 1214873856,
                "sha256": "cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1",
                "gguf_architecture": "qwen35",
            },
            "qnn_context_binary_published": False,
            "quantized_onnx_encodings_published": False,
            "model_source_directory_files": stub_files,
            "model_py_present": "model.py" in stub_files,
            "export_py_present": "export.py" in stub_files,
            "quantize_py_present": "quantize.py" in stub_files,
        },
        "installed_qairt": {
            "version": "2.49.0.260730",
            "sdk_manifest_sha256": sha256(QAIRT / "sdk.yaml"),
            "qwen_builder_sha256": sha256(builder_path),
            "factory_sha256": sha256(factory_path),
            "qwen35_4b_example_sha256": sha256(example_path),
            "factory_dispatches_qwen35": "Qwen3_5BuilderHTP.from_pretrained" in factory_path.read_text(),
            "only_shipped_qwen35_htp_example": "qwen3-5-4b-htp.json",
            "example_backend_type": example["dialog"]["engine"]["backend"]["type"],
            "example_context_bins": example["dialog"]["engine"]["model"]["binary"]["ctx-bins"],
            "direct_gguf_supported_model_types": gguf_types,
            "direct_gguf_supports_qwen35": "qwen35" in gguf_types,
            "qwen35_builder_hardcoded_split_map": {"tensor_width": 4096, "group_width": 256},
            "qwen35_builder_comment": "Hardcoded because num_key_value_heads and head_dim are generally fixed. Update if Qwen3.5 variants with different dimensions are added.",
            "qwen35_builder_contains_dimension_update_warning": "Update if Qwen3.5 variants with different dimensions are added" in builder_text,
        },
        "tokenizer_and_template": {
            "files": {path.name: sha256(path) for path in sorted(TOKENIZER.iterdir()) if path.is_file()},
            "thinking_enabled": False,
            "prompt_inventory": prompt_inventory,
        },
        "route_assessment": {
            "direct_public_gguf_to_installed_qairt": "unsupported_architecture_qwen35",
            "installed_qwen35_onnx_builder": "architecture dispatch exists but requires quantized ONNX plus encodings that are not publicly released for 2B; its dimension-specific start point is not compatible with the 2B config without a source change",
            "local_conversion_input_available": False,
            "compiled_sm8550_context_available": False,
            "android_execution": False,
            "qnn_htp_execution": False,
        },
        "exact_blocker": "The only currently published unauthenticated Qualcomm Qwen3.5-2B artifact is a qwen35 GGUF for GenieX llama.cpp. Installed QAIRT's direct GGUF builder does not support qwen35. Its separate Qwen3.5 HTP builder requires quantized ONNX plus encodings, but Qualcomm AI Hub Models v0.61.0 publishes no 2B model/export/quantize implementation or QNN checkpoint, and the installed builder hardcodes a 4096-wide split point that does not match either the official 2B full-attention KV width (512) or linear-key width (2048). No authorized local conversion input or compiled SM8550 context exists.",
        "required_user_action_or_decision": [
            "Provide an authorized, provenance-bound Qwen3.5-2B quantized ONNX plus encodings compatible with installed QAIRT, or a serialized SM8550/HTP v73 context and complete runtime bundle; or",
            "Explicitly authorize authenticated Qualcomm AI Hub Workbench use if a supported QNN context export for Qwen3.5-2B exists; or",
            "Explicitly authorize an updated QAIRT/toolchain or a Qwen3.5-2B architecture implementation that adds qwen35 GGUF support or correct 2B ONNX builder dimensions, with independent equivalence and provider proof.",
        ],
        "prohibited_shortcuts": [
            "Relabel GenieX llama.cpp NPU metrics as this repository's QNN/HTP route.",
            "Apply the 4B example or 4096-wide hardcoded builder split point to the 2B model.",
            "Claim HTP from a CPU response or without a compiled-context/provider proof.",
        ],
    }
    out = EXP / "results/support-assessment/result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(out)


if __name__ == "__main__":
    main()
