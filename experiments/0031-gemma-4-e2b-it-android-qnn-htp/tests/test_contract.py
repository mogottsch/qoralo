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
        self.assertEqual("ready_for_phone_viability_waiting_priority", self.contract["status"])
        active = self.contract["conversion_blocker"]
        self.assertIn("historical_failure", active)
        self.assertEqual("passed", active["transform_gate"])
        self.assertIn("phone.lock", active["next_gate"])
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
            EXP / "results/gemma4-sm8550-runtime-bundle",
        ):
            entries = {}
            for line in (directory / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ", 1)
                entries[name] = digest
            retained = {path.name for path in directory.iterdir() if path.is_file() and path.name != "SHA256SUMS"}
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

    def test_runtime_bundle_and_luts_are_bound_but_not_staged(self) -> None:
        result = json.loads(
            (EXP / "results/gemma4-sm8550-runtime-bundle/result.json").read_text()
        )
        self.assertEqual("positive_host_runtime_bundle_and_lut_fidelity", result["classification"])
        self.assertEqual("QnnHtp", result["runtime"]["backend"])
        self.assertEqual("greedy", result["runtime"]["sampling"])
        self.assertEqual(2048, result["runtime"]["max_new_tokens"])
        for lut in result["luts"].values():
            self.assertTrue(lut["fidelity"]["within_half_step"])
            self.assertLessEqual(
                lut["fidelity"]["max_abs_error"], lut["fidelity"]["half_step_error_bound"]
            )
        self.assertFalse(result["requested"]["phone_access"])
        self.assertFalse(result["requested"]["physical_htp_execution"])
        self.assertFalse(result["requested"]["inference"])

    def test_bounded_phone_gate_script_holds_lock_and_cleans_scope(self) -> None:
        script = (EXP / "tools/run_phone_viability.sh").read_text()
        self.assertIn('artifacts/locks/phone.lock', script)
        self.assertIn('flock -n 9', script)
        self.assertIn('trap cleanup EXIT', script)
        self.assertIn("dialog setMaxNumTokens dialog1 16", (EXP / "tools/prepare_phone_stage.py").read_text())
        self.assertIn("rm -rf '$REMOTE'", script)
        self.assertIn("remote-hash-check.txt", script)

    def test_phone_and_campaign_are_not_claimed(self) -> None:
        gate = self.contract["campaign_gate"]
        self.assertTrue(gate["bounded_viability_first"])
        self.assertTrue(gate["canonical_after_viability"])
        self.assertIn("no ADB", gate["phone_priority"])


if __name__ == "__main__":
    unittest.main()
