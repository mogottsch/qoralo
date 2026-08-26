from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


EXP = Path(__file__).resolve().parents[1]
SMOKE = EXP / "results/android-smoke"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AndroidSmokeEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.result = json.loads((SMOKE / "result.json").read_text())
        self.contract = json.loads((EXP / "protocol/experiment-contract.json").read_text())

    def test_is_bounded_android_evidence_not_a_campaign(self) -> None:
        self.assertTrue(self.result["android_execution_evidence"])
        self.assertFalse(self.result["canonical_campaign"])
        self.assertFalse(self.result["failed_pre_inference_attempt_counted"])
        self.assertEqual(64, self.result["request"]["max_new_tokens"])
        self.assertEqual(64, self.result["generation"]["actual_output_tokens"])
        self.assertEqual("max_tokens", self.result["generation"]["stop_reason"])
        self.assertIn("loaded-route", self.result["canonical_campaign_exclusion_reason"])

    def test_exact_artifacts_workload_and_output_are_bound(self) -> None:
        model = self.result["model_artifact"]
        runtime = self.result["runtime"]
        request = self.result["request"]
        contract_prompt = self.contract["tokenizer_and_template"]["prompt_inventory"]["short"]
        self.assertEqual(self.contract["deployment_artifact"]["sha256"], model["sha256"])
        self.assertEqual(self.contract["runtime"]["android_build"]["binary_sha256"], runtime["binary_sha256"])
        self.assertEqual(171, request["input_tokens"])
        self.assertEqual(contract_prompt["rendered_sha256"], request["rendered_prompt_sha256"])
        self.assertEqual(contract_prompt["token_ids_int32le_sha256"], request["token_ids_int32le_sha256"])
        output = SMOKE / self.result["generation"]["raw_output_path"]
        self.assertEqual(self.result["generation"]["raw_output_bytes"], output.stat().st_size)
        self.assertEqual(self.result["generation"]["raw_output_sha256"], sha(output))

    def test_safety_cleanup_and_memory_evidence(self) -> None:
        evidence = self.result["evidence"]
        self.assertTrue(evidence["phone_lock_held"])
        self.assertTrue(evidence["local_hash_diff_empty"])
        self.assertTrue(evidence["remote_hash_diff_empty"])
        self.assertEqual(0, evidence["process_exit_code"])
        self.assertEqual("verified_absent", evidence["cleanup_state"])
        self.assertEqual(85, self.result["memory"]["sample_count"])
        self.assertGreater(self.result["memory"]["peak_sampled_pss_kib"], 1_800_000)
        self.assertEqual(evidence["memory_samples_sha256"], sha(SMOKE / "memory-samples.txt"))

    def test_nullable_timings_and_output_sanity(self) -> None:
        timing = self.result["timing"]
        self.assertIsNone(timing["setup_seconds"])
        self.assertTrue(timing["setup_seconds_null_reason"])
        self.assertIsNone(timing["request_to_first_token_seconds"])
        self.assertTrue(timing["request_to_first_token_null_reason"])
        self.assertEqual(
            {"looks_sensible": True, "issue_notes": None},
            self.result["generation"]["output_sanity"],
        )

    def test_warm_conditions_are_retained(self) -> None:
        operating = self.result["operating_context"]
        self.assertEqual(2, operating["before"]["thermal"]["status"])
        self.assertEqual(47.6, operating["before"]["thermal"]["ap_c"])
        self.assertEqual(41.4, operating["before"]["thermal"]["skin_c"])
        self.assertEqual(60.5, operating["after"]["thermal"]["ap_c"])
        self.assertIsNone(operating["power_measurement"])
        self.assertTrue(operating["power_measurement_null_reason"])

    def test_evidence_manifests_bind_all_retained_files(self) -> None:
        for directory in (
            SMOKE,
            EXP / "results/android-smoke-cooldown",
            EXP / "results/android-smoke-pre-inference-transport-failure",
        ):
            entries = {}
            for line in (directory / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ", 1)
                entries[name] = digest
            retained = {path.name for path in directory.iterdir() if path.is_file() and path.name != "SHA256SUMS"}
            self.assertEqual(retained, set(entries))
            for name, digest in entries.items():
                self.assertEqual(digest, sha(directory / name))

    def test_cooldown_and_failed_attempt_are_separate(self) -> None:
        cooldown = json.loads((EXP / "results/android-smoke-cooldown/result.json").read_text())
        failed = json.loads((EXP / "results/android-smoke-pre-inference-transport-failure/result.json").read_text())
        self.assertTrue(cooldown["phone_lock_held"])
        self.assertTrue(cooldown["duration_bounded"])
        self.assertFalse(cooldown["temperature_pass_fail_gate_applied"])
        self.assertEqual(5, len(cooldown["samples"]))
        self.assertFalse(failed["android_inference_started"])
        self.assertFalse(failed["counted_as_smoke"])
        self.assertEqual(0, failed["remote_sha256_bytes"])
        self.assertEqual("verified_absent", failed["cleanup_state"])


if __name__ == "__main__":
    unittest.main()
