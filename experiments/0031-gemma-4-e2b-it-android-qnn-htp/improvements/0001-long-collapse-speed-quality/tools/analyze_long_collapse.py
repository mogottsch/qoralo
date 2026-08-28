#!/usr/bin/env python3
"""Quantify the completed QNN long collapse and compare accepted LiteRT references."""
from __future__ import annotations

import collections
import hashlib
import json
import re
import statistics
from pathlib import Path

from tokenizers import Tokenizer

HERE = Path(__file__).resolve()
TRACK = HERE.parents[1]
EXP = HERE.parents[3]
REPO = EXP.parents[1]
QNN_RESULT = EXP / "results/android-qnn-physical-campaign-attempt-02/result.json"
QNN_OUTPUT_DIR = EXP / "results/android-qnn-physical-campaign-attempt-02/raw/campaign/outputs"
QNN_TOKENIZER = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16/tokenizer.json"
REF_EXP = REPO / "experiments/0025-gemma-4-e2b-it-android"
OUT = TRACK / "results/long-collapse-baseline/result.json"
EXPECTED_LONG_RENDERED = "450b519d417e29c4239e39aef856db1813d2580cd62e9db9adaae3d94ba8f260"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def common_words(text: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", text.lower(), re.UNICODE)


def first_divergence(left: list[object], right: list[object]) -> int | None:
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return None if len(left) == len(right) else min(len(left), len(right))


def trajectory_metrics(ids: list[int], text: str) -> dict[str, object]:
    ngrams = {}
    for width in (4, 8, 16):
        values = [tuple(ids[index : index + width]) for index in range(len(ids) - width + 1)]
        counts = collections.Counter(values)
        top, count = counts.most_common(1)[0]
        positions = [index for index, value in enumerate(values) if value == top]
        ngrams[str(width)] = {
            "total": len(values),
            "unique": len(counts),
            "unique_ratio": len(counts) / len(values),
            "most_common_count": count,
            "most_common_first_token_index_zero_based": positions[0],
        }

    periodic = None
    for period in range(1, 65):
        index = len(ids) - period - 1
        while index >= 0 and ids[index] == ids[index + period]:
            index -= 1
        start = index + 1
        coverage = len(ids) - start
        if coverage < period * 2:
            continue
        candidate = {
            "start_token_index_zero_based": start,
            "period_tokens": period,
            "suffix_tokens": coverage,
            "complete_cycles": coverage // period,
            "trailing_partial_cycle_tokens": coverage % period,
        }
        if periodic is None or candidate["suffix_tokens"] > periodic["suffix_tokens"]:
            periodic = candidate

    collapse_onset = None
    window = 128
    width = 4
    for start in range(len(ids) - window + 1):
        grams = [tuple(ids[index : index + width]) for index in range(start, start + window - width + 1)]
        ratio = len(set(grams)) / len(grams)
        if ratio <= 0.25:
            collapse_onset = {
                "criterion": "first 128-token window whose 4-gram unique ratio is <= 0.25",
                "start_token_index_zero_based": start,
                "start_token_ordinal_one_based": start + 1,
                "observed_unique_ratio": ratio,
            }
            break

    words = common_words(text)
    word_grams = [tuple(words[index : index + 6]) for index in range(len(words) - 5)]
    word_counts = collections.Counter(word_grams)
    top_words, top_count = word_counts.most_common(1)[0]
    top_first = next(index for index, value in enumerate(word_grams) if value == top_words)
    return {
        "token_count": len(ids),
        "word_token_count": len(words),
        "ngram_metrics": ngrams,
        "rolling_collapse_onset": collapse_onset,
        "exact_periodic_suffix": periodic,
        "dominant_word_6gram": {
            "text": " ".join(top_words),
            "count": top_count,
            "first_word_index_zero_based": top_first,
        },
    }


def load_reference(backend: str) -> tuple[dict[str, object], dict[str, object], Path]:
    result_path = REF_EXP / f"results/android-{backend}-campaign/result.json"
    result = json.loads(result_path.read_text())
    stdout = REF_EXP / f"results/android-{backend}-campaign/raw/runner-stdout.jsonl"
    payload = json.loads(next(line for line in stdout.read_text().splitlines() if line.startswith("{")))
    payload_run = next(item for item in payload["runs"] if item["tier"] == "long")
    result_run = next(item for item in result["runs"] if item["id"] == payload_run["id"])
    run = dict(result_run)
    run["emitted_token_ids"] = payload_run["emitted_token_ids"]
    output = REF_EXP / f"results/android-{backend}-campaign" / result_run["output"]["path"]
    return result, run, output


def pct_change(candidate: float, baseline: float) -> float:
    return (candidate / baseline - 1) * 100


def main() -> None:
    qnn = json.loads(QNN_RESULT.read_text())
    qnn_outputs = sorted(QNN_OUTPUT_DIR.glob("warm-long-*.txt"))
    if len(qnn_outputs) != 5:
        raise RuntimeError("expected five retained QNN long outputs")
    qnn_hashes = {sha256(path) for path in qnn_outputs}
    if qnn_hashes != {"f0e9d284f679e2ae426264573bd2be16e7c1e4b190235a3511c5a92ecc097b2d"}:
        raise RuntimeError("QNN long output identity mismatch")
    qnn_text = qnn_outputs[0].read_text()
    tokenizer = Tokenizer.from_file(str(QNN_TOKENIZER))
    qnn_ids = tokenizer.encode(qnn_text, add_special_tokens=False).ids
    if len(qnn_ids) != 2048:
        raise RuntimeError("QNN output does not round-trip to the profiled 2048 tokens")
    qnn_metrics = trajectory_metrics(qnn_ids, qnn_text)
    if qnn_metrics["rolling_collapse_onset"]["start_token_index_zero_based"] != 83:
        raise RuntimeError("QNN collapse onset drifted")
    if qnn_metrics["exact_periodic_suffix"] != {
        "start_token_index_zero_based": 478,
        "period_tokens": 9,
        "suffix_tokens": 1570,
        "complete_cycles": 174,
        "trailing_partial_cycle_tokens": 4,
    }:
        raise RuntimeError("QNN periodic suffix drifted")

    references = {}
    reference_payloads = {}
    for backend in ("gpu", "cpu"):
        result, run, output = load_reference(backend)
        ids = run["emitted_token_ids"]
        if len(ids) != run["output_tokens"] or sha256(output) != run["output"]["sha256"]:
            raise RuntimeError(f"LiteRT {backend} output identity mismatch")
        metrics = trajectory_metrics(ids, output.read_text())
        if metrics["exact_periodic_suffix"] is not None:
            raise RuntimeError(f"LiteRT {backend} unexpectedly has repeated periodic suffix")
        references[backend] = {
            "experiment": "0025-gemma-4-e2b-it-android",
            "artifact_sha256": result["artifact_identity"]["model_sha256"],
            "artifact_bytes": result["artifact_identity"].get("model_bytes", 2_588_147_712),
            "rendered_long_sha256": result["prompts"]["long"]["rendered_sha256"],
            "input_tokens": result["prompts"]["long"]["input_tokens"],
            "output_tokens": run["output_tokens"],
            "stop_reason": run["stop_reason"],
            "output_sha256": run["output"]["sha256"],
            "output_sanity": run["output_sanity"],
            "trajectory": metrics,
        }
        reference_payloads[backend] = (result, run, output)

    gpu_ids = reference_payloads["gpu"][1]["emitted_token_ids"]
    cpu_ids = reference_payloads["cpu"][1]["emitted_token_ids"]
    gpu_text = reference_payloads["gpu"][2].read_text()
    cpu_text = reference_payloads["cpu"][2].read_text()
    qnn_words, gpu_words, cpu_words = map(common_words, (qnn_text, gpu_text, cpu_text))
    if first_divergence(qnn_words, gpu_words) != 0 or first_divergence(qnn_words, cpu_words) != 0:
        raise RuntimeError("cross-route common-text divergence boundary changed")
    if first_divergence(gpu_ids, cpu_ids) != 5:
        raise RuntimeError("LiteRT CPU/GPU trajectory divergence boundary changed")

    qnn_warm = qnn["warm_distributions"]
    gpu_agg = reference_payloads["gpu"][0]["loaded_route_aggregates"]
    comparisons = {}
    for tier in ("short", "medium", "long"):
        htp = {
            "ttft_seconds": qnn_warm[tier]["ttft_us"]["median"] / 1_000_000,
            "prefill_tokens_per_second": qnn_warm[tier]["prefill_tokens_per_second"]["median"],
            "raw_genie_decode_observation_tokens_per_second": qnn_warm[tier]["decode_tokens_per_second"]["median"],
            "decode_rate_first_token_inclusion": None,
            "decode_rate_strictly_normalized_comparable": False,
            "total_seconds": qnn_warm[tier]["total_request_us"]["median"] / 1_000_000,
            "output_tokens": qnn_warm[tier]["generated_tokens"][0],
            "sensible": qnn_warm[tier]["all_output_sanity_passed"],
        }
        gpu = {
            "ttft_seconds": gpu_agg[tier]["request_to_first_token_seconds"]["median"],
            "prefill_tokens_per_second": gpu_agg[tier]["prefill_tokens_per_second"]["median"],
            "normalized_decode_tokens_per_second": gpu_agg[tier]["decode_tokens_per_second"]["median"],
            "decode_rate_first_token_inclusion": False,
            "total_seconds": gpu_agg[tier]["total_seconds"]["median"],
            "output_tokens": gpu_agg[tier]["output_tokens"]["median"],
            "sensible": True,
        }
        comparisons[tier] = {
            "accepted_htp": htp,
            "accepted_litert_gpu": gpu,
            "gpu_vs_htp_percent": {
                "ttft": pct_change(gpu["ttft_seconds"], htp["ttft_seconds"]),
                "prefill_rate": pct_change(gpu["prefill_tokens_per_second"], htp["prefill_tokens_per_second"]),
                "decode_rate": None,
                "decode_rate_reason": (
                    "QNN is a raw Genie rate whose first-token inclusion is unspecified; LiteRT explicitly excludes "
                    "the first token. The numerical delta is not a normalized optimization metric."
                ),
                "total_completion_time": pct_change(gpu["total_seconds"], htp["total_seconds"]),
            },
        }

    qnn_abs_onset = 1929 + qnn_metrics["rolling_collapse_onset"]["start_token_index_zero_based"]
    qnn_abs_periodic = 1929 + qnn_metrics["exact_periodic_suffix"]["start_token_index_zero_based"]
    candidate_matrix = [
        {
            "priority": 1,
            "candidate": "explicit request-level HTP/LiteRT-GPU hybrid",
            "partition": "short and medium requests remain on QNN HTP; long requests use the accepted LiteRT GPU route",
            "fallback_semantics": "No tensor-level or hidden fallback; backend is selected before each complete logical request and labeled in evidence.",
            "quality_evidence": "Accepted GPU long output is sensible and EOS-stops at 756 tokens; HTP long repeats to 2048.",
            "speed_evidence": comparisons,
            "memory_setup_boundary": "Two distinct route setups if co-resident; accepted setup is 2.112 s HTP plus 10.520 s GPU and process-memory observations are not additive HTP/GPU-private memory.",
            "assessment": "Best currently evidenced speed+quality option: preserves faster HTP short/medium completion and cuts accepted long median completion time by about 59.1% (59.147%). Raw decode rates are not used for this decision.",
        },
        {
            "priority": 2,
            "candidate": "fallback-free HTP FP16 value caches on the three global-attention layers",
            "partition": "Keep all transformer ops on HTP; change only past_value_{4,9,14} AR1/AR128 cache IO from uFxp16 to identical FP16 and remove their conversion boundaries.",
            "rationale": "Global value caches carry the complete long history and are the narrowest stateful precision boundary implicated by long-position failure.",
            "speed_hypothesis": "Same 16-bit storage width and fewer Convert ops could avoid a speed loss, but this is unmeasured.",
            "assessment": "Smallest fallback-free precision experiment; requires host reconvert/recompile and bounded trajectory evidence.",
        },
        {
            "priority": 3,
            "candidate": "fallback-free HTP FP16 value caches on all 15 layers",
            "partition": "Keep keys and all compute on HTP; make every AR1/AR128 value cache IO identically FP16.",
            "rationale": "Tests broader cache-quantization accumulation if global-only precision is insufficient.",
            "speed_hypothesis": "May remove conversions but increases FP16 execution exposure; unmeasured.",
            "assessment": "Broader diagnostic, not first choice.",
        },
        {
            "priority": 4,
            "candidate": "normalization precision/fusion variant",
            "partition": "HTP-only; preserve fused FP16 RmsNorm/value path without the correction-induced expanded float component pattern.",
            "rationale": "The corrected AR1 conversion reports 75 float-precision normalization components and explicit value conversions.",
            "assessment": "Potential interaction, but less state-specific than global cache precision.",
        },
    ]

    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "improvement_track": "0001-long-collapse-speed-quality",
        "classification": "host_long_collapse_quantification_cross_route_comparison_and_candidate_ranking",
        "claim_boundary": (
            "This host-only milestone quantifies retained text/token trajectories and compares already accepted "
            "campaigns. QNN and LiteRT use different deployment artifacts, quantization schemes, and tokenizers; "
            "their outputs diverge at the first common word, so text cannot identify a numerical first-logit or "
            "internal-state divergence. The cause matrix ranks bounded hypotheses rather than claiming causality. "
            "No completed campaign file, registry row, phone run, or model artifact is changed."
        ),
        "qnn_collapse": {
            "output_count": len(qnn_outputs),
            "all_outputs_byte_identical": True,
            "output_sha256": next(iter(qnn_hashes)),
            "profile_generated_tokens": 2048,
            "retokenized_output_matches_profile_count": True,
            "trajectory": qnn_metrics,
            "absolute_context_positions": {
                "prompt_tokens": 1929,
                "rolling_collapse_onset_zero_based": qnn_abs_onset,
                "exact_periodic_suffix_start_zero_based": qnn_abs_periodic,
                "maximum_position_reached_exclusive": 1929 + 2048,
                "context_capacity": 4096,
                "crossed_context_boundary": False,
            },
        },
        "accepted_references": references,
        "cross_route_comparison": {
            "identical_rendered_long_bytes": all(
                value["rendered_long_sha256"] == EXPECTED_LONG_RENDERED for value in references.values()
            ) and sha256(EXP / "protocol/rendered/long.txt") == EXPECTED_LONG_RENDERED
            and qnn["requests"][11]["input_tokens"] == 1929,
            "tokenizer_spaces_are_different": True,
            "qnn_vs_gpu_first_common_word_divergence_zero_based": first_divergence(qnn_words, gpu_words),
            "qnn_vs_cpu_first_common_word_divergence_zero_based": first_divergence(qnn_words, cpu_words),
            "litert_gpu_vs_cpu_first_emitted_token_divergence_zero_based": first_divergence(gpu_ids, cpu_ids),
            "inference_limit": "No cross-route token-ID/logit equality claim: tokenizers and artifacts differ, and QNN emitted IDs were not directly retained.",
            "performance": comparisons,
            "performance_comparability": {
                "total_completion_time": (
                    "Comparable as end-to-end completion on identical rendered bytes, but output counts/stops differ: "
                    "HTP repeats to 2048 while LiteRT GPU EOS-stops at 756."
                ),
                "ttft": "Protocol-aligned observations from different runtimes; tokenizer counts differ by one token.",
                "prefill": "Same rendered bytes but route-native tokenizer counts are 1929 HTP vs 1930 LiteRT.",
                "decode": (
                    "Not strictly normalized: Genie first-token inclusion is unspecified while LiteRT excludes it. "
                    "No decode percentage delta is used in candidate ranking."
                ),
            },
        },
        "cause_evidence": {
            "deprioritized": [
                {
                    "cause": "4096 boundary crossing",
                    "reason": f"Collapse criterion begins around absolute position {qnn_abs_onset} and exact looping by {qnn_abs_periodic}; generation ends at 3977, below 4096.",
                },
                {
                    "cause": "greedy randomness",
                    "reason": "All five outputs are byte-identical and all routes use deterministic argmax/top-k1 semantics.",
                },
                {
                    "cause": "request reset leakage",
                    "reason": "All 15 source-proven resets completed, prompt counts remained exact, and per-tier outputs are deterministic.",
                },
            ],
            "still_plausible": [
                {
                    "cause": "deployment artifact/checkpoint quantization difference",
                    "evidence": "QNN and LiteRT share rendered bytes but use distinct artifacts/quantizers/tokenizers and diverge at the first output word.",
                },
                {
                    "cause": "long-position RoPE/SWA/global-mask or cache-state interaction",
                    "evidence": "Only the 1929-token prompt route collapses; onset is near absolute position 2012, well before capacity but after substantial cached context.",
                },
                {
                    "cause": "uFxp16 global value-cache feedback or normalization conversion path",
                    "evidence": "The HTP correction introduced explicit quantized AR1 value feedback; global value layers retain full history and are the narrowest precision experiment.",
                },
            ],
            "text_only_causality_claim": False,
        },
        "candidate_matrix": candidate_matrix,
        "recommended_next_milestones": [
            "Build a no-phone HTP-only global-value-cache FP16 AR1/AR128 candidate and inspect cache identity, Convert count, context size, and host compile time.",
            "Define an explicit request-level hybrid route using accepted HTP short/medium and LiteRT GPU long arms; model dual-route setup/memory honestly before any phone gate.",
            "Add a bounded logit/state capture design around QNN generated tokens 64-128 and periodic onset 478; do not infer internal divergence from text alone.",
        ],
        "requested": {"phone_access": False, "model_conversion": False, "campaign_rerun": False},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
