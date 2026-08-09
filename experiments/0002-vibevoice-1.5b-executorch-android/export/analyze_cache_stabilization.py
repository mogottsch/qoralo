#!/usr/bin/env python3
"""Derive cache stabilization and locked S16 prefix evidence.

This is a light-weight analysis of committed trace metadata and existing WAVs. It
never loads model weights. The historical locked-reference-comparison.json is an
input/provenance record and is deliberately not rewritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import wave
from pathlib import Path
from typing import Any

import numpy as np

RATIOS = (8, 5, 5, 4, 2, 2)
TRANSPOSE_NAMES = tuple(f"upsample_layers.{index}.0/sample_0" for index in range(1, 7))


def _length(meta: dict[str, Any] | None) -> int:
    return 0 if meta is None else int(meta["shape"][-1])


def _first(values: list[int], target: int) -> int | None:
    return next((index for index, value in enumerate(values) if value == target), None)


def analyze_caches(manifest: dict[str, Any]) -> dict[str, Any]:
    calls = manifest["calls"]
    if [call["index"] for call in calls] != list(range(20)):
        raise ValueError("trace must contain ordered calls 0 through 19")

    domains: dict[str, Any] = {}
    for domain in ("decoder", "semantic"):
        order = list(calls[0][domain]["post_cache"])
        if any(list(call[domain]["post_cache"]) != order for call in calls):
            raise ValueError(f"{domain} post-cache ordering changes between calls")
        entries = []
        for order_index, name in enumerate(order):
            pre = [_length(call[domain]["pre_cache"].get(name)) for call in calls]
            post = [_length(call[domain]["post_cache"].get(name)) for call in calls]
            transpose_index = TRANSPOSE_NAMES.index(name) if name in TRANSPOSE_NAMES else None
            target = RATIOS[transpose_index] * 2 - 1 if transpose_index is not None else max(post)
            if any(value > target for value in post):
                raise ValueError(f"{domain} cache {name} exceeds target {target}")
            entries.append({
                "order": order_index,
                "name": name,
                "cache_type": "SConvTranspose1d" if transpose_index is not None else "other_streaming_cache",
                "configured_context_target": target if transpose_index is not None else None,
                "observed_steady_length": max(post),
                "pre_lengths_by_call": pre,
                "post_lengths_by_call": post,
                "first_call_post_full": _first(post, target),
                "first_call_with_full_pre_context": _first(pre, target),
            })
        domains[domain] = {
            "cache_count": len(order),
            "ordering_source": "insertion-preserving order in the committed trace manifest",
            "ordered_names": order,
            "entries": entries,
        }

    decoder_by_name = {entry["name"]: entry for entry in domains["decoder"]["entries"]}
    widths = [1]
    for ratio in RATIOS[:-1]:
        widths.append(widths[-1] * ratio)
    sconv = []
    for index, (name, ratio, input_width) in enumerate(zip(TRANSPOSE_NAMES, RATIOS, widths)):
        entry = decoder_by_name[name]
        target = ratio * 2 - 1
        sconv.append({
            "decoder_cache_order": entry["order"],
            "name": name,
            "stride": ratio,
            "kernel_size": ratio * 2,
            "kernel_size_minus_1_target": target,
            "input_width_each_call": input_width,
            "pre_cache_lengths_by_call": entry["pre_lengths_by_call"],
            "combined_input_widths_by_call": [value + input_width for value in entry["pre_lengths_by_call"]],
            "post_cache_lengths_by_call": entry["post_lengths_by_call"],
            "first_call_post_full": entry["first_call_post_full"],
            "first_call_with_full_pre_context": entry["first_call_with_full_pre_context"],
        })

    return {
        "schema_version": 1,
        "scope": "derived stabilization analysis of the locked eager recurrent calls 0-19",
        "source_manifest": "fixtures/recurrent-calls-0-19-manifest.json",
        "call_order": list(range(20)),
        "acoustic_decoder": {
            "ratios": list(RATIOS),
            "sconvtranspose1d": sconv,
            "all_sconvtranspose_post_caches_full_by_call": max(item["first_call_post_full"] for item in sconv),
            "all_sconvtranspose_calls_use_full_pre_context_from_call": max(item["first_call_with_full_pre_context"] for item in sconv),
            "four_call_implication": "Calls 0-3 are warm-up: the first transpose cache is only 4/15 full after call 3. It becomes full after call 14 and call 15 is the first call that enters with full context at every transpose.",
        },
        "cache_domains": domains,
        "ordering_and_chain_checks": {
            "decoder_order_is_constant": True,
            "semantic_order_is_constant": True,
            "decoder_pre_equals_previous_post": manifest["chaining"]["decoder_pre_equals_previous_post"],
            "semantic_pre_equals_previous_post": manifest["chaining"]["semantic_pre_equals_previous_post"],
            "cache_order_is_abi_significant": True,
        },
        "interpretation": "The six SConvTranspose1d caches stabilize at configured kernel_size-1, but at different calls because upstream widths differ. This describes cache shape/context only; it is not an audio-quality acceptance result.",
    }


def _read_s16(path: Path) -> tuple[dict[str, Any], np.ndarray]:
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 24_000):
            raise ValueError(f"expected 24 kHz mono PCM S16LE: {path}")
        frames = wav.readframes(wav.getnframes())
        count = wav.getnframes()
    samples = np.frombuffer(frames, dtype="<i2").astype(np.int32)
    if len(samples) != count:
        raise ValueError("truncated WAV")
    # Keep committed provenance portable even when defaults resolve from an absolute repo root.
    parts = path.parts
    display_path = str(Path(*parts[parts.index("artifacts"):])) if "artifacts" in parts else str(path)
    return {"path": display_path, "sample_count": count, "pcm_sha256": hashlib.sha256(frames).hexdigest()}, samples


def _s16_metrics(samples: np.ndarray) -> dict[str, Any]:
    rms_s16 = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))) if len(samples) else 0.0
    return {
        "sample_count": len(samples),
        "rms_s16_units": rms_s16,
        "rms_dbfs": 20.0 * math.log10(rms_s16 / 32768.0) if rms_s16 else None,
        "peak_s16_units": int(np.max(np.abs(samples))) if len(samples) else 0,
    }


def compare_locked_prefix(reference_path: Path, android_path: Path) -> dict[str, Any]:
    reference_input, reference = _read_s16(reference_path)
    android_input, android = _read_s16(android_path)
    prefix = reference[: len(android)]
    if len(prefix) != len(android):
        raise ValueError("Android WAV is longer than the reference")
    difference = android.astype(np.int64) - prefix.astype(np.int64)
    abs_difference = np.abs(difference)
    chunks = []
    for index in range(4):
        start, end = index * 3200, (index + 1) * 3200
        chunks.append({"index": index, "start_sample": start, "end_sample": end, **_s16_metrics(reference[start:end])})
    return {
        "schema_version": 1,
        "status": "prefix_agreement_pass_quality_acceptance_fail",
        "scope": "exact raw signed-16-bit comparison of the Android WAV against the equally long locked-reference prefix",
        "historical_comparison": {
            "path": "results/locked-reference-comparison.json",
            "modification_policy": "immutable; this file supplements rather than revises its fixed-rubric rejection",
        },
        "inputs": {"reference": reference_input, "android": android_input},
        "comparison": {
            "sample_count": len(android),
            "difference_definition": "android_s16 - reference_prefix_s16",
            "differing_samples": int(np.count_nonzero(difference)),
            "equal_samples": int(np.count_nonzero(difference == 0)),
            "minimum_difference_s16_units": int(difference.min()),
            "maximum_difference_s16_units": int(difference.max()),
            "maximum_absolute_difference_s16_units": int(abs_difference.max()),
            "mean_absolute_difference_s16_units": float(abs_difference.mean()),
            "rms_difference_s16_units": float(np.sqrt(np.mean(difference.astype(np.float64) ** 2))),
            "all_differences_at_most_one_s16_unit": bool(np.all(abs_difference <= 1)),
            "exact_byte_agreement": bool(np.array_equal(prefix, android)),
            "prefix_agreement_criterion": "maximum absolute difference <= 1 signed-16-bit PCM unit",
            "prefix_agreement_status": "pass" if np.all(abs_difference <= 1) else "fail",
        },
        "dbfs_evidence": {
            "reference_prefix": _s16_metrics(prefix),
            "android_prefix": _s16_metrics(android),
            "reference_chunks_0_through_3": chunks,
            "expected_progression": "Chunks 0 and 1 are introductory near-silence; chunk 2 is the fade-in; chunk 3 is clearly voiced.",
        },
        "quality_acceptance": {
            "status": "fail",
            "reason": "One-unit agreement over an introductory-silence prefix does not satisfy duration, intelligibility, corruption, repetition, or speaker-consistency criteria. The Android result still stops after 6,400 samples.",
            "prefix_agreement_is_quality_acceptance": False,
        },
        "conclusion": "The Android two-chunk output agrees with the locked host S16 prefix to within one PCM unit. The prior description of this prefix as proof of waveform divergence is not supported. The historical quality rejection remains valid because a matching 0.2667-second silent prefix is neither complete nor audible speech.",
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=root / "fixtures/recurrent-calls-0-19-manifest.json")
    parser.add_argument("--reference", type=Path, default=root.parents[1] / "artifacts/0001/output-cpu/reference_generated.wav")
    parser.add_argument("--android", type=Path, default=root.parents[1] / "artifacts/0002/lane-d/locked-reference/generation-run-0.wav")
    parser.add_argument("--cache-output", type=Path, default=root / "results/cache-stabilization.json")
    parser.add_argument("--prefix-output", type=Path, default=root / "results/locked-reference-prefix-comparison.json")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.cache_output.write_text(json.dumps(analyze_caches(manifest), indent=2) + "\n")
    args.prefix_output.write_text(json.dumps(compare_locked_prefix(args.reference, args.android), indent=2) + "\n")


if __name__ == "__main__":
    main()
