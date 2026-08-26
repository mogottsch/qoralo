import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "experiments/0030-qwen-3.5-2b-android-vulkan-gpu"
SHARED = ROOT / "protocols/android-llm-benchmark"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((EXP / "protocol/experiment-contract.json").read_text())

    def test_canonical_protocol_and_workloads_are_exact(self) -> None:
        canonical = self.contract["canonical_protocol"]
        self.assertEqual("2bb2de193745bc9b74c98639ee077f07615702655b2fc6118185148e2a0c0b46", sha(SHARED / "contract.json"))
        for tier, digest in canonical["workloads"].items():
            self.assertEqual(digest, sha(SHARED / f"workloads/inference-v1/{tier}.json"))
        self.assertEqual(["short", "medium", "long"], canonical["tier_order"])
        self.assertEqual(5, canonical["minimum_loaded_route_requests_per_tier"])
        self.assertEqual("proven_full_in_session_conversation_and_kv_reset", canonical["request_isolation_strategy"])

    def test_model_and_prompt_route_match_pinned_qwen_bytes(self) -> None:
        artifact = self.contract["deployment_artifact"]
        self.assertEqual(1280835840, artifact["bytes"])
        self.assertEqual("aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223", artifact["sha256"])
        self.assertEqual("Q4_K_M", artifact["quantization"]["name"])
        prompts = self.contract["tokenizer_and_template"]["host_prompt_inventory"]
        self.assertEqual({"short": 174, "medium": 597, "long": 1926}, {k: v["input_tokens"] for k, v in prompts.items()})
        self.assertFalse(self.contract["tokenizer_and_template"]["thinking"]["enabled"])

    def test_vulkan_build_is_pinned_and_reproducible(self) -> None:
        runtime = self.contract["runtime"]
        self.assertEqual("GGML Vulkan GPU offload", runtime["provider_backend"])
        self.assertEqual(25, runtime["requested_gpu_layers"])
        self.assertEqual("Vulkan0 / Adreno (TM) 740", runtime["requested_device"])
        self.assertTrue(runtime["android_server"]["clean_rebuilds_byte_identical"])
        self.assertEqual(34242152, runtime["android_server"]["bytes"])
        self.assertEqual("b806fc03df6510eb7a141aea093cec7a878a2aa7456ea076a84791fadec68c00", runtime["android_server"]["sha256"])
        self.assertEqual(["libc.so", "libdl.so", "libm.so", "libvulkan.so"], runtime["dynamic_dependencies"])
        shaders = runtime["shader_sources"]
        manifest = ROOT / shaders["manifest"]
        self.assertEqual(147, shaders["compute_shader_source_count"])
        self.assertEqual(shaders["manifest_sha256"], sha(manifest))
        self.assertEqual(147, len(manifest.read_text().splitlines()))
        build = (EXP / "tools/build_android.sh").read_text()
        for required in (
            "-DGGML_VULKAN=ON", "-DVulkan_GLSLC_EXECUTABLE=", "-DSPIRV-Headers_DIR=",
            "217e93c664ec6704ec2d8c36fa116c1a4a1e2d40", "3617c6a36daa7c2c60dc4e017be821b3e235341b",
            "452a8331070f15d126df5e263fb9f04e78240dac5f1defe6c434b2c2eef0a53a",
            "b806fc03df6510eb7a141aea093cec7a878a2aa7456ea076a84791fadec68c00",
            "flock -w 1800", "LLAMA_BUILD_UI=OFF", "LLAMA_USE_PREBUILT_UI=OFF",
        ):
            self.assertIn(required, build)

    def test_phone_runner_is_scoped_and_requests_exact_offload(self) -> None:
        runner = (EXP / "tools/run_phone.sh").read_text()
        self.assertIn("flock -n 9", runner)
        self.assertIn("/data/local/tmp/vibevoice-0030-qwen-3.5-2b-android-vulkan-gpu", runner)
        self.assertIn("--device Vulkan0 --gpu-layers 25 --split-mode none --main-gpu 0", runner)
        self.assertIn("--backend-proof-log", runner)
        self.assertNotIn("/sdcard", runner)
        client = (EXP / "tools/run_client.py").read_text()
        self.assertIn("offloaded 25/25 layers to GPU", client)
        self.assertIn("Vulkan0 model buffer size", client)
        self.assertIn("Vulkan0 compute buffer size", client)
        self.assertIn("Adreno \\(TM\\) 740", client)
        self.assertIn("POST /slots/0?action=erase", client)
        self.assertIn('server_timings.get("cache_n") != 0', client)
        self.assertEqual(1, len(re.findall(r'\[\("first-short-01", "short", "first", 2048\)\]', client)))
        self.assertIn('range(1, 6)', client)

    def test_gpu_claim_is_bounded_not_exclusive(self) -> None:
        rationale = self.contract["route_rationale"]
        self.assertIn("all 25/25", rationale["offload_claim_boundary"])
        self.assertIn("CPU retains", rationale["offload_claim_boundary"])
        self.assertIn("not GPU-exclusive", rationale["offload_claim_boundary"])
        fatal = "\n".join(self.contract["fatal_gates"])
        self.assertIn("CPU-only fallback", fatal)
        self.assertIn("Vulkan model buffer", fatal)
        self.assertIn("Vulkan compute buffer", fatal)


if __name__ == "__main__":
    unittest.main()
