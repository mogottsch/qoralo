from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_zstd(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    process = subprocess.Popen(["zstd", "-q", "-dc", path], stdout=subprocess.PIPE)
    assert process.stdout is not None
    for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
        digest.update(block)
        total += len(block)
    process.stdout.close()
    if process.wait() != 0:
        raise RuntimeError(f"zstd decompression failed: {path}")
    return digest.hexdigest(), total


class ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((EXP / "protocol/experiment-contract.json").read_text())
        cls.result = json.loads((EXP / "results/support-assessment/result.json").read_text())
        cls.structural = json.loads(
            (EXP / "results/executorch-qnn-structural-probe/result.json").read_text()
        )
        cls.exact_compile = json.loads(
            (EXP / "results/executorch-qnn-exact-host-compile/compile-result.json").read_text()
        )
        cls.eager = json.loads(
            (EXP / "results/executorch-qnn-exact-host-compile/eager-equivalence.json").read_text()
        )
        cls.runner = json.loads(
            (EXP / "results/android-explicit-state-runner-host-build/result.json").read_text()
        )
        cls.physical_attempt = json.loads(
            (EXP / "results/android-qnn-physical-viability-20260827-attempt-01/result.json").read_text()
        )
        cls.boundary_fix = json.loads(
            (EXP / "results/android-runner-boundary-fix-host-build/result.json").read_text()
        )
        cls.physical_execution = json.loads(
            (EXP / "results/android-qnn-physical-viability-20260827-attempt-02/result.json").read_text()
        )
        cls.qdq_diagnosis = json.loads(
            (EXP / "results/host-w4a16-qdq-output-diagnosis/result.json").read_text()
        )
        cls.broadcast_localization = json.loads(
            (EXP / "results/host-qnn-broadcast-divergence-localization/result.json").read_text()
        )
        cls.repaired_pte = json.loads(
            (EXP / "results/exact-qnn-explicit-broadcast-host-validation/result.json").read_text()
        )
        cls.repaired_physical = json.loads(
            (EXP / "results/android-qnn-physical-viability-20260828-attempt-03/result.json").read_text()
        )

    def test_canonical_protocol_and_workloads(self) -> None:
        canonical = self.contract["canonical_protocol"]
        self.assertEqual(canonical["sha256"], sha(REPO / canonical["path"]))
        directory = REPO / "protocols/android-llm-benchmark/workloads/inference-v1"
        for tier, digest in canonical["workloads"].items():
            self.assertEqual(digest, sha(directory / f"{tier}.json"))
        self.assertEqual(2048, canonical["max_new_tokens"])
        self.assertEqual(["short", "medium", "long"], canonical["tier_order"])

    def test_model_geometry_exposes_installed_builder_mismatch(self) -> None:
        model = self.result["model"]
        self.assertEqual("Qwen3_5ForConditionalGeneration", model["architecture"])
        self.assertEqual(512, model["full_attention_kv_width"])
        self.assertEqual(2048, model["linear_key_width"])
        installed = self.result["installed_qairt"]
        self.assertTrue(installed["factory_dispatches_qwen35"])
        self.assertEqual({"tensor_width": 4096, "group_width": 256}, installed["qwen35_builder_hardcoded_split_map"])
        self.assertTrue(installed["qwen35_builder_contains_dimension_update_warning"])
        self.assertNotIn(4096, (model["full_attention_kv_width"], model["linear_key_width"]))

    def test_public_release_has_no_qnn_input(self) -> None:
        release = self.result["public_qualcomm_release"]
        self.assertEqual("GENIEX_LLAMACPP", release["published_runtime"])
        self.assertEqual("q4_0", release["published_precision"])
        artifact = release["published_artifact"]
        self.assertEqual("qwen35", artifact["gguf_architecture"])
        self.assertEqual(1_214_873_856, artifact["bytes"])
        self.assertEqual("cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1", artifact["sha256"])
        self.assertFalse(release["qnn_context_binary_published"])
        self.assertFalse(release["quantized_onnx_encodings_published"])
        self.assertFalse(release["model_py_present"])
        self.assertFalse(release["export_py_present"])
        self.assertFalse(release["quantize_py_present"])

    def test_direct_gguf_route_rejected(self) -> None:
        installed = self.result["installed_qairt"]
        self.assertFalse(installed["direct_gguf_supports_qwen35"])
        self.assertNotIn("qwen35", installed["direct_gguf_supported_model_types"])
        assessment = self.result["route_assessment"]
        self.assertEqual("unsupported_architecture_qwen35", assessment["direct_public_gguf_to_installed_qairt"])
        self.assertFalse(assessment["local_conversion_input_available"])
        self.assertFalse(assessment["compiled_sm8550_context_available"])

    def test_tokenizer_template_and_prompts_are_bound(self) -> None:
        frontend = self.result["tokenizer_and_template"]
        expected_files = self.contract["tokenizer_and_template"]
        self.assertEqual(expected_files["tokenizer_json_sha256"], frontend["files"]["tokenizer.json"])
        self.assertEqual(expected_files["tokenizer_config_sha256"], frontend["files"]["tokenizer_config.json"])
        self.assertEqual(expected_files["chat_template_sha256"], frontend["files"]["chat_template.jinja"])
        expected = {
            "short": (174, "dcfd3c24cb3f8a370f91b38c9720d7e3dd5c623d491fed70ded3726ec49048f4"),
            "medium": (597, "8b07ff28c1c94a93b79880aa27f73b9d5cbddc1f215f857cb58b1d021422c5e2"),
            "long": (1926, "a36f8139e2c4b83976fc74a37bf93f184272823b7144e7a167d9bee6836785ca"),
        }
        for tier, (count, token_hash) in expected.items():
            prompt = frontend["prompt_inventory"][tier]
            self.assertEqual(count, prompt["input_tokens"])
            self.assertEqual(token_hash, prompt["token_ids_int32le_sha256"])
            self.assertTrue(prompt["fits_context_4096"])
            self.assertEqual(prompt["rendered_sha256"], sha(EXP / f"protocol/rendered/{tier}.txt"))
            self.assertEqual(token_hash, sha(EXP / f"protocol/token-ids/{tier}.int32le"))

    def test_active_route_scopes_physical_execution_without_campaign_claim(self) -> None:
        self.assertTrue(self.contract["status"].startswith("active_"))
        prior = self.result["route_assessment"]
        self.assertFalse(prior["android_execution"])
        self.assertFalse(prior["qnn_htp_execution"])
        route = self.contract["executorch_qnn_route"]
        self.assertEqual(151, route["structural_probe_delegated_tensor_compute_nodes"])
        self.assertEqual(0, route["structural_probe_non_delegated_tensor_compute_nodes"])
        self.assertTrue(route["exact_model_compiled"])
        self.assertEqual(4102, route["exact_model_delegated_tensor_compute_nodes"])
        self.assertEqual(0, route["exact_model_non_delegated_tensor_compute_nodes"])
        self.assertTrue(route["android_runner_execution"])
        self.assertTrue(route["android_model_execution"])
        self.assertTrue(route["physical_qnn_htp_context_load"])
        self.assertTrue(route["physical_qnn_htp_execution"])
        self.assertFalse(route["campaign_ready"])

    def test_structural_probe_is_bounded_and_fallback_free(self) -> None:
        probe = self.structural
        self.assertEqual("host_aot_structural_viability_only", probe["evidence_class"])
        self.assertTrue(probe["all_tensor_compute_delegated"])
        self.assertEqual(0, probe["delegation"]["non_delegated_tensor_compute_nodes"])
        self.assertEqual(1, probe["delegation"]["qnn_subgraphs"])
        self.assertIn("synthetic", " ".join(probe["claim_limits"]).lower())
        self.assertIn("not Android", " ".join(probe["claim_limits"]))

    def test_exact_checkpoint_eager_equivalence(self) -> None:
        eager = self.eager
        self.assertEqual("exact_checkpoint_host_eager_equivalence", eager["evidence_class"])
        for key in ("logits", "recurrent_state_layer0", "conv_state_layer0"):
            self.assertEqual(0.0, eager[key]["max_abs"])
            self.assertEqual(0.0, eager[key]["mean_abs"])
        self.assertEqual(eager["reference_argmax"], eager["adapter_argmax"])
        self.assertEqual([], eager["missing"])
        self.assertEqual([], eager["unexpected"])

    def test_exact_checkpoint_compile_is_tensor_compute_fallback_free(self) -> None:
        result = self.exact_compile
        self.assertEqual("compiled", result["status"])
        self.assertEqual("exact_checkpoint_host_aot_compile", result["evidence_class"])
        self.assertTrue(result["all_tensor_compute_delegated"])
        self.assertEqual({}, result["non_delegated_tensor_compute"])
        self.assertEqual(4, result["delegated_subgraphs"])
        self.assertEqual(4102, result["delegated_nodes"])
        self.assertEqual(0, result["delegation_by_operator"]["qwen35_softplus_default"]["non_delegated"])
        self.assertEqual({"soc": "SM8550", "htp_arch": 73}, result["target"])
        self.assertEqual(4096, result["context_tokens"])
        self.assertEqual(174, result["calibration"]["tokens"])
        self.assertTrue(result["calibration"]["last_logits_finite"])
        self.assertIn("not run on Android", " ".join(result["claim_limits"]))

    def test_android_runner_is_host_only_and_matches_exact_pte_abi(self) -> None:
        runner = self.runner
        self.assertEqual("host_prepared_not_staged", runner["status"])
        self.assertEqual(51, runner["exact_pte_abi"]["inputs"])
        self.assertEqual(49, runner["exact_pte_abi"]["outputs"])
        self.assertEqual(48, runner["exact_pte_abi"]["state_inputs"])
        self.assertEqual(48, runner["exact_pte_abi"]["state_outputs"])
        self.assertEqual(
            self.exact_compile["pte"]["sha256"], runner["exact_pte_abi"]["pte_sha256"]
        )
        self.assertEqual("greedy", runner["runner_behavior"]["generation"])
        self.assertIn("single-request", runner["runner_behavior"]["campaign_eligibility"])
        limits = " ".join(runner["claim_limits"])
        self.assertIn("host only", limits)
        self.assertIn("staged", limits)

    def test_first_physical_attempt_preserves_provider_load_and_failure_boundary(self) -> None:
        attempt = self.physical_attempt
        self.assertEqual(
            "physical_qnn_htp_provider_and_context_load_before_model_execution_failure",
            attempt["evidence_class"],
        )
        provider = attempt["physical_provider_observations"]
        self.assertEqual(4, provider["qnn_backend_markers"])
        self.assertEqual(4, provider["dsp_arch_markers"])
        self.assertEqual(4, provider["serialized_contexts_created_successfully"])
        self.assertEqual(4, provider["qnn_graphs_retrieved_successfully"])
        self.assertEqual(0, provider["qnn_graph_execute_markers"])
        self.assertEqual("llama::fallback.out", attempt["failure"]["missing_operator"])
        self.assertFalse(attempt["request"]["model_graph_executed"])
        self.assertEqual(0, attempt["request"]["generated_tokens"])
        self.assertIsNone(attempt["request"]["output_path"])
        self.assertEqual(
            {"looks_sensible": None, "issue_notes": None},
            attempt["request"]["output_sanity"],
        )
        self.assertFalse(attempt["failure"]["retry_performed"])
        self.assertEqual("verified_absent", attempt["cleanup"]["remote_root"])
        self.assertEqual("verified_absent", attempt["cleanup"]["runner_process"])

        raw_dir = EXP / "results/android-qnn-physical-viability-20260827-attempt-01/raw"
        provider_log = (raw_dir / "runner.stderr.log").read_text()
        self.assertEqual(4, provider_log.count("backend_type: kHtpBackend"))
        self.assertEqual(4, provider_log.count("DSP ARCH graph is set to 73"))
        self.assertEqual(
            4, provider_log.count("QnnContext_createFromBinary done successfully")
        )
        self.assertEqual(4, provider_log.count("QnnGraph_retrieve done. status 0x0"))
        self.assertNotIn("QnnGraph_execute", provider_log)
        self.assertEqual(3, provider_log.count("kernel 'llama::fallback.out' not found"))
        self.assertEqual(
            (raw_dir / "local-sha256.txt").read_text(),
            (raw_dir / "remote-sha256.txt").read_text(),
        )
        cleanup = json.loads((raw_dir / "cleanup.json").read_text())
        self.assertEqual("verified_absent", cleanup["cleanup_state"])
        self.assertEqual("verified_absent", cleanup["process_cleanup_state"])

    def test_boundary_fix_is_host_only_and_hash_bound(self) -> None:
        fix = self.boundary_fix
        self.assertEqual("host_android_runner_boundary_kernel_link_fix", fix["evidence_class"])
        self.assertEqual("host_prepared_not_staged", fix["status"])
        self.assertEqual("llama::fallback.out", fix["blocker_addressed"]["missing_operator"])
        self.assertEqual(3, fix["blocker_addressed"]["required_registrations"])
        self.assertTrue(fix["link_evidence"]["whole_archive"])
        self.assertTrue(fix["link_evidence"]["embedded_registration_verified"])
        self.assertEqual(
            fix["revised_runner"]["sha256"],
            fix["retry_preflight"]["phone_script_expected_runner_sha256"],
        )
        self.assertFalse(fix["retry_preflight"]["phone_access_performed"])
        self.assertTrue(fix["retry_preflight"]["new_phone_priority_required"])
        cmake = (EXP / "tools/qwen35_explicit_state_runner.cmake").read_text()
        self.assertIn("custom_ops", cmake)
        phone_script = (EXP / "tools/run_phone_viability.sh").read_text()
        self.assertIn(fix["revised_runner"]["sha256"], phone_script)

    def test_second_attempt_proves_bounded_execution_but_not_output_fidelity(self) -> None:
        attempt = self.physical_execution
        self.assertEqual(
            "bounded_physical_exact_route_qnn_htp_model_execution",
            attempt["evidence_class"],
        )
        self.assertTrue(attempt["request"]["model_graph_executed"])
        self.assertEqual(696, attempt["request"]["qnn_graph_execute_started"])
        self.assertEqual(696, attempt["request"]["qnn_graph_execute_status_0x0"])
        self.assertEqual([0], attempt["request"]["generated_token_ids"])
        self.assertEqual("!", attempt["request"]["decoded_output"])
        self.assertFalse(attempt["request"]["host_reference"]["physical_token_matches"])
        self.assertEqual(
            {"looks_sensible": None, "issue_notes": None},
            attempt["request"]["output_sanity"],
        )
        self.assertEqual("single_request_viability_only", attempt["timings"]["campaign_eligibility"])
        self.assertFalse(attempt["timings"]["loaded_route_reused_across_requests"])
        self.assertIsNone(attempt["timings"]["decode_tokens_per_second"])
        self.assertEqual("verified_absent", attempt["cleanup"]["remote_root"])
        self.assertEqual("verified_absent", attempt["cleanup"]["runner_process"])
        self.assertEqual(
            attempt["request"]["decoded_output_sha256"],
            sha(EXP / "results/android-qnn-physical-viability-20260827-attempt-02/output.txt"),
        )

        profile = json.loads(
            (EXP / "results/android-qnn-physical-viability-20260827-attempt-02/profile-summary.json").read_text()
        )
        self.assertEqual(696, profile["expected_graph_executions"])
        for event in profile["events"].values():
            self.assertEqual(696, event["observations"])
        self.assertEqual(
            4.0, profile["events"]["Number of HVX threads used (count)"]["mean"]
        )

    def test_second_attempt_compressed_raw_evidence_recovers_exact_hashes(self) -> None:
        directory = EXP / "results/android-qnn-physical-viability-20260827-attempt-02"
        manifest = json.loads((directory / "compression-manifest.json").read_text())
        self.assertTrue(manifest["lossless"])
        for entry in manifest["files"]:
            compressed = directory / entry["compressed_name"]
            self.assertEqual(entry["compressed_sha256"], sha(compressed))
            recovered_sha, recovered_bytes = sha_zstd(compressed)
            self.assertEqual(entry["raw_sha256"], recovered_sha)
            self.assertEqual(entry["raw_bytes"], recovered_bytes)
            self.assertTrue(entry["decompression_verified"])

    def test_host_qdq_narrows_but_does_not_explain_physical_mismatch(self) -> None:
        diagnosis = self.qdq_diagnosis
        self.assertEqual("host_w4a16_qdq_output_diagnosis", diagnosis["evidence_class"])
        self.assertEqual(21365, diagnosis["pre_ptq"]["argmax"])
        self.assertEqual(760, diagnosis["post_ptq_qdq"]["argmax"])
        self.assertEqual(0, diagnosis["physical_observation"]["argmax"])
        self.assertEqual(
            {"pre_ptq": "Given", "host_w4a16_qdq": "The", "physical_qnn": "!"},
            {name: value["text"] for name, value in diagnosis["decoded_tokens"].items()},
        )
        self.assertNotEqual(
            diagnosis["post_ptq_qdq"]["argmax"],
            diagnosis["physical_observation"]["argmax"],
        )
        self.assertTrue(diagnosis["separate_process_boundary"])
        self.assertEqual(2467.0443990659987, diagnosis["timing_seconds"]["converted_qdq_execution"])
        self.assertEqual(6094088, diagnosis["process_boundaries"]["run_observed_peak_rss_kib"])
        for name in ("prepare_log", "run_log"):
            artifact = diagnosis["local_artifacts"][name]
            path = EXP / "results/host-w4a16-qdq-output-diagnosis" / name.replace("_", ".")
            self.assertEqual(artifact["sha256"], sha(path))
            self.assertEqual(artifact["bytes"], path.stat().st_size)
        tool = diagnosis["local_artifacts"]["tool"]
        tool_path = EXP / "tools" / Path(tool["path"]).name
        self.assertEqual(tool["sha256"], sha(tool_path))
        self.assertEqual(tool["bytes"], tool_path.stat().st_size)

    def test_qnn_broadcast_root_cause_and_minimal_fix(self) -> None:
        result = self.broadcast_localization
        self.assertEqual(
            "host_qnn_x86_first_token_and_minimal_broadcast_localization",
            result["evidence_class"],
        )
        exact = result["exact_first_token"]
        self.assertEqual(0, exact["input_position"])
        self.assertGreater(exact["layer0_conv_state_cosine"], 0.999)
        self.assertLess(abs(exact["layer0_recurrent_state_cosine"]), 0.01)
        self.assertGreater(exact["layer0_recurrent_state_qnn_to_qdq_l2_ratio"], 100)
        self.assertEqual(39209, exact["qnn_x86_logits_exact_max_count"])

        before = result["minimal_w4a16_probe_before_fix"]
        after = result["explicit_broadcast_fix"]
        self.assertEqual(128, before["qdq_recurrent_state_nonzero_values"])
        self.assertEqual(16, before["qnn_x86_recurrent_state_nonzero_values"])
        self.assertEqual(128, after["qnn_x86_recurrent_state_nonzero_values"])
        self.assertEqual(1.0, after["recurrent_state_cosine"])
        self.assertLess(after["recurrent_state_max_abs"], 1e-6)
        self.assertLess(after["final_logits_max_abs"], 3e-5)
        self.assertTrue(after["qdq_recurrent_state_unchanged"])
        self.assertEqual(after["source_sha256"], sha(EXP / after["source_path"]))
        self.assertTrue(self.contract["executorch_qnn_route"]["deployed_pte_contains_explicit_broadcast_fix"])

    def test_exact_repaired_pte_host_validation_is_preserved(self) -> None:
        result = self.repaired_pte
        self.assertEqual(
            "exact_explicit_broadcast_pte_host_compile_and_qnn_x86_validation",
            result["evidence_class"],
        )
        compile_result = json.loads(
            (EXP / "results/exact-qnn-explicit-broadcast-host-validation/compile-result.json").read_text()
        )
        self.assertTrue(compile_result["all_tensor_compute_delegated"])
        self.assertEqual({}, compile_result["non_delegated_tensor_compute"])
        self.assertEqual(4, compile_result["delegated_subgraphs"])
        self.assertEqual(4210, compile_result["delegated_nodes"])
        self.assertEqual(120, compile_result["explicit_expand_nodes_delegated"])
        self.assertEqual(174, compile_result["calibration"]["tokens"])
        self.assertEqual(21365, compile_result["calibration"]["last_argmax"])

        first = result["qnn_x86_first_token"]
        self.assertGreater(first["layer0_recurrent_state_cosine"], 0.999)
        self.assertLess(abs(first["layer0_recurrent_state_qnn_to_qdq_l2_ratio"] - 1), 0.01)
        self.assertEqual(1, first["logits_exact_max_count"])
        comparison = result["comparison_to_deployed_pte"]
        self.assertEqual(39209, comparison["deployed_logits_exact_max_count"])
        self.assertEqual(1, comparison["revised_logits_exact_max_count"])
        self.assertTrue(self.contract["executorch_qnn_route"]["revised_pte_physical_execution"])
        phone_script = (EXP / "tools/run_phone_viability.sh").read_text()
        self.assertIn(result["compile"]["pte_sha256"], phone_script)

    def test_repaired_pte_physical_check_removes_token_zero_but_not_qdq_drift(self) -> None:
        attempt = self.repaired_physical
        self.assertEqual(
            "bounded_physical_repaired_exact_route_qnn_htp_model_execution",
            attempt["evidence_class"],
        )
        self.assertEqual(
            self.repaired_pte["compile"]["pte_sha256"],
            attempt["deployed_artifacts"]["pte"]["sha256"],
        )
        request = attempt["request"]
        self.assertEqual(0, request["runner_exit_code"])
        self.assertEqual(696, request["qnn_graph_execute_started"])
        self.assertEqual(696, request["qnn_graph_execute_status_0x0"])
        self.assertEqual([1206], request["generated_token_ids"])
        self.assertEqual("To", request["decoded_output"])
        self.assertEqual({"looks_sensible": True, "issue_notes": None}, request["output_sanity"])
        self.assertFalse(request["fidelity_comparison"]["repaired_physical_matches_host_w4a16_qdq"])
        self.assertEqual(760, request["fidelity_comparison"]["host_w4a16_qdq_token_id"])
        self.assertEqual(
            request["decoded_output_sha256"],
            sha(EXP / "results/android-qnn-physical-viability-20260828-attempt-03/output.txt"),
        )
        self.assertAlmostEqual(
            174 / (attempt["timings"]["prefill_execute_ms"] / 1000),
            attempt["timings"]["input_tokens_per_second_from_prefill_execute"],
        )
        self.assertEqual("single_request_viability_only", attempt["timings"]["campaign_eligibility"])
        self.assertFalse(attempt["timings"]["loaded_route_reused_across_requests"])
        self.assertEqual("verified_absent", attempt["cleanup"]["remote_root"])
        self.assertEqual("verified_absent", attempt["cleanup"]["runner_process"])
        independent = (
            EXP
            / "results/android-qnn-physical-viability-20260828-attempt-03/raw/independent-cleanup-verification.txt"
        ).read_text()
        self.assertIn("runner_pids=\n", independent)
        self.assertIn("remote_root=absent", independent)

        profile = json.loads(
            (EXP / "results/android-qnn-physical-viability-20260828-attempt-03/profile-summary.json").read_text()
        )
        self.assertEqual(696, profile["expected_graph_executions"])
        for event in profile["events"].values():
            self.assertEqual(696, event["observations"])
        self.assertEqual(4.0, profile["events"]["Number of HVX threads used (count)"]["mean"])

    def test_repaired_physical_compressed_evidence_recovers_exact_hashes(self) -> None:
        directory = EXP / "results/android-qnn-physical-viability-20260828-attempt-03"
        manifest = json.loads((directory / "compression-manifest.json").read_text())
        self.assertTrue(manifest["lossless"])
        for entry in manifest["files"]:
            compressed = directory / entry["compressed_name"]
            self.assertEqual(entry["compressed_sha256"], sha(compressed))
            recovered_sha, recovered_bytes = sha_zstd(compressed)
            self.assertEqual(entry["raw_sha256"], recovered_sha)
            self.assertEqual(entry["raw_bytes"], recovered_bytes)
            self.assertTrue(entry["decompression_verified"])

    def test_histogram_position_zero_improvement_remains_host_only(self) -> None:
        directory = EXP / "results/host-histogram-precision-20260910"
        result = json.loads((directory / "result.json").read_text())
        report = json.loads((directory / "precision-comparison.json").read_text())
        candidate = json.loads((directory / "histogram-hidden-comparison.json").read_text())
        compile_result = json.loads((directory / "histogram-compile-result.json").read_text())
        self.assertEqual("HistogramObserver", compile_result["activation_observer"])
        self.assertEqual(4210, compile_result["delegated_nodes"])
        self.assertEqual(4, compile_result["delegated_subgraphs"])
        self.assertEqual({}, compile_result["non_delegated_tensor_compute"])
        self.assertEqual(73, compile_result["forward_outputs"])
        for flag in ("float_recurrence", "fp16_recurrence_island", "matmul_recurrence_reductions", "symmetric_activations"):
            self.assertFalse(compile_result[flag])
        self.assertEqual(0, candidate["token_position"])
        self.assertEqual(248045, candidate["token_id"])
        self.assertEqual(198, candidate["qdq_logits"]["argmax"])
        self.assertEqual(198, candidate["qnn_x86_logits"]["argmax"])
        self.assertEqual(24, report["hidden_layers_with_higher_cosine"])
        self.assertTrue(report["all_outputs_finite"])
        self.assertGreater(report["outputs"][0]["candidate_cosine"], 0.94)
        self.assertLess(report["outputs"][0]["candidate_mean_abs"], 0.49)
        self.assertGreater(report["outputs"][-1]["candidate_cosine"], 0.97)
        self.assertLess(report["outputs"][1]["cosine_delta"], 0)  # Retain this regression.
        self.assertFalse(result["full_174_token_histogram_replay_completed"])
        self.assertFalse(result["physical_histogram_execution"])
        self.assertFalse(result["campaign_ready"])
        self.assertFalse(result["registry_eligible"])
        self.assertTrue(result["current_physical_baseline"]["unchanged"])
        self.assertEqual(
            self.repaired_physical["deployed_artifacts"]["pte"]["sha256"],
            result["current_physical_baseline"]["pte_sha256"],
        )
        manifest = json.loads((directory / "artifact-manifest.json").read_text())["files"]
        self.assertEqual(result["compile"]["pte"]["sha256"], manifest["histogram_pte"]["sha256"])
        for name in ("adapter_source", "compiler_source", "comparison_runner_source", "comparison_report_source", "input_ids"):
            entry = manifest[name]
            self.assertEqual(entry["sha256"], sha(EXP / entry["path"]))
        self.assertEqual(
            report["input_report_sha256"]["baseline"], sha(directory / "baseline/hidden-comparison.json")
        )
        self.assertEqual(
            report["input_report_sha256"]["candidate"], sha(directory / "histogram-hidden-comparison.json")
        )

    def test_histogram_rejected_and_interrupted_routes_are_not_successes(self) -> None:
        directory = EXP / "results/host-histogram-precision-20260910"
        rejected = json.loads((directory / "rejected/result.json").read_text())
        self.assertEqual(268, rejected["float"]["non_delegated_tensor_compute_count"])
        self.assertEqual(143, rejected["fp16"]["non_delegated_tensor_compute_count"])
        self.assertEqual("preprocess_failed", rejected["symmetric"]["status"])
        interruption = json.loads((directory / "interrupted/app-priority.json").read_text())
        self.assertEqual("app_priority_interruption_not_numerical_failure", interruption["reason"])
        self.assertTrue(interruption["child_absent"])
        self.assertFalse(interruption["automatic_restart"])
        self.assertEqual(-15, interruption["supervisor_exit"]["exit_code"])
        for phase in ("01-hidden-compile", "02-qdq", "02-qnn", "02-compare"):
            outcome = json.loads((directory / "current" / phase / "exit.json").read_text())
            self.assertEqual(0, outcome["exit_code"])
            self.assertTrue(outcome["child_reaped"])

    def test_histogram_compressed_evidence_recovers_exact_hashes(self) -> None:
        directory = EXP / "results/host-histogram-precision-20260910"
        manifest = json.loads((directory / "compression-manifest.json").read_text())
        self.assertTrue(manifest["lossless"])
        for entry in manifest["files"]:
            compressed = directory / entry["compressed_path"]
            self.assertEqual(entry["compressed_sha256"], sha(compressed))
            recovered_sha, recovered_bytes = sha_zstd(compressed)
            self.assertEqual(entry["raw_sha256"], recovered_sha)
            self.assertEqual(entry["raw_bytes"], recovered_bytes)
            self.assertTrue(entry["decompression_verified"])

    def test_saved_replay_readiness_is_synthetic_not_real_model_evidence(self) -> None:
        directory = EXP / "results/saved-qdq-replay-helper-readiness"
        result = json.loads((directory / "result.json").read_text())
        self.assertEqual(
            "source_only_saved_qdq_replay_helper_synthetic_readiness", result["evidence_class"]
        )
        self.assertEqual(24, result["validation"]["synthetic_tests_passed"])
        self.assertEqual(0, result["validation"]["model_archives_loaded"])
        self.assertTrue(result["validation"]["torch_export_load_mocked_to_forbid_real_archive_loads"])
        self.assertFalse(result["full_histogram_model_replay_completed"])
        self.assertFalse(result["physical_execution_performed"])
        self.assertFalse(result["qnn_x86_execution_performed"])
        self.assertFalse(result["campaign_ready"])
        for entry in result["artifacts"].values():
            self.assertEqual(entry["sha256"], sha(EXP / entry["path"]))

    def test_full_histogram_replay_is_teacher_forced_host_only(self) -> None:
        directory = EXP / "results/host-histogram-full-short-20260910"
        result = json.loads((directory / "result.json").read_text())
        raw = json.loads((directory / "raw/result.json").read_text())
        self.assertEqual("completed", raw["status"])
        self.assertEqual(174, raw["evaluated_tokens"])
        self.assertEqual(174, raw["state_updates_completed"])
        self.assertEqual(173, raw["last_input_position"])
        self.assertEqual(2523, raw["final_logits"]["argmax"])
        self.assertEqual(1, raw["final_logits"]["max_count"])
        self.assertTrue(result["observed"]["all174_positional_logits_finite"])
        self.assertEqual(raw["final_logits"], result["observed"]["final_logits"])
        self.assertEqual(7200, result["timing"]["host_timeout_seconds"])
        for key in ("qnn_execution_performed", "physical_execution_performed", "autoregressive_generation_performed", "generated_text_sanity_checked", "campaign_ready", "registry_eligible", "automatic_retry"):
            self.assertFalse(result[key])
        self.assertEqual(b"You", (directory / "predicted-token.txt").read_bytes())
        self.assertEqual(sha(directory / "predicted-token.txt"), result["token_interpretation"]["sha256"])
        self.assertEqual(self.contract["tokenizer_and_template"]["tokenizer_json_sha256"], result["token_interpretation"]["tokenizer_json_sha256"])
        self.assertTrue(result["token_interpretation"]["interpretation_only_not_generated_response"])
        self.assertEqual(self.contract["executorch_qnn_route"]["revised_pte_sha256"], result["current_physical_baseline_pte_sha256"])
        self.assertEqual(0, result["cleanup"]["scratch_regular_files_remaining"])
        self.assertTrue(result["cleanup"]["owned_process_group_absent"])
        for name in ("helper_source", "verifier_source"):
            item = result["input_binding"][name]
            self.assertEqual(item["sha256"], sha(EXP / item["path"]))

    def test_full_replay_verification_exposes_local_only_retention_boundary(self) -> None:
        directory = EXP / "results/host-histogram-full-short-20260910"
        spec = importlib.util.spec_from_file_location("verify_saved_replay", EXP / "tools/verify_saved_replay_evidence.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        git_only = module.verify(directory)
        self.assertEqual(174, git_only["journal_positions_verified"])
        self.assertEqual(2, git_only["raw_recoveries_verified"])
        self.assertEqual(0, git_only["positional_tensors_numerically_checked"])
        self.assertFalse(git_only["local_positional_bytes_checked"])
        self.assertIn("LOCAL-ONLY", git_only["limitation"])
        full = json.loads((directory / "verification-with-local.json").read_text())
        self.assertEqual(176, full["raw_recoveries_verified"])
        self.assertEqual(174, full["positional_tensors_numerically_checked"])
        result = json.loads((directory / "result.json").read_text())
        self.assertFalse(result["retention"]["positional_bytes_in_git"])
        self.assertFalse(result["retention"]["positional_bytes_recoverable_from_git_hashes_alone"])
        self.assertEqual(2, len(result["retention"]["required_migration_paths"]))
        manifest = json.loads((directory / "compression-manifest.json").read_text())
        positional = [entry for entry in manifest["files"] if "position" in entry]
        self.assertEqual(174, len(positional))
        self.assertEqual(173105118, sum(entry["raw_bytes"] for entry in positional))
        self.assertTrue(all("compressed_local_path" in entry and "compressed_path" not in entry for entry in positional))

    def test_qnn_trajectory_readiness_does_not_claim_real_execution(self) -> None:
        directory = EXP / "results/qnn-trajectory-helper-readiness"
        result = json.loads((directory / "result.json").read_text())
        self.assertEqual("source_only_qnn_own_state_trajectory_helper_readiness", result["evidence_class"])
        self.assertEqual(30, result["validation"]["synthetic_tests_passed"])
        self.assertEqual(0, result["validation"]["actual_qnn_graph_calls"])
        self.assertEqual(0, result["validation"]["real_pte_or_model_archives_loaded"])
        self.assertEqual(73, result["planned_binding"]["pte_outputs"])
        self.assertEqual(48, result["planned_binding"]["state_outputs_carried"])
        self.assertEqual(24, result["planned_binding"]["hidden_diagnostics_retained_not_carried"])
        for key in ("real_qnn_trajectory_performed", "real_model_load_performed", "physical_execution_performed", "new_numerical_fidelity_claim", "campaign_ready", "registry_eligible"):
            self.assertFalse(result[key])
        budget = result["budget_plan"]
        self.assertFalse(budget["example_is_authorization"])
        self.assertGreater(budget["full174_estimated_seconds"], budget["maximum_timeout_seconds"])
        self.assertFalse(result["checkpoint_policy"]["native_restart_equivalence_claimed"])
        self.assertFalse(result["checkpoint_policy"]["loaded_route_campaign_reuse_claimed"])
        for entry in result["artifacts"].values():
            self.assertEqual(entry["sha256"], sha(EXP / entry["path"]))

    def test_four_position_qnn_prefix_retains_drift_and_bounds(self) -> None:
        directory = EXP / "results/host-qnn-trajectory-prefix-000-003-20260910"
        result = json.loads((directory / "result.json").read_text())
        self.assertEqual("host_qnn_x86_histogram_4_position_own_state_trajectory", result["evidence_class"])
        self.assertEqual([0, 1, 2, 3], result["authorization"]["input_positions"])
        for key in ("graph_calls_returned", "state_updates_completed", "comparisons_completed"):
            self.assertEqual(4, result["execution"][key])
        self.assertEqual(73, result["execution"]["forward_outputs"])
        self.assertEqual(48, result["execution"]["state_outputs_carried"])
        self.assertEqual(2, result["first_argmax_divergence_position"])
        self.assertLess(result["comparisons"][1]["cosine"], 0.7)
        self.assertEqual((248045, 71093), (result["comparisons"][2]["qdq_argmax"], result["comparisons"][2]["qnn_argmax"]))
        self.assertEqual(4, result["checkpoint"]["next_position"])
        self.assertFalse(result["checkpoint"]["resume_executed"])
        self.assertLess(result["timing"]["supervisor_elapsed_seconds"], 900)
        for key in ("full174_qnn_trajectory_verified", "same_state_causal_localization_claimed", "physical_execution_performed", "autoregressive_generation_performed", "campaign_ready", "registry_eligible"):
            self.assertFalse(result[key])
        self.assertTrue(result["cleanup"]["owned_process_group_absent"])
        self.assertEqual(0, result["cleanup"]["scratch_regular_files_remaining"])
        spec = importlib.util.spec_from_file_location("prefix_verifier", EXP / "tools/verify_qnn_prefix_evidence.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        check = module.verify(directory)
        self.assertEqual(13, check["raw_recoveries_verified"])
        self.assertEqual(4, check["checkpoint_headers_verified"])
        self.assertFalse(check["model_or_pte_loaded_or_executed"])
        # Root checkpoints/ ignores must not silently drop reviewed evidence at staging.
        for position in range(4):
            for suffix in ("json", "states.pt.zst"):
                path = directory / f"raw/checkpoints/position-{position:03d}.{suffix}"
                ignored = subprocess.run(["git", "check-ignore", "--no-index", "-q", str(path)], cwd=REPO)
                self.assertEqual(1, ignored.returncode, str(path))
        raw_state = directory / "raw/checkpoints/position-000.states.pt"
        self.assertEqual(0, subprocess.run(["git", "check-ignore", "--no-index", "-q", str(raw_state)], cwd=REPO).returncode)
        for key in ("runtime_source", "supervisor_source", "verifier_source"):
            entry = result["route"][key]
            self.assertEqual(entry["sha256"], sha(EXP / entry["path"]))

    def test_same_state_position1_inventory_is_not_an_executed_control(self) -> None:
        directory = EXP / "results/host-qnn-trajectory-prefix-000-003-20260910"
        inventory = json.loads((directory / "same-state-inventory.json").read_text())
        result = json.loads((directory / "result.json").read_text())
        self.assertTrue(inventory["source_only_inventory"])
        self.assertFalse(inventory["model_or_pte_loaded_or_executed"])
        self.assertEqual(0, inventory["source_input_position"])
        self.assertEqual(248045, inventory["source_token_id"])
        self.assertTrue(inventory["position0_logits_bit_identical_to_full_qdq_replay"])
        self.assertEqual(0, inventory["position0_logits_max_abs"])
        self.assertEqual(48, inventory["qdq_state_outputs_after_position0_retained"])
        self.assertEqual("30799090d14a42c92ea804a2763df55ff231ba232653d96484324ad40c492364", inventory["qdq_archive"]["sha256"])
        self.assertEqual(1, inventory["qnn_state_before_position1"]["next_position"])
        self.assertEqual(2, inventory["qnn_state_before_position2"]["next_position"])
        plan = result["same_state_next_plan"]
        self.assertEqual(1, plan["target_input_position"])
        self.assertFalse(plan["new_qdq_replay_performed"])
        self.assertFalse(plan["new_controlled_qnn_call_performed"])

    def test_controlled_position1_is_data_readiness_not_model_execution(self) -> None:
        directory = EXP / "results/controlled-position1-readiness"
        result = json.loads((directory / "result.json").read_text())
        self.assertEqual("source_data_only_controlled_position1_readiness", result["evidence_class"])
        self.assertEqual(23, result["synthetic_validation"]["tests_passed"])
        pack = result["materialized"]
        self.assertEqual(51, pack["input_tensors"])
        self.assertEqual(48, pack["state_tensors"])
        self.assertEqual((1, 8678), (pack["target_position"], pack["target_token"]))
        self.assertEqual("qdq_after_position0_not_qnn_resume", pack["origin"])
        self.assertEqual("bfe14bca74090778550618c1c6eb485728e15e6e784e936b87606dcb298ebe0d", pack["input_pack"]["sha256"])
        self.assertFalse(result["full_replay_state_byte_equality_proved"])
        self.assertFalse(result["exact_same_state_attribution_established"])
        self.assertFalse(result["new_qdq_execution_performed"])
        self.assertFalse(result["new_qnn_execution_performed"])
        self.assertFalse(result["physical_execution_performed"])
        self.assertFalse(result["vector_analysis"]["scalar_cosines_added"])
        calls = result["required_future_calls"]
        self.assertEqual(0, calls["current_model_calls_executed"])
        self.assertEqual(2, calls["exact_same_pack_attribution_path"]["total_calls"])
        self.assertFalse(calls["budgets_are_authorization"])
        self.assertFalse(calls["historical_only_path"]["exact_same_state_attribution"])
        for item in result["artifacts"].values():
            self.assertEqual(item["sha256"], sha(EXP / item["path"]))
        for item in json.loads((directory / "compression-manifest.json").read_text())["files"]:
            compressed = directory / item["compressed_path"]
            self.assertEqual(item["compressed_sha256"], sha(compressed))
            recovered_sha, recovered_bytes = sha_zstd(compressed)
            self.assertEqual(item["raw_sha256"], recovered_sha)
            self.assertEqual(item["raw_bytes"], recovered_bytes)
        old_plan = (EXP / "results/host-qnn-trajectory-prefix-000-003-20260910/SAME_STATE_PLAN.md").read_text()
        self.assertNotIn("identically matching the source used", old_plan)

    def test_one_qdq_position1_call_is_a_reference_not_paired_qnn(self) -> None:
        directory = EXP / "results/controlled-position1-qdq-20260910"
        result = json.loads((directory / "result.json").read_text())
        raw = json.loads((directory / "raw/result.json").read_text())
        self.assertEqual("completed_single_call", raw["status"])
        self.assertEqual("qdq", raw["backend"])
        self.assertEqual(1, raw["graph_calls_returned"])
        self.assertEqual(1, raw["target_position"])
        self.assertFalse(raw["input_mutation_observed"])
        self.assertEqual("4251bbce8005e37cb9fc4c8da8f0af604e7c4a9884179e2ccd358ef4865c78e4", raw["submitted_input_values_sha256"])
        self.assertTrue(raw["historical_qdq_logits_bit_identical"])
        self.assertEqual(0, raw["historical_qdq_comparison"]["max_abs"])
        self.assertEqual(0, raw["historical_qdq_comparison"]["mean_abs"])
        self.assertEqual(198, raw["logits"]["argmax"])
        self.assertGreater(raw["historical_qdq_comparison"]["cosine"], 1)  # Preserve rounding overshoot, don't invent above-perfect similarity.
        self.assertTrue(result["observed"]["authoritative_same_pack_qdq_reference_available"])
        self.assertEqual(1, result["new_qdq_calls"])
        self.assertEqual(0, result["new_qnn_calls"])
        self.assertFalse(result["paired_same_state_attribution_completed"])
        self.assertFalse(result["historical_full_replay_state_byte_identity_proved"])
        self.assertLess(result["timing"]["supervisor_elapsed_seconds"], 600)
        self.assertTrue(result["cleanup"]["owned_process_group_absent"])
        self.assertEqual(0, result["cleanup"]["scratch_regular_files_remaining"])
        self.assertEqual(result["paired_reference_handoff"]["raw_result_sha256"], sha(directory / "raw/result.json"))
        for e in json.loads((directory / "compression-manifest.json").read_text())["files"]:
            path = directory / e["compressed_path"]
            self.assertEqual(e["compressed_sha256"], sha(path))
            recovered_sha, recovered_bytes = sha_zstd(path)
            self.assertEqual(e["raw_sha256"], recovered_sha)
            self.assertEqual(e["raw_bytes"], recovered_bytes)

    def test_paired_position1_retains_current_call_and_state_effects(self) -> None:
        directory = EXP / "results/controlled-position1-paired-qnn-20260910"
        result = json.loads((directory / "result.json").read_text())
        qnn = json.loads((directory / "raw/qnn-result.json").read_text())
        qdq = json.loads((directory / "raw/qdq-result.json").read_text())
        analysis = json.loads((directory / "analysis/all73-comparison.json").read_text())
        self.assertEqual("completed_single_call", qnn["status"])
        self.assertEqual(1, qnn["graph_calls_returned"])
        self.assertEqual(1, qnn["target_position"])
        self.assertTrue(qnn["exact_same_pack_qdq_reference_used"])
        self.assertEqual(qnn["submitted_input_values_sha256"], qdq["submitted_input_values_sha256"])
        self.assertFalse(qnn["input_mutation_observed"])
        self.assertFalse(qdq["input_mutation_observed"])
        self.assertGreater(qnn["same_pack_qdq_comparison"]["cosine"], 0.88)
        self.assertLess(qnn["same_pack_qdq_comparison"]["cosine"], 0.90)
        self.assertEqual(73, len(analysis["outputs"]))
        self.assertTrue(analysis["all_three_bundles_finite"])
        self.assertGreater(analysis["logit_vector_terms"]["current_call"]["l2"], 0)
        self.assertGreater(analysis["logit_vector_terms"]["qnn_state_effect"]["l2"], 0)
        self.assertEqual(0, analysis["logit_vector_terms"]["historical_reference_shift"]["l2"])
        self.assertLess(analysis["logit_vector_terms"]["rounding_residual"]["max_abs"], 1e-6)
        self.assertEqual(0, analysis["double_identity_max_abs_residual"])
        self.assertFalse(result["saved_data_analysis"]["scalar_cosines_or_norms_added"])
        self.assertFalse(result["individual_operator_root_cause_identified"])
        self.assertFalse(result["full_trajectory_fidelity_established"])
        self.assertFalse(result["physical_execution_performed"])
        self.assertTrue(result["cleanup"]["owned_process_group_absent"])
        slot = result["saved_data_analysis"]["conv_history_slot_observation"]["slots"][2]
        self.assertEqual(6053, slot["channel_at_max"])
        self.assertGreater(abs(slot["qdq_value"] - slot["common_input_value"]), 1.5)
        self.assertLess(abs(slot["qnn_value"] - slot["common_input_value"]), 1e-5)
        for e in json.loads((directory / "compression-manifest.json").read_text())["files"]:
            path = directory / e["compressed_path"]
            self.assertEqual(e["compressed_sha256"], sha(path))
            raw_sha, size = sha_zstd(path)
            self.assertEqual(e["raw_sha256"], raw_sha)
            self.assertEqual(e["raw_bytes"], size)
        source = result["binding"]["analyzer_source"]
        self.assertEqual(source["sha256"], sha(EXP / source["path"]))

    def test_manifests_bind_retained_evidence(self) -> None:
        for directory in (
            EXP / "protocol",
            EXP / "results/support-assessment",
            EXP / "results/executorch-qnn-structural-probe",
            EXP / "results/executorch-qnn-exact-host-compile",
            EXP / "results/android-explicit-state-runner-host-build",
            EXP / "results/android-qnn-physical-viability-20260827-attempt-01",
            EXP / "results/android-runner-boundary-fix-host-build",
            EXP / "results/android-qnn-physical-viability-20260827-attempt-02",
            EXP / "results/host-w4a16-qdq-output-diagnosis",
            EXP / "results/host-qnn-broadcast-divergence-localization",
            EXP / "results/exact-qnn-explicit-broadcast-host-validation",
            EXP / "results/android-qnn-physical-viability-20260828-attempt-03",
            EXP / "results/host-histogram-precision-20260910",
            EXP / "results/saved-qdq-replay-helper-readiness",
            EXP / "results/host-histogram-full-short-20260910",
            EXP / "results/qnn-trajectory-helper-readiness",
            EXP / "results/host-qnn-trajectory-prefix-000-003-20260910",
            EXP / "results/controlled-position1-readiness",
            EXP / "results/controlled-position1-qdq-20260910",
            EXP / "results/controlled-position1-paired-qnn-20260910",
        ):
            entries = {}
            for line in (directory / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ", 1)
                entries[name] = digest
            retained = {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file() and path.name != "SHA256SUMS"}
            self.assertEqual(retained, set(entries))
            for name, digest in entries.items():
                self.assertEqual(digest, sha(directory / name))


if __name__ == "__main__":
    unittest.main()
