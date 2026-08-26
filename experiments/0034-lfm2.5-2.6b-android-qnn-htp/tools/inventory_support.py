#!/usr/bin/env python3
"""Inventory LFM2.5-2.6B QNN/HTP support without downloading model weights."""
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
    config = json.loads((TOKENIZER / "config.json").read_text())
    factory_path = QAIRT / "lib/python/qairt/gen_ai_api/gen_ai_builder_factory.py"
    support_path = QAIRT / "lib/python/qti/aisw/converters/gguf_builder/utils.py"
    release_notes_path = QAIRT / "QAIRT_ReleaseNotes.txt"
    factory_text = factory_path.read_text()
    support_text = support_path.read_text()
    release_notes = release_notes_path.read_text(errors="replace")
    enum_match = re.search(r"class SupportedLLMs\(Enum\):(.*?)(?:\n\nclass )", factory_text, re.S)
    factory_architectures = sorted(set(re.findall(r'=\s*"([A-Za-z0-9_]+(?:ForCausalLM|ForConditionalGeneration|LMHeadModel))"', enum_match.group(1)))) if enum_match else []
    model_types_match = re.search(r"MODEL_TYPE_TO_ARCH\s*=\s*\{(.*?)\}\n\n", support_text, re.S)
    gguf_types = sorted(set(re.findall(r'"([a-zA-Z0-9_]+)"\s*:', model_types_match.group(1)))) if model_types_match else []
    genie_configs = sorted(path.relative_to(QAIRT / "examples/Genie/configs").as_posix() for path in (QAIRT / "examples/Genie/configs").rglob("*.json"))
    qaihm_models = sorted(path.name for path in (QAIHM / "src/qai_hub_models/models").iterdir() if path.is_dir())

    tokenizer = AutoTokenizer.from_pretrained(str(TOKENIZER), local_files_only=True, trust_remote_code=False)
    prompt_inventory = {}
    for tier in TIERS:
        workload_path = REPO / f"protocols/android-llm-benchmark/workloads/inference-v1/{tier}.json"
        workload = json.loads(workload_path.read_text())
        rendered = tokenizer.apply_chat_template(workload["messages"], tokenize=False, add_generation_prompt=True)
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
            "fits_context_8192": len(ids) + workload["generation"]["max_new_tokens"] <= 8192,
            "leading_bos_count": next((index for index, token in enumerate(ids) if token != tokenizer.bos_token_id), len(ids)),
            "generation_prompt_ends_native_think": rendered.endswith("<think>"),
        }

    layer_counts = dict(sorted(__import__("collections").Counter(config["layer_types"]).items()))
    result = {
        "schema_version": 1,
        "experiment": "0034-lfm2.5-2.6b-android-qnn-htp",
        "classification": "negative_phone_independent_qnn_htp_feasibility",
        "model": {
            "source": "LiquidAI/LFM2.5-2.6B",
            "revision": "ab00687315bc1298e9d54e9c4b611dde9867ccc2",
            "architecture": config["architectures"][0],
            "model_type": config["model_type"],
            "layers": config["num_hidden_layers"],
            "layer_type_counts": layer_counts,
            "hidden_size": config["hidden_size"],
            "attention_heads": config["num_attention_heads"],
            "kv_heads": config["num_key_value_heads"],
            "conv_cache_length": config["conv_L_cache"],
            "vocab_size": config["vocab_size"],
            "native_context": config["max_position_embeddings"],
            "license": "LFM Open License v1.0",
            "license_sha256": "30adf9d6478191fb87f2424f63ba0728598335aaf99cd2848ef17e8e545fe94b",
        },
        "official_public_artifact": {
            "repository": "LiquidAI/LFM2.5-2.6B-GGUF",
            "revision": "84022ce711b28455e8c4fc364ce68c00cf995875",
            "filename": "LFM2.5-2.6B-Q4_K_M.gguf",
            "bytes": 1674455040,
            "sha256": "02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed",
            "format": "GGUF v3",
            "gguf_architecture": "lfm2",
            "quantization": "Q4_K_M",
            "downloaded_for_0034": False,
            "download_avoided_reason": "The exact bytes are already bound by 0029, and installed QAIRT rejects lfm2 by architecture before weights are needed.",
        },
        "public_qualcomm_support": {
            "huggingface_author_search_lfm25_count": 0,
            "huggingface_author_search_lfm2_count": 0,
            "qai_hub_models_version": "v0.61.0",
            "qai_hub_models_commit": "5975a79b55b40f5cbc61f3ac5e52abe47d9d8bd5",
            "matching_model_directories": [name for name in qaihm_models if "lfm" in name.lower() or "liquid" in name.lower()],
            "qnn_context_binary_published": False,
            "quantized_onnx_encodings_published": False,
            "model_export_or_quantize_implementation_present": False,
        },
        "installed_qairt": {
            "version": "2.49.0.260730",
            "sdk_manifest_sha256": sha256(QAIRT / "sdk.yaml"),
            "factory_sha256": sha256(factory_path),
            "gguf_support_table_sha256": sha256(support_path),
            "release_notes_sha256": sha256(release_notes_path),
            "factory_supported_architectures": factory_architectures,
            "factory_supports_lfm2": config["architectures"][0] in factory_architectures,
            "direct_gguf_supported_model_types": gguf_types,
            "direct_gguf_supports_lfm2": "lfm2" in gguf_types,
            "matching_genie_configs": [path for path in genie_configs if "lfm" in path.lower() or "liquid" in path.lower()],
            "release_notes_mentions_lfm_or_liquid": bool(re.search(r"\b(?:LFM|LiquidAI)\b", release_notes, re.I)),
            "sm8550_compile_target_supported_generically": True,
            "sm8550_compile_target_is_not_model_support": True,
            "license_or_install_action_taken": False,
        },
        "tokenizer_and_template": {
            "files": {path.name: sha256(path) for path in sorted(TOKENIZER.iterdir()) if path.is_file()},
            "special_token_ids": {"bos": tokenizer.bos_token_id, "eos": tokenizer.eos_token_id, "pad": tokenizer.pad_token_id},
            "native_reasoning_continuation": True,
            "prompt_inventory": prompt_inventory,
        },
        "route_assessment": {
            "official_gguf_to_installed_qairt": "unsupported_architecture_lfm2",
            "installed_high_level_onnx_builder": "no Lfm2ForCausalLM factory dispatch or model-specific state/cache transformation",
            "authorized_quantized_onnx_encodings_available": False,
            "compiled_sm8550_context_available": False,
            "android_execution": False,
            "qnn_htp_execution": False,
        },
        "exact_blocker": "No authorized QNN route exists in the installed/public tooling set. The official pinned LFM2.5-2.6B artifact is architecture lfm2, but QAIRT 2.49 supports neither lfm2 in its direct GGUF builder nor Lfm2ForCausalLM in its HTP factory, Genie configs, or release notes. Qualcomm publishes no LFM model/export/quantization recipe, quantized ONNX+encodings, or serialized context. LFM2's 22 convolutional state layers plus 8 attention layers require model-specific state/cache conversion and runtime orchestration; using the generic builder would be a new unsupported converter implementation, which is outside authorization.",
        "required_user_action_or_decision": [
            "Provide an authorized, provenance-bound LFM2.5-2.6B quantized ONNX+encodings input and model-specific QAIRT builder, or a complete SM8550/HTP v73 serialized-context runtime bundle; or",
            "Explicitly authorize authenticated Qualcomm AI Hub/engineering support if a non-public LFM QNN export exists; or",
            "Explicitly authorize an updated QAIRT/toolchain or a new LFM2 converter/runtime implementation, with host equivalence, state-reset, partition, and provider proofs.",
        ],
        "prohibited_shortcuts": [
            "Download the already-rejected GGUF and treat unsupported architecture failure as progress.",
            "Map lfm2 to llama/qwen or ignore convolutional recurrent state.",
            "Claim HTP from CPU/GPU execution or a generic SM8550 compiler target.",
            "Modify 0029 or 0033 evidence.",
        ],
    }
    out = EXP / "results/support-assessment/result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(out)


if __name__ == "__main__":
    main()
