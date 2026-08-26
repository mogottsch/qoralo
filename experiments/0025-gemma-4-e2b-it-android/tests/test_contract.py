#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parents[1]
CONTRACT = json.loads((EXP / "protocol/experiment-contract.json").read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ContractTest(unittest.TestCase):
    def test_canonical_protocol_and_workloads_are_exact(self) -> None:
        protocol = CONTRACT["canonical_protocol"]
        self.assertEqual(protocol["sha256"], sha256(ROOT / protocol["path"]))
        for tier, expected in protocol["workloads"].items():
            path = ROOT / f"protocols/android-llm-benchmark/workloads/inference-v1/{tier}.json"
            self.assertEqual(expected, sha256(path))
        self.assertEqual(2048, protocol["max_output_tokens"])
        self.assertEqual(1, protocol["first_request"]["count"])
        self.assertEqual(5, protocol["loaded_route_requests_per_tier"])
        self.assertTrue(protocol["loaded_engine_reused"])
        self.assertFalse(protocol["session_object_reused"])
        self.assertEqual("fresh_session_per_logical_request", protocol["request_isolation_strategy"])
        self.assertFalse(protocol["session_creation_in_total_request"])

    def test_runner_source_is_frozen(self) -> None:
        runner = CONTRACT["runtime"]["android_runner"]
        self.assertEqual(runner["source_sha256"], sha256(ROOT / runner["source"]))

    def test_runner_recreates_session_without_reloading_engine(self) -> None:
        source = (EXP / "tools/litert_lm_canonical_runner.cc").read_text()
        campaign_start = source.index('canonical campaign requires fresh_session')
        campaign = source[
            campaign_start:source.index("  Json result = {", campaign_start)
        ]
        self.assertIn("session.reset();", campaign)
        self.assertIn("engine->CreateSession(session_config)", campaign)
        self.assertNotIn("EngineFactory::CreateDefault", campaign)
        self.assertNotIn("ModelAssets::Create", campaign)
        self.assertIn('"session_recreation_in_total_request"] = false', source)
        self.assertIn('"fresh_session_per_logical_request"', campaign)

    def test_gpu_claim_fails_closed_without_provider_binding(self) -> None:
        source = (EXP / "tools/litert_lm_canonical_runner.cc").read_text()
        self.assertIn('"litert_hardware_accelerators", "kGpu only (no CPU fallback bit)"', source)
        self.assertIn('"binding_proven"', source)
        self.assertIn("GPU provider binding was not proven", source)
        self.assertIn("libLiteRtGpuAccelerator.so", source)
        self.assertIn("libOpenCL", source)

    def test_only_cpu_and_gpu_arms_are_in_scope(self) -> None:
        scope = CONTRACT["scope"]
        self.assertEqual(2, len(scope["arms"]))
        self.assertTrue(any("CPU" in arm for arm in scope["arms"]))
        self.assertTrue(any("GPU" in arm for arm in scope["arms"]))
        self.assertTrue(any("NPU" in item for item in scope["excluded"]))

    def test_sampler_adapter_is_exact_greedy_equivalent(self) -> None:
        route = CONTRACT["route"]
        self.assertIn("k=1", route["sampler_configuration"])
        self.assertIn("returns the single top-k token ID directly", route["greedy_equivalence_proof"]["behavior"])
        self.assertFalse(route["thinking_enabled"])
        self.assertFalse(route["speculative_decoding_enabled"])

    def test_optional_runtime_turns_are_not_fatal(self) -> None:
        nullable = " ".join(CONTRACT["nullable_not_fatal"])
        self.assertIn("BenchmarkInfo", nullable)
        fatal = " ".join(CONTRACT["fatal_gates"])
        self.assertNotIn("BenchmarkInfo", fatal)
        self.assertTrue(CONTRACT["timing_and_evidence"]["raw_first"])


if __name__ == "__main__":
    unittest.main()
