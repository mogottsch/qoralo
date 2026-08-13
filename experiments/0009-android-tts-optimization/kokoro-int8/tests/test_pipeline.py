from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import (  # noqa: E402
    analyze_wav,
    compare_acoustic_behavior,
    contains_forbidden_mse_key,
    load_corpus,
    load_json,
    write_pcm16_wav,
)


def test_corpus_is_multi_utterance_whole_text_and_keeps_canonical_0008_bytes() -> None:
    corpus = load_corpus(ROOT / "corpus.json")
    assert len(corpus["calibration"]) == 4
    assert len(corpus["evaluation"]) == 6
    assert "no text splitter" in corpus["construction"]
    canonical = corpus["evaluation"][0]
    assert canonical["id"] == "eval-canonical-0008"
    assert hashlib.sha256(canonical["text"].encode()).hexdigest() == canonical["source_sha256"]
    assert canonical["source_sha256"] == "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"


def test_source_and_quantization_contract_is_exact_and_cpu_portable() -> None:
    source = load_json(ROOT / "source-manifest.json")
    config = load_json(ROOT / "quantization-config.json")
    assert source["deployment_variant"] == "kokoro-multi-lang-v1_0"
    assert source["archive"]["sha256"] == "c133d26353d776da730870dac7da07dbfc9a5e3bc80cc5e8e83ab6e823be7046"
    assert source["required_files"]["model.onnx"]["sha256"] == "c436dc6a842b62aba06af67e40bafcfb9c60ac3af895358f1974ad9a7f7c026b"
    assert source["experiment_0008_evidence"]["voice_proof"]["assertion"] == "id2speaker[3] == af_heart"
    assert config["method"] == "onnxruntime_static_post_training_quantization"
    assert config["quant_format"] == "QDQ"
    assert config["activation_type"] == config["weight_type"] == "QInt8"
    assert config["op_types_to_quantize"] == ["Conv", "MatMul", "Gemm"]
    assert config["exclude_node_name_prefixes"] == ["/decoder/generator/"]
    assert config["candidate_name"].endswith("generator-fp32")
    serialized = json.dumps([source, config]).casefold()
    assert "qnn" not in serialized
    assert "qairt" not in serialized


def test_tool_lock_and_requirements_pin_the_same_wheels() -> None:
    lock = load_json(ROOT / "toolchain.lock.json")
    requirements = (ROOT / "requirements.lock").read_text()
    assert lock["build_platform"]["python"] == "CPython 3.11.13"
    assert lock["synthesis_runtime"]["sherpa_onnx"] == "1.13.5"
    assert len(lock["wheels"]) == 13
    for wheel in lock["wheels"]:
        assert len(wheel["sha256"]) == 64
        assert wheel["sha256"] in requirements
        assert wheel["version"] in requirements
        assert wheel["url"].startswith("https://files.pythonhosted.org/")


def test_audio_integrity_and_aggregate_behavior_avoid_sample_error() -> None:
    with tempfile.TemporaryDirectory() as directory:
        directory_path = Path(directory)
        rate = 24000
        time = np.arange(rate, dtype=np.float64) / rate
        samples = 0.2 * np.sin(2 * math.pi * 180.0 * time)
        first, second = directory_path / "first.wav", directory_path / "second.wav"
        write_pcm16_wav(first, samples, rate)
        write_pcm16_wav(second, samples * 0.98, rate)
        first_analysis, second_analysis = analyze_wav(first), analyze_wav(second)
        comparison = compare_acoustic_behavior(first_analysis, second_analysis)
        assert first_analysis["integrity"]["non_silent"]
        assert first_analysis["integrity"]["pcm_clip_count"] == 0
        assert comparison["passed"]
        assert not contains_forbidden_mse_key(comparison)


def test_silence_and_clipping_are_detected() -> None:
    with tempfile.TemporaryDirectory() as directory:
        directory_path = Path(directory)
        silence, clipped = directory_path / "silence.wav", directory_path / "clipped.wav"
        write_pcm16_wav(silence, np.zeros(2400), 24000)
        write_pcm16_wav(clipped, np.ones(2400), 24000)
        assert not analyze_wav(silence)["integrity"]["non_silent"]
        assert analyze_wav(clipped)["integrity"]["pcm_clip_count"] == 2400


def test_committed_gate_records_final_user_ballot_and_defers_android_measurement() -> None:
    gate = load_json(ROOT / "reports" / "quality-gate.json")
    assert gate["status"] == "passed_user_listening"
    assert gate["quality_gate"]["overall_status"] == "passed_user_listening"
    assert gate["quality_gate"]["subjective_verdict"] == "no_systematic_preference_or_int8_degradation_detected"
    assert gate["quality_gate"]["subjective_equivalence_claimed"] is False
    assert gate["quality_gate"]["user_listening"]["counts"] == {
        "ties": 4, "int8_preferred": 1, "fp32_preferred": 1,
    }
    assert gate["android"]["deployment_status"] == "eligible_for_later_android_benchmark"
    assert gate["android"]["rtf_status"] == "not_yet_measured_for_this_candidate"
    assert gate["android"]["pss_status"] == "not_yet_measured_for_this_candidate"
    assert not contains_forbidden_mse_key(gate)


def test_user_ballot_reveal_is_balanced_and_low_confidence() -> None:
    verdict = load_json(ROOT / "reports" / "user-listening-verdict.json")
    assert verdict["status"] == "validated_final_ballot"
    assert verdict["quality_gate_recommendation"] == "pass"
    assert verdict["counts"] == {"ties": 4, "int8_preferred": 1, "fp32_preferred": 1}
    directional = [row for row in verdict["observations"] if row["preferred_variant"] != "tie"]
    assert {row["preferred_variant"] for row in directional} == {"fp32", "int8"}
    assert {row["confidence"] for row in directional} == {2}


def test_blind_manifest_keeps_answer_key_outside_package() -> None:
    report = load_json(ROOT / "reports" / "blind-package.json")
    assert report["status"] == "ready_awaiting_user_listening"
    assert report["package"]["answer_key_included"] is False
    assert report["answer_key"]["retained_outside_package"] is True
    package = ROOT / report["package"]["path"]
    if package.exists():
        answer = load_json(ROOT / report["answer_key"]["path"])
        with zipfile.ZipFile(package) as archive:
            assert archive.testzip() is None
            names = [name.casefold() for name in archive.namelist()]
            for pair in answer["pairs"]:
                for label in ("A", "B"):
                    payload = archive.read(f"{pair['pair']}/{label}.wav")
                    assert hashlib.sha256(payload).hexdigest() == pair[label]["wav_sha256"]
        assert len([name for name in names if name.endswith(".wav")]) == 12
        assert not any(
            forbidden in name
            for name in names
            for forbidden in ("answer", "seed", "fp32", "int8")
        )


def test_failures_are_retained_with_resolutions() -> None:
    report = load_json(ROOT / "reports" / "failures.json")
    assert {failure["id"] for failure in report["failures"]} >= {
        "dynamic-qint8-convinteger-not-implemented",
        "static-s8s8-all-eligible-spectral-screen",
        "first-calibration-phoneme-normalization",
        "onnx-checker-loop-outer-scope",
    }
    assert all(failure.get("resolution") for failure in report["failures"])
    full = next(item for item in report["failures"] if item["id"] == "static-s8s8-all-eligible-spectral-screen")
    assert full["failed_pair_count"] == 6
    assert full["failure"]["observed_minimum"] > full["failure"]["documented_maximum"]


def test_selected_candidate_and_independent_rebuild_are_bit_exact_and_audited() -> None:
    quantization = load_json(ROOT / "reports" / "quantization-report.json")
    rebuild = load_json(ROOT / "reports" / "reproduction-rebuild.json")
    candidate = quantization["candidate"]
    assert candidate["bytes"] == 175_678_702
    assert candidate["sha256"] == "c37d76d0ada7414d18841ed454e8c7f00c8b1f631e97e1fd019c3ba01a0fbd92"
    assert rebuild["candidate"]["bytes"] == candidate["bytes"]
    assert rebuild["candidate"]["sha256"] == candidate["sha256"]
    audit = candidate["effective_quantization_audit"]
    assert audit["source_eligible_node_count"] == 265
    assert audit["expected_quantized_node_count"] == 163
    assert audit["effective_weight_qdq_node_count"] == 163
    assert audit["requested_excluded_node_count"] == 102
    assert audit["excluded_nodes_with_weight_qdq"] == 0
    assert audit["all_requested_nodes_have_weight_qdq"] is True
    assert audit["all_excluded_nodes_retain_unquantized_weights"] is True


def test_candidate_selection_retains_rejected_and_non_selected_recipes() -> None:
    report = load_json(ROOT / "reports" / "candidate-selection.json")
    assert report["status"] == "selected_candidate_ready_for_blind_listening"
    assert report["selected_candidate_subjective_status"] == "awaiting_user_listening"
    assert report["raw_sample_error_used"] is False
    assert report["android_performance_used"] is False
    attempts = report["attempts"]
    assert attempts["dynamic_default_qint8"]["disposition"] == "rejected_cpu_incompatible"
    full = attempts["static_s8s8_all_eligible"]
    assert full["model"]["bytes"] == 126_457_536
    assert full["acoustic_screen"]["failed_pair_count"] == 6
    assert full["acoustic_screen"]["failed_check_counts"][
        "spectral_centroid_relative_difference_at_most_0_20"
    ] == 6
    assert attempts["static_s8s8_linear_only"]["acoustic_screen"]["passed_pair_count"] == 6
    assert attempts["static_s8s8_generator_excluded"]["acoustic_screen"]["passed_pair_count"] == 6


def test_final_reports_are_six_matched_hash_addressed_pairs() -> None:
    fp32 = load_json(ROOT / "reports" / "synthesis-fp32.json")
    int8 = load_json(ROOT / "reports" / "synthesis-int8.json")
    analysis = load_json(ROOT / "reports" / "audio-analysis.json")
    assert fp32["exact_shared_inputs"] == int8["exact_shared_inputs"]
    expected = fp32["exact_shared_inputs"]["corpus_order"]
    assert len(expected) == 6
    assert [item["id"] for item in fp32["outputs"]] == expected
    assert [item["id"] for item in int8["outputs"]] == expected
    assert [item["id"] for item in analysis["pairs"]] == expected
    assert analysis["status"] == "passed"
    assert all(pair["passed"] for pair in analysis["pairs"])
    for report in (fp32, int8):
        for item in report["outputs"]:
            wav = item["wav"]
            assert len(wav["sha256"]) == 64
            assert f"--sha256-{wav['sha256']}.wav" in wav["path"]
            assert wav["integrity"]["pcm_clip_count"] == 0


def test_package_manifest_pins_ignored_models_audio_and_blind_zip() -> None:
    manifest = load_json(ROOT / "package-manifest.json")
    assert manifest["status"] == "passed_user_listening"
    generated = {item["path"]: item for item in manifest["generated_evidence"]}
    required = {
        "generated/model.static-qdq-s8s8-generator-fp32.onnx",
        "generated/model.static-qdq-s8s8.onnx",
        "generated/model.dynamic-default.qint8.onnx",
        "generated/screening/full-eligible-s8s8.onnx",
        "generated/screening/linear-only-s8s8.onnx",
        "generated/blind/kokoro-int8-listening.zip",
    }
    assert required <= set(generated)
    assert all(len(generated[path]["sha256"]) == 64 and generated[path]["bytes"] > 0 for path in required)
    selected = generated["generated/model.static-qdq-s8s8-generator-fp32.onnx"]
    rebuild = generated["generated/model.static-qdq-s8s8.onnx"]
    assert selected["sha256"] == rebuild["sha256"]
    assert selected["bytes"] == rebuild["bytes"]
    assert len([path for path in generated if path.startswith("generated/audio/") and path.endswith(".wav")]) == 12


def test_documentation_exposes_final_listening_result_and_limitations() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    handoff = (ROOT / "WORKER_HANDOFF.md").read_text(encoding="utf-8")
    for text in (readme, handoff):
        assert "passed_user_listening" in text
        assert "four ties" in text
        assert "user-listening-ballot.csv" in text
    assert "No calibrated" in readme
    assert "Android" in readme and "unmeasured" in readme
