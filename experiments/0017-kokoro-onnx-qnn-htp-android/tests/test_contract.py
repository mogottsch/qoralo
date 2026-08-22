from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


class ContractTests(unittest.TestCase):
    def test_protocol_and_transcript_are_frozen(self) -> None:
        policy = json.loads((ROOT / "protocol.json").read_text())
        transcript = (ROOT / "protocol/transcript.txt").read_bytes()
        self.assertTrue(policy["frozen_before_qnn_host_or_phone_outputs"])
        self.assertEqual(len(transcript), 116)
        self.assertEqual(
            hashlib.sha256(transcript).hexdigest(),
            policy["fixed_contract"]["transcript_sha256"],
        )
        self.assertEqual(
            policy["source"]["controlled_onnx"]["sha256"],
            "d11a0dd7c4eb768e1f0ef03090c69b6761f55e37b9f196749349591c40be232b",
        )
        self.assertFalse(policy["source"]["controlled_onnx"]["learned_weight_changes"])
        self.assertEqual(policy["source"]["controlled_onnx"]["quantized_operator_count"], 0)
        self.assertTrue(policy["host_gate"]["phone_forbidden_until_pass"])

    def test_source_inventory_tracks_committed_inputs_and_tools(self) -> None:
        inventory = json.loads((ROOT / "results/source-inventory.json").read_text())
        self.assertEqual(
            hashlib.sha256((ROOT / "protocol.json").read_bytes()).hexdigest(),
            inventory["fixed_contract"]["protocol_sha256"],
        )
        for name, expected in inventory["tools"].items():
            if not name.endswith(".py") and name != "kokoro_ort_runner.cc":
                continue
            path = ROOT / ("host" if name.endswith(".cc") else "tools") / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)

    def test_stage_decomposition_is_frozen_before_qnn_outputs(self) -> None:
        policy_path = ROOT / "protocol-stage-decomposition.json"
        policy = json.loads(policy_path.read_text())
        provenance = json.loads(
            (ROOT / "results/stage-decomposition-provenance.json").read_text()
        )
        cpu = json.loads((ROOT / "results/stage-cpu-equivalence.json").read_text())

        self.assertTrue(policy["frozen_before_staged_qnn_host_outputs"])
        self.assertTrue(policy["preserved_prior_evidence"]["monolithic_retry_forbidden"])
        self.assertEqual(
            policy["source_and_decomposition"]["source_graph"]["sha256"],
            "7278ed2f0dbe8307a42904434b81116f252dd996bb6a2c064f81ad44269f21cb",
        )
        self.assertEqual(policy["source_and_decomposition"]["stage_count"], 18)
        self.assertEqual(provenance["stage_count"], 18)
        self.assertEqual(provenance["coverage"]["source_nodes"], 1685)
        self.assertEqual(provenance["coverage"]["covered_unique_nodes"], 1685)
        self.assertEqual(
            len(provenance["coverage"]["duplicated_boundary_support_nodes"]), 5
        )
        self.assertTrue(
            all(
                stage["structure"]["quantized_operator_count"] == 0
                for stage in provenance["stages"]
            )
        )
        self.assertEqual(
            provenance["protocol"]["sha256"],
            hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        )
        for name in (
            "extract_staged_graphs.py",
            "run_staged_pipeline.py",
            "kokoro_stage_runner.cc",
        ):
            directory = "host" if name.endswith(".cc") else "tools"
            self.assertEqual(
                provenance["tools"][name],
                hashlib.sha256((ROOT / directory / name).read_bytes()).hexdigest(),
            )

        self.assertEqual(cpu["status"], "passed")
        self.assertEqual(cpu["stage_count"], 18)
        self.assertTrue(cpu["recomposition"]["audio_bit_exact"])
        self.assertTrue(cpu["recomposition"]["duration_bit_exact"])
        self.assertAlmostEqual(cpu["recomposition"]["cosine"], 1.0, places=12)
        self.assertEqual(cpu["recomposition"]["nrmse"], 0.0)
        self.assertEqual(
            cpu["recomposition"]["audio"]["sha256"],
            "56464612c786a6fcc9034e51a24d7e26d17910147a72e5e5672220c45f15045f",
        )
        self.assertEqual(
            cpu["recomposition"]["duration"]["sha256"],
            "7977e82d5304abba333a0b1caa0f0ef39b265b11205ff217c5979255cc44b80e",
        )

    def test_stage_interfaces_form_a_fixed_pipeline(self) -> None:
        policy = json.loads((ROOT / "protocol-stage-decomposition.json").read_text())
        stages = policy["source_and_decomposition"]["stages"]
        available = {"tokens", "style", "speed"}
        for expected_index, stage in enumerate(stages, start=1):
            self.assertEqual(stage["index"], expected_index)
            self.assertGreater(stage["nodes"], 0)
            self.assertEqual(stage["quantized_operator_count"], 0)
            for value in stage["inputs"]:
                self.assertIn(value["name"], available)
                self.assertTrue(all(dim > 0 for dim in value["shape"]))
            for value in stage["outputs"]:
                self.assertTrue(all(dim > 0 for dim in value["shape"]))
                available.add(value["name"])
        self.assertIn("audio", available)
        self.assertIn("pred_dur", available)

    def test_canonical_v2_contract_and_cpu_recomposition(self) -> None:
        transcript = REPO / "protocols/android-tts-benchmark/transcript.txt"
        raw = transcript.read_bytes()
        self.assertEqual(len(raw), 226)
        self.assertFalse(raw.endswith(b"\n"))
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67",
        )

        protocol_path = ROOT / "protocol-canonical-v2-stage-decomposition.json"
        protocol = json.loads(protocol_path.read_text())
        frontend = json.loads(
            (ROOT / "results/canonical-v2-frontend-provenance.json").read_text()
        )
        stages = json.loads(
            (ROOT / "results/canonical-v2-stage-decomposition-provenance.json").read_text()
        )
        cpu = json.loads(
            (ROOT / "results/canonical-v2-stage-cpu-equivalence.json").read_text()
        )
        self.assertTrue(protocol["frozen_before_canonical_v2_qnn_host_outputs"])
        self.assertEqual(
            protocol["frontend"]["historical_sherpa_exact_error"],
            "selected text is not fully covered by lexicon: 'makes'",
        )
        self.assertEqual(frontend["historical_sherpa_frontend"]["status"], "failed_closed")
        self.assertEqual(protocol["frontend"]["token_shape"], [1, 235])
        self.assertEqual(protocol["frontend"]["style_index"], 232)
        self.assertEqual(protocol["fixed_contract"]["duration_sum"], 602)
        self.assertEqual(protocol["fixed_contract"]["audio_shape"], [361200])
        self.assertEqual(protocol["fixed_contract"]["audio_duration_seconds"], 15.05)
        self.assertEqual(protocol["stage_decomposition"]["stage_count"], 18)
        self.assertEqual(protocol["stage_decomposition"]["source_nodes"], 1685)
        self.assertEqual(protocol["stage_decomposition"]["covered_unique_nodes"], 1685)
        self.assertEqual(
            protocol["representations"]["qnn_compatibility"]["sha256"],
            "0c7ce33eac4c6664819a61e48469a9cf43ad403d852b01af5517a13c7ed2a066",
        )
        self.assertEqual(
            stages["protocol"]["sha256"],
            hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(stages["stage_count"], 18)
        self.assertEqual(stages["coverage"]["source_nodes"], 1685)
        self.assertTrue(cpu["recomposition"]["audio_bit_exact"])
        self.assertTrue(cpu["recomposition"]["duration_bit_exact"])
        self.assertAlmostEqual(cpu["recomposition"]["cosine"], 1.0, places=12)
        self.assertEqual(cpu["recomposition"]["nrmse"], 0.0)
        self.assertEqual(
            cpu["recomposition"]["audio"]["sha256"],
            "fb8895f6bb9c2ee94dd18f8b9bfdc6f1b36f99e01c40f5806bdd71076acd6d36",
        )
        self.assertEqual(
            cpu["recomposition"]["duration"]["sha256"],
            "99494f78e82ad3d8b506d5b0a5c4edde6292c6a52ca54a47b50f109fa534480c",
        )
        tool_paths = {
            "prepare_canonical_v2_frontend.py": ROOT / "tools/prepare_canonical_v2_frontend.py",
            "run_canonical_v2_eager_oracle.py": ROOT / "tools/run_canonical_v2_eager_oracle.py",
            "export_canonical_v2_onnx_fp.py": ROOT / "tools/export_canonical_v2_onnx_fp.py",
            "prepare_canonical_v2_optimized_graph.py": ROOT / "tools/prepare_canonical_v2_optimized_graph.py",
            "annotate_canonical_v2_profile_shapes.py": ROOT / "tools/annotate_canonical_v2_profile_shapes.py",
            "rewrite_canonical_v2_qnn_compat.py": ROOT / "tools/rewrite_canonical_v2_qnn_compat.py",
            "extract_canonical_v2_staged_graphs.py": ROOT / "tools/extract_canonical_v2_staged_graphs.py",
            "kokoro_canonical_stage_runner.cc": ROOT / "host/kokoro_canonical_stage_runner.cc",
        }
        for name, path in tool_paths.items():
            self.assertEqual(
                protocol["tools"][name], hashlib.sha256(path.read_bytes()).hexdigest()
            )

    def test_canonical_v2_stage_interfaces_form_pipeline(self) -> None:
        protocol = json.loads(
            (ROOT / "protocol-canonical-v2-stage-decomposition.json").read_text()
        )
        available = {"tokens", "style", "speed"}
        for expected_index, stage in enumerate(
            protocol["stage_decomposition"]["stages"], start=1
        ):
            self.assertEqual(stage["index"], expected_index)
            self.assertGreater(stage["nodes"], 0)
            self.assertEqual(stage["quantized_operator_count"], 0)
            for value in stage["inputs"]:
                self.assertIn(value["name"], available)
                self.assertTrue(all(dim > 0 for dim in value["shape"]))
            for value in stage["outputs"]:
                self.assertTrue(all(dim > 0 for dim in value["shape"]))
                available.add(value["name"])
        self.assertIn("audio", available)
        self.assertIn("pred_dur", available)

    def test_migration_checkpoint_preserves_exact_interruption_boundary(self) -> None:
        checkpoint = json.loads(
            (ROOT / "results/canonical-v2-host-qnn-interrupted-checkpoint.json").read_text()
        )
        self.assertEqual(checkpoint["status"], "externally_interrupted")
        self.assertEqual(checkpoint["completed_prefix"]["count"], 15)
        self.assertEqual(
            checkpoint["completed_prefix"]["provider_counts"],
            {"QNNExecutionProvider": 15},
        )
        self.assertEqual(checkpoint["completed_prefix"]["cpu_provider_node_events"], 0)
        self.assertEqual(
            checkpoint["completed_prefix"]["indices"], list(range(1, 16))
        )
        active = checkpoint["interrupted_active_stage"]
        self.assertEqual((active["index"], active["name"]), (16, "generator_1_resblock_5"))
        self.assertEqual(
            active["observed_compiler_state"][
                "graph_sequencing_for_target_maximum_progress_percent"
            ],
            12,
        )
        self.assertFalse(active["observed_compiler_state"]["session_finalized"])
        self.assertFalse(active["observed_compiler_state"]["inference_executed"])
        self.assertEqual(
            [(item["index"], item["name"]) for item in checkpoint["unattempted_stages"]],
            [(17, "generator_1_merge"), (18, "waveform_istft")],
        )
        self.assertFalse(checkpoint["phone_eligibility"])
        self.assertFalse(checkpoint["final_audio_produced"])
        self.assertFalse(checkpoint["source"]["end_file_exists"])
        self.assertFalse(checkpoint["source"]["exit_code_file_exists"])
        self.assertEqual(
            checkpoint["resource_monitor"]["minimum_mem_available_kib"], 9539000
        )
        self.assertEqual(
            checkpoint["resource_monitor"]["maximum_swap_consumption_delta_kib"], 0
        )
        self.assertFalse(
            checkpoint["resource_monitor"]["pause_event_file_exists"]
        )
        self.assertIn(
            "restart the complete canonical 18-stage serial host run from stage 1",
            checkpoint["next_action"]["rule"],
        )

        old = json.loads((ROOT / "results/staged-host-qnn-feasibility.json").read_text())
        self.assertEqual(old["execution"]["completed_stages"], 18)
        self.assertEqual(old["execution"]["cpu_provider_node_events"], 0)
        self.assertFalse(old["outputs"]["audio"]["structural"]["valid"])
        self.assertEqual(old["outputs"]["duration"]["sum"], 305)
        self.assertEqual(old["outputs"]["duration"]["expected_sum"], 304)

        for relative in (
            "host/run_canonical_v2_staged_host_qnn.sh",
            "tools/summarize_staged_qnn_run.py",
            "tools/summarize_interrupted_staged_qnn_run.py",
            "REPRODUCING.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_current_environment_reconstruction_baseline_is_frozen(self) -> None:
        baseline_path = ROOT / "results/canonical-v2-cpu-reconstruction-baseline.json"
        policy_path = ROOT / "protocol-canonical-v2-reconstruction-baseline.json"
        cancelled_path = (
            ROOT / "results/canonical-v2-rerun-operator-cancelled-pre-gate.json"
        )
        baseline = json.loads(baseline_path.read_text())
        policy = json.loads(policy_path.read_text())
        cancelled = json.loads(cancelled_path.read_text())

        self.assertEqual(
            hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
            "0aff238d1cc45b7729c59a24a5938230491333c42290e9a1fef8d87da4a2ccd9",
        )
        self.assertEqual(
            hashlib.sha256(policy_path.read_bytes()).hexdigest(),
            "886bd22eb278b884ccf50e41bb1792d1d36a9612667d8080e90ccd8e3f71231e",
        )
        self.assertTrue(policy["frozen_before_new_qnn_outputs"])
        current = policy["current_environment_baseline"]
        historical = policy["historical_evidence"]
        self.assertEqual(
            current["record"]["sha256"],
            hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(current["independent_clean_staged_runs"], 2)
        self.assertTrue(current["audio"]["two_staged_runs_bit_exact"])
        self.assertTrue(current["audio"]["complete_graph_to_staged_bit_exact"])
        self.assertTrue(current["audio"]["structurally_valid"])
        self.assertEqual(
            current["audio"]["sha256"],
            "56ce6a24498d8db270c0a34eb1fe0a87b762a0fb8121616790f03391c132aa3c",
        )
        self.assertEqual(
            historical["wsl_audio_sha256"],
            "fb8895f6bb9c2ee94dd18f8b9bfdc6f1b36f99e01c40f5806bdd71076acd6d36",
        )
        self.assertTrue(historical["preserved_unchanged"])
        self.assertEqual(
            historical["cross_environment_bit_reproducibility"], "unproven"
        )
        self.assertEqual(len(current["stage_output_sha256"]), 18)
        self.assertEqual(
            current["stage_output_sha256"][0]["outputs"]["/bert_encoder/Add_output_0"],
            "01e4e86f9103f51430c4a46e96a1575ebae01d175e6f2d4e31a789dcb93db29a",
        )

        comparisons = baseline["numerical_comparisons"]
        self.assertTrue(
            comparisons["stage_1_reconstruction_rerun_1_vs_2"]["bit_exact"]
        )
        self.assertTrue(
            comparisons["final_audio_reconstruction_rerun_1_vs_2"]["bit_exact"]
        )
        self.assertTrue(
            comparisons["final_staged_vs_current_full_qnn_compat_cpu"]["bit_exact"]
        )
        unavailable = comparisons["historical_vs_current"]
        self.assertFalse(unavailable["hash_equal"])
        self.assertIsNone(unavailable["first_differing_flat_element"])
        self.assertIsNone(unavailable["maximum_absolute_error"])
        self.assertIsNone(unavailable["rmse"])
        self.assertIsNone(unavailable["cosine"])
        self.assertIn(
            "historical stage-1 and final float payloads",
            unavailable["unavailable_reason"],
        )
        self.assertTrue(
            baseline["current_final_audio_structural"][
                "valid_under_committed_structural_policy"
            ]
        )
        self.assertEqual(
            baseline["bounded_conclusion"]["qnn_gate"], "blocked_pending_review"
        )

        self.assertEqual(
            hashlib.sha256(cancelled_path.read_bytes()).hexdigest(),
            "86b305bdb82fba2948544dd27473a34ef7d10438a6bdeb9cb94595522cd25bc2",
        )
        self.assertEqual(
            policy["operator_cancelled_pre_gate_record"]["sha256"],
            hashlib.sha256(cancelled_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(cancelled["status"], "operator_cancelled_pre_gate")
        self.assertFalse(cancelled["boundary"]["docker_container_created"])
        self.assertFalse(cancelled["boundary"]["qnn_session_creation_began"])
        self.assertEqual(cancelled["boundary"]["stage_processes_started"], 0)
        self.assertFalse(cancelled["boundary"]["phone_access"])
        self.assertIn("/usr/bin/time", cancelled["boundary"]["launcher_error"])

        host_gate = (ROOT / "host/run_canonical_v2_staged_host_qnn.sh").read_text()
        summary_tool = (ROOT / "tools/summarize_staged_qnn_run.py").read_text()
        for expected_hash in (
            "0aff238d1cc45b7729c59a24a5938230491333c42290e9a1fef8d87da4a2ccd9",
            "886bd22eb278b884ccf50e41bb1792d1d36a9612667d8080e90ccd8e3f71231e",
        ):
            self.assertIn(expected_hash, host_gate + summary_tool)
        self.assertIn("--reconstruction-policy", summary_tool)
        self.assertIn("--reconstruction-baseline", summary_tool)
        self.assertIn("PREFLIGHT_ONLY", host_gate)

    def test_erased_experiment_0015_remains_absent(self) -> None:
        self.assertFalse((REPO / "experiments/0015-pocket-tts-qnn-htp-android").exists())

    def test_fixed_alignment_lowering_matches_repeat_interleave(self) -> None:
        # Exercise zeros and nonuniform lengths; production duration is separately
        # hash-gated and has length 125/sum 304.
        durations = np.asarray([1, 3, 0, 2, 4], dtype=np.int64)
        positions = np.arange(int(durations.sum()), dtype=np.float32)[None, :]
        lower = np.tril(np.ones((durations.size, durations.size), dtype=np.float32))
        column = durations.astype(np.float32)[:, None]
        end = lower @ column
        start = end - column
        candidate = ((positions >= start) & (positions < end)).astype(np.float32)

        indices = np.repeat(np.arange(durations.size), durations)
        expected = np.zeros_like(candidate)
        expected[indices, np.arange(indices.size)] = 1.0
        np.testing.assert_array_equal(candidate, expected)

    def test_rewrite_policy_requires_same_runtime_equivalence(self) -> None:
        rewrite = json.loads((ROOT / "protocol.json").read_text())["rewrite_policy"]
        gate = rewrite["cpu_equivalence_gate"]
        self.assertEqual(gate["duration_tensor"], "bit exact")
        self.assertEqual(gate["minimum_waveform_cosine"], 0.999)
        self.assertEqual(gate["maximum_waveform_nrmse"], 0.01)
        self.assertIn("same host ONNX Runtime", gate["reference"])
        self.assertIn("quantization or calibration", rewrite["forbidden_without_new_authorization"])


if __name__ == "__main__":
    unittest.main()
