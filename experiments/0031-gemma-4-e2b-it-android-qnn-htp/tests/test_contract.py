from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP / "tools"))

from qairt_constant_compat import gemma4_swa_lengths, value_ints_values  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((EXP / "protocol/experiment-contract.json").read_text())
        cls.support = json.loads((EXP / "results/support-assessment/result.json").read_text())

    def test_canonical_contract_and_workloads(self) -> None:
        canonical = self.contract["canonical_protocol"]
        self.assertEqual(canonical["sha256"], sha(REPO / canonical["path"]))
        workload_dir = REPO / "protocols/android-llm-benchmark/workloads/inference-v1"
        expected = {
            "short": "81d23ec04cb821625d3717ab50db7df3d9821a8d2987f1eb107fc90df9d1f2ae",
            "medium": "5e168aa3232f06c92959b686188192471b2d1a62cd1c857a616fd8e29456ddf1",
            "long": "092840fbe879259110fa4d0b15bc383012f16b7b42a38d224b2ead231e86aad8",
        }
        self.assertEqual(expected, canonical["workloads"])
        for tier, digest in expected.items():
            self.assertEqual(digest, sha(workload_dir / f"{tier}.json"))
        self.assertEqual(2048, canonical["max_new_tokens"])
        self.assertEqual(["short", "medium", "long"], canonical["tier_order"])

    def test_installed_sdk_identity_and_gemma_htp_support(self) -> None:
        sdk = self.support["sdk"]
        self.assertTrue(sdk["already_installed"])
        self.assertFalse(sdk["license_acceptance_or_sdk_download_performed"])
        for item in sdk["files"].values():
            path = Path(item["path"])
            self.assertEqual(item["bytes"], path.stat().st_size)
            self.assertEqual(item["sha256"], sha(path))
        support = self.support["support"]
        self.assertTrue(support["release_notes_explicit_gemma4"])
        self.assertEqual("QnnHtp", support["example_backend_type"])
        self.assertEqual(8192, support["example_context_size"])
        self.assertIn("serialized.bin", support["example_context_binaries"][0])
        self.assertTrue(support["sm8550_compile_target_supported_by_installed_api"])

    def test_public_checkpoint_head_and_downloaded_identity(self) -> None:
        head = self.support["public_w4a16_checkpoint"]
        self.assertEqual(200, head["http_status"])
        self.assertEqual(2_013_959_998, head["content_length_bytes"])
        self.assertFalse(head["authentication_used"])
        analysis = json.loads((EXP / "results/checkpoint-analysis/result.json").read_text())
        artifact = analysis["archive"]
        self.assertEqual(head["url"], artifact["url"])
        self.assertEqual(head["content_length_bytes"], artifact["bytes"])
        self.assertEqual("ed45053c8582f2646fb8dd80e0d8f55a462394199160bade96401615b6ce84a7", artifact["sha256"])
        self.assertEqual("passed", artifact["zip_integrity"])
        self.assertTrue(analysis["heavy_ram_lock_held"])
        self.assertTrue(analysis["onnx"]["external_ranges_within_model_data"])
        self.assertEqual(analysis["onnx"]["external_referenced_bytes_sum"], analysis["onnx"]["model_data_bytes"])
        self.assertEqual(analysis["onnx"]["external_max_offset_plus_length"], analysis["onnx"]["model_data_bytes"])

    def test_direct_gguf_shortcut_is_rejected(self) -> None:
        gguf = self.support["direct_gguf_path"]
        self.assertEqual("gemma4", gguf["google_public_gguf_architecture"])
        self.assertFalse(gguf["gemma4_supported"])
        self.assertEqual("rejected", gguf["decision"])
        self.assertNotIn("gemma4", gguf["installed_gguf_builder_supported_model_types"])

    def test_provider_and_fallback_proof_is_fail_closed(self) -> None:
        proof = self.contract["required_provider_proof"]
        self.assertIn("wholly accepted by HTP", proof["partition_boundary"])
        self.assertIn("not QNN/HTP evidence", proof["no_silent_cpu_only"])
        boundaries = self.contract["candidate_route"]["intentional_cpu_boundaries"]
        self.assertIn("greedy sampler and output detokenization", boundaries)
        fatal = " ".join(self.contract["fatal_gates"])
        self.assertIn("physical HTP", fatal)
        self.assertIn("fallback", fatal)

    def test_checkpoint_quantization_and_prompts_are_bound(self) -> None:
        analysis = json.loads((EXP / "results/checkpoint-analysis/result.json").read_text())
        enc = analysis["quantization"]["encodings_summary"]
        self.assertEqual({"4": 522}, enc["param_encodings"]["bitwidth_record_counts"])
        self.assertEqual({"16": 6194}, enc["activation_encodings"]["bitwidth_record_counts"])
        expected = {
            "short": (170, "31a85f9c813266bbbb3505a04a226a9b184882b636cc2f6f67193a6b1eb2ad78"),
            "medium": (594, "a0175c3e00e0a4863171ef8c2ab8f789e033529dd0449f6bd74028dd233ab0aa"),
            "long": (1929, "3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64"),
        }
        for tier, (count, token_hash) in expected.items():
            prompt = analysis["tokenizer_and_template"]["prompt_inventory"][tier]
            self.assertEqual(count, prompt["input_tokens"])
            self.assertEqual(token_hash, prompt["token_ids_int32le_sha256"])
            self.assertEqual(1, prompt["leading_bos_count"])
            self.assertTrue(prompt["fits_context_4096"])

    def test_historical_transform_blocker_and_active_no_execution_claim(self) -> None:
        blocker = json.loads((EXP / "results/transform-blocker/result.json").read_text())
        self.assertEqual(
            "campaign_runner_executable_fixed_reapproval_required",
            self.contract["status"],
        )
        active = self.contract["conversion_blocker"]
        self.assertIn("historical_failure", active)
        self.assertEqual("passed", active["transform_gate"])
        self.assertEqual(
            "passed_host_conversion_recompile_and_four_way_metadata_inspection",
            active["cache_quantization_correction_gate"],
        )
        self.assertEqual(
            "passed_host_dual_conversion_recompile_name_set_and_stage_validation",
            active["position_id_binding_correction_gate"],
        )
        self.assertEqual(
            "passed_host_source_semantics_exact_170_token_identity_and_stage_validation",
            active["automatic_bos_suppression_gate"],
        )
        self.assertEqual(
            "passed_host_shared_engine_keeper_fresh_dialog_isolation_and_stage_validation",
            active["canonical_campaign_harness_gate"],
        )
        self.assertIn("renewed explicit canonical-campaign approval", active["next_gate"])
        self.assertFalse(blocker["android_execution"])
        self.assertFalse(blocker["qnn_htp_execution"])
        self.assertFalse(blocker["compiled_context_created"])
        self.assertFalse(blocker["phone_accessed"])
        self.assertFalse(blocker["public_checkpoint_mutated"])
        probe = blocker["bounded_transform_probe"]
        self.assertFalse(probe["conversion_requested"])
        self.assertFalse(probe["compilation_requested"])
        self.assertEqual("KeyError", probe["exception_type"])
        self.assertIn("ConstantPropagation", probe["failing_stage"])
        self.assertTrue(blocker["identity_after_failure"]["onnx_unchanged"])
        self.assertTrue(blocker["required_user_action_or_decision"])

    def test_retained_evidence_manifests(self) -> None:
        for directory in (
            EXP / "results/support-assessment",
            EXP / "results/checkpoint-analysis",
            EXP / "results/transform-blocker",
            EXP / "results/qairt-2.49.40-capability",
            EXP / "results/qairt-2.49.40-transform-compat",
            EXP / "results/qairt-2.49.40-qnn-conversion",
            EXP / "results/qairt-2.49.40-sm8550-context",
            EXP / "results/qairt-2.49.40-cache-quantization-correction",
            EXP / "results/qairt-2.49.40-position-id-binding-correction",
            EXP / "results/gemma4-sm8550-runtime-bundle",
            EXP / "results/cache-corrected-phone-stage",
            EXP / "results/position-id-corrected-phone-stage",
            EXP / "results/genie-automatic-bos-suppression",
            EXP / "results/canonical-bos-corrected-phone-stage",
            EXP / "results/android-qnn-physical-viability-attempt-01",
            EXP / "results/android-qnn-physical-viability-attempt-02",
            EXP / "results/android-qnn-physical-viability-attempt-03",
            EXP / "results/android-qnn-physical-viability-attempt-04",
            EXP / "results/android-qnn-physical-viability-attempt-05",
            EXP / "results/canonical-campaign-harness-readiness",
            EXP / "results/canonical-campaign-launch-preflight",
        ):
            entries = {}
            for line in (directory / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ", 1)
                entries[name] = digest
            retained = {
                str(path.relative_to(directory))
                for path in directory.rglob("*")
                if path.is_file() and path.name != "SHA256SUMS"
            }
            self.assertEqual(retained, set(entries))
            for name, digest in entries.items():
                self.assertEqual(digest, sha(directory / name))

    def test_constant_value_ints_compatibility_is_narrow_and_schema_faithful(self) -> None:
        convert = lambda attr: attr
        self.assertEqual(
            (-1, 1, 35, 256),
            value_ints_values({"value_ints": [-1, 1, 35, 256]}, convert),
        )
        self.assertIsNone(value_ints_values({"value": object(), "value_ints": [1]}, convert))
        self.assertIsNone(value_ints_values({"value_float": 1.0}, convert))

    def test_gemma4_sliding_window_and_mask_width(self) -> None:
        self.assertEqual((512, 513), gemma4_swa_lengths(1, 4096))
        self.assertEqual((512, 640), gemma4_swa_lengths(128, 4096))
        self.assertEqual((3, 4), gemma4_swa_lengths(1, 4))
        with self.assertRaises(ValueError):
            gemma4_swa_lengths(4, 4)

    def test_positive_transform_is_static_but_not_qnn_or_android(self) -> None:
        result = json.loads(
            (EXP / "results/qairt-2.49.40-transform-compat/result.json").read_text()
        )
        self.assertEqual("positive_host_transform_only_compatibility_result", result["classification"])
        self.assertTrue(result["source_identity_unchanged"])
        self.assertEqual(2, result["transform"]["variant_count"])
        for artifact in result["transform"]["artifacts"]:
            self.assertTrue(artifact["onnx_checker_passed"])
            self.assertTrue(artifact["all_graph_inputs_static"])
            self.assertTrue(artifact["all_graph_outputs_static"])
        self.assertFalse(result["requested"]["qnn_conversion"])
        self.assertFalse(result["requested"]["htp_compilation"])
        self.assertFalse(result["requested"]["phone_access"])
        self.assertFalse(result["requested"]["inference"])

    def test_qnn_conversion_is_bound_but_compile_is_not_claimed(self) -> None:
        result = json.loads(
            (EXP / "results/qairt-2.49.40-qnn-conversion/result.json").read_text()
        )
        self.assertEqual("positive_host_qnn_conversion_result", result["classification"])
        self.assertEqual([1, 128], [item["ar"] for item in result["converted_models"]])
        self.assertTrue(result["quantization"]["overrides_supplied"])
        self.assertEqual([15, 15], result["quantization"]["converter_float_fallback_ops_per_variant"])
        self.assertEqual(15, len(result["quantization"]["ar1_float16_outputs"]))
        self.assertEqual([], result["quantization"]["ar128_float16_outputs"])
        self.assertFalse(result["requested"]["htp_compilation"])
        self.assertFalse(result["requested"]["phone_access"])
        self.assertFalse(result["requested"]["inference"])

    def test_sm8550_context_is_bound_but_physical_execution_is_not_claimed(self) -> None:
        result = json.loads(
            (EXP / "results/qairt-2.49.40-sm8550-context/result.json").read_text()
        )
        self.assertEqual(
            "positive_host_sm8550_htp_context_compile_and_inspection", result["classification"]
        )
        self.assertEqual("weight_sharing", result["compile"]["mode"])
        self.assertEqual("chipset:SM8550", result["compile"]["target"])
        self.assertEqual(6, result["inspection"]["backend_id"])
        self.assertEqual(2, result["inspection"]["num_graphs"])
        self.assertTrue(all(result["inspection"]["embedded_markers"].values()))
        self.assertTrue(result["requested"]["htp_compilation"])
        self.assertFalse(result["requested"]["phone_access"])
        self.assertFalse(result["requested"]["physical_htp_execution"])
        self.assertFalse(result["requested"]["inference"])

    def test_cache_quantization_correction_is_host_only_and_exact(self) -> None:
        result = json.loads(
            (EXP / "results/qairt-2.49.40-cache-quantization-correction/result.json").read_text()
        )
        self.assertEqual(
            "positive_host_cache_quantization_correction_and_sm8550_recompile",
            result["classification"],
        )
        self.assertFalse(result["source_identity"]["checkpoint_modified"])
        self.assertEqual(15, result["correction"]["boundary_count"])
        self.assertEqual({"uFxp_16": 31}, result["correction"]["dlc_output_datatypes"])
        self.assertEqual(2_280_676_608, result["correction"]["dlc_parameters"])
        self.assertEqual(6, result["inspection"]["backend_id"])
        self.assertEqual(2, result["inspection"]["num_graphs"])
        self.assertEqual(15, result["inspection"]["cache_contract_count"])
        self.assertTrue(result["inspection"]["all_cache_contracts_identical"])
        for contract in result["inspection"]["cache_contracts"]:
            self.assertEqual("QNN_DATATYPE_UFIXED_POINT_16", contract["datatype"])
            self.assertEqual(-32768, contract["offset"])
            self.assertTrue(contract["all_four_signatures_identical"])
        self.assertTrue(result["requested"]["qnn_conversion"])
        self.assertTrue(result["requested"]["htp_compilation"])
        self.assertFalse(result["requested"]["phone_access"])
        self.assertFalse(result["requested"]["physical_htp_execution"])
        self.assertFalse(result["requested"]["inference"])

    def test_position_id_binding_correction_is_host_only_and_preserves_cache_contracts(self) -> None:
        result = json.loads(
            (EXP / "results/qairt-2.49.40-position-id-binding-correction/result.json").read_text()
        )
        self.assertEqual(
            "positive_host_position_id_binding_correction_and_sm8550_recompile",
            result["classification"],
        )
        self.assertTrue(result["correction"]["numerically_identity"])
        self.assertFalse(result["correction"]["checkpoint_modified"])
        self.assertEqual(
            {"position_ids_global_cos": "position_ids_cos", "position_ids_global_sin": "position_ids_sin"},
            result["correction"]["renames"],
        )
        self.assertEqual(6, result["inspection"]["backend_id"])
        self.assertEqual(2, result["inspection"]["num_graphs"])
        self.assertEqual(0, result["inspection"]["old_global_positional_input_count"])
        self.assertTrue(result["inspection"]["genie_default_global_inputs_present_in_both_graphs"])
        self.assertTrue(result["inspection"]["all_cache_contracts_still_identical"])
        self.assertTrue(result["config_binding"]["host_name_set_match"])
        self.assertFalse(result["requested"]["phone_access"])
        self.assertFalse(result["requested"]["physical_htp_execution"])
        self.assertFalse(result["requested"]["inference"])

    def test_runtime_bundle_and_luts_are_bound_but_not_staged(self) -> None:
        result = json.loads(
            (EXP / "results/gemma4-sm8550-runtime-bundle/result.json").read_text()
        )
        self.assertEqual("positive_host_runtime_bundle_and_lut_fidelity", result["classification"])
        self.assertEqual("QnnHtp", result["runtime"]["backend"])
        self.assertEqual("greedy", result["runtime"]["sampling"])
        self.assertEqual(2048, result["runtime"]["max_new_tokens"])
        self.assertEqual(-1, result["runtime"]["bos_token_config"])
        self.assertTrue(result["runtime"]["automatic_bos_suppressed"])
        self.assertEqual(
            "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394",
            result["runtime"]["context_sha256"],
        )
        for lut in result["luts"].values():
            self.assertTrue(lut["fidelity"]["within_half_step"])
            self.assertLessEqual(
                lut["fidelity"]["max_abs_error"], lut["fidelity"]["half_step_error_bound"]
            )
        self.assertFalse(result["requested"]["phone_access"])
        self.assertFalse(result["requested"]["physical_htp_execution"])
        self.assertFalse(result["requested"]["inference"])
        extension = result["runtime"]["runtime_files"]["lib/libQnnHtpNetRunExtensions.so"]
        self.assertEqual(1091656, extension["bytes"])
        self.assertEqual(
            "e25a816d008b3d342d1e52eaebef6748194f194aea3154049ab3692004f704ae",
            extension["sha256"],
        )

    def test_first_phone_attempt_is_partial_context_load_not_inference(self) -> None:
        result = json.loads(
            (EXP / "results/android-qnn-physical-viability-attempt-01/result.json").read_text()
        )
        self.assertEqual(
            "physical_qnn_htp_context_load_partial_failure_before_inference",
            result["classification"],
        )
        self.assertTrue(all(result["physical_provider_evidence"].values()))
        self.assertEqual(139, result["outcome"]["exit_code"])
        self.assertEqual("libQnnHtpNetRunExtensions.so", result["outcome"]["missing_library"])
        self.assertFalse(result["outcome"]["graph_execution_observed"])
        self.assertFalse(result["outcome"]["output_created"])
        self.assertEqual(0, result["outcome"]["generated_tokens"])
        self.assertEqual("absent", result["stage"]["remote_cleanup_status"])
        self.assertFalse(result["gate"]["retry_performed"])

    def test_second_phone_attempt_deserialized_context_but_never_executed(self) -> None:
        result = json.loads(
            (EXP / "results/android-qnn-physical-viability-attempt-02/result.json").read_text()
        )
        self.assertEqual(
            "physical_qnn_htp_context_deserialized_model_validation_failure_before_execution",
            result["classification"],
        )
        self.assertTrue(all(result["physical_provider_evidence"].values()))
        self.assertEqual(30, result["outcome"]["validation_error_count"])
        self.assertTrue(all("_value_" in name for name in result["outcome"]["mismatched_tensors"]))
        self.assertFalse(result["outcome"]["graph_execution_observed"])
        self.assertFalse(result["outcome"]["output_created"])
        self.assertEqual(0, result["outcome"]["generated_tokens"])
        self.assertEqual("absent", result["stage"]["remote_cleanup_status"])
        self.assertFalse(result["gate"]["further_retry_performed"])

    def test_genie_automatic_bos_suppression_is_source_proven_host_only(self) -> None:
        result = json.loads(
            (EXP / "results/genie-automatic-bos-suppression/result.json").read_text()
        )
        self.assertEqual(
            "positive_host_genie_automatic_bos_suppression_and_effective_token_proof",
            result["classification"],
        )
        self.assertEqual(2, result["correction"]["bos_token_config_before"])
        self.assertEqual(-1, result["correction"]["bos_token_config_after"])
        self.assertFalse(result["correction"]["canonical_workload_bytes_changed"])
        self.assertTrue(result["correction"]["source_semantics"]["negative_bos_is_sentinel"])
        self.assertTrue(result["correction"]["source_semantics"]["lut_prepends_only_when_bos_nonnegative"])
        self.assertEqual(170, result["effective_short_identity"]["token_count"])
        self.assertEqual(1, result["effective_short_identity"]["leading_bos_count"])
        self.assertTrue(result["effective_short_identity"]["matches_committed_token_ids_byte_for_byte"])
        self.assertFalse(result["requested"]["phone_access"])
        self.assertFalse(result["requested"]["inference"])
        self.assertFalse(result["requested"]["campaign"])

    def test_cache_corrected_phone_stage_is_ready_without_phone_access(self) -> None:
        result = json.loads(
            (EXP / "results/cache-corrected-phone-stage/result.json").read_text()
        )
        self.assertEqual(
            "positive_host_cache_corrected_phone_stage_preparation",
            result["classification"],
        )
        self.assertEqual(
            "a1d52d0087a0719d5907a98d99e8bc5996b699c9cf8f3a21b301588b9f51cc44",
            result["stage"]["corrected_context_sha256"],
        )
        self.assertEqual(16, result["stage"]["viability_output_ceiling_tokens"])
        self.assertFalse(result["stage"]["canonical_campaign"])
        self.assertTrue(result["stage"]["required_runtime_completeness"])
        self.assertTrue(result["stage"]["all_manifest_files_verified"])
        self.assertTrue(result["stage"]["sha256sums_complete_and_verified"])
        self.assertTrue(result["stage"]["permissions_verified"])
        self.assertFalse(result["authorization_boundary"]["adb_used"])
        self.assertFalse(result["authorization_boundary"]["phone_lock_acquired"])
        self.assertFalse(result["authorization_boundary"]["phone_run_authorized_now"])

    def test_third_phone_attempt_clears_cache_validation_then_fails_io_binding(self) -> None:
        result = json.loads(
            (EXP / "results/android-qnn-physical-viability-attempt-03/result.json").read_text()
        )
        self.assertEqual(
            "physical_qnn_htp_context_deserialized_io_tensor_discovery_failure_before_execution",
            result["classification"],
        )
        self.assertTrue(all(result["physical_provider_evidence"].values()))
        self.assertEqual(1, result["outcome"]["exit_code"])
        self.assertEqual(0, result["outcome"]["prior_cache_quantization_validation_error_count"])
        self.assertTrue(result["outcome"]["prior_cache_quantization_blocker_cleared_on_physical_load"])
        self.assertEqual(
            ["position_ids_global_cos", "position_ids_global_sin"],
            result["outcome"]["unconnected_context_inputs"],
        )
        self.assertEqual(
            ["position_ids_cos", "position_ids_sin"],
            result["outcome"]["runtime_requested_missing_inputs"],
        )
        self.assertFalse(result["outcome"]["graph_execution_observed"])
        self.assertFalse(result["outcome"]["output_created"])
        self.assertEqual(0, result["outcome"]["generated_tokens"])
        self.assertIsNone(result["outcome"]["profile_components"])
        self.assertEqual("absent", result["stage"]["remote_cleanup_status"])
        self.assertFalse(result["gate"]["further_retry_performed"])

    def test_position_id_corrected_phone_stage_is_ready_without_phone_access(self) -> None:
        result = json.loads(
            (EXP / "results/position-id-corrected-phone-stage/result.json").read_text()
        )
        self.assertEqual(
            "positive_host_position_id_corrected_phone_stage_preparation",
            result["classification"],
        )
        self.assertEqual(
            "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394",
            result["stage"]["corrected_context_sha256"],
        )
        self.assertTrue(result["stage"]["position_id_binding_corrected"])
        self.assertEqual(16, result["stage"]["viability_output_ceiling_tokens"])
        self.assertTrue(result["stage"]["all_manifest_files_verified"])
        self.assertTrue(result["stage"]["sha256sums_complete_and_verified"])
        self.assertTrue(result["stage"]["permissions_verified"])
        self.assertFalse(result["authorization_boundary"]["adb_used"])
        self.assertFalse(result["authorization_boundary"]["phone_lock_acquired"])
        self.assertFalse(result["authorization_boundary"]["phone_run_authorized_now"])

    def test_fourth_phone_attempt_proves_bounded_htp_inference_but_not_canonical_input(self) -> None:
        result = json.loads(
            (EXP / "results/android-qnn-physical-viability-attempt-04/result.json").read_text()
        )
        self.assertEqual(
            "positive_physical_qnn_htp_bounded_inference_with_effective_prompt_bos_mismatch",
            result["classification"],
        )
        self.assertTrue(all(result["physical_provider_and_execution_evidence"].values()))
        self.assertEqual(17, result["execution"]["successful_qnn_graph_executions"])
        self.assertEqual(2, result["execution"]["successful_ar128_graph_executions"])
        self.assertEqual(15, result["execution"]["successful_ar1_graph_executions"])
        self.assertEqual(0, result["execution"]["qnn_cpu_backend_markers"])
        self.assertEqual(0, result["execution"]["runtime_fallback_markers"])
        self.assertTrue(result["execution"]["physical_htp_transformer_execution_proven"])
        self.assertEqual(170, result["prompt_identity"]["bound_single_bos_token_count"])
        self.assertEqual(171, result["prompt_identity"]["runtime_profile_prompt_tokens"])
        self.assertEqual(1, result["prompt_identity"]["effective_extra_leading_bos_count"])
        self.assertFalse(result["prompt_identity"]["canonical_effective_prompt_identity_passed"])
        self.assertTrue(result["outcome"]["graph_execution_observed"])
        self.assertEqual(16, result["outcome"]["generated_tokens"])
        self.assertEqual("max_tokens", result["outcome"]["stop_reason"])
        self.assertEqual({"looks_sensible": True, "issue_notes": None}, result["outcome"]["output_sanity"])
        self.assertEqual("absent", result["stage"]["remote_cleanup_status"])
        self.assertFalse(result["gate"]["canonical_campaign"])
        self.assertFalse(result["gate"]["further_retry_performed"])

    def test_canonical_bos_corrected_stage_is_ready_without_phone_access(self) -> None:
        result = json.loads(
            (EXP / "results/canonical-bos-corrected-phone-stage/result.json").read_text()
        )
        self.assertEqual(
            "positive_host_canonical_bos_corrected_phone_stage_preparation",
            result["classification"],
        )
        self.assertEqual(-1, result["stage"]["bos_token_config"])
        self.assertTrue(result["stage"]["automatic_bos_suppressed"])
        self.assertEqual(170, result["stage"]["host_effective_short_token_count"])
        self.assertEqual(1, result["stage"]["host_effective_short_leading_bos_count"])
        self.assertTrue(result["stage"]["all_manifest_files_verified"])
        self.assertTrue(result["stage"]["sha256sums_complete_and_verified"])
        self.assertFalse(result["authorization_boundary"]["adb_used"])
        self.assertFalse(result["authorization_boundary"]["phone_lock_acquired"])
        self.assertFalse(result["authorization_boundary"]["phone_run_authorized_now"])

    def test_fifth_phone_attempt_confirms_exact_canonical_effective_input(self) -> None:
        result = json.loads(
            (EXP / "results/android-qnn-physical-viability-attempt-05/result.json").read_text()
        )
        self.assertEqual(
            "positive_physical_qnn_htp_bounded_inference_with_canonical_effective_prompt_identity",
            result["classification"],
        )
        self.assertTrue(all(result["physical_provider_and_execution_evidence"].values()))
        self.assertEqual(17, result["execution"]["successful_qnn_graph_executions"])
        self.assertEqual(2, result["execution"]["successful_ar128_graph_executions"])
        self.assertEqual(15, result["execution"]["successful_ar1_graph_executions"])
        self.assertEqual(0, result["execution"]["qnn_cpu_backend_markers"])
        self.assertEqual(0, result["execution"]["runtime_fallback_markers"])
        self.assertEqual(170, result["prompt_identity"]["runtime_profile_prompt_tokens"])
        self.assertEqual(1, result["prompt_identity"]["runtime_logged_leading_bos_count"])
        self.assertTrue(result["prompt_identity"]["runtime_logged_prefix_matches_bound_tokens"])
        self.assertTrue(result["prompt_identity"]["canonical_effective_prompt_identity_passed"])
        self.assertTrue(result["outcome"]["graph_execution_observed"])
        self.assertEqual(16, result["outcome"]["generated_tokens"])
        self.assertEqual({"looks_sensible": True, "issue_notes": None}, result["outcome"]["output_sanity"])
        self.assertEqual("absent", result["stage"]["remote_cleanup_status"])
        self.assertFalse(result["gate"]["canonical_campaign"])
        self.assertFalse(result["gate"]["further_retry_performed"])

    def test_canonical_campaign_harness_is_host_ready_but_unapproved(self) -> None:
        result = json.loads(
            (EXP / "results/canonical-campaign-harness-readiness/result.json").read_text()
        )
        self.assertEqual(
            "positive_host_canonical_campaign_harness_and_fresh_dialog_isolation_plan",
            result["classification"],
        )
        campaign = result["campaign"]
        self.assertEqual(1, campaign["process_count"])
        self.assertEqual(1, campaign["loaded_engine_count"])
        self.assertTrue(campaign["shared_engine"])
        self.assertTrue(campaign["keeper_dialog_unqueried"])
        self.assertEqual("fresh_dialog_per_logical_request_with_independent_engine_state", campaign["request_isolation"])
        self.assertEqual(16, campaign["request_count"])
        self.assertEqual({"short": 6, "medium": 5, "long": 5}, campaign["tier_counts"])
        self.assertEqual(2048, campaign["max_new_tokens"])
        self.assertEqual(1800, campaign["request_timeout_seconds"])
        self.assertTrue(result["failure_isolation"]["unique_output_per_request"])
        self.assertTrue(result["failure_isolation"]["unique_profile_per_request"])
        self.assertFalse(result["failure_isolation"]["automatic_retry"])
        self.assertTrue(all(result["host_source_proof"].values()))
        self.assertTrue(all(value for key, value in result["runner"].items() if isinstance(value, bool)))
        self.assertFalse(result["requested"]["adb"])
        self.assertFalse(result["requested"]["campaign_execution"])
        self.assertFalse(result["authorization"]["campaign_authorized"])
        runner = EXP / "tools/run_phone_campaign.sh"
        self.assertTrue(runner.stat().st_mode & 0o111)
        self.assertTrue(result["runner"]["runner_executable"])

    def test_campaign_launch_preflight_failed_before_runner_or_phone(self) -> None:
        result = json.loads(
            (EXP / "results/canonical-campaign-launch-preflight/result.json").read_text()
        )
        self.assertEqual(
            "host_campaign_launcher_permission_failure_before_runner_or_phone_access",
            result["classification"],
        )
        self.assertEqual(126, result["outcome"]["launcher_exit_code"])
        self.assertFalse(result["outcome"]["runner_body_entered"])
        self.assertFalse(result["outcome"]["phone_lock_acquired"])
        self.assertFalse(result["outcome"]["adb_used"])
        self.assertFalse(result["outcome"]["remote_root_created"])
        self.assertFalse(result["outcome"]["genie_process_started"])
        self.assertEqual(0, result["outcome"]["logical_requests_started"])
        self.assertFalse(result["outcome"]["automatic_retry_performed"])
        self.assertEqual("100755", result["outcome"]["corrected_mode_after"])

    def test_bounded_phone_gate_script_holds_lock_and_cleans_scope(self) -> None:
        script = (EXP / "tools/run_phone_viability.sh").read_text()
        self.assertIn('artifacts/locks/phone.lock', script)
        self.assertIn('flock -n 9', script)
        self.assertIn('trap cleanup EXIT', script)
        self.assertIn("dialog setMaxNumTokens dialog1 16", (EXP / "tools/prepare_phone_stage.py").read_text())
        self.assertIn("rm -rf '$REMOTE'", script)
        self.assertIn("remote-hash-check.txt", script)
        self.assertIn("libQnnHtpNetRunExtensions.so", script)
        self.assertIn("EXPECTED_CONTEXT_SHA256", script)
        self.assertIn('manifest.get("bos_token_config") != -1', script)
        self.assertIn("7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394", script)
        self.assertIn("stage_completeness_check_passed", (EXP / "tools/prepare_phone_stage.py").read_text())

    def test_phone_and_campaign_are_not_claimed(self) -> None:
        gate = self.contract["campaign_gate"]
        self.assertFalse(self.contract["canonical_campaign_harness_readiness"]["campaign_executed"])
        self.assertFalse(self.contract["canonical_campaign_harness_readiness"]["campaign_authorized"])
        self.assertTrue(gate["bounded_viability_first"])
        self.assertTrue(gate["canonical_after_viability"])
        self.assertIn("no ADB", gate["phone_priority"])


if __name__ == "__main__":
    unittest.main()
