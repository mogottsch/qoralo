#!/usr/bin/env python3
"""QNN-convert the two bound Gemma4 transform outputs; do not compile."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from qairt_constant_compat import install

EXP = Path(__file__).resolve().parents[1]
CKPT = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16"
CACHE = EXP / ".local/qairt-2.49.40-transform-compat"
EXPECTED_TRANSFORM = {
    1: {
        "onnx": "9f3077b4a8ccec48781843f6391bb9d77bf4d0c2578a864c108a916b24c9e472",
        "encodings": "0dbb1aad69b419594707cc45d31656b95457b5a78c0bce462f1f03db77bfe2a8",
    },
    128: {
        "onnx": "d1171990305f50e89076709dcf024056f66393a90d35a79e774dc5612b0e3a9a",
        "encodings": "7e26400519d338171bc9d3e9c87182ef0853ce6dfc0c543ad85ea2d815dea251",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    from qairt.gen_ai_api.builders.gen_ai_utils import get_input_layout
    from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory

    patch = install()
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

    transformed = builder.transform(
        model_path=builder.framework_model_path,
        config=builder._transformation_config,
        encodings_path=CACHE / "model.encodings",
        lora_output_config=None,
    )
    if len(transformed) != 2 or any(len(parts) != 1 for parts in transformed):
        raise RuntimeError("expected two one-split transformed variants")

    checked = []
    for ar, parts in zip((1, 128), transformed, strict=True):
        exported = parts[0]
        onnx_path = Path(exported.onnx_path)
        encodings_path = Path(exported.encodings_path)
        actual = {"onnx": sha256(onnx_path), "encodings": sha256(encodings_path)}
        if actual != EXPECTED_TRANSFORM[ar]:
            raise RuntimeError(f"AR{ar} transform identity mismatch: {actual}")
        checked.append(
            {
                "ar": ar,
                "onnx_path": str(onnx_path),
                "onnx_sha256": actual["onnx"],
                "encodings_path": str(encodings_path),
                "encodings_sha256": actual["encodings"],
            }
        )

    print(
        json.dumps(
            {
                "event": "qnn_conversion_start",
                "qairt_version": "2.49.40.260810",
                "target_configuration": "chipset:SM8550",
                "transformed_variants": checked,
                "compatibility_patch": patch,
                "qnn_conversion_requested": True,
                "htp_compilation_requested": False,
                "phone_access": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    converted = []
    try:
        for ar, parts in zip((1, 128), transformed, strict=True):
            exported = parts[0]
            builder._conversion_config.input_tensor_config = get_input_layout(exported.onnx_path)
            model = builder.convert(
                exported,
                builder._conversion_config,
                builder._calibration_config,
            )
            module_path = Path(model.module.path)
            converted.append(
                {
                    "ar": ar,
                    "model_name": model.name,
                    "dlc_path": str(module_path),
                    "dlc_bytes": module_path.stat().st_size,
                    "dlc_sha256": sha256(module_path),
                }
            )
    except Exception as error:
        print(
            json.dumps(
                {
                    "event": "qnn_conversion_failed",
                    "exception_type": type(error).__name__,
                    "exception_message": str(error),
                    "converted_before_failure": converted,
                    "qnn_conversion_requested": True,
                    "htp_compilation_requested": False,
                    "phone_access": False,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        raise

    print(
        json.dumps(
            {
                "event": "qnn_conversion_complete",
                "qairt_version": "2.49.40.260810",
                "target_configuration": "chipset:SM8550",
                "converted_models": converted,
                "qnn_conversion_requested": True,
                "htp_compilation_requested": False,
                "phone_access": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
