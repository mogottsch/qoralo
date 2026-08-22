#!/usr/bin/env python3
"""Tests for deterministic experiment-page generation and local navigation."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "generate_experiment_pages.py"
SPEC = importlib.util.spec_from_file_location("experiment_pages", SCRIPT)
assert SPEC and SPEC.loader
pages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pages)


class PageInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.status_headers = 0
        self.primary_sections: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.ids: set[str] = set()
        self.registry_entries: list[str] = []
        self.metrics: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("data-status-header") == "true":
            self.status_headers += 1
        if values.get("data-primary-section"):
            self.primary_sections.append(values["data-primary-section"] or "")
        if values.get("id"):
            self.ids.add(values["id"] or "")
        if values.get("data-registry-entry"):
            self.registry_entries.append(values["data-registry-entry"] or "")
        if values.get("data-metric"):
            self.metrics[values["data-metric"] or ""] = values.get("data-value") or ""
        for attribute in ("href", "src"):
            if values.get(attribute):
                self.links.append((attribute, values[attribute] or ""))


def inspect(path: Path) -> PageInspector:
    parser = PageInspector()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


class ExperimentPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = pages.discover()
        self.assertTrue(self.sources, "expected at least one experiment page source")

    def test_sources_have_exact_primary_structure(self) -> None:
        for source in self.sources:
            with self.subTest(source=source):
                metadata, markdown = pages.parse_source(source)
                pages.inspect_headings(markdown, source)
                self.assertEqual(metadata["experiment"], source.parent.name)

    def test_generated_files_are_current_and_deterministic(self) -> None:
        for source in self.sources:
            with self.subTest(source=source):
                first = pages.build(source)
                second = pages.build(source)
                self.assertEqual(first, second)
                self.assertEqual(first, source.with_name("index.html").read_text(encoding="utf-8"))

    def test_generated_semantics(self) -> None:
        expected = ["experiment-description", "progress", "results"]
        for source in self.sources:
            with self.subTest(source=source):
                parser = inspect(source.with_name("index.html"))
                self.assertEqual(parser.status_headers, 1)
                self.assertEqual(parser.primary_sections, expected)
                for anchor in expected:
                    self.assertIn(anchor, parser.ids)

    def test_local_links_resolve_and_media_is_committed(self) -> None:
        for source in self.sources:
            output = source.with_name("index.html")
            parser = inspect(output)
            for attribute, raw_url in parser.links:
                with self.subTest(source=source, url=raw_url):
                    parts = urlsplit(raw_url)
                    if parts.scheme or raw_url.startswith(("#", "mailto:")):
                        if raw_url.startswith("#"):
                            self.assertIn(raw_url[1:], parser.ids)
                        continue
                    target = (output.parent / unquote(parts.path)).resolve()
                    self.assertTrue(target.exists(), f"broken {attribute}: {raw_url}")
                    if attribute == "src" and target.suffix.lower() == ".wav":
                        tracked = subprocess.run(
                            ["git", "ls-files", "--error-unmatch", str(target.relative_to(REPO))],
                            cwd=REPO,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        self.assertEqual(tracked.returncode, 0, f"media is not committed: {target}")

    def test_registry_snapshots_match_normalized_data(self) -> None:
        registry = json.loads(pages.REGISTRY_PATH.read_text(encoding="utf-8"))
        by_id = {entry["id"]: entry for entry in pages.registry_records(registry)}
        for source in self.sources:
            metadata, _ = pages.parse_source(source)
            if "registry" not in metadata:
                continue
            parser = inspect(source.with_name("index.html"))
            entry_id = metadata["registry"]
            with self.subTest(source=source, registry=entry_id):
                self.assertEqual(parser.registry_entries, [entry_id])
                entry = by_id[entry_id]
                for name, value in parser.metrics.items():
                    self.assertEqual(value, str(entry["metrics"][name]))
                wav = pages.registry_wav(entry)
                audio_sources = [url for attribute, url in parser.links if attribute == "src" and url.endswith(".wav")]
                if wav:
                    self.assertEqual(audio_sources, [f"../../android-benchmarks/{wav['path']}"])
                else:
                    self.assertEqual(audio_sources, [])

    def test_selected_target_and_check_cli(self) -> None:
        source = self.sources[0]
        result = subprocess.run(
            ["python3", str(SCRIPT), "--check", source.parent.name],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_shape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "wrong" / "page.md"
            source.parent.mkdir()
            source.write_text(
                "---\nexperiment: wrong\nstatus: active\nsummary: test\n---\n\n"
                "# Wrong\n\n## Setup\n\nNo.\n",
                encoding="utf-8",
            )
            metadata, markdown = pages.parse_source(source)
            self.assertEqual(metadata["status"], "active")
            with self.assertRaises(ValueError):
                pages.inspect_headings(markdown, source)


if __name__ == "__main__":
    unittest.main()
