#!/usr/bin/env python3
"""Bounded no-compile support probe for the public Gemma4 w4a16 checkpoint."""
from __future__ import annotations

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
CHECKPOINT = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16"
CACHE = EXP / ".local/qairt-builder-probe-cache"


def main() -> None:
    from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory

    print(json.dumps({
        "event": "probe_start",
        "checkpoint": str(CHECKPOINT),
        "python": sys.version,
        "compile_requested": False,
    }, sort_keys=True), flush=True)
    builder = GenAIBuilderFactory.create(
        str(CHECKPOINT),
        "HTP",
        cache_root=str(CACHE),
        tokenizer_path=str(CHECKPOINT / "tokenizer.json"),
        config_path=str(CHECKPOINT / "config.json"),
    )
    print(json.dumps({
        "event": "builder_created",
        "builder_class": f"{builder.__class__.__module__}.{builder.__class__.__name__}",
        "backend": str(getattr(builder, "backend_type", getattr(builder, "_backend_type", None))),
        "model_path": str(builder.framework_model_path),
    }, sort_keys=True), flush=True)
    builder.set_targets(["chipset:SM8550"])
    config = builder.config
    transform = builder._transformation_config.model_transformer_config
    resolved = builder._compilation_config._soc_details_resolved
    print(json.dumps({
        "event": "target_applied",
        "context_size": getattr(config, "context_size", None),
        "hidden_size": getattr(config, "n_embd", None),
        "layers": getattr(config, "n_layer", None),
        "vocab": getattr(config, "n_vocab", None),
        "target": "chipset:SM8550",
        "resolved_target": {
            "chipset": getattr(resolved, "chipset", None),
            "dsp_arch": getattr(resolved, "dsp_arch", None),
            "model": getattr(resolved, "model", None),
            "num_of_hvx_threads": getattr(resolved, "num_of_hvx_threads", None),
            "vtcm_size_in_mb": getattr(resolved, "vtcm_size_in_mb", None),
        },
        "transform": {
            "auto_regression_number": transform.arn_cl_options.auto_regression_number,
            "context_length": transform.arn_cl_options.context_length,
            "num_splits": transform.split_model.num_splits,
            "split_embedding": transform.split_model.split_embedding,
            "split_lm_head": transform.split_model.split_lm_head,
        },
        "compile_requested": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
