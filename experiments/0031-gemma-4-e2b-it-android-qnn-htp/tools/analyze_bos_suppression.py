#!/usr/bin/env python3
"""Prove host-side Genie BOS suppression and exact canonical short token identity."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from tokenizers import Tokenizer

EXP = Path(__file__).resolve().parents[1]
SDK = Path("/home/moritz/opt/qairt/2.49.40.260810")
BUNDLE = EXP / ".local/runtime-bundle"
OUT = EXP / "results/genie-automatic-bos-suppression/result.json"
EXPECTED = {
    "context_cpp": "2e46999f7e519b321120ffc2f614c57805958a823fc15f1efa8acbc997a2c62b",
    "lut_cpp": "ff7a399f9c14fb20ba21495a2dc51f025d6f88a86148f85b7682ee38ae43bc0f",
    "standalone_sampler_example": "4a04629be725c5cef11719252253ac2755dc001102a9ae2cb04eb70783956598",
    "prefix_quant_docs": "725e5af3538ee6132f5ccdcd218f90a9f2d694571ea0b483b40e6faa1b73a2ff",
    "rendered_short": "b286f8dda746e8056836a2e71049df866527bee51e368363dd80cfbe27e60e7a",
    "short_token_ids": "31a85f9c813266bbbb3505a04a226a9b184882b636cc2f6f67193a6b1eb2ad78",
    "tokenizer": "cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f",
    "context": "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394",
}
SOURCES = {
    "context_cpp": SDK / "examples/Genie/Genie/src/qualla/context.cpp",
    "lut_cpp": SDK / "examples/Genie/Genie/src/qualla/encoders/text-encoders/LUT.cpp",
    "standalone_sampler_example": SDK / "examples/Genie/configs/standalone-sampler.json",
    "prefix_quant_docs": SDK / "docs/QAIRT-Docs/Genie/general/tutorials/dialog/prefix_quant/prefix_quant.html",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    for name, path in SOURCES.items():
        if sha256(path) != EXPECTED[name]:
            raise RuntimeError(f"QAIRT BOS source identity mismatch: {name}")
    context_source = SOURCES["context_cpp"].read_text(errors="replace")
    lut_source = SOURCES["lut_cpp"].read_text(errors="replace")
    example = json.loads(SOURCES["standalone_sampler_example"].read_text())
    docs = SOURCES["prefix_quant_docs"].read_text(errors="replace")
    if 'conf.optional<int32_t>("bos-token", -1)' not in context_source:
        raise RuntimeError("QAIRT context does not retain negative BOS sentinel semantics")
    if "if (_ctx->bos_tok() >= 0)" not in lut_source or "p_vec.push_back(_ctx->bos_tok())" not in lut_source:
        raise RuntimeError("QAIRT LUT BOS insertion branch mismatch")
    if example["standalone-sampler"]["context"]["bos-token"] != -1:
        raise RuntimeError("shipped negative-BOS example mismatch")
    if 'set “bos-token” as -1' not in docs:
        raise RuntimeError("shipped BOS suppression documentation mismatch")

    config_path = BUNDLE / "gemma4-e2b-htp-cl4096-greedy.json"
    config = json.loads(config_path.read_text())
    context = config["dialog"]["context"]
    if context["bos-token"] != -1 or context["eos-token"] != [1, 106]:
        raise RuntimeError("corrected Genie context token configuration mismatch")
    manifest = json.loads((BUNDLE / "runtime-manifest.json").read_text())
    context_name = "models/weight_sharing_model_ar128_ar1_cl4096_scl512_1_of_1.serialized.bin"
    if manifest["files"][context_name]["sha256"] != EXPECTED["context"]:
        raise RuntimeError("BOS-corrected bundle context mismatch")

    rendered = EXP / "protocol/rendered/short.txt"
    token_file = EXP / "protocol/token-ids/short.int32le"
    tokenizer_path = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16/tokenizer.json"
    if sha256(rendered) != EXPECTED["rendered_short"] or sha256(token_file) != EXPECTED["short_token_ids"]:
        raise RuntimeError("canonical short identity mismatch")
    if sha256(tokenizer_path) != EXPECTED["tokenizer"]:
        raise RuntimeError("tokenizer identity mismatch")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    ids = tokenizer.encode(rendered.read_text(), add_special_tokens=False).ids
    raw = b"".join(struct.pack("<i", token) for token in ids)
    if raw != token_file.read_bytes() or hashlib.sha256(raw).hexdigest() != EXPECTED["short_token_ids"]:
        raise RuntimeError("host tokenizer does not reproduce bound token IDs")
    leading_bos = 0
    for token in ids:
        if token != 2:
            break
        leading_bos += 1
    if len(ids) != 170 or leading_bos != 1:
        raise RuntimeError("bound short prompt is not the exact single-BOS 170-token sequence")

    attempt04 = json.loads(
        (EXP / "results/android-qnn-physical-viability-attempt-04/result.json").read_text()
    )
    if attempt04["prompt_identity"]["effective_extra_leading_bos_count"] != 1:
        raise RuntimeError("attempt-04 automatic-BOS diagnosis mismatch")

    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_genie_automatic_bos_suppression_and_effective_token_proof",
        "status": "automatic_bos_suppressed_host_proven_stage_rebuild_required",
        "claim_boundary": (
            "QAIRT 2.49.40 source and shipped examples/documentation define negative bos-token as the no-prepend "
            "sentinel, and the LUT encoder inserts BOS only for nonnegative values. The corrected private config "
            "sets bos-token=-1. The pinned tokenizer independently reproduces the exact committed 170-token, "
            "single-BOS sequence from unchanged canonical rendered bytes. Therefore the host-derived effective "
            "sequence is exactly the bound sequence with no automatic prefix. This is host proof; a later locked "
            "physical gate must confirm Genie's runtime profile/log reports the same 170-token identity."
        ),
        "attempt04_diagnosis": {
            "bound_prompt_tokens": 170,
            "runtime_prompt_tokens": 171,
            "effective_extra_leading_bos_count": 1,
            "source_result": "results/android-qnn-physical-viability-attempt-04/result.json",
        },
        "correction": {
            "config_path": "gemma4-e2b-htp-cl4096-greedy.json",
            "bos_token_config_before": 2,
            "bos_token_config_after": -1,
            "canonical_workload_bytes_changed": False,
            "rendered_prompt_bytes_changed": False,
            "tokenizer_changed": False,
            "model_or_context_changed": False,
            "source_semantics": {
                "negative_bos_is_sentinel": True,
                "lut_prepends_only_when_bos_nonnegative": True,
                "shipped_negative_bos_example_present": True,
                "shipped_documentation_uses_negative_bos_to_suppress_prefix": True,
            },
        },
        "effective_short_identity": {
            "rendered_sha256": EXPECTED["rendered_short"],
            "tokenizer_sha256": EXPECTED["tokenizer"],
            "token_count": len(ids),
            "leading_bos_count": leading_bos,
            "first_token_ids": ids[:8],
            "token_ids_int32le_sha256": EXPECTED["short_token_ids"],
            "matches_committed_token_ids_byte_for_byte": True,
            "host_effective_sequence_exact": True,
        },
        "qairt_source_provenance": {
            name: {"path": str(path), "bytes": path.stat().st_size, "sha256": EXPECTED[name]}
            for name, path in SOURCES.items()
        },
        "bundle": {
            "context_sha256": EXPECTED["context"],
            "config_sha256": sha256(config_path),
            "runtime_manifest_sha256": sha256(BUNDLE / "runtime-manifest.json"),
        },
        "requested": {
            "phone_access": False, "phone_lock": False, "physical_htp_execution": False,
            "inference": False, "campaign": False,
        },
        "next_gate": (
            "Rebuild/hash the private stage, obtain independent review and a new explicit phone handoff, then "
            "confirm one bounded run reports exactly 170 prompt tokens and no extra BOS before any campaign."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
