from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
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


def fixture_manifest() -> dict:
    fixture = json.loads((PUBLICATION / "tests/fixtures/six-candidate-results.json").read_text())
    paths = {model: build_publication.EXP / relative for model, relative in fixture.items()}
    return build_publication.build_manifest(paths)


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = fixture_manifest()

    def test_complete_six_candidate_contract(self):
        build_publication.validate_manifest(self.manifest)
        self.assertEqual(36, self.manifest["transcript"]["word_count"])
        self.assertEqual(2, self.manifest["protocol"]["version"])
        self.assertEqual(
            [f"Candidate {letter}" for letter in "ABCDEF"],
            [candidate["label"] for candidate in self.manifest["candidates"]],
        )
        self.assertEqual(6, len({candidate["model"] for candidate in self.manifest["candidates"]}))
        self.assertEqual("explicit_reveal_only", self.manifest["anonymization"]["identity_disclosure"])
        for candidate in self.manifest["candidates"]:
            for field in ("display_name", "seed", "voice", "revisions", "commands", "native", "raw", "transformations"):
                self.assertIn(field, candidate)
            self.assertEqual([], candidate["forbidden_transformations_used"])
            self.assertRegex(candidate["raw"]["published_url"], r"^audio/candidate-[a-f]-raw\.wav$")

    def test_schema_rejects_three_candidates_identity_mode_and_hash_drift(self):
        for mutation in (
            lambda value: value["candidates"].__setitem__(slice(3, None), []),
            lambda value: value["anonymization"].__setitem__("identity_disclosure", "manifest_only"),
            lambda value: value["candidates"][0]["native"].__setitem__("sha256", "not-a-hash"),
        ):
            malformed = copy.deepcopy(self.manifest)
            mutation(malformed)
            with self.assertRaises(Exception):
                build_publication.validate_manifest(malformed)
        inconsistent = copy.deepcopy(self.manifest)
        inconsistent["candidates"][0]["native"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "native hash mismatch"):
            build_publication.validate_manifest(inconsistent)

    def test_default_builder_fails_closed_until_all_real_evidence_exists(self):
        missing = [path for path in build_publication.RESULT_FILES.values() if not path.is_file()]
        if missing:
            with self.assertRaisesRegex(ValueError, "evidence is incomplete"):
                build_publication.build_manifest()


class BuiltPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        cls.source_manifest = fixture_manifest()
        build_publication.build(cls.output, cls.source_manifest)
        cls.html = (cls.output / "index.html").read_text()
        cls.manifest = json.loads((cls.output / "bakeoff-manifest.json").read_text())
        embedded = cls.html.split('<script id="bakeoff" type="application/json">', 1)[1].split("</script>", 1)[0]
        cls.page_data = json.loads(embedded)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_fixture_builds_six_neutral_cards_and_candidate_media(self):
        candidates = self.page_data["candidates"]
        self.assertEqual([f"Candidate {letter}" for letter in "ABCDEF"], [item["label"] for item in candidates])
        self.assertEqual(6, len({item["slug"] for item in candidates}))
        self.assertEqual(11, sum(1 + (item["normalized_url"] is not None) for item in candidates))
        self.assertEqual({"label", "slug", "status", "raw_url", "normalized_url"}, set(candidates[0]))
        for candidate in self.manifest["candidates"]:
            for kind in ("raw", "normalized"):
                artifact = candidate[kind]
                if artifact:
                    self.assertTrue((self.output / artifact["published_url"]).is_file())
                    self.assertRegex(artifact["published_url"], r"^audio/candidate-[a-f]-(raw|normalized)\.wav$")

    def test_initial_document_and_embedded_json_have_no_identity(self):
        identities = [candidate["display_name"] for candidate in self.manifest["candidates"]]
        model_ids = [candidate["model"] for candidate in self.manifest["candidates"]]
        for forbidden in identities + model_ids:
            self.assertNotIn(forbidden, self.html)
        self.assertNotIn('id="crew"', self.html)
        self.assertNotIn('id="report"', self.html)
        self.assertNotIn("display_name", json.dumps(self.page_data))
        self.assertNotRegex(json.dumps(self.page_data), r"audio/(?!candidate-[a-f]-)[^\"]+\.wav")
        self.assertIn('class="identity" id="candidate-', self.html)
        self.assertIn("Comparison unavailable.", self.html)
        self.assertIn("Audio unavailable.", self.html)

    def test_identity_manifest_is_requested_only_from_explicit_reveal_handlers(self):
        self.assertEqual(1, self.html.count("fetch('bakeoff-manifest.json'"))
        self.assertIn("identityRequest=fetch", self.html)
        self.assertIn("candidates.addEventListener('click'", self.html)
        self.assertIn("document.querySelector('#reveal-all').addEventListener('click'", self.html)
        self.assertIn("const identities=await loadIdentities()", self.html)
        # One-card reveal receives exactly the clicked button; reveal-all excludes revealed/disabled buttons.
        self.assertIn("if(button)reveal(button)", self.html)
        self.assertIn("button.reveal:not(:disabled)", self.html)

    def test_reveal_controls_keyboard_and_accessible_failure_contract(self):
        self.assertIn('type="button" class="reveal"', self.html)
        self.assertIn('type="button" id="reveal-all"', self.html)
        self.assertIn('aria-controls="candidate-', self.html)
        self.assertIn('role="status" aria-live="polite"', self.html)
        self.assertIn("Identity unavailable. Try again.", self.html)
        self.assertIn("identityRequest=undefined", self.html)
        self.assertIn("button.disabled=true", self.html)

    def test_privacy_csp_and_responsive_contract(self):
        self.assertIn('name="robots" content="noindex,nofollow,noarchive"', self.html)
        self.assertIn('name="referrer" content="no-referrer"', self.html)
        self.assertIn("object-src 'none'", self.html)
        self.assertIn("connect-src 'self'", self.html)
        self.assertIn("form-action 'none'", self.html)
        self.assertIn("PRIVATE · NO INDEXING", self.html)
        self.assertIn("@media(max-width:800px)", self.html)
        self.assertIn("@media(max-width:440px)", self.html)
        self.assertIn('name="viewport"', self.html)

    def test_supporting_files_are_static_not_embedded(self):
        for filename in ("bakeoff-manifest.json", "candidate-decision-report.json", "crew-tasks.json"):
            self.assertTrue((self.output / filename).is_file())
        self.assertNotIn("awaiting_explicit_user_approval", self.html)

    def test_static_upload_script_discovers_all_candidate_audio_without_uploading(self):
        script = (PUBLICATION / "publish.sh").read_text()
        self.assertIn('find "$BUILD/audio"', script)
        self.assertIn("-name '*.wav'", script)
        self.assertIn('filename=$relative', script)
        for letter in "abcdef":
            self.assertTrue(any(path.name == f"candidate-{letter}-raw.wav" for path in (self.output / "audio").iterdir()))

    def test_audio_remains_ignored_and_unstaged(self):
        canonical = build_publication.EXP / "artifacts/publication-build/audio/candidate-f-raw.wav"
        ignored = subprocess.run(["git", "check-ignore", str(canonical)], cwd=build_publication.REPO, capture_output=True)
        self.assertEqual(0, ignored.returncode)
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=build_publication.REPO, text=True, capture_output=True, check=True).stdout
        self.assertNotRegex(staged, r"(?m)\.(wav|flac|mp3|m4a)$")


if __name__ == "__main__":
    unittest.main()
