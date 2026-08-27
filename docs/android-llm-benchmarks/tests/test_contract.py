#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
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


class DashboardContractTest(unittest.TestCase):
    SORTABLE_COLUMNS = [
        "Experiment",
        "Execution",
        "Model",
        "Route",
        "Quantization",
        "Status",
        "Provider",
        "Setup",
        "TTFT",
        "Prefill",
        "Decode",
        "Peak memory",
        "Output sanity",
    ]

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads((REGISTRY_DIR / "registry.json").read_text(encoding="utf-8"))
        cls.dashboard = (REGISTRY_DIR / "index.html").read_text(encoding="utf-8")
        spec = importlib.util.spec_from_file_location(
            "android_llm_dashboard_generator",
            REGISTRY_DIR / "build_registry.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.generator = module
        cls.generated = module.build(cls.registry)

    def test_committed_dashboard_matches_generator(self) -> None:
        self.assertEqual(self.generated, self.dashboard)

    def test_every_llm_column_is_sortable(self) -> None:
        self.assertEqual(
            len(self.SORTABLE_COLUMNS),
            self.dashboard.count('<button type="button" class="sort-button">'),
        )
        for label in self.SORTABLE_COLUMNS:
            self.assertIn(
                f'<button type="button" class="sort-button">{label}</button>',
                self.dashboard,
            )
        self.assertEqual(
            len(self.registry["entries"]) * len(self.SORTABLE_COLUMNS),
            self.dashboard.count("<td data-sort="),
        )
        self.assertIn("unavailable values last", self.dashboard)
        self.assertIn("aria-sort", self.dashboard)

    def test_dashboard_uses_shared_tts_visual_and_table_controls(self) -> None:
        for token in (
            "--bg:#0f172a",
            "--panel:#172033",
            "--accent:#67e8f9",
            "--focus:#fbbf24",
            'id="routes-fullscreen"',
            'id="routes-sticky-header"',
            ".table-panel:fullscreen",
            ".sort-button::after {content:' ↕'",
        ):
            self.assertIn(token, self.dashboard)

    def test_execution_badges_are_bounded_and_scanable(self) -> None:
        cpu_entries = [
            entry for entry in self.registry["entries"]
            if self.generator.execution(entry)[1] == "cpu"
        ]
        gpu_entries = [
            entry for entry in self.registry["entries"]
            if self.generator.execution(entry)[1] == "gpu"
        ]
        self.assertEqual(
            len(cpu_entries),
            self.dashboard.count('<span class="execution execution-cpu">CPU</span>'),
        )
        self.assertEqual(
            len(gpu_entries),
            self.dashboard.count('<span class="execution execution-gpu">GPU offload</span>'),
        )
        self.assertEqual(
            len(gpu_entries),
            self.dashboard.count('<small class="execution-note">not GPU-exclusive</small>'),
        )
        self.assertNotIn('<span class="execution execution-qnn">', self.dashboard)
        self.assertTrue(
            {"0031", "0032", "0034"}.isdisjoint(
                entry["experiment"] for entry in self.registry["entries"]
            ),
            "Pre-conversion QNN blockers must not become benchmark rows.",
        )
        self.assertEqual(
            len(self.registry["entries"]),
            self.dashboard.count("<summary>Full route + provider</summary>"),
        )

        qnn_probe = json.loads(json.dumps(cpu_entries[0]))
        qnn_probe["runtime"]["provider"] = "QNN HTP provider"
        self.assertEqual("QNN / HTP", self.generator.execution(qnn_probe)[0])
        self.assertIn("does not establish full-HTP", self.generator.execution(qnn_probe)[3])

    def test_dashboard_retains_llm_claim_boundaries(self) -> None:
        self.assertIn("Output sanity is not quality.", self.dashboard)
        self.assertIn("does not establish correctness, grounding, transcript usefulness, or acceptance", self.dashboard)
        self.assertIn("process PSS/VmHWM does not establish total GPU-private or vendor memory", self.dashboard)
        self.assertIn("GPU-offload route, not GPU-exclusive execution", self.dashboard)
        self.assertNotIn("Listening", self.SORTABLE_COLUMNS)
        self.assertNotIn("RTF", self.SORTABLE_COLUMNS)
        self.assertNotIn("Audio", self.SORTABLE_COLUMNS)


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
