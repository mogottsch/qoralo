#!/usr/bin/env python3
"""Compile corrected AR1 and original AR128 as one SM8550 weight-shared context."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from qairt_constant_compat import install

EXP = Path(__file__).resolve().parents[1]
CKPT = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16"
SOURCE_CACHE = EXP / ".local/qairt-2.49.40-transform-compat"
AR1_CACHE = EXP / ".local/qairt-2.49.40-cache-aligned-v5"
COMPILE_CACHE = EXP / ".local/qairt-2.49.40-context-cache-aligned-v5"
EXPECTED_DLCS = {
    1: "7e88facdba8c8b015579cbc3bf76dbad4f2f913cd29b450d555d6174bd48c9e1",
    128: "5f17ece8a99cd649abdadb61e2e104e5cd569a1d1735e9e6ecb5c297286156ee",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_dlc(ar: int) -> Path:
    cache = AR1_CACHE if ar == 1 else SOURCE_CACHE
    matches = list(cache.rglob(f"ar{ar}_cl4096_1_of_1.dlc"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one AR{ar} DLC, found {len(matches)}")
    if sha256(matches[0]) != EXPECTED_DLCS[ar]:
        raise RuntimeError(f"AR{ar} DLC hash mismatch")
    return matches[0]


def main() -> None:
    from qairt import Model
    from qairt.api.compiler.config import CompilerModes
    from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory

    install()
    builder = GenAIBuilderFactory.create(
        str(CKPT), "HTP", cache_root=str(COMPILE_CACHE),
        tokenizer_path=str(CKPT / "tokenizer.json"), config_path=str(CKPT / "config.json"),
    )
    builder.set_targets(["chipset:SM8550"])
    builder._prepare_embedding_lut = False
    config = builder._compilation_config
    if config is None or not config.graph_custom_configs:
        raise RuntimeError("missing HTP compilation graph configuration")

    dlcs = [(ar, find_dlc(ar)) for ar in (1, 128)]
    models = [Model.load(path) for _, path in dlcs]
    template = config.graph_custom_configs[0]
    for model in models:
        graph_config = template.model_copy(deep=True)
        graph_config.name = model.name
        config.graph_custom_configs.append(graph_config)
    if config.graph_custom_configs[0].name == "placeholder":
        config.graph_custom_configs.pop(0)
    config.set_mode(CompilerModes.WEIGHT_SHARING.value)

    print(json.dumps({
        "event": "cache_aligned_htp_compile_start",
        "qairt_version": "2.49.40.260810",
        "target": "chipset:SM8550", "soc_model": 43, "dsp_arch": "v73",
        "pd_session": "unsigned", "mode": "weight_sharing",
        "models": [
            {"ar": ar, "name": model.name, "dlc_sha256": EXPECTED_DLCS[ar]}
            for (ar, _), model in zip(dlcs, models, strict=True)
        ],
        "graph_configs": [item.name for item in config.graph_custom_configs],
        "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)
    try:
        compiled = builder.compile(models, config)
        context_path = Path(compiled.module.path)
        context = {"path": str(context_path), "bytes": context_path.stat().st_size,
                   "sha256": sha256(context_path), "name": compiled.name}
    except Exception as error:
        print(json.dumps({
            "event": "cache_aligned_htp_compile_failed",
            "exception_type": type(error).__name__, "exception_message": str(error),
            "target": "chipset:SM8550", "mode": "weight_sharing",
            "phone_access": False, "inference": False,
        }, sort_keys=True), flush=True)
        raise
    print(json.dumps({
        "event": "cache_aligned_htp_compile_complete", "qairt_version": "2.49.40.260810",
        "target": "chipset:SM8550", "soc_model": 43, "dsp_arch": "v73",
        "mode": "weight_sharing", "context": context,
        "phone_access": False, "inference": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
