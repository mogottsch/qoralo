from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


class ContractTests(unittest.TestCase):
    def test_protocol_and_transcript_are_frozen(self) -> None:
        policy = json.loads((ROOT / "protocol.json").read_text())
        transcript = (ROOT / "protocol/transcript.txt").read_bytes()
        self.assertTrue(policy["frozen_before_qnn_host_or_phone_outputs"])
        self.assertEqual(len(transcript), 116)
        self.assertEqual(
            hashlib.sha256(transcript).hexdigest(),
            policy["fixed_contract"]["transcript_sha256"],
        )
        self.assertEqual(
            policy["source"]["controlled_onnx"]["sha256"],
            "d11a0dd7c4eb768e1f0ef03090c69b6761f55e37b9f196749349591c40be232b",
        )
        self.assertFalse(policy["source"]["controlled_onnx"]["learned_weight_changes"])
        self.assertEqual(policy["source"]["controlled_onnx"]["quantized_operator_count"], 0)
        self.assertTrue(policy["host_gate"]["phone_forbidden_until_pass"])

    def test_source_inventory_tracks_committed_inputs_and_tools(self) -> None:
        inventory = json.loads((ROOT / "results/source-inventory.json").read_text())
        self.assertEqual(
            hashlib.sha256((ROOT / "protocol.json").read_bytes()).hexdigest(),
            inventory["fixed_contract"]["protocol_sha256"],
        )
        for name, expected in inventory["tools"].items():
            if not name.endswith(".py") and name != "kokoro_ort_runner.cc":
                continue
            path = ROOT / ("host" if name.endswith(".cc") else "tools") / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)

    def test_erased_experiment_0015_remains_absent(self) -> None:
        self.assertFalse((REPO / "experiments/0015-pocket-tts-qnn-htp-android").exists())

    def test_fixed_alignment_lowering_matches_repeat_interleave(self) -> None:
        # Exercise zeros and nonuniform lengths; production duration is separately
        # hash-gated and has length 125/sum 304.
        durations = np.asarray([1, 3, 0, 2, 4], dtype=np.int64)
        positions = np.arange(int(durations.sum()), dtype=np.float32)[None, :]
        lower = np.tril(np.ones((durations.size, durations.size), dtype=np.float32))
        column = durations.astype(np.float32)[:, None]
        end = lower @ column
        start = end - column
        candidate = ((positions >= start) & (positions < end)).astype(np.float32)

        indices = np.repeat(np.arange(durations.size), durations)
        expected = np.zeros_like(candidate)
        expected[indices, np.arange(indices.size)] = 1.0
        np.testing.assert_array_equal(candidate, expected)

    def test_rewrite_policy_requires_same_runtime_equivalence(self) -> None:
        rewrite = json.loads((ROOT / "protocol.json").read_text())["rewrite_policy"]
        gate = rewrite["cpu_equivalence_gate"]
        self.assertEqual(gate["duration_tensor"], "bit exact")
        self.assertEqual(gate["minimum_waveform_cosine"], 0.999)
        self.assertEqual(gate["maximum_waveform_nrmse"], 0.01)
        self.assertIn("same host ONNX Runtime", gate["reference"])
        self.assertIn("quantization or calibration", rewrite["forbidden_without_new_authorization"])


if __name__ == "__main__":
    unittest.main()
