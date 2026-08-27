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
        self.assertIn("active_exact_architecture_aware", self.contract["status"])
        route = self.result["route_assessment"]
        self.assertFalse(route["compiled_sm8550_context_available"])
        self.assertFalse(route["android_execution"])
        self.assertFalse(route["qnn_htp_execution"])
        milestone = self.contract["host_export_milestone"]
        self.assertIn("not_android_qnn_or_htp", milestone["classification"])
        self.assertEqual("passed", milestone["rewritten_onnx"]["onnx_checker"])
        self.assertEqual(16, milestone["bounded_output"]["max_new_tokens"])
        self.assertIn("No ADB", self.contract["phone_boundary"])

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
