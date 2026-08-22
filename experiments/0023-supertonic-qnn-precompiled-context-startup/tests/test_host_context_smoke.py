import hashlib
import json
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((EXP / "protocol/experiment-contract.json").read_text())
RESULT_PATH = EXP / "results/host-context-smoke/host-context-functional-smoke.json"
RESULT = json.loads(RESULT_PATH.read_text())
CLEAN_PATH = EXP / "results/clean-host-setup/clean-setup-result.json"
CLEAN = json.loads(CLEAN_PATH.read_text())
TRANSCRIPT_SHA = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
EXPECTED_GRAPHS = {
    "duration": "8a1875ef0f6960ca16fc06814509b1c3258e8f50b04a5d590d3ab6db8c775016",
    "text": "769fd1d257674e8624bdea941f7a903d9460051f9845b604cd2c2980f281a8c3",
    "vector": "f2318c54726a034dcc89aa9818a91f1c3db0e3067b9932c7c2dae65957897c7b",
    "vocoder": "35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7",
}


class HostContextSmokeTest(unittest.TestCase):
    def test_legacy_transcript_is_exact(self):
        payload = (EXP / "protocol/transcript.txt").read_bytes()
        self.assertEqual(len(payload), 230)
        self.assertFalse(payload.endswith(b"\n"))
        self.assertEqual(hashlib.sha256(payload).hexdigest(), TRANSCRIPT_SHA)
        self.assertEqual(RESULT["input"]["transcript"]["sha256"], TRANSCRIPT_SHA)

    def test_scope_is_pragmatic_0011_route(self):
        self.assertIn("experiment 0011", CONTRACT["scope"]["baseline_route"])
        self.assertEqual(CONTRACT["scope"]["latent_length"], 238)
        self.assertEqual(CONTRACT["scope"]["trimmed_samples"], 729746)
        self.assertEqual(CONTRACT["runtime"]["session.disable_cpu_ep_fallback"], "1")
        self.assertEqual(CONTRACT["minimum_measurements"]["fresh_process_cold_setup_runs_per_arm"], 3)

    def test_all_four_components_pass_functionally(self):
        self.assertEqual(set(RESULT["components"]), set(EXPECTED_GRAPHS))
        self.assertTrue(RESULT["aggregate"]["all_functional_checks_passed"])
        self.assertTrue(RESULT["aggregate"]["all_ort_node_events_qnn_only"])
        self.assertEqual(RESULT["aggregate"]["components"], 4)
        for name, component in RESULT["components"].items():
            self.assertEqual(component["source_graph"]["sha256"], EXPECTED_GRAPHS[name])
            self.assertTrue(all(component["functional_checks"].values()))
            self.assertTrue(component["profiles"]["generation_ort"]["qnn_only_nodes"])
            self.assertTrue(component["profiles"]["reload_ort"]["qnn_only_nodes"])
            self.assertTrue(component["profiles"]["generation_qnn"]["has_accelerator_execute_cycles"])
            self.assertTrue(component["profiles"]["reload_qnn"]["has_accelerator_execute_cycles"])
            self.assertTrue(component["profiles"]["generation_qnn"]["has_finalize_event"])
            self.assertTrue(component["profiles"]["reload_qnn"]["has_load_binary_event"])

    def test_external_context_artifacts_and_copied_evidence_are_hash_bound(self):
        total = 0
        evidence_root = EXP / "results/host-context-smoke"
        for component in RESULT["components"].values():
            descriptor = component["external_context"]["descriptor"]
            binary = component["external_context"]["binary"]
            self.assertRegex(descriptor["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(binary["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(descriptor["bytes"], 0)
            self.assertGreater(binary["bytes"], 0)
            total += descriptor["bytes"] + binary["bytes"]
            for kind, copied in component["copied_evidence"].items():
                folder = "profiles" if "profile" in kind else "raw"
                path = evidence_root / folder / copied["path"]
                self.assertTrue(path.is_file(), path)
                self.assertEqual(path.stat().st_size, copied["bytes"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), copied["sha256"])
        self.assertEqual(total, RESULT["aggregate"]["total_external_context_bytes"])

    def test_overlap_is_explicit_and_timings_cannot_support_claims(self):
        exclusion = RESULT["coordination_and_timing_exclusion"]
        self.assertIn("overlapped experiment 0017", exclusion["reason"])
        self.assertFalse(exclusion["performance_claim_permitted"])
        self.assertFalse(exclusion["resource_claim_permitted"])
        self.assertEqual(len(exclusion["overlap_windows_utc"]), 3)
        self.assertIn("three clean fresh-process", exclusion["required_follow_up"])
        self.assertIn("isolated setup performance or speedup", RESULT["claim_boundary"]["not_established"])
        self.assertIn("physical phone HTP execution", RESULT["claim_boundary"]["not_established"])

    def test_clean_campaign_has_five_fresh_balanced_runs_per_arm(self):
        isolation = CLEAN["campaign_isolation"]
        self.assertEqual(isolation["fresh_processes_per_arm"], 5)
        self.assertTrue(isolation["fresh_container_per_run"])
        self.assertFalse(isolation["other_qnn_campaign_overlap"])
        self.assertFalse(isolation["phone_access"])
        self.assertEqual(
            isolation["balanced_schedule"],
            ["source", "context", "context", "source", "context", "source", "source", "context", "source", "context"],
        )
        self.assertIn("held by the parent shell for the full campaign", isolation["lock"])
        self.assertEqual(len(CLEAN["schedule"]), 10)
        self.assertTrue(all(item["exit_code"] == 0 for item in CLEAN["schedule"]))

    def test_clean_session_sequence_distribution_and_delta_are_exact(self):
        source = CLEAN["session_sequence"]["source"]
        context = CLEAN["session_sequence"]["context"]
        self.assertEqual(source["count"], 5)
        self.assertEqual(context["count"], 5)
        self.assertEqual(
            source["values_seconds"],
            [24.77686643799825, 24.01408597900081, 24.545940363997943, 24.731559668001864, 25.09281176800141],
        )
        self.assertEqual(
            context["values_seconds"],
            [0.20134365400008392, 0.20715009700143128, 0.1922275830002036, 0.18710627899781684, 0.2008688030000485],
        )
        comparison = CLEAN["comparison"]
        self.assertAlmostEqual(comparison["source_median_seconds"], source["median_seconds"])
        self.assertAlmostEqual(comparison["context_median_seconds"], context["median_seconds"])
        self.assertAlmostEqual(
            comparison["source_minus_context_median_seconds"],
            source["median_seconds"] - context["median_seconds"],
        )
        self.assertGreater(comparison["source_over_context_median_ratio"], 100.0)
        self.assertGreater(comparison["context_setup_reduction_percent"], 99.0)
        self.assertLess(comparison["context_setup_reduction_percent"], 100.0)

    def test_clean_artifacts_and_provider_boundary_match_functional_proof(self):
        for component, expected in EXPECTED_GRAPHS.items():
            self.assertEqual(
                CLEAN["artifact_identities"]["source"][component]["model"]["sha256"], expected
            )
            functional_context = RESULT["components"][component]["external_context"]
            clean_context = CLEAN["artifact_identities"]["context"][component]
            self.assertEqual(clean_context["model"]["sha256"], functional_context["descriptor"]["sha256"])
            self.assertEqual(
                clean_context["external_context_binary"]["sha256"], functional_context["binary"]["sha256"]
            )
        provider = CLEAN["provider_and_fallback_evidence"]
        self.assertEqual(
            provider["functional_companion"]["sha256"], hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        )
        self.assertTrue(provider["functional_companion"]["same_artifact_identities"])
        self.assertTrue(provider["functional_companion"]["all_ort_node_events_qnn_only"])
        self.assertFalse(provider["physical_phone_proof"])
        self.assertIn("Profiling was disabled", provider["timed_processes"])

    def test_clean_raw_results_are_committed_and_hash_bound(self):
        root = EXP / "results/clean-host-setup/raw"
        for item in CLEAN["schedule"]:
            copied = item["raw_record"]
            path = root / copied["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_size, copied["bytes"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), copied["sha256"])
        self.assertIn("inference latency or end-to-end RTF", CLEAN["claim_boundary"]["not_established"])
        self.assertIn("cold OS filesystem-cache behavior", CLEAN["claim_boundary"]["not_established"])


if __name__ == "__main__":
    unittest.main()
