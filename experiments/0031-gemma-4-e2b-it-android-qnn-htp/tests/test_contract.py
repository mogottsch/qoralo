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

    def test_public_checkpoint_is_provisional_until_download_hash(self) -> None:
        artifact = self.support["public_w4a16_checkpoint"]
        self.assertEqual(200, artifact["http_status"])
        self.assertEqual(2_013_959_998, artifact["content_length_bytes"])
        self.assertFalse(artifact["authentication_used"])
        self.assertFalse(artifact["downloaded"])
        self.assertIsNone(artifact["sha256"])
        self.assertTrue(artifact["sha256_null_reason"])
        contract_artifact = self.contract["selected_public_checkpoint"]
        self.assertEqual(artifact["url"], contract_artifact["url"])
        self.assertEqual(artifact["content_length_bytes"], contract_artifact["bytes_from_http_head"])

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

    def test_phone_and_campaign_are_not_yet_claimed(self) -> None:
        self.assertIn("awaiting_heavy_lock", self.contract["status"])
        gate = self.contract["campaign_gate"]
        self.assertTrue(gate["bounded_viability_first"])
        self.assertTrue(gate["canonical_after_viability"])
        self.assertIn("no ADB", gate["phone_priority"])


if __name__ == "__main__":
    unittest.main()
