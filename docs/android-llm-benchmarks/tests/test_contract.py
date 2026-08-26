#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REGISTRY_DIR = HERE.parent
ROOT = REGISTRY_DIR.parents[1]


class OutputSanitySchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads((REGISTRY_DIR / "schema.json").read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(schema["$defs"]["output_sanity"])

    def assert_valid(self, value: dict) -> None:
        self.assertEqual([], list(self.validator.iter_errors(value)))

    def assert_invalid(self, value: dict) -> None:
        self.assertTrue(list(self.validator.iter_errors(value)))

    def test_allowed_combinations(self) -> None:
        self.assert_valid({"looks_sensible": True, "issue_notes": None})
        self.assert_valid({"looks_sensible": False, "issue_notes": "Repeated punctuation after the first sentence."})
        self.assert_valid({"looks_sensible": None, "issue_notes": None})

    def test_notes_exist_only_for_obvious_failure(self) -> None:
        self.assert_invalid({"looks_sensible": True, "issue_notes": "Good."})
        self.assert_invalid({"looks_sensible": False, "issue_notes": None})
        self.assert_invalid({"looks_sensible": False, "issue_notes": ""})
        self.assert_invalid({"looks_sensible": None, "issue_notes": "Unchecked."})

    def test_exactly_two_fields(self) -> None:
        self.assert_invalid({"looks_sensible": True, "issue_notes": None, "quality": "good"})


class RepositoryContractTest(unittest.TestCase):
    def test_registry_rows_are_android_only(self) -> None:
        schema = json.loads((REGISTRY_DIR / "schema.json").read_text(encoding="utf-8"))
        entry = schema["$defs"]["entry"]
        self.assertNotIn("execution_target", entry["required"])
        self.assertNotIn("execution_target", entry["properties"])
        self.assertEqual({"$ref": "#/$defs/device"}, entry["properties"]["device"])

    def test_protocol_v2_uses_loaded_route_without_claiming_session_reuse(self) -> None:
        schema = json.loads((REGISTRY_DIR / "schema.json").read_text(encoding="utf-8"))
        self.assertEqual(["first", "loaded_route"], schema["$defs"]["run"]["properties"]["phase"]["enum"])
        run = schema["$defs"]["run"]
        aggregate = schema["$defs"]["tier_aggregate"]
        self.assertIn("loaded_route_count", aggregate["required"])
        self.assertNotIn("same_session_count", aggregate["properties"])
        self.assertIn("request_isolation", run["required"])
        isolation = schema["$defs"]["request_isolation"]
        self.assertIn("reset_or_session_creation_seconds", isolation["required"])
        self.assertIn("loaded_model_runtime_route_reused", isolation["required"])

    def test_gpu_rows_bind_provider_and_exclude_cpu_fallback(self) -> None:
        registry = json.loads((REGISTRY_DIR / "registry.json").read_text(encoding="utf-8"))
        gpu_rows = [
            entry for entry in registry["entries"]
            if entry["runtime"]["options"].get("neural_backend") == "GPU"
        ]
        self.assertGreaterEqual(len(gpu_rows), 1)
        for entry in gpu_rows:
            options = entry["runtime"]["options"]
            self.assertIs(options.get("gpu_provider_binding_proven"), True)
            self.assertIs(options.get("cpu_fallback_used"), False)

    def test_current_registry_and_workload_validate(self) -> None:
        registry = json.loads((REGISTRY_DIR / "registry.json").read_text(encoding="utf-8"))
        completed = subprocess.run(
            [sys.executable, str(REGISTRY_DIR / "validate.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn(
            f"PASS: {len(registry['entries'])} Android LLM registry entries",
            completed.stdout,
        )


if __name__ == "__main__":
    unittest.main()
