import hashlib
import json
import os
import subprocess
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
        for literal in ("session.disable_cpu_ep_fallback", "R5CW81PR8SY", "manufacturer=samsung",
                        "SM-S918B", "device=dm3q", "SM8550", "arm64-v8a", "boot=1",
                        "verified_boot=green", "flash_locked=1", "phone.lock",
                        "unset ADB_LIBUSB", "PHONE_COORDINATION_CLEARED"):
            if literal == "session.disable_cpu_ep_fallback":
                self.assertIn(literal, (EXP / "tools/pocket_context_benchmark_runner.cc").read_text())
            else:
                self.assertIn(literal, text)

    def test_native_adb_transport_is_exact_and_pre_adb_attempt_is_bounded(self):
        transport = json.loads((EXP / "protocol/phone-transport-contract.json").read_text())
        adb = Path(transport["adb"]["path"])
        self.assertEqual(adb, Path("/usr/bin/adb"))
        self.assertTrue(adb.is_file())
        self.assertTrue(os.access(adb, os.X_OK))
        self.assertFalse(adb.is_symlink())
        self.assertEqual(adb.resolve(), adb)
        self.assertEqual(hashlib.sha256(adb.read_bytes()).hexdigest(), transport["adb"]["sha256"])
        version = subprocess.check_output([str(adb), "version"], text=True).splitlines()
        for line in transport["adb"]["version_lines_required"]:
            self.assertIn(line, version)
        runner = (EXP / "device/run_phone_arm.sh").read_text()
        self.assertIn("ADB=${ADB:-/usr/bin/adb}", runner)
        self.assertIn(transport["adb"]["sha256"], runner)
        self.assertIn("! -L $ADB", runner)
        attempt = json.loads((EXP / "results/pre-adb-transport-attempt.json").read_text())
        self.assertEqual(attempt["result"], "stopped_before_adb_or_device_access")
        self.assertTrue(attempt["phone_lock"]["acquired_nonblocking"])
        self.assertTrue(attempt["phone_lock"]["released"])
        for field in ("adb_process_started", "device_accessed", "remote_root_created",
                      "stage_pushed", "runner_started", "measurement"):
            self.assertFalse(attempt[field])

    def test_cleanup_status_is_tri_state(self):
        helper = EXP / "tools/classify_cleanup_status.py"
        cases = [
            (["0", "1"], 0, "verified_absent"),
            (["0", "0"], 1, "remote_present"),
            (["1", "99"], 2, "pending_device_reconnect"),
            (["0", "2"], 3, "cleanup_verification_error"),
        ]
        for args, expected_rc, expected_status in cases:
            result = subprocess.run([str(helper), *args], text=True, capture_output=True)
            self.assertEqual(result.returncode, expected_rc)
            self.assertEqual(result.stdout.strip(), expected_status)
        runner = (EXP / "device/run_phone_arm.sh").read_text()
        self.assertIn("cleanup-transport.exit", runner)
        self.assertIn("cleanup-exists.exit", runner)
        self.assertIn("cleanup_pending_device_reconnect", runner)

    def test_phone_interruption_checkpoint_is_excluded_and_cleanup_pending(self):
        result = json.loads((EXP / "results/phone-campaign-checkpoint/checkpoint.json").read_text())
        boundary = result["completed_boundary"]
        self.assertEqual((boundary["source_runs_complete"], boundary["source_runs_required"]), (3, 3))
        self.assertEqual((boundary["context_runs_complete"], boundary["context_runs_required"]), (1, 3))
        self.assertTrue(boundary["source_wav_deterministic"])
        interruption = result["interruption"]
        self.assertEqual(interruption["classification"], "external_device_disconnect_incomplete_excluded")
        self.assertEqual(interruption["runner_adb_exit_code"], 255)
        self.assertFalse(interruption["measurement_included"])
        self.assertFalse(interruption["result_json_present"])
        self.assertFalse(interruption["wav_present"])
        self.assertEqual(interruption["cleanup_status"], "pending_device_reconnect")
        self.assertFalse(interruption["preserved_cleanup_proof"]["valid"])
        self.assertTrue(result["phone_lock_released"])

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

    def test_android_stages_are_provenance_only(self):
        result = json.loads((EXP / "results/android-stage-provenance.json").read_text())
        self.assertEqual(result["status"], "source_and_context_android_stages_prepared_no_phone_access")
        self.assertEqual(result["source_stage"]["file_count"], 19)
        self.assertEqual(result["source_stage"]["file_bytes_sum"], 1179649223)
        self.assertEqual(result["context_stage"]["file_count"], 27)
        self.assertEqual(result["context_stage"]["file_bytes_sum"], 654600434)
        self.assertEqual(result["context_stage"]["descriptor_count"], 8)
        self.assertEqual(result["context_stage"]["external_binary_count"], 8)
        self.assertTrue(result["context_stage"]["source_onnx_absent"])
        self.assertEqual(result["runner"]["needed"],
                         ["libonnxruntime.so", "libc++_shared.so", "libm.so", "libdl.so", "libc.so"])
        self.assertTrue(all(result["gates"].values()))
        self.assertFalse(result["phone"]["attempted"])
        self.assertFalse(result["phone"]["phone_lock_acquired"])
        self.assertFalse(result["phone"]["adb_invoked"])
        self.assertIsNone(result["portability"]["physical_context_load_status"])

    def test_eos_frame_drift_is_descriptive_not_execution_blocking(self):
        runner = (EXP / "tools/pocket_context_benchmark_runner.cc").read_text()
        analyzer = (EXP / "tools/analyze_phone_benchmark.py").read_text()
        proof = (EXP / "tools/analyze_physical_proof.py").read_text()
        self.assertNotIn("EOS/frame contract drift", runner)
        self.assertIn("behavior_matches_reference", runner)
        self.assertIn("generation emitted no latent frames", runner)
        self.assertIn("item['generation_seconds']/info['seconds']", analyzer)
        self.assertIn("EOS/frame differences are descriptive", analyzer)
        self.assertIn("Descriptive only; structural validity/provider proof", proof)

    def test_executables(self):
        for path in list((EXP / "tools").glob("*.sh")) + list((EXP / "device").glob("*.sh")):
            self.assertTrue(os.access(path, os.X_OK), path)


if __name__ == "__main__":
    unittest.main()
