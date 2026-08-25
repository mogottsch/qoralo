#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads((EXP / "protocol/experiment-contract.json").read_text())
        cls.host = json.loads((EXP / "results/host-smoke/result.json").read_text())

    def test_canonical_contract_and_workloads_are_exact(self) -> None:
        canonical = self.contract["canonical_protocol"]
        self.assertEqual(canonical["sha256"], sha(ROOT / canonical["path"]))
        for tier, expected in canonical["workloads"].items():
            path = ROOT / "protocols/android-llm-benchmark/workloads/inference-v1" / f"{tier}.json"
            self.assertEqual(expected, sha(path))
            workload = json.loads(path.read_text())
            self.assertEqual(2048, workload["generation"]["max_new_tokens"])
            self.assertFalse(workload["generation"]["do_sample"])

    def test_route_is_explicitly_third_party_cpu_and_nonthinking(self) -> None:
        artifact = self.contract["deployment_artifact"]
        self.assertFalse(artifact["official_qwen_artifact"])
        self.assertIn("third-party", artifact["source_kind"])
        self.assertIsNone(artifact["quantization"]["conversion_tool_revision"])
        self.assertTrue(artifact["quantization"]["conversion_tool_revision_missing_reason"])
        self.assertFalse(self.contract["tokenizer_and_template"]["thinking"]["enabled"])
        self.assertEqual("GGML CPU", self.contract["runtime"]["provider_backend"])
        self.assertFalse(self.contract["route_rationale"]["official_litert_lm_support_check"]["qwen35_2b_listed"])

    def test_host_prompt_inventory_is_hash_bound_and_fits(self) -> None:
        for tier, prompt in self.host["prompts"].items():
            rendered = EXP / "results/host-smoke" / prompt["rendered_path"]
            self.assertEqual(prompt["rendered_sha256"], sha(rendered))
            self.assertTrue(rendered.read_bytes().endswith(b"<think>\n\n</think>\n\n"))
            self.assertLessEqual(prompt["input_tokens"] + 2048, prompt["context_tokens"])
            locked = self.contract["tokenizer_and_template"]["host_prompt_inventory"][tier]
            self.assertEqual(locked["rendered_sha256"], prompt["rendered_sha256"])
            self.assertEqual(locked["token_ids_int32le_sha256"], prompt["token_ids_int32le_sha256"])

    def test_host_output_hash_and_sanity(self) -> None:
        self.assertFalse(self.host["host_is_android_evidence"])
        self.assertEqual(1, len(self.host["runs"]))
        run = self.host["runs"][0]
        output = EXP / "results/host-smoke" / run["output_path"]
        self.assertEqual(run["output_sha256"], sha(output))
        self.assertEqual({"looks_sensible": True, "issue_notes": None}, run["output_sanity"])
        self.assertEqual(64, run["output_tokens"])
        self.assertEqual("max_tokens", run["stop_reason"])
        self.assertEqual(0, run["server_timings"]["cache_n"])
        self.assertFalse(run["final_event"]["truncated"])

    def test_phone_scripts_encode_safety_and_campaign_shape(self) -> None:
        phone = (EXP / "tools/run_phone.sh").read_text()
        client = (EXP / "tools/run_client.py").read_text()
        self.assertIn('flock -n 9', phone)
        self.assertIn('exec 9>&-', phone)
        self.assertIn('/data/local/tmp/vibevoice-0027-qwen-3.5-2b-android', phone)
        self.assertIn('SM-S918B', phone)
        self.assertIn('SM8550', phone)
        self.assertIn('--reasoning off', phone)
        self.assertIn('/slots/0?action=erase', client)
        self.assertIn('"cache_prompt": False', client)
        self.assertIn('server_timings.get("cache_n") != 0', client)
        self.assertIn('server_timings.get("prompt_n") != len(token_ids)', client)
        self.assertIn('prompt_ms <= 0', client)
        self.assertIn('range(1, 6)', client)
        self.assertIn('fsync', client)

    def test_android_smoke_is_hash_bound_and_cleaned(self) -> None:
        path = EXP / "results/android-smoke/result.json"
        if not path.exists():
            self.skipTest("Android smoke has not run yet")
        result = json.loads(path.read_text())
        self.assertEqual("android_smoke", result["scope"])
        self.assertEqual("SM-S918B", result["device"]["model"])
        self.assertEqual("SM8550", result["device"]["soc"])
        self.assertTrue(result["stage_and_cleanup"]["local_remote_hashes_equal"])
        self.assertEqual("verified_absent", result["stage_and_cleanup"]["cleanup_state"])
        self.assertEqual(1, len(result["runs"]))
        run = result["runs"][0]
        output = EXP / "results/android-smoke" / run["output_path"]
        self.assertEqual(run["output_sha256"], sha(output))
        self.assertEqual({"looks_sensible": True, "issue_notes": None}, run["output_sanity"])
        self.assertEqual(0, run["server_timings"]["cache_n"])
        self.assertEqual(174, run["server_timings"]["prompt_n"])
        self.assertGreater(run["server_timings"]["prompt_ms"], 0)
        self.assertFalse(run["final_event"]["truncated"])


if __name__ == "__main__":
    unittest.main()
