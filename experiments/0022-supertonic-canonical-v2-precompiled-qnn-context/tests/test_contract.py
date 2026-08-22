import hashlib
import json
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parents[1]
CONTRACT = json.loads((EXP / "protocol/experiment-contract.json").read_text())
STATE = json.loads((EXP / "results/preflight-state.json").read_text())
POLICY_PATH = EXP / "protocol/padding-compatibility-policy.json"
POLICY = json.loads(POLICY_PATH.read_text())
PROOF = json.loads((EXP / "results/t235-t239-masked-padding-compatibility.json").read_text())
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

    def test_terminal_shape_gate_is_explicit(self):
        self.assertEqual(STATE["state"], "stopped_joint_constraint_incompatibility")
        stopped = STATE["not_started_due_to_terminal_gate_failure"]
        self.assertIn("EPContext generation", stopped)
        self.assertIn("phone staging or execution", stopped)
        gate = CONTRACT["current_blocker_or_design_gate"]
        self.assertEqual(gate["kind"], "resolved_incompatible_stop")
        self.assertEqual(gate["result"], "failed_joint_constraint_incompatibility")
        self.assertIn("T239/L238", gate["fact"])
        self.assertIn("canonical-v2", gate["fact"])
        self.assertEqual(CONTRACT["canonical_input"]["processed_length_without_padding"], 235)
        self.assertEqual(CONTRACT["lineage"]["baseline_processed_text_length"], 239)

    def test_masked_padding_proof_fails_closed(self):
        self.assertEqual(PROOF["decision"]["result"], "failed_joint_constraint_incompatibility")
        self.assertFalse(PROOF["decision"]["compatible"])
        self.assertFalse(PROOF["decision"]["oracle_equivalence_passed"])
        self.assertTrue(PROOF["decision"]["frozen_t239_reproduction_passed"])
        self.assertTrue(PROOF["decision"]["pad_payload_invariance_passed"])
        self.assertEqual(
            PROOF["decision"]["required_action"],
            "stop_before_runner_implementation_context_generation_output_or_phone_access",
        )
        candidate = PROOF["candidate_t239_input"]
        self.assertEqual(candidate["zero_based_padding_positions"], [235, 236, 237, 238])
        self.assertEqual(candidate["filler_id"], 0)
        self.assertEqual(candidate["text_ids"]["shape"], [1, 239])
        self.assertEqual(candidate["text_mask"]["shape"], [1, 1, 239])
        self.assertEqual(candidate["text_mask"]["values"][:235], [1.0] * 235)
        self.assertEqual(candidate["text_mask"]["values"][235:], [0.0] * 4)

    def test_proof_policy_and_material_differences_are_locked(self):
        self.assertEqual(
            PROOF["policy"]["sha256"], hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()
        )
        comparison = PROOF["comparisons"]["dynamic_t235_oracle_vs_dynamic_t239_masked"]
        self.assertGreater(
            comparison["duration"]["max_abs"],
            POLICY["oracle_equivalence_limits"]["duration_max_abs_lte"],
        )
        self.assertGreater(
            comparison["text_embedding_semantic_prefix"]["max_abs"],
            POLICY["oracle_equivalence_limits"]["text_embedding_semantic_prefix_max_abs_lte"],
        )
        self.assertGreater(
            comparison["text_embedding_semantic_prefix"]["rmse"],
            POLICY["oracle_equivalence_limits"]["text_embedding_semantic_prefix_rmse_lte"],
        )
        self.assertLess(
            comparison["text_embedding_semantic_prefix"]["cosine"],
            POLICY["oracle_equivalence_limits"]["text_embedding_semantic_prefix_cosine_gte"],
        )

    def test_claim_boundaries_cover_proof_and_listening(self):
        joined = " ".join(CONTRACT["claim_boundaries"])
        self.assertIn("physical phone HTP proof", joined)
        self.assertIn("not_reviewed", joined)
        self.assertIn("No FP32-arithmetic claim", joined)


if __name__ == "__main__":
    unittest.main()
