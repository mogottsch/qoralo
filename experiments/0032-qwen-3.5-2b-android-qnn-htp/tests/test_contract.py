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
        cls.structural = json.loads(
            (EXP / "results/executorch-qnn-structural-probe/result.json").read_text()
        )
        cls.exact_compile = json.loads(
            (EXP / "results/executorch-qnn-exact-host-compile/compile-result.json").read_text()
        )
        cls.eager = json.loads(
            (EXP / "results/executorch-qnn-exact-host-compile/eager-equivalence.json").read_text()
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

    def test_active_route_does_not_claim_physical_execution(self) -> None:
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
        self.assertFalse(route["android_execution"])
        self.assertFalse(route["physical_qnn_htp_execution"])

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
        self.assertFalse(self.contract["executorch_qnn_route"]["android_execution"])
        self.assertIn("not run on Android", " ".join(result["claim_limits"]))

    def test_manifests_bind_retained_evidence(self) -> None:
        for directory in (
            EXP / "protocol",
            EXP / "results/support-assessment",
            EXP / "results/executorch-qnn-structural-probe",
            EXP / "results/executorch-qnn-exact-host-compile",
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
