import hashlib
import json
import os
from collections import Counter
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

    def test_host_context_smoke_is_complete_and_bounded(self):
        result = json.loads((EXP / "results/host-context-smoke.json").read_text())
        self.assertEqual(result["status"], "all_eight_host_context_functional_smokes_passed")
        self.assertEqual([item["component"] for item in result["components"]],
                         ["text", "prefill", "bos", "latent", "flow", "decoder12", "decoder6", "decoder1"])
        aggregate = result["aggregate"]
        self.assertEqual(aggregate["component_count"], 8)
        self.assertEqual(aggregate["generation_qnn_provider_events"], 8)
        self.assertEqual(aggregate["generation_cpu_provider_events"], 0)
        self.assertEqual(aggregate["reload_qnn_provider_events"], 8)
        self.assertEqual(aggregate["reload_cpu_provider_events"], 0)
        self.assertTrue(aggregate["all_outputs_equal"])
        self.assertTrue(aggregate["all_reloads_source_onnx_absent"])
        self.assertAlmostEqual(aggregate["generation_session_create_seconds_sum"], 23.895610355000827)
        self.assertAlmostEqual(aggregate["isolated_reload_session_create_seconds_sum"], 0.5861214130018197)
        for component in result["components"]:
            self.assertEqual(len(component["committed_profiles"]), 6)
            for record in component["committed_profiles"]:
                profile = ROOT / record["path"]
                self.assertEqual(profile.stat().st_size, record["bytes"])
                self.assertEqual(hashlib.sha256(profile.read_bytes()).hexdigest(), record["sha256"])
                if profile.suffix == ".json":
                    events = json.loads(profile.read_text())
                    providers = Counter(event.get("args", {}).get("provider") for event in events)
                    self.assertEqual(providers["QNNExecutionProvider"], 1)
                    self.assertEqual(providers["CPUExecutionProvider"], 0)
            self.assertEqual(component["generation"]["provider_events"], {"QNNExecutionProvider": 1})
            self.assertEqual(component["isolated_reload"]["provider_events"], {"QNNExecutionProvider": 1})
            self.assertTrue(component["generate_reload_outputs_equal"])
            self.assertTrue(component["isolated_reload"]["source_onnx_absent"])
            for value in component["zero_element_inputs"].values():
                self.assertEqual(value["elements"], 0)
                self.assertEqual(value["bytes"], 0)
                self.assertEqual(value["sha256"], hashlib.sha256(b"").hexdigest())
        self.assertIsNone(result["pending"]["android_e2e"])
        self.assertIsNone(result["pending"]["phone_wav"])

    def test_executables(self):
        for path in list((EXP / "tools").glob("*.sh")) + list((EXP / "device").glob("*.sh")):
            self.assertTrue(os.access(path, os.X_OK), path)


if __name__ == "__main__":
    unittest.main()
