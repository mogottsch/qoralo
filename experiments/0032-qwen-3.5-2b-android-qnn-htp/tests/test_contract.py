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

    def test_negative_result_never_claims_execution(self) -> None:
        self.assertIn("blocked_no_public_qnn", self.contract["status"])
        assessment = self.result["route_assessment"]
        self.assertFalse(assessment["android_execution"])
        self.assertFalse(assessment["qnn_htp_execution"])
        self.assertTrue(self.result["required_user_action_or_decision"])
        self.assertIn("No ADB", self.contract["phone_boundary"])

    def test_manifests_bind_retained_evidence(self) -> None:
        for directory in (EXP / "protocol", EXP / "results/support-assessment"):
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
