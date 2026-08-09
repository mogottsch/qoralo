import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ABI = json.loads((ROOT / "fixtures/four-call-cache-abi.json").read_text())
TRACE = json.loads(
    (ROOT / "fixtures/recurrent-calls-0-19-manifest.json").read_text()
)
STABILIZATION = json.loads(
    (ROOT / "results/cache-stabilization.json").read_text()
)


def test_frozen_methods_list_every_tensor_in_normative_order():
    assert ABI["status"] == "frozen_pre_export"
    assert ABI["export_status"] == "not_started_by_design"

    for domain, method_name, primary_input, primary_output in (
        ("decoder", "acoustic_decode", [1, 1, 64], [1, 1, 3200]),
        ("semantic", "semantic_encode", [1, 1, 3200], [1, 1, 128]),
    ):
        method = ABI["methods"][method_name]
        caches = method["caches"]
        assert len(caches) == 34
        assert [item["order"] for item in caches] == list(range(34))
        assert method["inputs"][0]["shape"] == primary_input
        assert method["outputs"][0]["shape"] == primary_output
        assert len(method["inputs"]) == 37
        assert len(method["outputs"]) == 36

        expected_names = STABILIZATION["cache_domains"][domain]["ordered_names"]
        assert [item["source_name"] for item in caches] == expected_names
        assert [item["name"] for item in method["inputs"]] == (
            [method["inputs"][0]["name"], "phase", f"{domain}_valid_lengths"]
            + [f"{domain}_cache_{index:02d}" for index in range(34)]
        )
        assert [item["order"] for item in method["inputs"]] == list(range(37))
        assert [item["order"] for item in method["outputs"]] == list(range(36))


def test_capacity_shapes_and_lengths_match_all_twenty_call_evidence():
    transpose_targets = {28: 15, 29: 9, 30: 9, 31: 7, 32: 3, 33: 3}
    for domain, method_name in (
        ("decoder", "acoustic_decode"),
        ("semantic", "semantic_encode"),
    ):
        by_name = {
            entry["name"]: entry
            for entry in STABILIZATION["cache_domains"][domain]["entries"]
        }
        for cache in ABI["methods"][method_name]["caches"]:
            evidence = by_name[cache["source_name"]]
            assert cache["dtype"] == "float32"
            assert cache["capacity"] >= max(evidence["post_lengths_by_call"])
            assert cache["capacity_shape"][:-1] == TRACE["calls"][0][domain][
                "post_cache"
            ][cache["source_name"]]["shape"][:-1]
            assert cache["pre_valid_lengths_calls_0_3"] == evidence[
                "pre_lengths_by_call"
            ][:4]
            assert cache["post_valid_lengths_calls_0_3"] == evidence[
                "post_lengths_by_call"
            ][:4]
            if domain == "decoder" and cache["order"] in transpose_targets:
                assert cache["capacity"] == transpose_targets[cache["order"]]


def test_exact_four_call_transitions_reset_and_non_mutation_are_frozen():
    transitions = ABI["call_transitions"]
    assert [(item["required_phase"], item["next_phase"]) for item in transitions] == [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
    ]
    assert transitions[0]["decoder_pre_valid_lengths"] == [0] * 34
    assert transitions[0]["semantic_pre_valid_lengths"] == [0] * 34
    for previous, current in zip(transitions, transitions[1:]):
        assert previous["decoder_post_valid_lengths"] == current[
            "decoder_pre_valid_lengths"
        ]
        assert previous["semantic_post_valid_lengths"] == current[
            "semantic_pre_valid_lengths"
        ]
    assert transitions[3]["decoder_post_valid_lengths"][28] == 4
    assert ABI["reset_and_state_rules"]["silent_mutation_prohibited"] is True
    assert "MUST NOT alias" in ABI["reset_and_state_rules"]["aliasing"]


def test_constants_precision_and_all_thresholds_are_predeclared():
    precision = ABI["precision_policy"]
    assert precision["qwen2_backbone"]["weights"] == "int8"
    assert precision["connectors_diffusion_decoder_semantic"]["weights"] == "float32"

    package = ABI["packaging"]
    assert package["phase_specific_artifacts"] == 0
    assert package["external_ptd_files"] == 0
    assert "inline-constant multi-method PTE" in package["audio_artifact"]

    thresholds = ABI["thresholds"]
    assert thresholds["qwen_int8"]["selected_token"].startswith("exact equality")
    assert thresholds["pcm_s16"]["maximum_absolute_difference_units"] == 1
    assert thresholds["fp32_boundaries"]["decoder_cache_android"]["atol"] == 6e-5
    energy = thresholds["chunk_energy_dbfs"]
    assert energy["reference_calls_0_3"][3] == -21.712573890892052
    assert energy["chunk_3_required_range_dbfs"] == [
        -24.712573890892052,
        -18.712573890892052,
    ]
    assert thresholds["perceptual_protocol"]["required_status"] == "pass"
