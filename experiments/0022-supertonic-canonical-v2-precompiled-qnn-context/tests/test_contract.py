import hashlib
import json
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parents[1]
CONTRACT = json.loads((EXP / "protocol/experiment-contract.json").read_text())
STATE = json.loads((EXP / "results/preflight-state.json").read_text())
CANONICAL_SHA = "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67"


class ContractTest(unittest.TestCase):
    def test_canonical_transcript_is_exact(self):
        local = (EXP / "protocol/transcript.txt").read_bytes()
        central = (ROOT / "protocols/android-tts-benchmark/transcript.txt").read_bytes()
        self.assertEqual(local, central)
        self.assertEqual(len(local), 226)
        self.assertFalse(local.endswith(b"\n"))
        self.assertEqual(hashlib.sha256(local).hexdigest(), CANONICAL_SHA)
        self.assertEqual(CONTRACT["canonical_input"]["sha256"], CANONICAL_SHA)

    def test_matched_arms_and_run_count_are_frozen(self):
        self.assertEqual(set(CONTRACT["matched_arms"]), {
            "A_source_onnx", "B_precompiled_context", "only_intended_variable"
        })
        self.assertGreaterEqual(CONTRACT["measurements"]["cold_processes_per_arm_minimum"], 3)
        self.assertEqual(CONTRACT["measurements"]["runs_per_process"], 6)
        self.assertEqual(CONTRACT["measurements"]["warm_run_indices"], [1, 2, 3, 4, 5])
        self.assertEqual(CONTRACT["runtime"]["provider_options"]["session.disable_cpu_ep_fallback"], "1")

    def test_frozen_hashes_and_context_mode(self):
        for graph in CONTRACT["graphs"].values():
            if isinstance(graph, dict):
                self.assertRegex(graph["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(CONTRACT["runtime"]["onnxruntime_version"], "1.27.1")
        self.assertEqual(CONTRACT["runtime"]["epcontext_mode"]["ep.context_embed_mode"], "0")
        self.assertTrue(CONTRACT["runtime"]["epcontext_mode"]["external_context_binary_required"])

    def test_safe_boundary_and_shape_gate_are_explicit(self):
        self.assertEqual(STATE["state"], "safe_boundary_before_implementation")
        self.assertIn("EPContext generation", STATE["not_started"])
        self.assertIn("phone staging or execution", STATE["not_started"])
        gate = CONTRACT["current_blocker_or_design_gate"]
        self.assertIn("T239/L238", gate["fact"])
        self.assertIn("canonical-v2", gate["fact"])
        self.assertEqual(CONTRACT["canonical_input"]["processed_length_without_padding"], 235)
        self.assertEqual(CONTRACT["lineage"]["baseline_processed_text_length"], 239)

    def test_claim_boundaries_cover_proof_and_listening(self):
        joined = " ".join(CONTRACT["claim_boundaries"])
        self.assertIn("physical phone HTP proof", joined)
        self.assertIn("not_reviewed", joined)
        self.assertIn("No FP32-arithmetic claim", joined)


if __name__ == "__main__":
    unittest.main()
