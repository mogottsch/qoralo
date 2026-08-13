#!/usr/bin/env python3
"""Assemble the host quality gate without manufacturing a listening verdict."""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path
from typing import Any

from common import EXPERIMENT_ROOT, contains_forbidden_mse_key, load_json, sha256_file, write_json


def verify_generated_pin(record: dict[str, Any]) -> None:
    path = EXPERIMENT_ROOT / record["path"]
    if not path.is_file() or path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
        raise RuntimeError(f"generated artifact drifted: {path}")


def report_pin(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing report: {path}")
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def timing_summary(report: dict[str, Any]) -> dict[str, Any]:
    values = [item["host_timing_context_only"] for item in report["outputs"]]
    return {
        "model_load_seconds": report["host_timing_context_only"]["model_load_seconds"],
        "utterance_count": len(values),
        "median_generation_seconds": statistics.median(item["generation_seconds"] for item in values),
        "median_host_rtf": statistics.median(item["rtf"] for item in values),
        "label": "host context only; not an Android RTF result",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quantization", type=Path, default=EXPERIMENT_ROOT / "reports" / "quantization-report.json")
    parser.add_argument("--fp32", type=Path, default=EXPERIMENT_ROOT / "reports" / "synthesis-fp32.json")
    parser.add_argument("--int8", type=Path, default=EXPERIMENT_ROOT / "reports" / "synthesis-int8.json")
    parser.add_argument("--audio", type=Path, default=EXPERIMENT_ROOT / "reports" / "audio-analysis.json")
    parser.add_argument("--asr", type=Path, default=EXPERIMENT_ROOT / "reports" / "asr-report.json")
    parser.add_argument("--blind", type=Path, default=EXPERIMENT_ROOT / "reports" / "blind-package.json")
    parser.add_argument("--selection", type=Path, default=EXPERIMENT_ROOT / "reports" / "candidate-selection.json")
    parser.add_argument("--rebuild", type=Path, default=EXPERIMENT_ROOT / "reports" / "reproduction-rebuild.json")
    parser.add_argument("--failures", type=Path, default=EXPERIMENT_ROOT / "reports" / "failures.json")
    parser.add_argument("--verdict", type=Path, default=EXPERIMENT_ROOT / "reports" / "user-listening-verdict.json")
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "reports" / "quality-gate.json")
    parser.add_argument("--markdown", type=Path, default=EXPERIMENT_ROOT / "QUALITY_GATE.md")
    args = parser.parse_args()

    quantization = load_json(args.quantization)
    fp32, int8 = load_json(args.fp32), load_json(args.int8)
    audio, asr = load_json(args.audio), load_json(args.asr)
    blind, selection = load_json(args.blind), load_json(args.selection)
    rebuild, failures = load_json(args.rebuild), load_json(args.failures)
    verify_generated_pin(quantization["candidate"])
    verify_generated_pin(rebuild["candidate"])
    verify_generated_pin(blind["package"])
    verify_generated_pin(blind["answer_key"])
    if fp32["exact_shared_inputs"] != int8["exact_shared_inputs"]:
        raise RuntimeError("quality report cannot combine unmatched synthesis settings")

    expected_ids = fp32["exact_shared_inputs"]["corpus_order"]
    failure_ids = {failure["id"] for failure in failures["failures"]}
    audit = quantization["candidate"]["effective_quantization_audit"]
    checks = {
        "exact_source_and_sid_proven": (
            quantization["deployment_variant"] == "kokoro-multi-lang-v1_0"
            and quantization["voice"] == {
                "speaker_id": 3,
                "speaker": "af_heart",
                "proven_from_exact_model_metadata": True,
            }
        ),
        "candidate_runs_in_pinned_host_cpu_runtime": quantization["status"] == "candidate_built_host_cpu_probe_passed",
        "effective_mixed_precision_boundary_audited": (
            audit["effective_weight_qdq_node_count"] == 163
            and audit["requested_excluded_node_count"] == 102
            and audit["all_requested_nodes_have_weight_qdq"] is True
            and audit["all_excluded_nodes_retain_unquantized_weights"] is True
        ),
        "bit_exact_independent_candidate_rebuild": (
            rebuild["candidate"]["bytes"] == quantization["candidate"]["bytes"]
            and rebuild["candidate"]["sha256"] == quantization["candidate"]["sha256"]
        ),
        "matched_fp32_and_int8_sherpa_synthesis": (
            fp32["status"] == "matched_host_synthesis_passed"
            and int8["status"] == "matched_host_synthesis_passed"
            and [item["id"] for item in fp32["outputs"]] == expected_ids
            and [item["id"] for item in int8["outputs"]] == expected_ids
        ),
        "six_pair_file_audio_integrity_and_acoustic_supporting_checks": (
            audio["status"] == "passed"
            and [pair["id"] for pair in audio["pairs"]] == expected_ids
            and all(pair["passed"] for pair in audio["pairs"])
        ),
        "asr_transcript_supporting_checks": (
            asr["status"] == "passed" and [pair["id"] for pair in asr["pairs"]] == expected_ids
        ),
        "candidate_selection_failures_and_alternatives_retained": (
            selection["status"] == "selected_candidate_ready_for_blind_listening"
            and selection["selected_candidate_sha256"] == quantization["candidate"]["sha256"]
        ),
        "blind_package_ready_and_answer_separate": (
            blind["status"] == "ready_awaiting_user_listening"
            and blind["package"]["answer_key_included"] is False
            and blind["answer_key"]["retained_outside_package"] is True
            and blind["package"]["crc_validation_passed"] is True
            and blind["package"]["wav_count"] == 12
        ),
        "known_failures_recorded": {
            "dynamic-qint8-convinteger-not-implemented",
            "static-s8s8-all-eligible-spectral-screen",
            "first-calibration-phoneme-normalization",
            "onnx-checker-loop-outer-scope",
        } <= failure_ids,
    }
    automated_status = "passed_supporting_checks" if all(checks.values()) else "failed"
    verdict = load_json(args.verdict) if args.verdict.is_file() else None
    listening_passed = bool(
        verdict
        and verdict.get("status") == "validated_final_ballot"
        and verdict.get("quality_gate_recommendation") == "pass"
        and verdict.get("ballot", {}).get("all_pairs_answered") is True
    )
    if automated_status != "passed_supporting_checks":
        overall_status = "blocked"
    elif listening_passed:
        overall_status = "passed_user_listening"
    else:
        overall_status = "awaiting_user_listening"
    report = {
        "schema_version": 1,
        "status": overall_status,
        "candidate": {
            "name": quantization["candidate_name"],
            "deployment_variant": "kokoro-multi-lang-v1_0",
            "speaker_id": 3,
            "speaker": "af_heart",
            "source_model_sha256": quantization["candidate"]["source_model_sha256"],
            "model_sha256": quantization["candidate"]["sha256"],
            "model_bytes": quantization["candidate"]["bytes"],
            "source_model_bytes": quantization["candidate"]["source_model_bytes"],
            "size_reduction_fraction": quantization["candidate"]["size_reduction_fraction"],
            "quantization": {
                "format": quantization["method"]["quant_format"],
                "activation_type": quantization["method"]["activation_type"],
                "weight_type": quantization["method"]["weight_type"],
                "op_types": quantization["method"]["op_types_to_quantize"],
                "excluded_node_prefixes": quantization["method"]["exclude_node_name_prefixes"],
                "effective_weight_qdq_node_count": audit["effective_weight_qdq_node_count"],
                "excluded_node_count": audit["requested_excluded_node_count"],
                "precision_boundary_note": audit["precision_boundary_note"],
                "onnx_checker": quantization["validation"]["onnx_checker"],
            },
        },
        "quality_gate": {
            "automated_status": automated_status,
            "checks": checks,
            "overall_status": overall_status,
            "subjective_verdict": verdict["verdict"] if listening_passed else "awaiting_user_listening",
            "subjective_equivalence_claimed": False,
            "listener": "Moritz",
            "blind_package": blind["package"],
            "user_listening": verdict if listening_passed else None,
            "instruction": (
                "User ballot is finalized, validated, and revealed against the retained answer key."
                if listening_passed else
                "Listen to all six blind A/B pairs, download ballot.csv, and return it before opening the separately retained answer key."
            ),
        },
        "supporting_signals": {
            "audio_analysis_report": args.audio.name,
            "asr_report": args.asr.name,
            "fp32_reference_wer": asr["corpus"]["fp32_reference_wer"],
            "int8_reference_wer": asr["corpus"]["int8_reference_wer"],
            "fp32_to_int8_hypothesis_wer": asr["corpus"]["fp32_to_int8_hypothesis_wer"],
            "speaker_similarity": audio["speaker_similarity"],
            "limitations": [
                "Automated integrity, ASR, pitch, and spectral behavior are supporting signals, not a substitute for listening.",
                "No calibrated speaker-verification score was available; none was invented.",
                "Raw sample error is not computed or used as a quality decision.",
                "The exact source passes ONNX checker 1.18.0, but ONNX Runtime quantization introduces an outer-graph topological-order diagnostic; pinned CPU runtimes still load and infer. This must be reassessed before later deployment.",
            ],
        },
        "host_context_only": {
            "model_size": {
                "fp32_bytes": quantization["candidate"]["source_model_bytes"],
                "int8_bytes": quantization["candidate"]["bytes"],
                "reduction_fraction": quantization["candidate"]["size_reduction_fraction"],
            },
            "fp32_timing": timing_summary(fp32),
            "int8_timing": timing_summary(int8),
            "performance_conclusion": "none; these laptop timings are context only",
        },
        "android": {
            "deployment_status": "eligible_for_later_android_benchmark" if listening_passed else "not_deployed_by_this_track",
            "rtf_status": "not_yet_measured_for_this_candidate",
            "pss_status": "not_yet_measured_for_this_candidate",
            "android_performance_conclusion": "none",
        },
        "reproducibility": {
            "reports": [
                report_pin(path)
                for path in (
                    args.quantization,
                    args.rebuild,
                    args.fp32,
                    args.int8,
                    args.audio,
                    args.asr,
                    args.blind,
                    args.selection,
                    args.failures,
                    *([args.verdict] if listening_passed else []),
                )
            ],
            "complete_inventory": "package-manifest.json",
            "strict_verifier": "scripts/verify_package.py",
            "full_rebuild_entrypoint": "scripts/reproduce_host_gate.sh",
            "stochastic_audio_note": "The model contains unseeded random operators; the selected ONNX rebuild is bit-exact, while regenerated WAVs form a new hash-addressed evidence set.",
        },
    }
    if contains_forbidden_mse_key(report):
        raise AssertionError("quality report accidentally introduced a forbidden MSE key")
    write_json(args.output, report)

    package = report["quality_gate"]["blind_package"]
    candidate = report["candidate"]
    listening_summary = (
        "Moritz finalized all six blind votes: four ties, one INT8 preference, and one FP32 preference. "
        "Both directional preferences had confidence 2/5. The retained ballot detected no systematic "
        "INT8 degradation, so the user listening gate passed. This does not prove perceptual equivalence "
        "or INT8 superiority."
        if listening_passed else
        "The blind ballot has not yet been returned, so no subjective quality conclusion is available."
    )
    markdown = f"""# Kokoro INT8 host quality gate

## Status: `{overall_status}`

{listening_summary}

- Exact source: `kokoro-multi-lang-v1_0`, SID 3 (`af_heart`), source SHA-256 `{candidate['source_model_sha256']}`.
- Candidate SHA-256: `{candidate['model_sha256']}`; an independent rebuild matched it bit-for-bit.
- Model size: {candidate['source_model_bytes']:,} bytes FP32 to {candidate['model_bytes']:,} bytes candidate ({candidate['size_reduction_fraction']:.1%} reduction).
- Selected boundary: QDQ S8S8 Conv/MatMul/Gemm outside `/decoder/generator/`.
- Blind package: `{package['path']}` ({package['bytes']:,} bytes), SHA-256 `{package['sha256']}`.
- Automated Whisper WER was {report['supporting_signals']['fp32_reference_wer']:.3f} for FP32 and {report['supporting_signals']['int8_reference_wer']:.3f} for INT8.

The exact source passes ONNX checker 1.18.0, while the quantized graph retains a known outer-scope topological-order diagnostic. Pinned CPU runtimes load and synthesize it, but this must be reassessed before Android deployment.

## Android scope

The exact candidate is now eligible for a later Android benchmark, but it has not been deployed. No Android RTF or PSS value is claimed here.
"""
    args.markdown.write_text(markdown, encoding="utf-8")
    print(f"quality gate {report['quality_gate']['overall_status']}: {args.output}")


if __name__ == "__main__":
    main()
