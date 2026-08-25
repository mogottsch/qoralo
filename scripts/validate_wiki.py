#!/usr/bin/env python3
"""Validate the repository-backed Obsidian wiki without external packages."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "docs" / "wiki"
REQUIRED = {"Home.md", "README.md", "index.md", "log.md"}
LINK = re.compile(r"(?<!!)\[[^]]+]\(([^)]+)\)")
TOP_LEVEL_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:\s+.*)?$")


def frontmatter(path: Path, text: str) -> set[str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("unterminated YAML frontmatter") from exc
    keys = {
        match.group(1)
        for line in lines[1:end]
        if not line.startswith((" ", "\t")) and (match := TOP_LEVEL_KEY.match(line))
    }
    missing = {"title", "kind", "project"} - keys
    if missing:
        raise ValueError(f"missing frontmatter keys: {', '.join(sorted(missing))}")
    return keys


def local_target(source: Path, raw: str) -> Path | None:
    parts = urlsplit(raw)
    if parts.scheme or raw.startswith(("#", "mailto:")):
        return None
    target = (source.parent / unquote(parts.path)).resolve()
    try:
        target.relative_to(WIKI.resolve())
    except ValueError as exc:
        raise ValueError(f"link escapes the vault: {raw}") from exc
    return target


def main() -> int:
    errors: list[str] = []
    pages = sorted(WIKI.rglob("*.md"))
    if not WIKI.is_dir():
        errors.append(f"missing vault: {WIKI.relative_to(ROOT)}")
    missing_required = REQUIRED - {path.name for path in pages if path.parent == WIKI}
    if missing_required:
        errors.append(f"missing required root pages: {', '.join(sorted(missing_required))}")

    indexed: set[Path] = set()
    index_path = WIKI / "index.md"
    for path in pages:
        text = path.read_text(encoding="utf-8")
        try:
            frontmatter(path, text)
        except ValueError as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
        if text.count("\n# ") + int(text.startswith("# ")) != 1:
            errors.append(f"{path.relative_to(ROOT)}: expected exactly one level-one heading")
        if path.parent.name == "concepts":
            body = text.split("---", 2)[-1]
            if not re.search(r"^>\s+\S", body, flags=re.MULTILINE):
                errors.append(f"{path.relative_to(ROOT)}: concept needs a plain-language opening quote")
        for match in LINK.finditer(text):
            raw = match.group(1).strip()
            try:
                target = local_target(path, raw)
            except ValueError as exc:
                errors.append(f"{path.relative_to(ROOT)}: {exc}")
                continue
            if target is None:
                continue
            if not target.exists():
                errors.append(f"{path.relative_to(ROOT)}: broken link: {raw}")
            if path == index_path:
                indexed.add(target)

    expected_indexed = set(pages) - {index_path}
    for path in sorted(expected_indexed - indexed):
        errors.append(f"{path.relative_to(ROOT)}: page is missing from docs/wiki/index.md")

    log = WIKI / "log.md"
    if log.exists() and not re.search(r"^## \[\d{4}-\d{2}-\d{2}] ", log.read_text(), re.MULTILINE):
        errors.append("docs/wiki/log.md: expected at least one dated log entry")

    if errors:
        print("Wiki validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"PASS: {len(pages)} wiki pages; frontmatter, links, index coverage, and concept openings valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
