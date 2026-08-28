from __future__ import annotations

import hashlib
import json
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
        self.assertIn("physical_direct_qnn_htp_canonical_short_max16_output_sanity_passed", self.contract["status"])
        route = self.result["route_assessment"]
        self.assertFalse(route["compiled_sm8550_context_available"])
        self.assertFalse(route["android_execution"])
        self.assertFalse(route["qnn_htp_execution"])
        milestone = self.contract["host_export_milestone"]
        self.assertIn("not_android_qnn_or_htp", milestone["classification"])
        self.assertEqual("passed", milestone["rewritten_onnx"]["onnx_checker"])
        self.assertEqual(16, milestone["bounded_output"]["max_new_tokens"])
        self.assertIn("Canonical-short max16 gate cleaned absent", self.contract["phone_boundary"])

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
