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
        self.registry_metrics: list[tuple[str, str, str]] = []
        self.current_registry_entry: str | None = None
        self.shared_media_notes = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("data-status-header") == "true":
            self.status_headers += 1
        if values.get("data-primary-section"):
            self.primary_sections.append(values["data-primary-section"] or "")
        if values.get("id"):
            self.ids.add(values["id"] or "")
        if values.get("data-registry-entry"):
            self.current_registry_entry = values["data-registry-entry"] or ""
            self.registry_entries.append(self.current_registry_entry)
        if "shared-media" in (values.get("class") or "").split():
            self.shared_media_notes += 1
        if values.get("data-metric"):
            assert self.current_registry_entry is not None
            self.registry_metrics.append(
                (
                    self.current_registry_entry,
                    values["data-metric"] or "",
                    values.get("data-value") or "",
                )
            )
        for attribute in ("href", "src"):
            if values.get(attribute):
                self.links.append((attribute, values[attribute] or ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "aside" and self.current_registry_entry is not None:
            self.current_registry_entry = None


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

    def test_description_opens_with_narrative_paragraph(self) -> None:
        for source in self.sources:
            with self.subTest(source=source):
                _, markdown = pages.parse_source(source)
                description = markdown.split("## Experiment description", 1)[1].split("## Progress", 1)[0]
                opening = description.strip().split("\n\n", 1)[0].strip()
                self.assertGreaterEqual(len(opening), 80)
                self.assertFalse(opening.startswith(("#", "-", "*", "|", ">", "```")))

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
        for source in self.sources:
            metadata, _ = pages.parse_source(source)
            entry_ids = pages.registry_ids(metadata.get("registry"))
            if not entry_ids:
                continue
            benchmark = metadata.get("benchmark", "android-tts")
            registry_path = pages.BENCHMARKS[benchmark][0]
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            by_id = {entry["id"]: entry for entry in pages.registry_records(registry)}
            parser = inspect(source.with_name("index.html"))
            with self.subTest(source=source, registry=entry_ids):
                self.assertEqual(parser.registry_entries, entry_ids)
                for entry_id, name, value in parser.registry_metrics:
                    entry = by_id[entry_id]
                    if benchmark == "android-llm":
                        medium = entry["aggregates"]["by_tier"]["medium"]
                        expected = {
                            "setup_seconds": entry["setup"]["seconds"],
                            "medium_ttft_seconds": medium["median_request_to_first_token_seconds"],
                            "medium_prefill_tokens_per_second": medium["median_prefill_tokens_per_second"],
                            "medium_decode_tokens_per_second": medium["median_decode_tokens_per_second"],
                            "peak_pss_bytes": entry["memory"]["peak_pss_bytes"],
                        }[name]
                    else:
                        expected = entry["metrics"][name]
                    self.assertEqual(value, str(expected))
                expected_audio = []
                seen_audio: set[str] = set()
                wav_records = 0
                if benchmark == "android-tts":
                    for entry_id in entry_ids:
                        wav = pages.registry_wav(by_id[entry_id])
                        if wav:
                            wav_records += 1
                            media = f"../../android-benchmarks/{wav['path']}"
                            if media not in seen_audio:
                                expected_audio.append(media)
                                seen_audio.add(media)
                audio_sources = [
                    url
                    for attribute, url in parser.links
                    if attribute == "src" and url.endswith(".wav")
                ]
                self.assertEqual(audio_sources, expected_audio)
                self.assertEqual(parser.shared_media_notes, wav_records - len(expected_audio))

    def test_selected_target_and_check_cli(self) -> None:
        source = self.sources[0]
        result = subprocess.run(
            ["python3", str(SCRIPT), "--check", source.parent.name],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_android_llm_metadata_selects_llm_overview_without_changing_tts_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            markdown = (
                "# Experiment 9999 — Generator route test\n\n"
                "## Experiment description\n\n"
                "This temporary narrative is intentionally long enough to model a useful experiment opening paragraph.\n\n"
                "## Progress\n\nPrepared.\n\n"
                "## Results\n\nNo measurement claims.\n"
            )
            llm_source = root / "9999-llm" / "page.md"
            llm_source.parent.mkdir()
            llm_source.write_text(
                "---\nexperiment: 9999-llm\nstatus: active\nsummary: LLM route test.\n"
                "benchmark: android-llm\n---\n\n" + markdown,
                encoding="utf-8",
            )
            tts_source = root / "9999-tts" / "page.md"
            tts_source.parent.mkdir()
            tts_source.write_text(
                "---\nexperiment: 9999-tts\nstatus: active\nsummary: TTS route test.\n---\n\n"
                + markdown,
                encoding="utf-8",
            )
            llm_html = pages.build(llm_source)
            tts_html = pages.build(tts_source)
            self.assertIn('href="../../android-llm-benchmarks/index.html"', llm_html)
            self.assertNotIn('href="../../android-benchmarks/index.html"', llm_html)
            self.assertIn('href="../../android-benchmarks/index.html"', tts_html)
            self.assertNotIn('href="../../android-llm-benchmarks/index.html"', tts_html)

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
