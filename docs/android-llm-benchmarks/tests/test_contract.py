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
    def test_current_registry_and_workload_validate(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(REGISTRY_DIR / "validate.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("PASS: 0 Android LLM registry entries", completed.stdout)


if __name__ == "__main__":
    unittest.main()
