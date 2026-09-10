from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((EXP / "protocol/experiment-contract.json").read_text())
        cls.result = json.loads((EXP / "results/support-assessment/result.json").read_text())

    def test_canonical_protocol_and_workloads(self) -> None:
        canonical = self.contract["canonical_protocol"]
        self.assertEqual(canonical["sha256"], sha(REPO / canonical["path"]))
        directory = REPO / "protocols/android-llm-benchmark/workloads/inference-v1"
        for tier, digest in canonical["workloads"].items():
            self.assertEqual(digest, sha(directory / f"{tier}.json"))
        self.assertEqual(2048, canonical["max_new_tokens"])
        self.assertEqual(["short", "medium", "long"], canonical["tier_order"])

    def test_lfm_identity_and_hybrid_state_are_bound(self) -> None:
        model = self.result["model"]
        self.assertEqual("Lfm2ForCausalLM", model["architecture"])
        self.assertEqual("lfm2", model["model_type"])
        self.assertEqual(30, model["layers"])
        self.assertEqual({"conv": 22, "full_attention": 8}, model["layer_type_counts"])
        self.assertEqual(3, model["conv_cache_length"])
        self.assertEqual(131072, model["native_context"])

    def test_exact_official_artifact_is_reused_but_not_redownloaded(self) -> None:
        artifact = self.result["official_public_artifact"]
        self.assertEqual("lfm2", artifact["gguf_architecture"])
        self.assertEqual(1_674_455_040, artifact["bytes"])
        self.assertEqual("02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed", artifact["sha256"])
        self.assertFalse(artifact["downloaded_for_0034"])
        self.assertTrue(artifact["download_avoided_reason"])

    def test_installed_and_public_support_are_absent(self) -> None:
        installed = self.result["installed_qairt"]
        self.assertFalse(installed["factory_supports_lfm2"])
        self.assertFalse(installed["direct_gguf_supports_lfm2"])
        self.assertNotIn("lfm2", installed["direct_gguf_supported_model_types"])
        self.assertEqual([], installed["matching_genie_configs"])
        self.assertFalse(installed["release_notes_mentions_lfm_or_liquid"])
        public = self.result["public_qualcomm_support"]
        self.assertEqual([], public["matching_model_directories"])
        self.assertFalse(public["qnn_context_binary_published"])
        self.assertFalse(public["quantized_onnx_encodings_published"])

    def test_tokenizer_template_and_prompts_are_bound(self) -> None:
        frontend = self.result["tokenizer_and_template"]
        contract_frontend = self.contract["tokenizer_and_template"]
        self.assertEqual(contract_frontend["tokenizer_json_sha256"], frontend["files"]["tokenizer.json"])
        self.assertEqual(contract_frontend["tokenizer_config_sha256"], frontend["files"]["tokenizer_config.json"])
        self.assertEqual(contract_frontend["chat_template_sha256"], frontend["files"]["chat_template.jinja"])
        expected = {
            "short": (171, "eae8e828110f634d5c9954df0372e869f67f67aed846f9f544781faa1d4d29bc"),
            "medium": (600, "bfd8e9ee4fecef5b3203ad67ee0c2fe1a5a4d3267cfabc83c4388f04e25789e9"),
            "long": (1922, "bf6cd4a807f1933a4890a52fc847242be44c45cfc712bc9767ed8030845ec512"),
        }
        for tier, (count, token_hash) in expected.items():
            prompt = frontend["prompt_inventory"][tier]
            self.assertEqual(count, prompt["input_tokens"])
            self.assertEqual(token_hash, prompt["token_ids_int32le_sha256"])
            self.assertEqual(1, prompt["leading_bos_count"])
            self.assertTrue(prompt["generation_prompt_ends_native_think"])
            self.assertTrue(prompt["fits_context_4096"])
            self.assertEqual(prompt["rendered_sha256"], sha(EXP / f"protocol/rendered/{tier}.txt"))
            self.assertEqual(token_hash, sha(EXP / f"protocol/token-ids/{tier}.int32le"))

    def test_active_export_does_not_claim_qnn_android_or_completion(self) -> None:
        self.assertIn("blocked_phone_transport_before_integrated_staging", self.contract["status"])
        route = self.result["route_assessment"]
        self.assertFalse(route["compiled_sm8550_context_available"])
        self.assertFalse(route["android_execution"])
        self.assertFalse(route["qnn_htp_execution"])
        milestone = self.contract["host_export_milestone"]
        self.assertIn("not_android_qnn_or_htp", milestone["classification"])
        self.assertEqual("passed", milestone["rewritten_onnx"]["onnx_checker"])
        self.assertEqual(16, milestone["bounded_output"]["max_new_tokens"])
        self.assertIn("lost transport before remote-root creation/staging", self.contract["phone_boundary"])

    def test_qnn_aot_is_complete_but_not_physical_execution(self) -> None:
        milestone = self.contract["qnn_aot_milestone"]
        self.assertEqual(263, milestone["pipeline_parts"])
        self.assertEqual(1583, milestone["source_nodes"])
        self.assertEqual(1583, milestone["supported_source_nodes"])
        self.assertEqual(0, milestone["unsupported_source_nodes"])
        self.assertEqual(2747, milestone["qnn_ops"])
        self.assertTrue(milestone["session_disable_cpu_ep_fallback"])
        self.assertFalse(milestone["physical_execution"])
        self.assertFalse(milestone["registry_eligible"])
        evidence = json.loads((EXP / milestone["evidence"]).read_text())
        self.assertTrue(evidence["compiler"]["all_parts_compiled"])
        self.assertEqual({"chipset": "SM8550", "htp_arch": "V73", "soc_model": 43}, evidence["compiler"]["target"])
        self.assertEqual(0, evidence["compiler"]["total_unsupported_source_nodes"])
        self.assertEqual(263, len(evidence["parts"]))
        for part in evidence["parts"]:
            self.assertEqual(part["source_nodes"], part["supported_nodes"])
            self.assertEqual(0, part["unsupported_nodes"])

    def test_phone_stage_is_preparation_only(self) -> None:
        preparation = self.contract["phone_preparation"]
        self.assertIn("host_only", preparation["classification"])
        self.assertTrue(preparation["adb_contact_by_owner"])
        self.assertFalse(preparation["phone_staged"])
        self.assertFalse(preparation["android_execution"])
        self.assertFalse(preparation["registry_eligible"])
        self.assertEqual(16, preparation["bounded_request"]["max_new_tokens"])
        evidence = json.loads((EXP / preparation["evidence"]).read_text())
        self.assertEqual("retry_stage_prepared_with_npu_device_filter_and_diagnostics", evidence["status"])
        self.assertTrue(evidence["phone_boundary"]["adb_contact_by_0034_owner"])
        self.assertTrue(evidence["ignored_stage"]["retained_outside_git"])

    def test_first_phone_attempt_failed_closed_before_execution(self) -> None:
        attempt = self.contract["phone_attempt_1"]
        self.assertIn("pre_inference", attempt["classification"])
        self.assertTrue(attempt["stage_hashes_verified_local_and_remote"])
        self.assertEqual(0, attempt["sessions_loaded"])
        self.assertFalse(attempt["model_token_execution"])
        self.assertFalse(attempt["qnn_htp_graph_execution"])
        self.assertFalse(attempt["output_created"])
        self.assertTrue(attempt["scoped_cleanup_verified_absent"])
        result = json.loads((EXP / attempt["evidence"]).read_text())
        self.assertEqual(1, result["execution"]["exit_code"])
        self.assertIn("fallback", result["execution"]["stderr"])
        self.assertTrue(result["cleanup"]["phone_lock_held_for_full_lifecycle"])

    def test_second_phone_attempt_proves_npu_selection_but_no_execution(self) -> None:
        attempt = self.contract["phone_attempt_2"]
        self.assertIn("npu_epcontext_claim_failure", attempt["classification"])
        self.assertTrue(attempt["npu_only_selection"])
        self.assertEqual("NPU", attempt["qnn_ep_device"]["hardware_type_name"])
        self.assertEqual("Qualcomm", attempt["qnn_ep_device"]["vendor"])
        self.assertEqual(0, attempt["sessions_loaded"])
        self.assertFalse(attempt["model_token_execution"])
        self.assertFalse(attempt["qnn_htp_graph_execution"])
        self.assertFalse(attempt["output_created"])
        self.assertEqual(0, attempt["profiles_created"])
        self.assertTrue(attempt["scoped_cleanup_verified_absent"])
        self.assertFalse(attempt["further_phone_retry_authorized"])
        result = json.loads((EXP / attempt["evidence"]).read_text())
        qnn = result["provider_diagnostics"]["available_devices"][1]
        self.assertEqual({"ep_name": "QNNExecutionProvider", "hardware_type": 2, "hardware_type_name": "NPU", "vendor": "Qualcomm", "vendor_id": 1297040209, "device_id": 0}, qnn)
        self.assertTrue(result["provider_diagnostics"]["session_disable_cpu_ep_fallback"])
        self.assertEqual(0, result["execution"]["sessions_loaded"])
        self.assertTrue(result["cleanup"]["scoped_remote_root_verified_absent"])

    def test_direct_qnn_continuation_is_host_prepared_only(self) -> None:
        route = self.contract["direct_qnn_continuation"]
        self.assertFalse(route["onnxruntime_used"])
        self.assertEqual(["QnnContext_createFromBinary", "QnnGraph_retrieve", "QnnGraph_execute"], route["runtime_path"])
        self.assertEqual(263, route["context_count"])
        self.assertTrue(route["first_context_host_emulator"]["executed"])
        self.assertEqual(43, route["first_context_host_emulator"]["target_soc_model"])
        self.assertEqual(73, route["first_context_host_emulator"]["target_dsp_arch"])
        self.assertFalse(route["physical_android_execution"])
        self.assertFalse(route["registry_eligible"])
        result = json.loads((EXP / route["evidence"]).read_text())
        self.assertEqual("success", result["host_probe"]["direct_api_evidence"]["QnnContext_createFromBinary"])
        self.assertEqual("status 0", result["host_probe"]["direct_api_evidence"]["QnnGraph_execute"])
        self.assertTrue(result["host_probe"]["outputs"]["all_finite"])
        self.assertFalse(result["android_runner"]["onnxruntime_or_epcontext_used"])
        self.assertTrue(result["ignored_android_stage"]["retained_outside_git"])

    def test_consolidated_direct_qnn_route_is_host_prepared_only(self) -> None:
        route = self.contract["consolidated_direct_qnn_route"]
        self.assertEqual((263, 37), (route["source_part_count"], route["context_count"]))
        self.assertTrue(route["all_contexts_loaded_once"])
        self.assertFalse(route["per_request_or_token_reload"])
        self.assertEqual(0, route["unsupported_nodes"])
        self.assertTrue(route["host_cpu_five_step_argmax_match"])
        self.assertFalse(route["physical_execution"])
        result = json.loads((EXP / route["evidence"]).read_text())
        self.assertEqual((1583, 1583, 0), (result["compiler"]["source_nodes"], result["compiler"]["supported_nodes"], result["compiler"]["unsupported_nodes"]))
        self.assertEqual(37, len(result["contexts"]))
        self.assertTrue(result["host_validation"]["htp_emulator_layer00"]["graph_execute_succeeded"])

    def test_consolidated_phone_attempt_fails_before_execution(self) -> None:
        attempt = self.contract["consolidated_direct_qnn_phone_attempt_1"]
        self.assertEqual((19, 20, "layer-19"), (attempt["contexts_loaded"], attempt["failed_context_ordinal"], attempt["failed_context"]))
        self.assertEqual(0, attempt["graphs_executed"])
        self.assertTrue(attempt["process_rss_is_not_total_backend_residency"])
        self.assertTrue(attempt["cleanup_absent"])
        result = json.loads((EXP / attempt["evidence"]).read_text())
        self.assertEqual("QnnContext_createFromBinary", result["direct_qnn"]["failure_api"])
        self.assertFalse(result["direct_qnn"]["output_created"])

    def test_whole_route_shared_context_is_host_prepared_only(self) -> None:
        route = self.contract["whole_route_shared_context"]
        self.assertEqual((1, 37, 263), (route["context_count"], route["graph_count"], route["source_part_count"]))
        self.assertTrue(route["all_graphs_present_once_in_exact_order"])
        self.assertFalse(route["per_request_or_token_reload"])
        self.assertFalse(route["host_retrieval"])
        self.assertEqual("rejected_by_context_create", route["physical_android_support"])
        result = json.loads((EXP / route["evidence"]).read_text())
        self.assertEqual(37, len(result["execution_order"]))
        self.assertIn("not supported on this platform", result["host_retrieval"]["exact_error"])
        self.assertFalse(result["host_retrieval"]["success"])

    def test_whole_route_shared_phone_attempt_fails_before_retrieval(self) -> None:
        attempt = self.contract["whole_route_shared_context_phone_attempt_1"]
        self.assertEqual((1, 37, 0), (attempt["contexts_required"], attempt["graphs_in_context"], attempt["contexts_loaded"]))
        self.assertEqual((0, 0), (attempt["graphs_retrieved"], attempt["graphs_executed"]))
        self.assertIn("blob materialization", attempt["process_vmhwm_interpretation"])
        result = json.loads((EXP / attempt["evidence"]).read_text())
        self.assertEqual("QnnContext_createFromBinary", result["direct_qnn"]["failure_api"])
        self.assertFalse(result["direct_qnn"]["output_created"])
        self.assertTrue(result["cleanup"]["scoped_remote_root_verified_absent"])

    def test_matched_qairt_24940_android_stage_was_exactly_bound(self) -> None:
        route = self.contract["matched_qairt_24940_android_retry"]
        self.assertEqual(route["context_build_id"], route["android_backend_build_id_expected"])
        self.assertTrue(route["build_ids_exactly_equal"])
        self.assertEqual((1, 37), (route["context_count"], route["graph_count"]))
        self.assertFalse(route["context_streaming"])
        self.assertFalse(route["physical_execution"])
        self.assertTrue(route["phone_priority_granted"])
        self.assertIn("rejected_by_QnnContext_createFromBinary", route["outcome"])
        result = json.loads((EXP / route["evidence"]).read_text())
        self.assertTrue(result["matched_android_runtime"]["context_runtime_build_ids_equal"])
        self.assertEqual("v2.49.0.260730134355", result["superseded_runtime"]["backend_build_id_observed_physically"])
        self.assertTrue(result["ignored_android_stage"]["all_local_hashes_verified"])

    def test_matched_qairt_24940_phone_attempt_rules_out_runtime_mismatch(self) -> None:
        attempt = self.contract["matched_qairt_24940_android_phone_attempt_1"]
        self.assertEqual(attempt["context_build_id"], attempt["physical_backend_build_id"])
        self.assertTrue(attempt["build_ids_exactly_equal"])
        self.assertEqual((0, 0, 0), (attempt["contexts_loaded"], attempt["graphs_retrieved"], attempt["graphs_executed"]))
        self.assertIn("blob materialization", attempt["process_vmhwm_interpretation"])
        result = json.loads((EXP / attempt["evidence"]).read_text())
        self.assertEqual("QnnContext_createFromBinary", result["direct_qnn"]["failure_api"])
        self.assertTrue(result["cleanup"]["scoped_remote_root_verified_absent"])
        option2 = self.contract["authorized_option_2"]
        self.assertFalse(option2["shared_resource_format"])
        self.assertFalse(option2["context_streaming"])

    def test_ordinary_monolithic_option_2_host_preparation_is_bound(self) -> None:
        route = self.contract["authorized_option_2"]
        self.assertEqual((1, 1), (route["context_count"], route["graph_count"]))
        self.assertFalse(route["shared_resource_format"])
        self.assertFalse(route["weight_sharing_format"])
        self.assertFalse(route["context_streaming"])
        self.assertTrue(route["fallback_disabled"])
        self.assertEqual((1541, 1541, 0), (route["optimized_source_nodes"], route["supported_nodes"], route["unsupported_nodes"]))
        self.assertTrue(route["host_htp_graph_execute_succeeded"])
        self.assertEqual(route["reference_greedy_token"], route["host_greedy_token"])
        self.assertTrue(route["physical_execution"])
        result = json.loads((EXP / route["evidence"]).read_text())
        self.assertEqual((41, 60), (result["context"]["graph_inputs"], result["context"]["graph_outputs"]))
        self.assertTrue(result["host_htp_execution"]["greedy_decision_equal"])
        self.assertIn("not physical performance", result["host_htp_execution"]["timing_interpretation"])

    def test_ordinary_monolithic_physical_position0_viability(self) -> None:
        gate = self.contract["ordinary_monolithic_phone_viability_position0"]
        self.assertEqual("direct QNN HTP", gate["backend"])
        self.assertEqual((1, 1, 1), (gate["context_count"], gate["graph_count"], gate["graph_executions"]))
        self.assertTrue(gate["context_loaded"])
        self.assertTrue(gate["graph_loaded"])
        self.assertTrue(gate["loaded_once"])
        self.assertFalse(gate["neural_cpu_fallback_available"])
        self.assertEqual(gate["reference_global_argmax"], gate["output_global_argmax"])
        self.assertFalse(gate["canonical_campaign"])
        self.assertFalse(gate["registry_result"])
        result = json.loads((EXP / gate["evidence"]).read_text())
        self.assertEqual("ordinary non-shared", result["route"]["context_format"])
        self.assertEqual(1, result["route"]["graph_executions"])
        self.assertTrue(result["workload"]["global_argmax_equal"])
        self.assertIn("not a canonical benchmark", result["timing"]["interpretation"])
        self.assertTrue(result["cleanup"]["scoped_remote_root_verified_absent"])

    def test_ordinary_monolithic_host_two_step_carries_state(self) -> None:
        check = self.contract["ordinary_monolithic_host_two_step_state_check"]
        self.assertEqual((1, 1, 2, 0), (check["context_count"], check["graph_count"], check["graph_executions"], check["context_reloads"]))
        self.assertEqual([124894, 124899], check["canonical_short_prefix_tokens"])
        self.assertEqual([0, 1], check["positions"])
        self.assertEqual(38, check["explicit_state_tensors_carried"])
        self.assertTrue(check["position_and_mask_updated"])
        self.assertEqual(check["reference_global_argmax"], check["position_1_global_argmax"])
        self.assertFalse(check["physical_execution"])
        self.assertFalse(check["canonical_prompt_completed"])
        result = json.loads((EXP / check["evidence"]).read_text())
        self.assertTrue(result["result"]["greedy_decision_equal"])
        self.assertIn("without reload", result["route"]["state_behavior"])
        self.assertIn("not physical", result["timing"]["interpretation"])

    def test_ordinary_monolithic_physical_two_step_carries_state(self) -> None:
        gate = self.contract["ordinary_monolithic_phone_two_step_state_check"]
        self.assertEqual((1, 1, 2, 0), (gate["context_count"], gate["graph_count"], gate["graph_executions"], gate["context_reloads"]))
        self.assertEqual([124894, 124899], gate["canonical_short_prefix_tokens"])
        self.assertEqual([0, 1], gate["positions"])
        self.assertEqual(38, gate["explicit_state_tensors_carried"])
        self.assertTrue(gate["position_and_mask_updated"])
        self.assertEqual((25, 25, 25), (gate["position_1_global_argmax"], gate["cpu_reference_argmax"], gate["host_x86_htp_reference_argmax"]))
        self.assertFalse(gate["neural_cpu_fallback_available"])
        self.assertFalse(gate["canonical_prompt_completed"])
        self.assertFalse(gate["generated_text"])
        result = json.loads((EXP / gate["evidence"]).read_text())
        self.assertEqual(2, result["route"]["graph_executions"])
        self.assertTrue(result["workload"]["all_argmax_equal"])
        self.assertIn("not a canonical benchmark", result["timing"]["interpretation"])
        self.assertTrue(result["cleanup"]["scoped_remote_root_verified_absent"])

    def test_canonical_short_gate_plan_is_bound(self) -> None:
        plan = self.contract["canonical_short_bounded_generation_gate_plan"]
        self.assertTrue(plan["plan_only"])
        self.assertTrue(plan["phone_authorized"])
        self.assertEqual("passed_bounded_max16_output_sanity", plan["outcome"])
        self.assertEqual((1, 1, 0), (plan["context_count"], plan["graph_count"], plan["context_reloads"]))
        self.assertFalse(plan["context_streaming"])
        self.assertEqual((171, 16, 2048), (plan["canonical_short_input_tokens"], plan["max_new_tokens"], plan["protocol_output_ceiling"]))
        self.assertTrue(plan["raw_output_preserved_before_validation"])
        self.assertTrue(plan["decode_after_cleanup"])
        result = json.loads((EXP / plan["evidence"]).read_text())
        self.assertEqual("not authorized for ADB; await Moritz/Pi agreement and explicit phone priority", result["authorization_status"])
        self.assertEqual(171, result["exact_workload"]["input_tokens"])
        self.assertIn("Plan and unchanged-stage review only", result["claim_boundary"])

    def test_canonical_short_physical_bounded_output_sanity(self) -> None:
        gate = self.contract["ordinary_monolithic_phone_canonical_short_max16"]
        self.assertEqual((1, 1, 0, 186), (gate["context_count"], gate["graph_count"], gate["context_reloads"], gate["graph_executions"]))
        self.assertEqual((171, 16), (gate["canonical_short_input_tokens"], gate["generated_tokens"]))
        self.assertEqual("max_tokens", gate["stop_reason"])
        self.assertFalse(gate["eos_present"])
        self.assertTrue(gate["raw_output_preserved_before_validation"])
        self.assertTrue(gate["all_token_ids_in_vocab"])
        self.assertTrue(gate["coherent_partial_continuation"])
        self.assertFalse(gate["complete_answer"])
        self.assertFalse(gate["statistical_performance"])
        self.assertFalse(gate["campaign"])
        result = json.loads((EXP / gate["evidence"]).read_text())
        self.assertEqual(64, result["workload"]["raw_output_bytes"])
        self.assertTrue(result["decode"]["performed_after_cleanup_and_raw_preservation"])
        self.assertIn("truncated", result["decode"]["sanity"])
        self.assertTrue(result["cleanup"]["scoped_remote_root_verified_absent"])

    def test_ar1_performance_profile_quantifies_current_bottlenecks(self) -> None:
        profile = self.contract["ordinary_monolithic_ar1_performance_profile"]
        self.assertFalse(profile["phone_access"])
        self.assertEqual(134750216, profile["input_raw_bytes_per_execution"])
        self.assertEqual(134184960, profile["fp32_attention_state_input_bytes"])
        self.assertEqual(512000, profile["fp32_logit_output_bytes"])
        self.assertEqual(6029426688, profile["compiler_estimated_spill_bytes"])
        self.assertEqual(6068150272, profile["compiler_estimated_fill_bytes"])
        self.assertFalse(profile["statistical_performance"])
        result = json.loads((EXP / profile["evidence"]).read_text())
        self.assertTrue(result["per_execution_raw_io"]["inputs"]["all_raw_memory"])
        self.assertEqual(1596407808, result["context"]["graph_blob_v2"]["constSize"])
        self.assertEqual(2698, sum(result["qnn_graph"]["operation_types"].values()))
        self.assertIn("metadata does not prove", result["bottleneck_assessment"][0])

    def test_chunked_prefill_ar32_ar128_host_probes(self) -> None:
        probes = self.contract["chunked_prefill_ar32_ar128_host_probes"]
        self.assertFalse(probes["phone_access"])
        self.assertFalse(probes["exact_numerical_equivalence"])
        self.assertFalse(probes["physical_execution"])
        for name, width in (("ar32", 32), ("ar128", 128)):
            item = probes["probes"][name]
            self.assertEqual(width, item["sequence_length"])
            self.assertTrue(item["argmax_equal"])
            self.assertTrue(item["qnn_compile_success"])
            self.assertEqual((1542, 0, 2699), (item["supported_nodes"], item["unsupported_nodes"], item["qnn_operations"]))
            self.assertLess(item["state_allclose_count"], item["state_tensor_count"])
        result = json.loads((EXP / probes["evidence"]).read_text())
        self.assertIn("material", result["fidelity_interpretation"])
        self.assertEqual(["AR57", "AR171"], probes["next_probes"])

    def test_chunked_prefill_ar57_ar171_exact_tiling_probes(self) -> None:
        probes = self.contract["chunked_prefill_ar57_ar171_host_probes"]
        self.assertFalse(probes["phone_access"])
        self.assertFalse(probes["exact_numerical_equivalence"])
        self.assertFalse(probes["physical_execution"])
        self.assertEqual("AR171", probes["selected_candidate"])
        self.assertEqual([57, 114, 171], probes["ar57"]["boundaries"])
        self.assertEqual(probes["ar57"]["argmax_reference"], probes["ar57"]["argmax_chunk"])
        self.assertEqual([171], probes["ar171"]["boundaries"])
        self.assertEqual(probes["ar171"]["argmax_reference"], probes["ar171"]["argmax_chunk"])
        for name in ("ar57", "ar171"):
            item = probes[name]
            self.assertTrue(item["qnn_compile_success"])
            self.assertEqual((1542, 0, 2699), (item["supported_nodes"], item["unsupported_nodes"], item["qnn_operations"]))
        self.assertTrue(probes["ar171"]["host_htp_context_create"])
        self.assertTrue(probes["ar171"]["host_htp_graph_retrieve"])
        self.assertFalse(probes["ar171"]["host_htp_execution_completed"])
        self.assertEqual(1800, probes["ar171"]["host_htp_timeout_seconds"])
        self.assertEqual(0, probes["ar171"]["host_htp_output_files"])
        result = json.loads((EXP / probes["evidence"]).read_text())
        self.assertIn("not numerically allclose", result["fidelity_boundary"])
        self.assertIn("not a target-SM8550", result["ar171"]["host_htp_execution"]["interpretation"])

    def test_ar171_physical_runtime_diagnostic_is_bounded(self) -> None:
        gate = self.contract["chunked_prefill_ar171_phone_runtime_diagnostic"]
        self.assertEqual("direct QNN HTP through qnn-net-run", gate["backend"])
        self.assertEqual((48, 48), (gate["stage_files_verified_local"], gate["stage_files_verified_remote"]))
        self.assertEqual((41, 133358252, 171), (gate["input_tensors"], gate["input_bytes"], gate["tokens_consumed"]))
        self.assertEqual((1, 1, 1), (gate["context_count"], gate["graph_count"], gate["graph_executions"]))
        self.assertTrue(gate["execution_succeeded"])
        self.assertEqual((60, 38, 22), (gate["output_files"], gate["state_files"], gate["logit_files"]))
        self.assertTrue(gate["all_outputs_finite"])
        self.assertEqual(gate["cpu_global_argmax"], gate["physical_global_argmax"])
        self.assertFalse(gate["numerical_equivalence"])
        self.assertFalse(gate["cpu_input_preparation_timed"])
        self.assertFalse(gate["canonical_end_to_end_ttft"])
        self.assertFalse(gate["statistical_performance"])
        result = json.loads((EXP / gate["evidence"]).read_text())
        self.assertEqual(5234013, result["profile"]["accelerator_execute_us"])
        self.assertIn("CPU embedding/input preparation was not timed", result["profile"]["interpretation"])
        self.assertTrue(result["cleanup"]["scoped_remote_root_verified_absent"])

    def test_ar171_physical_state_bridges_to_ar1_with_drift(self) -> None:
        bridge = self.contract["ar171_physical_state_to_ar1_host_bridge"]
        self.assertFalse(bridge["phone_access"])
        self.assertEqual((597, 171, 4095), (bridge["bridge_token"], bridge["bridge_position"], bridge["ar1_cache_length"]))
        self.assertEqual({"physical_ar171": 4695, "cpu_ar171": 4695, "sequential_ar1": 4695}, bridge["next_argmax"])
        self.assertTrue(bridge["all_argmax_equal"])
        self.assertFalse(bridge["numerical_equivalence"])
        self.assertEqual((3, 38), (bridge["pre_bridge_physical_cpu_state_allclose_count"], bridge["state_tensor_count"]))
        self.assertGreater(bridge["pre_bridge_state_max_abs"], 10000)
        self.assertFalse(bridge["concurrent_residency"]["attempted"])
        self.assertEqual(3202476296, bridge["concurrent_residency"]["combined_context_binary_bytes"])
        self.assertFalse(bridge["per_token_context_streaming"])
        self.assertGreater(bridge["pre_bridge_endpoint_logit_metrics"]["physical_vs_cpu_ar171_max_abs"], 7)
        self.assertEqual(58, bridge["present_2_key_outliers"]["physical_abs_gt_100"])
        self.assertEqual([0, 5, 57, 76], bridge["present_2_key_outliers"]["largest_index"])
        self.assertFalse(bridge["retained_sequential_physical_ar1_state"])
        self.assertEqual(4, bridge["max16_sequences"]["matching_prefix_tokens"])
        self.assertEqual(5272, bridge["max16_sequences"]["physical_ar171"][4])
        self.assertEqual(1561, bridge["max16_sequences"]["cpu_ar171"][4])
        self.assertFalse(bridge["max16_sequences"]["reference_equal"])
        result = json.loads((EXP / bridge["evidence"]).read_text())
        self.assertTrue(result["raw_layout_validation"]["all_file_sizes_match_declared_dtype_and_dimensions"])
        self.assertIn("large physical-vs-CPU drift", result["raw_layout_validation"]["present_2_key_outlier_observation"]["interpretation"])
        self.assertIn("one explicit prefill-to-decode phase transition", result["concurrent_residency_assessment"]["selected_phase_semantics"])

    def test_ar171_ar1_phase_switch_readiness_is_bound(self) -> None:
        ready = self.contract["ar171_ar1_phase_switch_readiness"]
        self.assertFalse(ready["phone_access"])
        self.assertTrue(ready["phone_authorized"])
        self.assertEqual((51, 3362360562), (ready["stage_payload_files"], ready["stage_payload_bytes"]))
        self.assertTrue(ready["bridge_host_validation"])
        self.assertEqual((41, 134750212), (ready["bridge_ar1_input_tensors"], ready["bridge_ar1_input_bytes"]))
        self.assertTrue(ready["all_state_copy_padding_mask_checks"])
        self.assertEqual(1, ready["explicit_phase_transition_count"])
        self.assertFalse(ready["simultaneous_context_residency"])
        self.assertFalse(ready["per_token_context_streaming"])
        self.assertEqual((597, 4695), (ready["expected_prefill_argmax"], ready["expected_next_argmax"]))
        self.assertTrue(ready["phase_execution_completed"])
        self.assertEqual("passed_argmax_597_to_4695", ready["outcome"])
        result = json.loads((EXP / ready["evidence"]).read_text())
        self.assertEqual("not authorized for phone execution; pending independent review and explicit Pi priority", result["authorization_status"])
        self.assertEqual("layer2 head5 token position76", self.contract["ar171_physical_state_to_ar1_host_bridge"]["present_2_key_outliers"]["localization"])
        self.assertFalse(result["planned_execution"]["per_token_context_streaming"])

    def test_physical_ar171_ar1_phase_switch_is_bounded(self) -> None:
        gate = self.contract["ar171_ar1_phone_phase_switch_diagnostic"]
        self.assertEqual((51, 51, 42), (gate["stage_payload_files_verified_local"], gate["stage_payload_files_verified_remote"], gate["bridge_hash_lines"]))
        self.assertFalse(gate["simultaneous_context_residency"])
        self.assertEqual(1, gate["phase_transition_count"])
        self.assertFalse(gate["per_token_context_streaming"])
        self.assertEqual((171, 597), (gate["prefill"]["tokens"], gate["prefill"]["argmax"]))
        self.assertEqual((597, 171, 4695), (gate["ar1"]["token"], gate["ar1"]["position"], gate["ar1"]["argmax"]))
        self.assertTrue(gate["prefill"]["all_finite"])
        self.assertTrue(gate["ar1"]["all_finite"])
        self.assertFalse(gate["initial_cpu_embedding_preparation_timed"])
        self.assertFalse(gate["numerical_equivalence"])
        self.assertFalse(gate["text_generation"])
        self.assertFalse(gate["canonical_ttft"])
        self.assertFalse(gate["statistical_performance"])
        result = json.loads((EXP / gate["evidence"]).read_text())
        self.assertTrue(result["prefill"]["raw_output_preserved_before_bridge"])
        self.assertTrue(result["decode_step"]["raw_output_preserved_before_validation"])
        self.assertIn("severe physical state/logit drift", result["fidelity_boundary"])
        self.assertTrue(result["cleanup"]["scoped_remote_root_verified_absent"])

    def test_ar1_max16_resume_is_ready_not_executed(self) -> None:
        ready = self.contract["ar1_max16_resume_readiness"]
        self.assertFalse(ready["phone_access"])
        self.assertTrue(ready["phone_authorized"])
        self.assertEqual((597, 171, 16), (ready["start_token"], ready["start_position"], ready["max_new_tokens"]))
        self.assertEqual((1, 0), (ready["context_count"], ready["context_reloads"]))
        self.assertFalse(ready["context_streaming"])
        self.assertEqual((4, 4), (ready["physical_reference_matching_prefix_tokens"], ready["first_divergence_index"]))
        self.assertFalse(ready["numerical_equivalence"])
        self.assertTrue(ready["host_x86_htp_max1"]["context_loaded"])
        self.assertEqual(4695, ready["host_x86_htp_max1"]["output_argmax"])
        self.assertEqual((53, 1932854438), (ready["stage"]["payload_files"], ready["stage"]["payload_bytes"]))
        self.assertTrue(ready["physical_execution"])
        self.assertEqual("passed_exact_cpu_physical_state_reference_sequence", ready["outcome"])
        result = json.loads((EXP / ready["evidence"]).read_text())
        self.assertIn("impractical-runtime", result["custom_runner"]["host_x86_htp_max1"]["interpretation"])
        self.assertIn("coherent partial", result["cpu_max16_validation"]["physical_route_sanity"])
        self.assertNotEqual(result["cpu_max16_validation"]["physical_ar171_state_tokens"], result["cpu_max16_validation"]["cpu_ar171_state_tokens"])

    def test_physical_ar1_max16_resume_operability_has_explicit_gaps(self) -> None:
        gate = self.contract["ar1_max16_phone_resume_diagnostic"]
        self.assertEqual((53, 53), (gate["stage_files_verified_local"], gate["stage_files_verified_remote"]))
        self.assertEqual((597, 171), (gate["start_token"], gate["start_position"]))
        self.assertEqual((1, 1, 0, 16), (gate["context_count"], gate["graph_count"], gate["context_reloads"], gate["graph_executions"]))
        self.assertFalse(gate["context_streaming"])
        self.assertEqual([4695,10966,622,310,5272,267,2014,116311,9516,28817,374,278,2909,19260,1703,2165], gate["tokens"])
        self.assertTrue(gate["exact_cpu_physical_state_sequence_equal"])
        self.assertTrue(gate["coherent_partial"])
        self.assertFalse(gate["raw_states_serialized"])
        self.assertFalse(gate["raw_logits_serialized"])
        self.assertFalse(gate["explicit_output_finite_scan"])
        self.assertFalse(gate["detailed_profile_serialized"])
        self.assertFalse(gate["numerical_equivalence"])
        self.assertFalse(gate["canonical_end_to_end_ttft"])
        result = json.loads((EXP / gate["evidence"]).read_text())
        self.assertEqual(64, result["output"]["raw_bytes"])
        self.assertIn("Per-call raw state/logit finiteness", result["evidence_gap"]["what_is_not_proven"])
        self.assertIn("excludes AR171 prefill", result["timing"]["scope"])
        self.assertTrue(result["cleanup"]["scoped_remote_root_verified_absent"])

    def test_integrated_output_is_incremental_exclusive_and_profile_fail_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "integrated-output-test"
            subprocess.run(
                [
                    "g++", "-std=c++17", "-O2",
                    f"-I{EXP / 'phone'}",
                    str(EXP / "tests/integrated_output_test.cpp"),
                    "-o", str(binary),
                ],
                check=True,
            )
            completed = subprocess.run([str(binary), str(root / "output")], check=True, capture_output=True, text=True)
            self.assertIn("integrated no-QNN control-flow checks passed", completed.stdout)

    def test_integrated_ar171_ar1_runner_is_host_ready_only(self) -> None:
        ready = self.contract["integrated_ar171_ar1_runner_readiness"]
        self.assertFalse(ready["phone_access"])
        self.assertTrue(ready["phone_authorized"])
        self.assertEqual((1, 2, 1, 1, 0), (ready["process_backend_count"], ready["contexts_loaded_sequentially"], ready["simultaneous_contexts"], ready["explicit_phase_transitions"], ready["context_reloads_per_phase"]))
        self.assertFalse(ready["per_token_context_streaming"])
        self.assertEqual((171, 16, 15, 60, 60, 38), (ready["prompt_tokens"], ready["max_new_tokens"], ready["ar1_max_graph_executions"], ready["ar171_outputs_finite_scanned"], ready["ar1_outputs_finite_scanned_per_token"], ready["state_tensors_bridged_in_memory"]))
        self.assertIn("total emitted tokens", ready["output_cap_semantics"])
        self.assertTrue(ready["exclusive_incremental_token_output"])
        self.assertTrue(ready["optional_profile_failure_preserves_output"])
        self.assertTrue(ready["actual_emission_timestamps"])
        self.assertTrue(ready["tokenization_precomputed_and_excluded_from_timing"])
        self.assertIn("Final-emitted includes intervening prefill profile", ready["emission_timing_boundary"])
        self.assertEqual(("QNN_DATATYPE_INT_64", [1, 171], 1368), (ready["ar171_position_abi"]["data_type"], ready["ar171_position_abi"]["dimensions"], ready["ar171_position_abi"]["bytes"]))
        self.assertEqual(("QNN_DATATYPE_INT_64", [1, 1], 8), (ready["ar1_position_abi"]["data_type"], ready["ar1_position_abi"]["dimensions"], ready["ar1_position_abi"]["bytes"]))
        self.assertFalse(ready["prior_qnn_net_run_int32_boundary_generalized"])
        self.assertTrue(ready["prompt_embedding_byte_equal_to_accepted_input"])
        self.assertTrue(ready["prompt_mask_byte_equal_to_accepted_input"])
        self.assertFalse(ready["combined_shared_context_viability_claim"])
        self.assertFalse(ready["integrated_inference_completed"])
        self.assertFalse(ready["physical_execution"])
        self.assertEqual("transport_lost_before_staging", ready["physical_attempt_outcome"])
        result = json.loads((EXP / ready["evidence"]).read_text())
        self.assertTrue(result["source"]["required_fragments_present"])
        self.assertEqual(0, result["contexts"]["ar171"]["shared_weights_bytes"])
        self.assertEqual(0, result["contexts"]["ar1"]["shared_weights_bytes"])
        self.assertFalse(result["shared_context_assessment"]["combined_context_viability_claim"])
        self.assertEqual(3193053184, result["shared_context_assessment"]["combined_const_bytes"])
        self.assertIn("total emitted tokens", result["integrated_semantics"]["output_cap_semantics"])
        self.assertIn("fsync", result["integrated_semantics"]["output_persistence"])
        self.assertIn("Actual request-start", result["integrated_semantics"]["timing"])
        self.assertIn("not reused or generalized", result["api_type_boundary"]["non_generalization"])
        self.assertIn("No integrated inference ran", result["host_runtime_boundary"])

    def test_qnn_position_preflight_accepts_only_explicit_numeric_contracts(self) -> None:
        tool = EXP / "tools/verify_qnn_position_input.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            numeric_float = root / "positions.f32"
            native_int64 = root / "positions.i64"
            historical_int32 = root / "positions.i32"
            import struct
            numeric_float.write_bytes(struct.pack("<4f", 0.0, 1.0, 2.0, 3.0))
            native_int64.write_bytes(struct.pack("<4q", 0, 1, 2, 3))
            historical_int32.write_bytes(struct.pack("<4i", 0, 1, 2, 3))
            subprocess.run(["python3", str(tool), "--file", str(numeric_float), "--mode", "default-float32", "--start", "0", "--count", "4", "--command", "qnn-net-run --input_list inputs.txt"], check=True, capture_output=True)
            subprocess.run(["python3", str(tool), "--file", str(native_int64), "--mode", "native-int64", "--start", "0", "--count", "4", "--command", "qnn-net-run --use_native_input_files --input_list inputs.txt"], check=True, capture_output=True)
            for command in (
                ["python3", str(tool), "--file", str(historical_int32), "--mode", "default-float32", "--start", "0", "--count", "4", "--command", "qnn-net-run --input_list inputs.txt"],
                ["python3", str(tool), "--file", str(historical_int32), "--mode", "native-int64", "--start", "0", "--count", "4", "--command", "qnn-net-run --use_native_input_files --input_list inputs.txt"],
                ["python3", str(tool), "--file", str(numeric_float), "--mode", "default-float32", "--start", "0", "--count", "4", "--command", "qnn-net-run --use_native_input_files --input_list inputs.txt"],
                ["python3", str(tool), "--file", str(native_int64), "--mode", "native-int64", "--start", "0", "--count", "4", "--command", "qnn-net-run --native_input_tensor_names unrelated_graph unrelated_tensor --input_list inputs.txt"],
                ["python3", str(tool), "--file", str(native_int64), "--mode", "native-int64", "--start", "0", "--count", "4", "--command", "qnn-net-run --native_input_tensor_names graph position_ids --input_list inputs.txt"],
                ["python3", str(tool), "--file", str(native_int64), "--mode", "native-int64", "--start", "0", "--count", "4", "--command", "qnn-net-run --native_input_tensor_names=graph:position_ids --input_list inputs.txt"],
                ["python3", str(tool), "--file", str(native_int64), "--mode", "native-int64", "--start", "0", "--count", "4", "--command", "qnn-net-run --native_input_tensor_names --input_list inputs.txt"],
                ["python3", str(tool), "--file", str(native_int64), "--mode", "native-int64", "--start", "0", "--count", "4", "--command", "qnn-net-run --use_native_input_files --native_input_tensor_names graph position_ids --input_list inputs.txt"],
                ["python3", str(tool), "--file", str(native_int64), "--mode", "native-int64", "--start", "0", "--count", "4", "--command", "qnn-net-run --use_native_input_files=true --input_list inputs.txt"],
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    subprocess.run(command, check=True, capture_output=True)

    def test_qnn_net_run_position_ingestion_is_reclassified(self) -> None:
        audit = self.contract["qnn_net_run_position_ingestion_audit"]
        self.assertFalse(audit["source_verified"])
        self.assertTrue(audit["packaged_source_and_runtime_behavior_consistent"])
        self.assertFalse(audit["binary_source_linkage_cryptographically_proven"])
        self.assertFalse(audit["recorded_commands_set_input_data_type"])
        self.assertFalse(audit["recorded_commands_use_native_input_files"])
        self.assertFalse(audit["recorded_commands_set_native_input_tensor_names"])
        self.assertFalse(audit["sample_app_input_data_type_flag_is_binary_contract"])
        self.assertEqual("QNN_DATATYPE_INT_64", audit["graph_position_data_type"])
        self.assertEqual([0], audit["ar171_position_file"]["converted_unique"])
        self.assertEqual([0], audit["ar1_phase_position_file"]["converted_unique"])
        self.assertFalse(audit["exact_position_semantics_proven"])
        self.assertTrue(audit["physical_htp_execution_still_proven"])
        self.assertFalse(audit["phone_access"])
        self.assertTrue(audit["future_preflight"]["rejects_historical_int32_bit_patterns"])
        self.assertTrue(audit["future_preflight"]["rejects_wrong_native_size"])
        self.assertTrue(audit["future_preflight"]["rejects_mode_flag_mismatch"])
        self.assertTrue(audit["future_preflight"]["integrated_into_future_qnn_net_run_scripts"])
        self.assertFalse(audit["future_preflight"]["targeted_native_input_mode_supported"])
        self.assertTrue(audit["future_preflight"]["rejects_equals_syntax"])
        self.assertTrue(audit["future_preflight"]["rejects_missing_or_conflicting_selectors"])
        result = json.loads((EXP / audit["evidence"]).read_text())
        self.assertTrue(result["interpretation"]["conversion_result_reproduced_from_packaged_source_and_raw_bytes"])
        self.assertFalse(result["interpretation"]["binary_source_linkage_cryptographically_proven"])
        self.assertIn("1368", result["runtime_binary_witness"]["exact_error"])
        self.assertIn("684", result["runtime_binary_witness"]["exact_error"])
        self.assertTrue(result["raw_position_files"]["ar171"]["all_converted_to_zero"])
        self.assertTrue(result["raw_position_files"]["ar1_phase_switch"]["all_converted_to_zero"])
        self.assertFalse(result["recorded_invocations"]["physical_execution_metadata"]["ar171"]["sets_input_data_type"])
        self.assertFalse(result["recorded_invocations"]["physical_execution_metadata"]["ar171"]["sets_native_input_tensor_names"])
        self.assertIn("did not prove rotary positions", result["impact"]["invalidated_claims"][0])
        self.assertIn("physically", result["impact"]["still_valid"][0])

    def test_phone_evidence_guard_handles_transport_unknown(self) -> None:
        completed = subprocess.run(
            ["bash", str(EXP / "tests/test_phone_evidence_guard.sh")],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("fake-ADB checks passed", completed.stdout)

    def test_integrated_phone_attempt_is_transport_only(self) -> None:
        attempt = self.contract["integrated_phone_attempt_1_transport_failure"]
        self.assertTrue(attempt["device_identity_verified"])
        self.assertTrue(attempt["local_elf_preflight"])
        self.assertEqual(13, attempt["local_manifest_entries_verified"])
        for key in ("remote_root_command_dispatched", "stage_push_started", "remote_hash_check_started", "runner_launched", "context_load_started", "graph_execution_started", "output_created", "model_runtime_evidence", "performance_evidence"):
            self.assertFalse(attempt[key])
        self.assertEqual("unknown_unverified_transport_failure", attempt["cleanup_status"])
        self.assertFalse(attempt["raw_cleanup_present_is_correct"])
        self.assertTrue(attempt["phone_lock_released"])
        self.assertTrue(attempt["future_guard"]["cleanup_absence_query_transport_is_unknown"])
        self.assertTrue(attempt["future_guard"]["pid_query_transport_sets_remote_retention_before_exit"])
        self.assertTrue(attempt["future_guard"]["fake_adb_regression"])
        result = json.loads((EXP / attempt["evidence"]).read_text())
        self.assertEqual("unknown_unverified", result["cleanup"]["remote_root_status"])
        self.assertFalse(result["transport_failure"]["remote_mkdir_dispatched"])
        self.assertIn("Transport-preflight failure only", result["claim_boundary"])

    def test_final_pipeline_host_equivalence_is_bounded(self) -> None:
        result = json.loads((EXP / "results/htp-pipeline-host-equivalence/result.json").read_text())
        self.assertIn("host_only", result["classification"])
        self.assertEqual(171, result["canonical_short"]["input_tokens"])
        self.assertEqual(263, result["pipeline"]["parts"])
        self.assertTrue(result["all_five_greedy_tokens_equal"])
        self.assertEqual(5, len(result["comparisons"]))
        self.assertTrue(all(item["all_argmax_equal"] for item in result["comparisons"]))
        output = (EXP / "results/htp-pipeline-host-equivalence/output.txt").read_bytes()
        self.assertEqual(result["output_sha256"], hashlib.sha256(output).hexdigest())

    def test_export_provenance_and_host_output_are_bound(self) -> None:
        provenance = json.loads((EXP / "results/export-provenance/result.json").read_text())
        smoke = json.loads((EXP / "results/host-export-smoke/result.json").read_text())
        self.assertEqual(22, provenance["exported_graph"]["architecture_state_inventory"]["recurrent_conv_layers"])
        self.assertEqual(8, provenance["exported_graph"]["architecture_state_inventory"]["group_query_attention_layers"])
        self.assertEqual(167, provenance["exported_graph"]["architecture_state_inventory"]["matmul_nbits"])
        self.assertEqual("host_only_bounded_export_viability", smoke["classification"])
        output = (EXP / "results/host-export-smoke/output.txt").read_bytes()
        self.assertEqual(smoke["observation"]["output_sha256"], hashlib.sha256(output).hexdigest())
        self.assertEqual({"looks_sensible": True, "issue_notes": None}, smoke["observation"]["output_sanity"])

    def test_manifests_bind_retained_evidence(self) -> None:
        for directory in (
            EXP / "protocol",
            EXP / "results/support-assessment",
            EXP / "results/export-provenance",
            EXP / "results/host-export-smoke",
            EXP / "results/htp-pipeline-host-equivalence",
            EXP / "results/qnn-aot",
            EXP / "results/phone-preparation",
            EXP / "results/phone-attempt-1-provider-selection-failure",
            EXP / "results/phone-attempt-2-npu-context-claim-failure",
            EXP / "results/direct-qnn-host-preparation",
            EXP / "results/direct-qnn-phone-attempt-1-linker-failure",
            EXP / "results/direct-qnn-phone-attempt-2-context-limit",
            EXP / "results/qnn-consolidated-host-preparation",
            EXP / "results/consolidated-qnn-phone-attempt-1-residency-limit",
            EXP / "results/qnn-whole-route-shared-host-preparation",
            EXP / "results/whole-route-shared-qnn-phone-attempt-1-load-failure",
            EXP / "results/qairt-24940-matched-android-preparation",
            EXP / "results/qairt-24940-matched-phone-attempt-1-context-create-failure",
            EXP / "results/qnn-ordinary-monolithic-host-preparation",
            EXP / "results/qnn-ordinary-monolithic-phone-viability-position0",
            EXP / "results/qnn-ordinary-monolithic-host-two-step-state-check",
            EXP / "results/qnn-ordinary-monolithic-phone-two-step-state-check",
            EXP / "results/qnn-ordinary-monolithic-canonical-short-gate-plan",
            EXP / "results/qnn-ordinary-monolithic-phone-canonical-short-max16",
            EXP / "results/qnn-ordinary-monolithic-ar1-profile",
            EXP / "results/qnn-prefill-ar32-ar128-host-probes",
            EXP / "results/qnn-prefill-ar57-ar171-host-probes",
            EXP / "results/qnn-prefill-ar171-phone-runtime-diagnostic",
            EXP / "results/qnn-prefill-ar171-to-ar1-host-bridge",
            EXP / "results/qnn-prefill-ar171-ar1-phase-switch-readiness",
            EXP / "results/qnn-prefill-ar171-ar1-phone-phase-switch-diagnostic",
            EXP / "results/qnn-prefill-ar171-ar1-max16-readiness",
            EXP / "results/qnn-prefill-ar171-ar1-phone-max16-resume",
            EXP / "results/qnn-prefill-ar171-ar1-integrated-readiness",
            EXP / "results/qnn-net-run-position-ingestion-audit",
            EXP / "results/qnn-integrated-phone-attempt-1-transport-before-staging",
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
