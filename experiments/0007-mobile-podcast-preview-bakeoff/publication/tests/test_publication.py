from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

PUBLICATION = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_publication", PUBLICATION / "build_publication.py")
build_publication = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = build_publication
SPEC.loader.exec_module(build_publication)


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build_publication.build_manifest()

    def test_complete_reproducibility_fields_and_three_candidates(self):
        build_publication.validate_manifest(self.manifest)
        self.assertEqual(36, self.manifest["transcript"]["word_count"])
        self.assertEqual(2, self.manifest["protocol"]["version"])
        self.assertEqual({"realtime", "pocket", "kokoro"}, {c["model"] for c in self.manifest["candidates"]})
        for candidate in self.manifest["candidates"]:
            for field in ("seed", "voice", "revisions", "commands", "native", "raw", "transformations"):
                self.assertIn(field, candidate)
            self.assertEqual([], candidate["forbidden_transformations_used"])
            self.assertEqual(64, len(candidate["native"]["sha256"]))

    def test_schema_rejects_hash_shape_and_cross_file_inconsistency(self):
        malformed = copy.deepcopy(self.manifest)
        malformed["candidates"][0]["native"]["sha256"] = "not-a-hash"
        with self.assertRaises(Exception):
            build_publication.validate_manifest(malformed)
        inconsistent = copy.deepcopy(self.manifest)
        inconsistent["candidates"][0]["native"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "native hash mismatch"):
            build_publication.validate_manifest(inconsistent)

    def test_blocked_short_output_has_raw_but_no_fabricated_normalized_audio(self):
        pocket = next(c for c in self.manifest["candidates"] if c["model"] == "pocket")
        self.assertEqual("blocked", pocket["status"])
        self.assertIsNotNone(pocket["raw"])
        self.assertIsNone(pocket["normalized"])
        self.assertFalse(pocket["transformations"]["applied"])


class BuiltPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        build_publication.build(cls.output)
        cls.html = (cls.output / "index.html").read_text()
        cls.crew = json.loads((cls.output / "crew-tasks.json").read_text())
        cls.manifest = json.loads((cls.output / "bakeoff-manifest.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_controls_urls_labels_and_anonymous_player_mapping(self):
        embedded = self.html.split('<script id="bakeoff" type="application/json">', 1)[1].split("</script>", 1)[0]
        page_data = json.loads(embedded)
        self.assertEqual(3, len(page_data["candidates"]))
        self.assertEqual(5, sum(1 + (c["normalized_url"] is not None) for c in page_data["candidates"]))
        self.assertIn(" controls ", self.html)
        for label in ("Candidate A", "Candidate B", "Candidate C"):
            self.assertIn(label, self.html)
        for name in ("realtime", "pocket", "kokoro"):
            self.assertNotIn(f'"model":"{name}"', self.html)
        for candidate in self.manifest["candidates"]:
            for kind in ("raw", "normalized"):
                artifact = candidate[kind]
                if artifact:
                    self.assertTrue((self.output / artifact["published_url"]).is_file())
                    self.assertIn(artifact["published_url"], self.html)

    def test_privacy_and_responsive_contract(self):
        self.assertIn('name="robots" content="noindex,nofollow,noarchive"', self.html)
        self.assertIn("object-src 'none'", self.html)
        self.assertIn("PRIVATE · NO INDEXING", self.html)
        self.assertIn("@media(max-width:800px)", self.html)
        self.assertIn('name="viewport"', self.html)

    def test_all_18_tasks_edges_status_and_progress_rendering(self):
        self.assertEqual(18, len(self.crew["tasks"]))
        ids = {task["id"] for task in self.crew["tasks"]}
        self.assertEqual({f"task-{n}" for n in range(1, 19)}, ids)
        for task in self.crew["tasks"]:
            self.assertFalse(set(task["depends_on"]) - ids)
        self.assertIn("Depends on:", self.html)
        self.assertIn("Progress:", self.html)
        self.assertIn("counts.done", self.html)
        self.assertIn("t.depends_on.map", self.html)

    def test_audio_remains_ignored_and_unstaged(self):
        import subprocess
        wav = next((self.output / "audio").glob("*.wav"))
        ignored = subprocess.run(["git", "check-ignore", str(wav)], cwd=build_publication.REPO, capture_output=True)
        # Temporary output is outside the repository; canonical build output is covered by artifacts/.
        canonical = build_publication.EXP / "artifacts/publication-build/audio/check.wav"
        self.assertEqual(0, subprocess.run(["git", "check-ignore", str(canonical)], cwd=build_publication.REPO, capture_output=True).returncode)
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=build_publication.REPO, text=True, capture_output=True, check=True).stdout
        self.assertNotRegex(staged, r"(?m)\.(wav|flac|mp3|m4a)$")


if __name__ == "__main__":
    unittest.main()
