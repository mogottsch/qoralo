import copy
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("kokoro_track", HERE / "validate_track.py")
track_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(track_module)
TrackError = track_module.TrackError


class KokoroTrackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.track = track_module.read_json(HERE / "model-track.json")
        cls.descriptor = track_module.read_json(HERE / "benchmark-descriptor.json")
        cls.config = track_module.read_json(HERE / "sherpa-config.json")
        cls.proof = track_module.read_json(HERE / "voice-proof.json")
        cls.inventory = track_module.read_json(HERE / "deployed-inventory.json")
        cls.source = HERE / "conversion/generate_voices_bin.py"

    def validate(self, *, track=None, descriptor=None, config=None, proof=None, inventory=None):
        track_module.validate(track or self.track, descriptor or self.descriptor, config or self.config,
                              proof or self.proof, inventory or self.inventory, self.source)

    def test_committed_track_and_host_smoke_are_valid(self):
        track_module.validate_committed()
        report = json.loads((HERE / "host-smoke-report.json").read_text())
        self.assertFalse(report["android_performance_evidence"])
        self.assertFalse(report["timing_recorded"])
        self.assertTrue(report["output"]["non_silent"])
        self.assertGreater(report["output"]["frames"], 0)

    def test_machine_proves_v1_0_sid_3_is_af_heart(self):
        self.assertEqual("af_heart", track_module.conversion_mapping(self.source)[3])
        self.assertEqual("3->af_heart", self.proof["metadata_entry"])
        self.assertEqual(track_module.EXACT_MODEL_SHA256, self.proof["model_sha256"])

    def test_rejects_v1_1_or_archive_revision_drift(self):
        changed = copy.deepcopy(self.track)
        changed["deployment_variant"] = "kokoro-multi-lang-v1_1"
        changed["archive"]["filename"] = "kokoro-multi-lang-v1_1.tar.bz2"
        with self.assertRaises(TrackError):
            self.validate(track=changed)

    def test_rejects_wrong_speaker_id_name_or_proof(self):
        for key, value in (("speaker_id", 4), ("speaker", "af_bella")):
            changed = copy.deepcopy(self.descriptor)
            changed[key] = value
            with self.assertRaises(TrackError):
                self.validate(descriptor=changed)
        changed = copy.deepcopy(self.proof)
        changed["metadata_entry"] = "3->af_bella"
        with self.assertRaises(TrackError):
            self.validate(proof=changed)

    def test_rejects_missing_frontend_and_inference_files(self):
        for missing in ("espeak-ng-data/en_dict", "lexicon-us-en.txt", "date-zh.fst", "voices.bin"):
            changed = copy.deepcopy(self.inventory)
            item = next(item for item in changed["files"] if item["path"] == missing)
            changed["files"].remove(item)
            changed["total_bytes"] -= item["bytes"]
            with self.assertRaises(TrackError):
                self.validate(inventory=changed)

    def test_rejects_assets_absolute_and_traversal_paths(self):
        for bad in ("asset://model.onnx", "/sdcard/model.onnx", "../model.onnx", "models\\kokoro\\model.onnx"):
            changed = copy.deepcopy(self.config)
            changed["model"] = bad
            with self.assertRaises(TrackError):
                self.validate(config=changed)

    def test_rejects_qnn_and_every_unsupported_provider(self):
        for provider in ("qnn", "cuda", "nnapi", "coreml", ""):
            changed = copy.deepcopy(self.descriptor)
            changed["provider"] = provider
            with self.assertRaises(TrackError):
                self.validate(descriptor=changed)

    def test_rejects_extra_unpinned_file_or_hash_drift(self):
        changed = copy.deepcopy(self.descriptor)
        changed["files"]["models/kokoro/unpinned.bin"] = "0" * 64
        with self.assertRaises(TrackError):
            self.validate(descriptor=changed)
        changed = copy.deepcopy(self.descriptor)
        changed["files"]["models/kokoro/model.onnx"] = "0" * 64
        with self.assertRaises(TrackError):
            self.validate(descriptor=changed)

    def test_host_report_cannot_publish_performance(self):
        report = json.loads((HERE / "host-smoke-report.json").read_text())
        report["rtf"] = 0.1
        with self.assertRaises(TrackError):
            track_module.validate_host_report(report)


if __name__ == "__main__":
    unittest.main()
