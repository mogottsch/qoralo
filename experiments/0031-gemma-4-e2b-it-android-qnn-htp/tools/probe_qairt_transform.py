#!/usr/bin/env python3
"""Bounded transform-only Gemma4 support probe; does not convert or compile."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
CKPT = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16"
CACHE = EXP / ".local/qairt-transform-probe"


def main() -> None:
    from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory

    if CACHE.exists():
        shutil.rmtree(CACHE)
    CACHE.mkdir(parents=True)
    encodings_copy = CACHE / "model.encodings"
    shutil.copy2(CKPT / "model.encodings", encodings_copy)
    builder = GenAIBuilderFactory.create(
        str(CKPT),
        "HTP",
        cache_root=str(CACHE),
        tokenizer_path=str(CKPT / "tokenizer.json"),
        config_path=str(CKPT / "config.json"),
    )
    builder.set_targets(["chipset:SM8550"])
    transform = builder._transformation_config.model_transformer_config
    transform.arn_cl_options.auto_regression_number = [1, 128]
    transform.arn_cl_options.context_length = [4096]
    transform.split_model.num_splits = 1
    transform.split_model.split_embedding = False
    transform.split_model.split_lm_head = False
    builder.set_transformation_options(transform)
    print(json.dumps({
        "event": "transform_start",
        "source_onnx": str(builder.framework_model_path),
        "source_encodings_copy": str(encodings_copy),
        "original_checkpoint_mutated": False,
        "auto_regression_number": [1, 128],
        "context_length": [4096],
        "num_splits": 1,
        "split_embedding": False,
        "split_lm_head": False,
        "conversion_requested": False,
        "compilation_requested": False,
    }, sort_keys=True), flush=True)
    transformed = builder.transform(
        model_path=builder.framework_model_path,
        config=builder._transformation_config,
        encodings_path=encodings_copy,
        lora_output_config=None,
    )
    artifacts = []
    for variant_index, splits in enumerate(transformed):
        for split_index, exported in enumerate(splits):
            item = {
                "variant_index": variant_index,
                "split_index": split_index,
                "onnx_path": str(exported.onnx_path),
                "onnx_bytes": Path(exported.onnx_path).stat().st_size,
                "encodings_path": str(exported.encodings_path) if exported.encodings_path else None,
                "encodings_bytes": Path(exported.encodings_path).stat().st_size if exported.encodings_path else None,
            }
            artifacts.append(item)
    print(json.dumps({
        "event": "transform_complete",
        "variant_count": len(transformed),
        "artifacts": artifacts,
        "conversion_requested": False,
        "compilation_requested": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
