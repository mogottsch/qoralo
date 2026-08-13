import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

EXPERIMENT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


wav = load_module("host_wav", EXPERIMENT / "tools/host_wav.py")
apk_gate = load_module("inspect_apk", EXPERIMENT / "tools/inspect_apk.py")
integration = load_module("integration_gate", EXPERIMENT / "tools/integration_gate.py")


class DescriptorIntegrationTest(unittest.TestCase):
    def test_all_descriptors_share_android_contract_and_verified_inventory(self):
        aggregate, readiness = integration.generate()
        self.assertEqual(["pocket", "kokoro", "supertonic_3"], [x["candidate"] for x in aggregate["models"]])
        self.assertEqual(sum(x["deployed_bytes"] for x in aggregate["models"]), aggregate["aggregate_deployed_bytes"])
        self.assertEqual(aggregate["aggregate_deployed_bytes"] * 2, aggregate["aggregate_required_free_bytes"])
        self.assertTrue(readiness["all_unblocked_descriptors_conform"])
        self.assertTrue(all(not item["blocked"] for item in readiness["models"]))
        for candidate, path in integration.DESCRIPTORS.items():
            integration.validate_descriptor(candidate, integration.load(path))

    def test_committed_aggregate_is_current(self):
        aggregate, readiness = integration.generate()
        self.assertEqual(aggregate, integration.load(EXPERIMENT / "integration/aggregate-inventory.json"))
        self.assertEqual(readiness, integration.load(EXPERIMENT / "integration/host-readiness.json"))


class IndependentWavTest(unittest.TestCase):
    def setUp(self):
        self.samples = [0.1, -0.25, 0.4, -0.1] * 100
        self.payload = wav.encode_pcm16(self.samples, 16000)

    def test_full_decode_frame_sample_duration_and_hash(self):
        expected = hashlib.sha256(self.payload).hexdigest()
        report = wav.validate_bytes(self.payload, expected)
        self.assertEqual(400, report.frames)
        self.assertEqual(16000, report.sample_rate_hz)
        self.assertAlmostEqual(0.025, report.duration_seconds)
        self.assertGreater(report.rms, 0)

    def test_hash_drift(self):
        with self.assertRaisesRegex(wav.WavError, "hash drift"):
            wav.validate_bytes(self.payload, "0" * 64)

    def test_silence_and_clipping(self):
        with self.assertRaisesRegex(wav.WavError, "silent"):
            wav.validate_bytes(wav.encode_pcm16([0.0] * 100, 8000))
        with self.assertRaisesRegex(wav.WavError, "clipped"):
            wav.validate_bytes(wav.encode_pcm16([0.2, 1.0] * 100, 8000))

    def test_truncation_malformed_header_and_trailing_bytes(self):
        with self.assertRaises(wav.WavError):
            wav.validate_bytes(self.payload[:-1])
        damaged = bytearray(self.payload); damaged[0:4] = b"NOPE"
        with self.assertRaisesRegex(wav.WavError, "header"):
            wav.validate_bytes(bytes(damaged))
        with self.assertRaisesRegex(wav.WavError, "trailing"):
            wav.validate_bytes(self.payload + b"x")

    def test_partial_frame_and_format_disagreement(self):
        damaged = bytearray(self.payload)
        # PCM data size and RIFF size both claim a complete file with an odd partial frame.
        damaged = damaged[:-1]
        damaged[4:8] = (len(damaged) - 8).to_bytes(4, "little")
        damaged[40:44] = (len(damaged) - 44).to_bytes(4, "little")
        with self.assertRaisesRegex(wav.WavError, "incomplete|partial"):
            wav.validate_bytes(bytes(damaged))
        damaged = bytearray(self.payload); damaged[32:34] = (4).to_bytes(2, "little")
        with self.assertRaisesRegex(wav.WavError, "canonical"):
            wav.validate_bytes(bytes(damaged))

    def test_non_finite_source_samples_are_rejected_before_encoding(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaisesRegex(wav.WavError, "non-finite"):
                wav.encode_pcm16([0.1, value], 16000)


class ApkInspectionTest(unittest.TestCase):
    def fixture(self, directory, *, abi="arm64-v8a", extra=None):
        directory = Path(directory)
        aar = directory / "runtime.aar"
        apk = directory / "app.apk"
        libraries = {name: ("bytes-" + name).encode() for name in apk_gate.NATIVE_LIBS}
        with zipfile.ZipFile(aar, "w") as archive:
            for name, payload in libraries.items(): archive.writestr(f"jni/arm64-v8a/{name}", payload)
        with zipfile.ZipFile(apk, "w") as archive:
            for name, payload in libraries.items(): archive.writestr(f"lib/{abi}/{name}", payload)
            archive.writestr("classes.dex", b"dex")
            if extra: archive.writestr(extra, b"forbidden")
        return aar, apk

    def test_arm64_apk_exactly_uses_pinned_aar_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            aar, apk = self.fixture(directory)
            with mock.patch.object(apk_gate, "PINNED_AAR_SIZE", aar.stat().st_size), mock.patch.object(apk_gate, "PINNED_AAR_SHA256", hashlib.sha256(aar.read_bytes()).hexdigest()):
                report = apk_gate.inspect(apk, aar)
            self.assertEqual("arm64-v8a", report["abi"])
            self.assertFalse(report["bundled_models_archives_or_audio"])

    def test_rejects_other_abi_and_bundled_model_or_reference_audio(self):
        for abi, extra in (("x86_64", None), ("arm64-v8a", "assets/models/model.onnx"), ("arm64-v8a", "assets/reference.wav")):
            with self.subTest(abi=abi, extra=extra), tempfile.TemporaryDirectory() as directory:
                aar, apk = self.fixture(directory, abi=abi, extra=extra)
                with mock.patch.object(apk_gate, "PINNED_AAR_SIZE", aar.stat().st_size), mock.patch.object(apk_gate, "PINNED_AAR_SHA256", hashlib.sha256(aar.read_bytes()).hexdigest()):
                    with self.assertRaises(ValueError): apk_gate.inspect(apk, aar)


if __name__ == "__main__":
    unittest.main()
