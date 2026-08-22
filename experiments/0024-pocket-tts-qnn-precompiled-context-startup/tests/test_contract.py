import hashlib
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((EXP / "protocol/experiment-contract.json").read_text())


class ContractTest(unittest.TestCase):
    def test_transcript_exact(self):
        data = (EXP / "protocol/transcript.txt").read_bytes()
        self.assertEqual(len(data), 226)
        self.assertFalse(data.endswith(b"\n"))
        self.assertEqual(hashlib.sha256(data).hexdigest(), CONTRACT["canonical_transcript"]["sha256"])
        self.assertEqual(data, (ROOT / "protocols/android-tts-benchmark/transcript.txt").read_bytes())

    def test_eight_graphs_and_three_cold_runs(self):
        self.assertEqual(len(CONTRACT["historical_0014_graph_sha256_for_comparison_not_identity"]), 8)
        self.assertGreaterEqual(CONTRACT["comparison"]["fresh_cold_processes_per_arm_minimum"], 3)
        self.assertIsNone(CONTRACT["comparison"]["arbitrary_speedup_gate"])

    def test_fail_closed_and_device_gates_are_literal(self):
        text = (EXP / "device/run_phone_arm.sh").read_text()
        for literal in ("session.disable_cpu_ep_fallback", "R5CW81PR8SY", "SM-S918B",
                        "SM8550", "arm64-v8a", "phone.lock", "ADB_LIBUSB=1",
                        "PHONE_COORDINATION_CLEARED"):
            if literal == "session.disable_cpu_ep_fallback":
                self.assertIn(literal, (EXP / "tools/pocket_context_benchmark_runner.cc").read_text())
            else:
                self.assertIn(literal, text)

    def test_context_isolation_and_proof(self):
        component = (EXP / "tools/qnn_context_component.py").read_text()
        campaign = (EXP / "tools/generate_contexts.sh").read_text()
        self.assertIn('session.disable_cpu_ep_fallback", "1"', component)
        self.assertIn("require_source_absent", component)
        self.assertIn("QNNExecutionProvider", component)
        self.assertIn("CPUExecutionProvider", component)
        self.assertIn("flock -n 8", campaign)
        self.assertIn("QNN_HOST_ACCESS_CONFIRMED", campaign)

    def test_cpu_checkpoint_is_hash_bound_and_qnn_pending(self):
        result = json.loads((EXP / "results/reconstruction.json").read_text())
        self.assertEqual(result["status"], "cpu_reconstruction_complete_waiting_for_serialized_qnn_clearance")
        self.assertFalse(result["derivative_graphs"]["exact_0014_hashes_reproduced"])
        self.assertTrue(result["derivative_graphs"]["documented_derivatives_allowed"])
        self.assertEqual(result["host_cpu_e2e"]["result"], "passed")
        self.assertEqual(result["host_cpu_e2e"]["eos_step"], 160)
        self.assertEqual(result["host_cpu_e2e"]["latent_frames"], 163)
        self.assertEqual(result["host_cpu_e2e"]["wav"]["samples"], 312960)
        self.assertFalse(result["qnn_and_phone"]["attempted"])
        wav = EXP / "results/host-cpu-derivative.wav"
        self.assertEqual(hashlib.sha256(wav.read_bytes()).hexdigest(), result["host_cpu_e2e"]["wav"]["sha256"])
        self.assertEqual(result["quality"]["status"], "not_reviewed")

    def test_executables(self):
        for path in list((EXP / "tools").glob("*.sh")) + list((EXP / "device").glob("*.sh")):
            self.assertTrue(os.access(path, os.X_OK), path)


if __name__ == "__main__":
    unittest.main()
