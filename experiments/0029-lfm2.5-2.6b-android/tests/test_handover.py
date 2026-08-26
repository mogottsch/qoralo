from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parents[1]
WORKLOADS = ROOT / "protocols/android-llm-benchmark/workloads/inference-v1"

spec = importlib.util.spec_from_file_location("render_workloads", EXP / "tools/render_workloads.py")
assert spec and spec.loader
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HandoverEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads((EXP / "protocol/experiment-contract.json").read_text())

    def test_renderer_reproduces_retained_prompts(self) -> None:
        inventory = self.contract["tokenizer_and_template"]["prompt_inventory"]
        for tier in ("short", "medium", "long"):
            workload = json.loads((WORKLOADS / f"{tier}.json").read_bytes())
            expected = EXP / "results/host-smoke/rendered" / f"{tier}.txt"
            self.assertEqual(expected.read_bytes(), renderer.render(workload["messages"]))
            self.assertEqual(inventory[tier]["rendered_bytes"], expected.stat().st_size)
            self.assertEqual(inventory[tier]["rendered_sha256"], sha(expected))

    def test_template_and_gguf_metadata_are_hash_bound(self) -> None:
        template = EXP / "protocol/chat_template.jinja"
        tokenizer = self.contract["tokenizer_and_template"]
        self.assertEqual(tokenizer["embedded_chat_template_bytes"], template.stat().st_size)
        self.assertEqual(tokenizer["embedded_chat_template_sha256"], sha(template))
        metadata = json.loads((EXP / "protocol/gguf-metadata.json").read_text())
        self.assertEqual("Ab00687315Bc1298E9D54E9C4B611Dde9867Ccc2", metadata["general.name"])
        self.assertEqual(15, metadata["general.file_type"])
        self.assertEqual(2, metadata["general.quantization_version"])
        self.assertEqual({"F32": 99, "Q4_K": 148, "Q6_K": 19}, metadata["tensor_type_counts"])

    def test_protocol_v2_loaded_route_semantics(self) -> None:
        protocol = self.contract["canonical_protocol"]
        self.assertEqual(2, protocol["schema_version"])
        self.assertEqual(
            "2bb2de193745bc9b74c98639ee077f07615702655b2fc6118185148e2a0c0b46",
            protocol["sha256"],
        )
        self.assertEqual(5, protocol["minimum_loaded_route_requests_per_tier"])
        self.assertTrue(protocol["loaded_model_runtime_route_reused"])
        self.assertFalse(protocol["model_remap_or_reload_between_requests"])
        self.assertFalse(protocol["accelerator_recompilation_between_requests"])
        self.assertFalse(protocol["retained_prompt_or_kv_reuse_between_requests"])
        self.assertIsNone(protocol["request_isolation_strategy"])
        self.assertIn("viability smoke only", self.contract["runtime"]["binary_scope"])

    def test_prompt_token_inventory_and_context_capacity(self) -> None:
        inventory = self.contract["tokenizer_and_template"]["prompt_inventory"]
        expected = {
            "short": (171, "eae8e828110f634d5c9954df0372e869f67f67aed846f9f544781faa1d4d29bc"),
            "medium": (600, "bfd8e9ee4fecef5b3203ad67ee0c2fe1a5a4d3267cfabc83c4388f04e25789e9"),
            "long": (1922, "bf6cd4a807f1933a4890a52fc847242be44c45cfc712bc9767ed8030845ec512"),
        }
        for tier, (count, token_hash) in expected.items():
            self.assertEqual(count, inventory[tier]["input_tokens"])
            self.assertEqual(token_hash, inventory[tier]["token_ids_int32le_sha256"])
            proof = self.contract["context_capacity"]["proof"][tier]
            self.assertEqual(count + 2048, proof["input_plus_ceiling"])
            self.assertLessEqual(proof["input_plus_ceiling"], 8192)
            self.assertTrue(proof["fits"])

    def test_reconstruction_cross_check_is_host_only_and_exact(self) -> None:
        result = json.loads((EXP / "results/reconstruction-check/result.json").read_text())
        self.assertFalse(result["android_evidence"])
        self.assertFalse(result["phone_accessed"])
        self.assertEqual(0, result["exit_code"])
        self.assertTrue(result["matches_retained_host_smoke_output"])
        self.assertEqual(
            result["output_sha256"],
            sha(EXP / "results/reconstruction-check/output.txt"),
        )
        inventory = json.loads((EXP / "results/reconstruction-check/prompt-inventory.json").read_text())
        for tier, observed in inventory.items():
            expected = self.contract["tokenizer_and_template"]["prompt_inventory"][tier]
            self.assertEqual(expected["input_tokens"], observed["input_tokens"])
            self.assertEqual(expected["token_ids_int32le_sha256"], observed["token_ids_int32le_sha256"])

    def test_android_build_manifest_and_bound_binary(self) -> None:
        manifest = json.loads((EXP / "results/android-build/manifest.json").read_text())
        binary = manifest["binary"]
        contract_binary = self.contract["runtime"]["android_build"]
        self.assertFalse(manifest["android_execution_evidence"])
        self.assertFalse(manifest["phone_accessed"])
        self.assertEqual(5074184, binary["bytes"])
        self.assertEqual(
            "88a91aba5511a712f45aca21c566275681de30e2161f10bb99f9ac54f45b979e",
            binary["sha256"],
        )
        self.assertEqual(binary["bytes"], contract_binary["binary_bytes"])
        self.assertEqual(binary["sha256"], contract_binary["binary_sha256"])
        self.assertEqual(["libm.so", "libdl.so", "libc.so"], binary["dynamic_dependencies"])
        local_binary = EXP / ".local/android-stage/llama-completion"
        if local_binary.exists():
            self.assertEqual(binary["bytes"], local_binary.stat().st_size)
            self.assertEqual(binary["sha256"], sha(local_binary))

    def test_android_build_and_phone_tools_fail_closed(self) -> None:
        build = (EXP / "tools/build_llama_cpp.sh").read_text()
        self.assertIn("5c0d18881e0e9794c96b2602736b758bac9d9388", build)
        self.assertIn("28.1.13356709", build)
        self.assertIn("-DANDROID_PLATFORM=android-31", build)
        self.assertIn("-DANDROID_STL=c++_static", build)
        phone = (EXP / "tools/run_phone_smoke.sh").read_text()
        self.assertIn("PHONE_RUN_APPROVED", phone)
        self.assertIn("artifacts/locks/phone.lock", phone)
        self.assertIn("SM-S918B", phone)
        self.assertIn("SM8550", phone)
        self.assertIn("vibevoice-0029-lfm2.5-2.6b-android", phone)

    def test_host_output_is_hash_bound_and_host_only(self) -> None:
        result = json.loads((EXP / "results/host-smoke/result.json").read_text())
        self.assertFalse(result["android_evidence"])
        self.assertEqual(171, result["prompt"]["input_tokens"])
        self.assertEqual(
            result["generation"]["output_sha256"],
            sha(EXP / "results/host-smoke/output.txt"),
        )
        self.assertEqual(64, result["generation"]["ceiling_tokens"])

    def test_pinned_model_identity(self) -> None:
        result = json.loads((EXP / "results/host-smoke/result.json").read_text())
        artifact = result["model_artifact"]
        self.assertEqual(1674455040, artifact["bytes"])
        self.assertEqual(
            "02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed",
            artifact["sha256"],
        )
        self.assertEqual(
            "5c0d18881e0e9794c96b2602736b758bac9d9388",
            result["runtime"]["revision"],
        )
        self.assertEqual(
            "ab00687315bc1298e9d54e9c4b611dde9867ccc2",
            self.contract["upstream_model"]["revision"],
        )
        self.assertEqual(
            self.contract["upstream_model"]["license_sha256"],
            sha(EXP / "protocol/upstream-LICENSE"),
        )


if __name__ == "__main__":
    unittest.main()
