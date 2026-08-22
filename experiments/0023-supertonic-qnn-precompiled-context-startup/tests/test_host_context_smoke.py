import hashlib
import json
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((EXP / "protocol/experiment-contract.json").read_text())
RESULT = json.loads(
    (EXP / "results/host-context-smoke/host-context-functional-smoke.json").read_text()
)
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


if __name__ == "__main__":
    unittest.main()
