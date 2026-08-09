from __future__ import annotations
import json, re, subprocess, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
PINS = json.loads((HERE / "pins.json").read_text())
PROVENANCE = json.loads((HERE / "provenance.json").read_text())
class PreparationTests(unittest.TestCase):
    def test_revisions_and_weight_digest_are_exact(self):
        self.assertRegex(PINS["source"]["revision"], r"^[0-9a-f]{40}$")
        self.assertRegex(PINS["model"]["revision"], r"^[0-9a-f]{40}$")
        self.assertRegex(PINS["tokenizer"]["revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(PINS["tokenizer"]["repository"], "Qwen/Qwen2.5-0.5B")
        weight = PINS["model"]["files"]["model.safetensors"]
        self.assertEqual(weight["bytes"], 2_035_332_888)
        self.assertEqual(weight["sha256"], "7758b150b8139deb48ac1ff6f181f745c8fedd5511232fd974b3eb217d83b514")
    def test_every_direct_dependency_is_exact_and_locked(self):
        inputs = [x for x in (HERE / "requirements.in").read_text().splitlines() if x and not x.startswith("#")]
        self.assertTrue(all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^<>=!~]+", x) for x in inputs))
        lock = (HERE / "requirements.lock").read_text()
        for item in inputs:
            name, version = item.split("==")
            expected = rf"(?m)^{re.escape(name)}=={re.escape(version)}(?:\+cu128)? \\$"
            self.assertRegex(lock, expected)
        self.assertIn("--hash=sha256:", lock)
    def test_setup_is_isolated_and_model_revision_is_never_floating(self):
        setup = (HERE / "setup.sh").read_text()
        self.assertIn('uv venv --python 3.11 "$VENV"', setup)
        self.assertIn('uv pip sync --python "$VENV/bin/python"', setup)
        self.assertNotRegex(setup, r"(?m)^\s*(sudo|pip3?|python3? -m pip)\b")
        self.assertIn('revision=os.environ["MODEL_REV"]', setup)
        self.assertIn('revision=os.environ["TOKENIZER_REV"]', setup)
        self.assertNotIn("revision=\"main\"", setup)
    def test_smoke_is_fail_closed_behind_shared_gate(self):
        wrapper = (HERE / "smoke-load.sh").read_text()
        internal = (HERE / "_smoke_load.py").read_text()
        self.assertIn('tools/with-resources.sh', wrapper)
        self.assertIn('--task task-2 --kind smoke-load', wrapper)
        self.assertIn('VIBEVOICE_SMOKE_GATE=task-2', wrapper)
        self.assertIn('refusing ungated model load', internal)
        self.assertIn('local_files_only=True', internal)
        self.assertIn('TRANSFORMERS_OFFLINE="1"', internal)
        self.assertIn('"offline_local_only": True', internal)
        self.assertIn('"attention": "sdpa"', internal)
        result = json.loads((HERE / "smoke-load-result.json").read_text())
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["offline_local_only"])
        self.assertIn("kind=smoke-load", result["gate"])
    def test_official_voice_provenance_and_limits_are_explicit(self):
        voice = PROVENANCE["voice_conditioning"]
        self.assertEqual(voice["selected"], "en-Grace_woman.pt")
        self.assertEqual(len(voice["supported_english_presets"]), 6)
        self.assertIn("no underlying recording/source identity is published", voice["provenance"])
        self.assertFalse(PROVENANCE["license_and_access"]["manual_or_proprietary_terms_required"])
        self.assertEqual(PROVENANCE["generation"]["native_sample_rate_hz"], 24000)
        self.assertIn("torch.randn", PROVENANCE["generation"]["determinism"])
    def test_shell_scripts_parse(self):
        for name in ("setup.sh", "smoke-load.sh"):
            subprocess.run(["bash", "-n", HERE / name], check=True)
if __name__ == "__main__": unittest.main()
