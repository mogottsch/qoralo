#!/usr/bin/env python3
"""Bounded transform-only Gemma4 probe with a narrow ONNX schema fix."""
from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import onnx

from qairt_constant_compat import install

EXP = Path(__file__).resolve().parents[1]
CKPT = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16"
CACHE = EXP / ".local/qairt-2.49.40-transform-compat"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def constant_inventory(path: Path) -> dict[str, object]:
    model = onnx.load(path, load_external_data=False)
    forms: Counter[tuple[str, ...]] = Counter()
    value_ints: list[list[int]] = []
    for node in model.graph.node:
        if node.op_type != "Constant":
            continue
        names = tuple(attribute.name for attribute in node.attribute)
        forms[names] += 1
        for attribute in node.attribute:
            if attribute.name == "value_ints":
                value_ints.append(list(attribute.ints))
    return {
        "constant_nodes": sum(forms.values()),
        "attribute_forms": {"+".join(key): value for key, value in sorted(forms.items())},
        "value_ints_values": value_ints,
    }


def main() -> None:
    from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory

    source_paths = {
        "onnx": CKPT / "model_dynamic.onnx",
        "external_data": CKPT / "model.data",
        "encodings": CKPT / "model.encodings",
    }
    before = {name: sha256(path) for name, path in source_paths.items()}
    inventory = constant_inventory(source_paths["onnx"])
    expected = {
        "constant_nodes": 52,
        "attribute_forms": {"value": 48, "value_ints": 4},
        "value_ints_values": [[-1], [1], [35], [256]],
    }
    if inventory != expected:
        raise RuntimeError(f"unexpected Constant inventory: {inventory!r}")

    patch = install()
    if CACHE.exists():
        shutil.rmtree(CACHE)
    CACHE.mkdir(parents=True)
    encodings_copy = CACHE / "model.encodings"
    shutil.copy2(source_paths["encodings"], encodings_copy)

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

    print(
        json.dumps(
            {
                "event": "transform_start",
                "qairt_version": "2.49.40.260810",
                "builder_class": f"{builder.__class__.__module__}.{builder.__class__.__name__}",
                "source_identity": before,
                "constant_inventory": inventory,
                "compatibility_patch": patch,
                "target": "chipset:SM8550",
                "auto_regression_number": [1, 128],
                "context_length": [4096],
                "num_splits": 1,
                "split_embedding": False,
                "split_lm_head": False,
                "checkpoint_rewritten": False,
                "conversion_requested": False,
                "compilation_requested": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    try:
        transformed = builder.transform(
            model_path=builder.framework_model_path,
            config=builder._transformation_config,
            encodings_path=encodings_copy,
            lora_output_config=None,
        )
    except Exception as error:
        after_failure = {name: sha256(path) for name, path in source_paths.items()}
        print(
            json.dumps(
                {
                    "event": "transform_failed",
                    "exception_type": type(error).__name__,
                    "exception_message": str(error),
                    "compatibility_patch": patch,
                    "source_identity_after": after_failure,
                    "source_identity_unchanged": before == after_failure,
                    "checkpoint_rewritten": False,
                    "conversion_requested": False,
                    "compilation_requested": False,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        raise

    artifacts = []
    for variant_index, splits in enumerate(transformed):
        for split_index, exported in enumerate(splits):
            onnx_path = Path(exported.onnx_path)
            encodings_path = Path(exported.encodings_path) if exported.encodings_path else None
            artifacts.append(
                {
                    "variant_index": variant_index,
                    "split_index": split_index,
                    "onnx_path": str(onnx_path),
                    "onnx_bytes": onnx_path.stat().st_size,
                    "onnx_sha256": sha256(onnx_path),
                    "encodings_path": str(encodings_path) if encodings_path else None,
                    "encodings_bytes": encodings_path.stat().st_size if encodings_path else None,
                    "encodings_sha256": sha256(encodings_path) if encodings_path else None,
                }
            )

    after = {name: sha256(path) for name, path in source_paths.items()}
    print(
        json.dumps(
            {
                "event": "transform_complete",
                "qairt_version": "2.49.40.260810",
                "variant_count": len(transformed),
                "artifacts": artifacts,
                "compatibility_patch": patch,
                "source_identity_after": after,
                "source_identity_unchanged": before == after,
                "checkpoint_rewritten": False,
                "conversion_requested": False,
                "compilation_requested": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
