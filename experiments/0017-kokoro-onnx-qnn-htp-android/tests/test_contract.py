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

    def test_stage_decomposition_is_frozen_before_qnn_outputs(self) -> None:
        policy_path = ROOT / "protocol-stage-decomposition.json"
        policy = json.loads(policy_path.read_text())
        provenance = json.loads(
            (ROOT / "results/stage-decomposition-provenance.json").read_text()
        )
        cpu = json.loads((ROOT / "results/stage-cpu-equivalence.json").read_text())

        self.assertTrue(policy["frozen_before_staged_qnn_host_outputs"])
        self.assertTrue(policy["preserved_prior_evidence"]["monolithic_retry_forbidden"])
        self.assertEqual(
            policy["source_and_decomposition"]["source_graph"]["sha256"],
            "7278ed2f0dbe8307a42904434b81116f252dd996bb6a2c064f81ad44269f21cb",
        )
        self.assertEqual(policy["source_and_decomposition"]["stage_count"], 18)
        self.assertEqual(provenance["stage_count"], 18)
        self.assertEqual(provenance["coverage"]["source_nodes"], 1685)
        self.assertEqual(provenance["coverage"]["covered_unique_nodes"], 1685)
        self.assertEqual(
            len(provenance["coverage"]["duplicated_boundary_support_nodes"]), 5
        )
        self.assertTrue(
            all(
                stage["structure"]["quantized_operator_count"] == 0
                for stage in provenance["stages"]
            )
        )
        self.assertEqual(
            provenance["protocol"]["sha256"],
            hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        )
        for name in (
            "extract_staged_graphs.py",
            "run_staged_pipeline.py",
            "kokoro_stage_runner.cc",
        ):
            directory = "host" if name.endswith(".cc") else "tools"
            self.assertEqual(
                provenance["tools"][name],
                hashlib.sha256((ROOT / directory / name).read_bytes()).hexdigest(),
            )

        self.assertEqual(cpu["status"], "passed")
        self.assertEqual(cpu["stage_count"], 18)
        self.assertTrue(cpu["recomposition"]["audio_bit_exact"])
        self.assertTrue(cpu["recomposition"]["duration_bit_exact"])
        self.assertAlmostEqual(cpu["recomposition"]["cosine"], 1.0, places=12)
        self.assertEqual(cpu["recomposition"]["nrmse"], 0.0)
        self.assertEqual(
            cpu["recomposition"]["audio"]["sha256"],
            "56464612c786a6fcc9034e51a24d7e26d17910147a72e5e5672220c45f15045f",
        )
        self.assertEqual(
            cpu["recomposition"]["duration"]["sha256"],
            "7977e82d5304abba333a0b1caa0f0ef39b265b11205ff217c5979255cc44b80e",
        )

    def test_stage_interfaces_form_a_fixed_pipeline(self) -> None:
        policy = json.loads((ROOT / "protocol-stage-decomposition.json").read_text())
        stages = policy["source_and_decomposition"]["stages"]
        available = {"tokens", "style", "speed"}
        for expected_index, stage in enumerate(stages, start=1):
            self.assertEqual(stage["index"], expected_index)
            self.assertGreater(stage["nodes"], 0)
            self.assertEqual(stage["quantized_operator_count"], 0)
            for value in stage["inputs"]:
                self.assertIn(value["name"], available)
                self.assertTrue(all(dim > 0 for dim in value["shape"]))
            for value in stage["outputs"]:
                self.assertTrue(all(dim > 0 for dim in value["shape"]))
                available.add(value["name"])
        self.assertIn("audio", available)
        self.assertIn("pred_dur", available)

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
