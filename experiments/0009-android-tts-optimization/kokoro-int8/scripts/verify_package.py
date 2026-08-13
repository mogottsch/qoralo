#!/usr/bin/env python3
"""Strictly verify the retained Kokoro host quality package and optional CPU smoke."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import zipfile
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT_ROOT,
    analyze_wav,
    compare_acoustic_behavior,
    contains_forbidden_mse_key,
    load_corpus,
    load_json,
    sha256_file,
    validate_source,
    write_json,
)
from make_package_manifest import discover, entry
from quantize import checker_probe, effective_quantization_audit, resolve_excluded_nodes, verify_toolchain

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def verify_pin(record: dict[str, Any], *, base: Path = EXPERIMENT_ROOT) -> Path:
    path = base / record["path"]
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_size != record["bytes"]
        or sha256_file(path) != record["sha256"]
    ):
        raise RuntimeError(f"artifact pin mismatch: {path}")
    return path


def verify_inventory(manifest_path: Path) -> dict[str, int]:
    manifest = load_json(manifest_path)
    recorded = {
        item["path"]: item
        for section in ("committable_files", "generated_evidence")
        for item in manifest[section]
    }
    actual_paths = discover(manifest_path.resolve())
    actual_names = {path.relative_to(EXPERIMENT_ROOT).as_posix() for path in actual_paths}
    if actual_names != set(recorded):
        raise RuntimeError(
            "package inventory drifted; "
            f"missing={sorted(set(recorded) - actual_names)}, "
            f"unexpected={sorted(actual_names - set(recorded))}"
        )
    for path in actual_paths:
        measured = entry(path)
        expected = recorded[measured["path"]]
        if measured != expected:
            raise RuntimeError(f"package manifest entry drifted: {measured['path']}")
    return {
        "committable_files": len(manifest["committable_files"]),
        "generated_evidence_files": len(manifest["generated_evidence"]),
    }


def verify_final_audio(fp32: dict[str, Any], int8: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    if fp32["exact_shared_inputs"] != int8["exact_shared_inputs"]:
        raise RuntimeError("final synthesis settings are not matched")
    expected_ids = fp32["exact_shared_inputs"]["corpus_order"]
    by_variant = {
        "fp32": {item["id"]: item for item in fp32["outputs"]},
        "int8": {item["id"]: item for item in int8["outputs"]},
    }
    if list(by_variant["fp32"]) != expected_ids or list(by_variant["int8"]) != expected_ids:
        raise RuntimeError("final synthesis output order or completeness drifted")
    retained_pairs = {pair["id"]: pair for pair in analysis["pairs"]}
    if list(retained_pairs) != expected_ids or analysis["status"] != "passed":
        raise RuntimeError("retained final acoustic analysis is incomplete or failed")

    maxima = {
        "duration_ratio_int8_over_fp32": 0.0,
        "pitch_median_relative_difference": 0.0,
        "voiced_fraction_absolute_difference": 0.0,
        "spectral_centroid_relative_difference": 0.0,
    }
    minimum_cosine = 1.0
    for utterance_id in expected_ids:
        measured: dict[str, Any] = {}
        for variant in ("fp32", "int8"):
            pinned = by_variant[variant][utterance_id]["wav"]
            path = verify_pin(pinned)
            if f"--sha256-{pinned['sha256']}.wav" not in path.name:
                raise RuntimeError(f"WAV is not hash-addressed: {path}")
            measured[variant] = analyze_wav(path)
            if measured[variant]["sha256"] != pinned["sha256"]:
                raise RuntimeError(f"WAV reanalysis pin mismatch: {path}")
            integrity = measured[variant]["integrity"]
            if not integrity["finite"] or not integrity["non_silent"] or integrity["pcm_clip_count"]:
                raise RuntimeError(f"WAV integrity failed during strict verification: {path}")
        comparison = compare_acoustic_behavior(measured["fp32"], measured["int8"])
        if not comparison["passed"]:
            raise RuntimeError(f"retained pair no longer passes supporting screen: {utterance_id}")
        retained = retained_pairs[utterance_id]["aggregate_acoustic_comparison"]
        if comparison != retained:
            raise RuntimeError(f"retained acoustic metrics are not reproducible: {utterance_id}")
        for name in maxima:
            value = comparison["metrics"][name]
            if value is not None:
                maxima[name] = max(maxima[name], value)
        minimum_cosine = min(minimum_cosine, comparison["metrics"]["normalized_32_band_power_cosine"])
    return {"pair_count": len(expected_ids), "maximums": maxima, "minimum_band_power_cosine": minimum_cosine}


def verify_blind(blind: dict[str, Any], fp32: dict[str, Any], int8: dict[str, Any]) -> dict[str, Any]:
    package = verify_pin(blind["package"])
    answer_path = verify_pin(blind["answer_key"])
    answer = load_json(answer_path)
    source_hashes = {
        item["wav"]["sha256"]: variant
        for variant, report in (("fp32", fp32), ("int8", int8))
        for item in report["outputs"]
    }
    expected_names = {"README.txt", "ballot.csv", "listening-guide.html"}
    for pair in answer["pairs"]:
        expected_names.update({f"{pair['pair']}/A.wav", f"{pair['pair']}/B.wav"})
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != expected_names or archive.testzip() is not None:
            raise RuntimeError("blind ZIP member set, uniqueness, or CRC validation failed")
        if any(
            forbidden in name.casefold()
            for name in names
            for forbidden in ("answer", "seed", "fp32", "int8")
        ):
            raise RuntimeError("blind ZIP member name leaks identity")
        for info in archive.infolist():
            if info.date_time != FIXED_ZIP_TIME or info.compress_type != zipfile.ZIP_STORED:
                raise RuntimeError(f"blind ZIP metadata drifted: {info.filename}")
        for pair in answer["pairs"]:
            for label in ("A", "B"):
                assignment = pair[label]
                payload_hash = hashlib.sha256(archive.read(f"{pair['pair']}/{label}.wav")).hexdigest()
                if payload_hash != assignment["wav_sha256"] or source_hashes.get(payload_hash) != assignment["variant"]:
                    raise RuntimeError(f"blind assignment or payload drifted: {pair['pair']}/{label}")
        ballot_rows = list(csv.reader(io.StringIO(archive.read("ballot.csv").decode("utf-8"))))
        if ballot_rows[0] != ["pair", "preferred (A/B/tie)", "confidence (1-5)", "notes"]:
            raise RuntimeError("blind ballot header drifted")
        if len(ballot_rows) != len(answer["pairs"]) + 1 or any(any(row[1:]) for row in ballot_rows[1:]):
            raise RuntimeError("blind ballot is incomplete or already filled")
    return {"pair_count": len(answer["pairs"]), "wav_count": len(answer["pairs"]) * 2, "crc_passed": True}


def sherpa_runtime_smoke(source_root: Path, candidate: Path, corpus: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    import sherpa_onnx

    if importlib.metadata.version("sherpa-onnx") != "1.13.5" or importlib.metadata.version("sherpa-onnx-core") != "1.13.5":
        raise RuntimeError("sherpa runtime version drifted")
    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=str(candidate),
                voices=str(source_root / "voices.bin"),
                tokens=str(source_root / "tokens.txt"),
                data_dir=str(source_root / "espeak-ng-data"),
                lexicon=str(source_root / "lexicon-us-en.txt"),
            ),
            provider="cpu",
            num_threads=1,
            debug=False,
        )
    )
    if not config.validate():
        raise RuntimeError("sherpa rejected selected candidate configuration")
    tts = sherpa_onnx.OfflineTts(config)
    generation = sherpa_onnx.GenerationConfig()
    generation.sid = 3
    generation.speed = 1.0
    audio = tts.generate(corpus["evaluation"][1]["text"], generation)
    samples = np.asarray(audio.samples, dtype=np.float64)
    if audio.sample_rate != 24000 or samples.ndim != 1 or samples.size == 0 or not np.all(np.isfinite(samples)):
        raise RuntimeError("sherpa selected-candidate smoke returned invalid audio")
    if float(np.sqrt(np.mean(samples * samples))) < 1e-5 or int(np.count_nonzero(np.abs(samples) > 1.0)):
        raise RuntimeError("sherpa selected-candidate smoke returned silence or out-of-range audio")
    return {
        "status": "passed_nonempty_finite_nonsilent_24khz_audio",
        "frontend_and_runtime": "sherpa-onnx 1.13.5 OfflineTts Kokoro",
        "embedded_onnxruntime": sherpa_onnx.onnxruntime_version,
        "provider": "cpu",
        "num_threads": 1,
        "speaker_id": 3,
        "speed": 1.0,
        "utterance_id": corpus["evaluation"][1]["id"],
        "ephemeral_audio_not_retained": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=EXPERIMENT_ROOT / "package-manifest.json")
    parser.add_argument("--require-manifest", action="store_true")
    parser.add_argument("--runtime-smoke", action="store_true")
    parser.add_argument("--output", type=Path, default=EXPERIMENT_ROOT / "reports/verification-report.json")
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    source = validate_source(source_root, EXPERIMENT_ROOT / "source-manifest.json", verify_archive=True)
    tools = verify_toolchain(
        EXPERIMENT_ROOT / "toolchain.lock.json",
        EXPERIMENT_ROOT / ".cache/wheels",
        Path("/usr/bin/espeak-ng"),
    )
    if args.manifest.exists():
        verify_inventory(args.manifest.resolve())
    elif args.require_manifest:
        raise RuntimeError("package manifest is required but missing")

    corpus = load_corpus(EXPERIMENT_ROOT / "corpus.json")
    quantization = load_json(EXPERIMENT_ROOT / "reports/quantization-report.json")
    candidate = verify_pin(quantization["candidate"])
    if quantization["candidate"]["source_model_sha256"] != source["required_files"]["model.onnx"]["sha256"]:
        raise RuntimeError("candidate source provenance drifted")
    config = load_json(EXPERIMENT_ROOT / "quantization-config.json")
    exclusions = resolve_excluded_nodes(source_root / "model.onnx", config)
    audit = effective_quantization_audit(source_root / "model.onnx", candidate, config, exclusions)
    if audit != quantization["candidate"]["effective_quantization_audit"]:
        raise RuntimeError("effective mixed-precision graph audit drifted")
    checker = checker_probe(source_root / "model.onnx", candidate)
    if checker != quantization["validation"]["onnx_checker"]:
        raise RuntimeError("retained source/candidate checker result drifted")

    rebuild = load_json(EXPERIMENT_ROOT / "reports/reproduction-rebuild.json")
    rebuild_path = verify_pin(rebuild["candidate"])
    if sha256_file(rebuild_path) != sha256_file(candidate) or rebuild["candidate"]["sha256"] != quantization["candidate"]["sha256"]:
        raise RuntimeError("independent candidate rebuild is not bit-exact")

    fp32 = load_json(EXPERIMENT_ROOT / "reports/synthesis-fp32.json")
    int8 = load_json(EXPERIMENT_ROOT / "reports/synthesis-int8.json")
    analysis = load_json(EXPERIMENT_ROOT / "reports/audio-analysis.json")
    audio_summary = verify_final_audio(fp32, int8, analysis)
    asr = load_json(EXPERIMENT_ROOT / "reports/asr-report.json")
    if asr["status"] != "passed" or [pair["id"] for pair in asr["pairs"]] != fp32["exact_shared_inputs"]["corpus_order"]:
        raise RuntimeError("ASR supporting report is incomplete or failed")
    blind = load_json(EXPERIMENT_ROOT / "reports/blind-package.json")
    blind_summary = verify_blind(blind, fp32, int8)
    selection = load_json(EXPERIMENT_ROOT / "reports/candidate-selection.json")
    failures = load_json(EXPERIMENT_ROOT / "reports/failures.json")
    checker_report = load_json(EXPERIMENT_ROOT / "reports/checker-limitation.json")
    gate = load_json(EXPERIMENT_ROOT / "reports/quality-gate.json")
    required_failures = {
        "dynamic-qint8-convinteger-not-implemented",
        "static-s8s8-all-eligible-spectral-screen",
        "first-calibration-phoneme-normalization",
        "onnx-checker-loop-outer-scope",
    }
    if not required_failures <= {item["id"] for item in failures["failures"]}:
        raise RuntimeError("failure retention report is incomplete")
    if (
        checker_report["status"] != "reproduced_quantizer_introduced_topological_order_limitation"
        or checker_report["source"]["checker_passed"] is not True
        or checker_report["candidate"]["sha256"] != quantization["candidate"]["sha256"]
        or checker["candidate"]["passed"] is not False
    ):
        raise RuntimeError("checker limitation is missing, inaccurate, or no longer reproducible")
    if selection["selected_candidate_sha256"] != quantization["candidate"]["sha256"]:
        raise RuntimeError("candidate selection pin drifted")
    if (
        gate.get("status") != "awaiting_user_listening"
        or gate["quality_gate"]["overall_status"] != "awaiting_user_listening"
        or gate["quality_gate"]["subjective_equivalence_claimed"] is not False
    ):
        raise RuntimeError("quality gate no longer explicitly awaits user listening")
    if contains_forbidden_mse_key(gate) or contains_forbidden_mse_key(analysis):
        raise RuntimeError("a decision report introduced a raw-sample MSE key")

    runtime_smoke = sherpa_runtime_smoke(source_root, candidate, corpus) if args.runtime_smoke else {
        "status": "not_requested",
        "command_flag": "--runtime-smoke",
    }
    report = {
        "schema_version": 1,
        "status": "passed",
        "scope": "strict host package verification; no phone access or Android performance measurement",
        "checks": {
            "full_exact_source_inventory": True,
            "locked_wheelhouse_and_installed_versions": True,
            "selected_candidate_hash_and_size": True,
            "selected_candidate_effective_weight_qdq_boundary": True,
            "source_checker_pass_and_candidate_quantizer_ordering_limitation": True,
            "bit_exact_independent_candidate_rebuild": True,
            "six_matched_pair_wav_hashes_integrity_and_acoustic_reanalysis": True,
            "asr_supporting_report": True,
            "blind_zip_crc_metadata_payload_assignments_and_empty_ballot": True,
            "candidate_selection_and_failure_retention": True,
            "explicit_awaiting_user_listening_status": True,
        },
        "source": source["full_source_inventory"],
        "toolchain": {
            "python": tools["python"],
            "wheel_count": tools["wheel_count"],
            "espeak_executable_sha256": tools["espeak_executable_sha256"],
            "espeak_library_sha256": tools["espeak_library_sha256"],
        },
        "candidate": {
            "bytes": candidate.stat().st_size,
            "sha256": sha256_file(candidate),
            "rebuild_path": rebuild["candidate"]["path"],
            "rebuild_sha256": sha256_file(rebuild_path),
            "effective_weight_qdq_node_count": audit["effective_weight_qdq_node_count"],
            "excluded_node_count": audit["requested_excluded_node_count"],
        },
        "retained_audio": audio_summary,
        "blind": blind_summary,
        "runtime_smoke": runtime_smoke,
        "android": {"accessed": False, "rtf_measured": False, "pss_measured": False},
        "overall_quality_status": "awaiting_user_listening",
    }
    write_json(args.output, report)
    print(f"strict package verification passed: {args.output}")


if __name__ == "__main__":
    main()
