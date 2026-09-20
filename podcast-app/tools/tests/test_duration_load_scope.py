import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_duration_load_gate import CONTRACT_SHA
from prepare_wiring_gate import PROJECT
import hashlib


class DurationLoadScopeTests(unittest.TestCase):
    def test_native_probe_has_one_constructor_and_no_inference_call(self):
        source = (PROJECT / "app/src/main/cpp/podcast_runtime.cpp").read_text()
        start = source.index("jstring NativeDurationLoadOnly(")
        body = source[start:source.index("\n#endif", start)]
        self.assertEqual(1, body.count("Ort::Session duration_session("))
        self.assertIsNone(re.search(r"(?:\.|->)Run\s*\(", body))
        self.assertNotIn("Render(", body)
        self.assertNotIn("new Engine(", body)
        self.assertIn('setenv("ADSP_LIBRARY_PATH", native_dir.c_str(), 1)', body)
        self.assertNotIn('setenv("LD_LIBRARY_PATH"', body)
        self.assertNotIn('dlopen(', body)
        self.assertIn("ORT_LOGGING_LEVEL_VERBOSE", body)
        self.assertIn("OrtGetApiBase()->GetVersionString()", body)

    def test_debug_entry_has_no_gemma_or_tts_adapter_call(self):
        service = (PROJECT / "app/src/debug/java/dev/qoralo/podcast/wiring/DurationLoadService.kt").read_text()
        self.assertNotIn("GemmaLiteRtGpuEngine", service)
        self.assertNotIn("SupertonicQnnHtpEngine", service)
        self.assertNotIn("renderChapter(", service)
        self.assertEqual(1, service.count("DurationLoadNative.probe("))
        self.assertNotIn("DurationLoadService", (PROJECT / "app/src/main/AndroidManifest.xml").read_text())
        controller = (PROJECT / "tools/run_duration_load_gate.py").read_text()
        self.assertNotIn("RealRuntimeWiringTest", controller)
        self.assertNotIn("ScreenSemanticsTest", controller)
        self.assertIn("DurationLoadOnlyTest", controller)
        self.assertNotIn('["push"', controller)

    def test_pinned_contract_has_no_environment_variant(self):
        raw = (PROJECT / "app/src/debug/assets/duration-load/contract.json").read_bytes()
        self.assertEqual(CONTRACT_SHA, hashlib.sha256(raw).hexdigest())
        contract = json.loads(raw)
        self.assertEqual("43", contract["socModel"])
        self.assertEqual("1", contract["disableCpuEpFallback"])
        self.assertEqual(0, contract["sessionRunCalls"])
        self.assertEqual("unchanged-baseline-apk-native-library-directory-only", contract["adspLibraryPathPolicy"])


if __name__ == "__main__":
    unittest.main()
