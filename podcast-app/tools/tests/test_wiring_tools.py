import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_wiring_gate import PROJECT, check_inputs
from run_wiring_gate import ANIMATIONS, DeviceSettings
from analyze_wiring_evidence import profile_observations


class WiringToolsTests(unittest.TestCase):
    def test_partial_setting_mutation_failure_restores_even_failed_write(self):
        values = {name: str(i + 1) for i, name in enumerate(ANIMATIONS)}
        calls = []
        def shell(command):
            calls.append(command)
            parts = command.split()
            if parts[1] == "get":
                return values[parts[3]]
            if parts[1] == "put":
                values[parts[3]] = parts[4]
                if parts[3] == ANIMATIONS[1] and parts[4] == "0":
                    raise RuntimeError("transport interrupted after write")
                return ""
            raise AssertionError(command)
        settings = DeviceSettings(shell)
        original = settings.capture()
        with self.assertRaises(RuntimeError):
            settings.disable_animations()
        self.assertEqual([], settings.restore())
        self.assertEqual(original, values)
        self.assertIn(f"settings put global {ANIMATIONS[1]} 2", calls)

    def test_null_setting_restores_by_delete_and_checks_result(self):
        values = dict.fromkeys(ANIMATIONS, "null")
        def shell(command):
            parts = command.split()
            if parts[1] == "get":
                return values[parts[3]]
            values[parts[3]] = "null" if parts[1] == "delete" else parts[4]
            return ""
        settings = DeviceSettings(shell)
        settings.capture(); settings.disable_animations()
        self.assertEqual([], settings.restore())
        self.assertEqual(dict.fromkeys(ANIMATIONS, "null"), values)

    def test_missing_settings_capture_cannot_mutate(self):
        shell = Mock()
        settings = DeviceSettings(shell)
        with self.assertRaises(ValueError):
            settings.disable_animations()
        shell.assert_not_called()

    def test_provider_declaration_alone_is_not_htp_proof(self):
        self.assertFalse(profile_observations([], [])["htpProofEstablished"])
        self.assertFalse(profile_observations([{"args": {"provider": "QNNExecutionProvider"}}], [])["htpProofEstablished"])
        rows = self.backend_rows()
        events = [self.node_event()]
        self.assertTrue(profile_observations(events, rows)["htpProofEstablished"])
        self.assertFalse(profile_observations(events + [self.node_event("CPUExecutionProvider")], rows)["htpProofEstablished"])

    def test_non_node_annotation_plus_rpc_cycles_is_not_execution_proof(self):
        metadata = {"cat": "Session", "ph": "X", "dur": 10, "name": "model_loading_uri",
                    "args": {"provider": "QNNExecutionProvider"}}
        result = profile_observations([metadata], self.backend_rows())
        self.assertFalse(result["htpProofEstablished"])
        self.assertEqual(0, result["ortExecutionNodeCount"])
        self.assertEqual([], result["ortProviders"])

    def test_node_fence_and_missing_execution_fields_do_not_qualify(self):
        for change in [{"cat": "Session"}, {"ph": "B"}, {"name": "qnn_fence_before"}, {"dur": 0}, {"dur": "NaN"}]:
            self.assertFalse(profile_observations([self.node_event() | change], self.backend_rows())["htpProofEstablished"])
        self.assertFalse(profile_observations([self.node_event(), self.node_event() | {"args": {}}], self.backend_rows())["htpProofEstablished"])

    def test_nonfinite_or_wrong_unit_rpc_cycle_records_do_not_qualify(self):
        for value in ["nan", "inf", "-inf", "0", "-1", "bad", None]:
            for index in (0, 1):
                rows = self.backend_rows()
                rows[index]["Time"] = value
                self.assertFalse(profile_observations([self.node_event()], rows)["htpProofEstablished"])
        rows = self.backend_rows()
        rows[1]["Unit of Measurement"] = "US"
        self.assertFalse(profile_observations([self.node_event()], rows)["htpProofEstablished"])

    @staticmethod
    def node_event(provider="QNNExecutionProvider"):
        return {"cat": "Node", "ph": "X", "name": "duration_qnn_kernel_time", "dur": 10, "args": {"provider": provider}}

    @staticmethod
    def backend_rows():
        return [{"Time": "10", "Event Identifier": "RPC (execute) time", "Unit of Measurement": "US", "Timing Source": "BACKEND", "Event Level": "ROOT"},
                {"Time": "2000", "Event Identifier": "Accelerator (execute) time (cycles)", "Unit of Measurement": "CYCLES", "Timing Source": "BACKEND", "Event Level": "ROOT"}]

    def test_apk_input_mutation_rejected_before_device_access(self):
        assets = PROJECT / "app/src/debug/assets/wiring"
        contract = assets / "contract.json"
        with tempfile.TemporaryDirectory() as temporary:
            apk = Path(temporary) / "fixture.zip"
            def create(mutate):
                with zipfile.ZipFile(apk, "w") as archive:
                    for path in assets.iterdir():
                        payload = path.read_bytes()
                        if mutate and path.name == "source.txt":
                            payload = bytes([payload[0] ^ 1]) + payload[1:]
                        archive.writestr("assets/wiring/" + path.name, payload)
            create(False)
            self.assertEqual("podcast-runtime-wiring-v1", check_inputs(apk, contract)["id"])
            create(True)
            with self.assertRaisesRegex(ValueError, "input mismatch"):
                check_inputs(apk, contract)

    def test_service_manifest_is_debug_only_nonexported_and_separate_process(self):
        debug = (PROJECT / "app/src/debug/AndroidManifest.xml").read_text()
        production = (PROJECT / "app/src/main/AndroidManifest.xml").read_text()
        self.assertIn('android:exported="false"', debug)
        self.assertIn('android:process=":generation"', debug)
        self.assertNotIn("RuntimeWiringService", production)
        self.assertFalse((PROJECT / "app/src/release/assets/wiring").exists())
        release = (PROJECT / "app/src/release/java/dev/qoralo/podcast/runtime/RuntimeDiagnostics.kt").read_text()
        self.assertNotIn("enable(", release)
        self.assertIn('fun qnnProfileDirectory(): String = ""', release)


if __name__ == "__main__":
    unittest.main()
