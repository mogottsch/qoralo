from __future__ import annotations

import importlib.util
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "experiments/0002-vibevoice-1.5b-executorch-android"
SCRIPT = EXPERIMENT / "export/analyze_cache_stabilization.py"
CACHE_RESULT = EXPERIMENT / "results/cache-stabilization.json"
PREFIX_RESULT = EXPERIMENT / "results/locked-reference-prefix-comparison.json"
HISTORICAL = EXPERIMENT / "results/locked-reference-comparison.json"

spec = importlib.util.spec_from_file_location("analyze_cache_stabilization", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_sconvtranspose_targets_and_first_full_context_calls() -> None:
    result = json.loads(CACHE_RESULT.read_text())
    layers = result["acoustic_decoder"]["sconvtranspose1d"]
    assert [layer["kernel_size_minus_1_target"] for layer in layers] == [15, 9, 9, 7, 3, 3]
    assert [layer["input_width_each_call"] for layer in layers] == [1, 8, 40, 200, 800, 1600]
    assert [layer["first_call_post_full"] for layer in layers] == [14, 1, 0, 0, 0, 0]
    assert [layer["first_call_with_full_pre_context"] for layer in layers] == [15, 2, 1, 1, 1, 1]
    assert layers[0]["post_cache_lengths_by_call"] == list(range(1, 16)) + [15] * 5
    assert result["acoustic_decoder"]["all_sconvtranspose_calls_use_full_pre_context_from_call"] == 15


def test_complete_cache_ordering_is_unique_and_stable() -> None:
    result = json.loads(CACHE_RESULT.read_text())
    assert result["call_order"] == list(range(20))
    for domain in ("decoder", "semantic"):
        caches = result["cache_domains"][domain]
        assert caches["cache_count"] == 34
        assert len(caches["ordered_names"]) == len(set(caches["ordered_names"])) == 34
        assert [entry["order"] for entry in caches["entries"]] == list(range(34))
        assert [entry["name"] for entry in caches["entries"]] == caches["ordered_names"]
        assert all(len(entry["pre_lengths_by_call"]) == 20 for entry in caches["entries"])
        assert all(len(entry["post_lengths_by_call"]) == 20 for entry in caches["entries"])
    assert result["ordering_and_chain_checks"]["cache_order_is_abi_significant"] is True


def test_locked_prefix_exact_s16_differences_and_dbfs_progression() -> None:
    result = json.loads(PREFIX_RESULT.read_text())
    comparison = result["comparison"]
    assert comparison["sample_count"] == 6400
    assert comparison["differing_samples"] == 3014
    assert comparison["equal_samples"] == 3386
    assert comparison["maximum_absolute_difference_s16_units"] == 1
    assert math.isclose(comparison["mean_absolute_difference_s16_units"], 0.4709375, abs_tol=1e-12)
    assert comparison["all_differences_at_most_one_s16_unit"] is True
    assert comparison["exact_byte_agreement"] is False

    chunks = result["dbfs_evidence"]["reference_chunks_0_through_3"]
    assert math.isclose(chunks[0]["rms_dbfs"], -93.6608167424245, abs_tol=1e-9)
    assert math.isclose(chunks[1]["rms_dbfs"], -93.4909351277393, abs_tol=1e-9)
    assert math.isclose(chunks[2]["rms_dbfs"], -52.37993833024675, abs_tol=1e-9)
    assert math.isclose(chunks[3]["rms_dbfs"], -21.712573890892052, abs_tol=1e-9)
    assert chunks[0]["rms_dbfs"] < chunks[2]["rms_dbfs"] < chunks[3]["rms_dbfs"]


def test_prefix_agreement_is_not_quality_acceptance_or_historical_rewrite() -> None:
    result = json.loads(PREFIX_RESULT.read_text())
    assert result["comparison"]["prefix_agreement_status"] == "pass"
    assert result["quality_acceptance"]["status"] == "fail"
    assert result["quality_acceptance"]["prefix_agreement_is_quality_acceptance"] is False
    assert result["historical_comparison"]["modification_policy"].startswith("immutable")
    historical_status = subprocess.check_output(
        ["git", "status", "--short", "--", str(HISTORICAL.relative_to(ROOT))], cwd=ROOT, text=True
    )
    assert historical_status == ""
