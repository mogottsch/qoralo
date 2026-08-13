import array
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POCKET = ROOT / "models" / "pocket"
SPEC = importlib.util.spec_from_file_location("pocket_track", POCKET / "pocket.py")
pocket = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(pocket)


class DescriptorTests(unittest.TestCase):
    def setUp(self):
        self.descriptor = json.loads((POCKET / "model.json").read_text())
        self.inventory = json.loads((POCKET / "archive-inventory.json").read_text())

    def validate(self, descriptor=None, inventory=None):
        pocket.validate_descriptor(descriptor or self.descriptor, inventory or self.inventory)

    def test_committed_descriptor_and_evidence_pass(self):
        self.validate()
        pocket.validate_evidence(self.descriptor)
        self.assertEqual(8, len(self.descriptor["deployed_files"]))
        self.assertFalse(self.descriptor["voice"]["voice_match"])

    def test_rejects_provider_and_thread_substitutions(self):
        for field, value in (("provider", "qnn"), ("provider", "nnapi"), ("num_threads", 2)):
            changed = copy.deepcopy(self.descriptor); changed["runtime"][field] = value
            with self.assertRaises(pocket.PocketError): self.validate(changed)

    def test_rejects_missing_sample_rate(self):
        changed = copy.deepcopy(self.descriptor); del changed["runtime"]["sample_rate_hz"]
        with self.assertRaises(pocket.PocketError): self.validate(changed)

    def test_rejects_unverified_or_mislabeled_voice(self):
        changes = (("actual_reference", "test_wavs/loona.wav"), ("actual_reference", "test_wavs/alba.wav"),
                   ("actual_reference_sha256", "0" * 64), ("voice_match", True), ("requested_voice", "Bria"))
        for field, value in changes:
            changed = copy.deepcopy(self.descriptor); changed["voice"][field] = value
            with self.assertRaises(pocket.PocketError, msg=field): self.validate(changed)

    def test_rejects_non_int8_date_or_component_substitution(self):
        changed = copy.deepcopy(self.descriptor); changed["pocket"]["lm_main"] = "lm_main.onnx"
        with self.assertRaises(pocket.PocketError): self.validate(changed)
        changed = copy.deepcopy(self.descriptor); changed["archive"]["filename"] = "sherpa-onnx-pocket-tts-fp32-2026-01-27.tar.bz2"
        with self.assertRaises(pocket.PocketError): self.validate(changed)

    def test_rejects_paths_outside_root_and_bundled_assets(self):
        for value in ("../decoder.int8.onnx", "/tmp/decoder.int8.onnx", "assets/decoder.int8.onnx", "a\\decoder.int8.onnx"):
            changed = copy.deepcopy(self.descriptor); changed["pocket"]["decoder"] = value
            with self.assertRaises(pocket.PocketError): self.validate(changed)

    def test_archive_inventory_proves_alba_absent(self):
        changed = copy.deepcopy(self.inventory)
        changed["files"].append({"path": "test_wavs/alba.wav", "bytes": 1, "sha256": "0" * 64})
        with self.assertRaises(pocket.PocketError): self.validate(inventory=changed)

    def test_license_evidence_retains_both_unresolved_sources(self):
        evidence = self.descriptor["license_evidence"]
        self.assertEqual("research_only_unresolved", evidence["disposition"])
        self.assertEqual("CC-BY-4.0", evidence["bundled_license"]["spdx"])
        self.assertIn("non-commercial", (POCKET / evidence["non_commercial_statement"]["path"]).read_text())

    def test_committed_host_smoke_is_audio_only_android_non_evidence(self):
        report = json.loads((POCKET / "host-smoke.json").read_text())
        self.assertEqual("passed", report["status"])
        self.assertEqual("host_configuration_smoke_only", report["scope"])
        self.assertFalse(report["android_performance_evidence"])
        self.assertFalse(report["timing_recorded"])
        self.assertNotIn("rtf", json.dumps(report).casefold())
        self.assertTrue(report["output"]["complete_decode"] and report["output"]["non_silent"])
        self.assertEqual(24000, report["output"]["sample_rate_hz"])


class RootAndAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name) / "model"; self.root.mkdir()

    def tearDown(self): self.temp.cleanup()

    def make_wav(self, path, samples=(100, -200, 300), rate=24000):
        path.parent.mkdir(parents=True, exist_ok=True)
        values = array.array("h", samples)
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(rate); stream.writeframes(values.tobytes())

    def fixture_descriptor(self):
        paths = set(pocket.EXPECTED_DEPLOYED)
        for relative in paths:
            path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            if relative.endswith(".wav"): self.make_wav(path)
            else: path.write_bytes(relative.encode())
        pins = [{"path": x, "bytes": (self.root / x).stat().st_size,
                 "sha256": hashlib.sha256((self.root / x).read_bytes()).hexdigest()} for x in sorted(paths)]
        return {"deployed_files": pins, "voice": {"actual_reference": "test_wavs/bria.wav"}}

    def test_root_hashes_and_reference_format_pass(self):
        descriptor = self.fixture_descriptor()
        self.assertEqual(8, len(pocket.validate_model_root(descriptor, self.root)))

    def test_hash_drift_fails(self):
        descriptor = self.fixture_descriptor(); (self.root / "vocab.json").write_bytes(b"changed")
        with self.assertRaises(pocket.PocketError): pocket.validate_model_root(descriptor, self.root)

    def test_symlink_escape_fails(self):
        descriptor = self.fixture_descriptor()
        escaped = Path(self.temp.name) / "escaped"; escaped.write_bytes(b"escape")
        target = self.root / "vocab.json"; target.unlink(); target.symlink_to(escaped)
        with self.assertRaises(pocket.PocketError): pocket.validate_model_root(descriptor, self.root)

    def test_audio_validation_accepts_signal_and_rejects_silence(self):
        good = self.root / "good.wav"; self.make_wav(good, (1000, -1000) * 100)
        result = pocket.validate_audio(good)
        self.assertTrue(result["complete_decode"] and result["non_silent"])
        silent = self.root / "silent.wav"; self.make_wav(silent, (0,) * 100)
        with self.assertRaises(pocket.PocketError): pocket.validate_audio(silent)

    def test_audio_validation_rejects_rate_and_clipping(self):
        wrong = self.root / "wrong.wav"; self.make_wav(wrong, rate=16000)
        with self.assertRaises(pocket.PocketError): pocket.validate_audio(wrong)
        clipped = self.root / "clip.wav"; self.make_wav(clipped, (32767, -32768))
        with self.assertRaises(pocket.PocketError): pocket.validate_audio(clipped)


if __name__ == "__main__": unittest.main()
