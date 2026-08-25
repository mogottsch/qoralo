#!/usr/bin/env python3
"""Generate self-contained experiment pages from docs/experiments/*/page.md.

The renderer intentionally uses only Python's standard library. Run without
arguments to rebuild every discovered page, or pass experiment directory names
(or page.md paths) to rebuild a selection. Use --check in CI to compare the
committed HTML with a fresh rendering without writing files.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]
PAGES_ROOT = REPO / "docs" / "experiments"
REGISTRY_PATH = REPO / "docs" / "android-benchmarks" / "registry.json"
PRIMARY_SECTIONS = ("Experiment description", "Progress", "Results")
STATUSES = {"active", "completed", "blocked", "stopped", "deferred"}


def parse_source(source: Path) -> tuple[dict[str, str], str]:
    text = source.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"{source}: expected front matter starting with ---")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError(f"{source}: unterminated front matter") from exc
    metadata: dict[str, str] = {}
    for number, line in enumerate(lines[1:end], 2):
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"{source}:{number}: expected key: value")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key or not value or key in metadata:
            raise ValueError(f"{source}:{number}: invalid or duplicate metadata")
        metadata[key] = value
    required = {"experiment", "status", "summary"}
    missing = required - metadata.keys()
    if missing:
        raise ValueError(f"{source}: missing metadata: {', '.join(sorted(missing))}")
    if metadata["status"] not in STATUSES:
        raise ValueError(f"{source}: unsupported status {metadata['status']!r}")
    if metadata["experiment"] != source.parent.name:
        raise ValueError(f"{source}: experiment must match its directory name")
    markdown = "\n".join(lines[end + 1 :]).strip() + "\n"
    return metadata, markdown


def slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", re.sub(r"[*`]", "", text).lower()).strip("-")
    return value or "section"


def safe_url(url: str) -> str:
    scheme = urlsplit(url).scheme.lower()
    if scheme and scheme not in {"http", "https", "mailto"}:
        return "#unsafe-link"
    return html.escape(url, quote=True)


def inline(text: str) -> str:
    """Render the deliberately small inline Markdown subset used by pages."""
    escaped = html.escape(text, quote=True)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*", r"<em>\1</em>", escaped)

    def link(match: re.Match[str]) -> str:
        return f'<a href="{safe_url(html.unescape(match.group(2)))}">{match.group(1)}</a>'

    return re.sub(r"\[([^]]+)]\(([^)]+)\)", link, escaped)


def source_revision(experiment: str) -> tuple[str, str]:
    path = f"experiments/{experiment}"
    try:
        value = subprocess.check_output(
            ["git", "log", "-1", "--format=%H%x00%cs", "--", path],
            cwd=REPO,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown", "unknown"
    if "\x00" not in value:
        return "uncommitted", "uncommitted"
    commit, date = value.split("\x00", 1)
    return commit, date


def registry_records(registry: dict[str, object]) -> list[dict[str, object]]:
    """Return visible route records and their explicitly nested remeasurements."""
    records: list[dict[str, object]] = []
    entries = registry.get("entries", [])
    assert isinstance(entries, list)
    for entry in entries:
        assert isinstance(entry, dict)
        records.append(entry)
        remeasurements = entry.get("remeasurements", [])
        if isinstance(remeasurements, list):
            records.extend(item for item in remeasurements if isinstance(item, dict))
    return records


def registry_ids(value: str | None) -> list[str]:
    """Parse the optional comma-separated registry records attached to a page."""
    if not value:
        return []
    ids = [item.strip() for item in value.split(",")]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("registry metadata must contain unique, non-empty IDs")
    return ids


def registry_entry(entry_id: str) -> dict[str, object]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    matches = [entry for entry in registry_records(registry) if entry.get("id") == entry_id]
    if len(matches) != 1:
        raise ValueError(f"registry entry {entry_id!r} was not found exactly once")
    return matches[0]


def registry_wav(entry: dict[str, object]) -> dict[str, object] | None:
    """Read media from a visible route or a nested historical remeasurement."""
    value = entry.get("wav") or entry.get("representative_wav")
    return value if isinstance(value, dict) else None


def format_metric(name: str, value: object) -> str:
    if value is None:
        return "Unavailable"
    if name == "load_seconds":
        return f"{float(value):.3f} s"
    if name in {"cold_rtf", "warm_median_rtf", "first_post_setup_rtf", "proof_run_rtf"}:
        return f"{float(value):.6f}"
    if name in {"peak_pss_bytes", "peak_vm_hwm_bytes"}:
        return f"{int(value) / (1024 * 1024):.1f} MiB"
    return str(value)


def registry_snapshot(
    entry: dict[str, object], *, show_route: bool = False, seen_media: set[str] | None = None
) -> str:
    metrics = entry["metrics"]
    assert isinstance(metrics, dict)
    labels = (
        ("load_seconds", "Setup / load"),
        ("cold_rtf", "First / cold RTF"),
        ("warm_median_rtf", "Warm median RTF"),
        ("peak_pss_bytes", "Peak sampled PSS"),
        ("peak_vm_hwm_bytes", "Process VmHWM"),
    )
    cells = "".join(
        f'<div class="metric" data-metric="{name}" data-value="{html.escape(str(metrics.get(name)))}">'
        f'<span>{label}</span><strong>{format_metric(name, metrics.get(name))}</strong></div>'
        for name, label in labels
    )
    wav = registry_wav(entry)
    audio = ""
    if wav is not None and wav.get("path"):
        media = f"../../android-benchmarks/{wav['path']}"
        if seen_media is not None and media in seen_media:
            audio = (
                '<p class="shared-media"><strong>Shared exact retained media.</strong> '
                'This arm points to the same committed WAV and hash as the matched arm above; '
                f'it is not a second audio artifact or separate review. <a href="{safe_url(media)}">'
                f'<code>{html.escape(str(wav["sha256"])[:12])}…</code></a></p>'
            )
        else:
            audio = (
                '<div class="audio-card"><div><strong>Retained representative</strong>'
                f'<span>{float(wav["duration_seconds"]):.2f} s · {int(wav["sample_rate_hz"]) / 1000:g} kHz · '
                f'<code>{html.escape(str(wav["sha256"])[:12])}…</code></span></div>'
                f'<audio controls preload="metadata" src="{safe_url(media)}">'
                f'<a href="{safe_url(media)}">Listen to the retained WAV</a></audio></div>'
            )
            if seen_media is not None:
                seen_media.add(media)
    else:
        reason = entry.get("missing_reasons", {}).get("wav", "No retained WAV is registered for this route.")
        audio = f'<p class="unavailable"><strong>Audio unavailable.</strong> {inline(str(reason))}</p>'
    route = ""
    if show_route:
        route = f'<strong class="registry-route">{inline(str(entry.get("route", entry["id"])))}</strong>'
    return (
        f'<aside class="registry-card" data-registry-entry="{html.escape(str(entry["id"]))}">'
        f'<div class="eyebrow">Normalized benchmark registry{route}</div>'
        f'<div class="metrics">{cells}</div>{audio}</aside>'
    )


def registry_snapshots(entries: list[dict[str, object]]) -> str:
    seen_media: set[str] = set()
    return "\n".join(
        registry_snapshot(entry, show_route=len(entries) > 1, seen_media=seen_media)
        for entry in entries
    )


def inspect_headings(markdown: str, source: Path) -> tuple[str, list[str]]:
    h1 = re.findall(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    h2 = re.findall(r"^##\s+(.+)$", markdown, flags=re.MULTILINE)
    if len(h1) != 1:
        raise ValueError(f"{source}: expected exactly one level-one heading")
    if h2 != list(PRIMARY_SECTIONS):
        raise ValueError(
            f"{source}: level-two headings must be exactly {', '.join(PRIMARY_SECTIONS)} in order"
        )
    return h1[0], h2


def render_markdown(markdown: str, source: Path, snapshot: str) -> str:
    """Render blocks and wrap the three H2 blocks in semantic sections."""
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_kind: str | None = None
    table_rows: list[list[str]] = []
    in_code = False
    code_lines: list[str] = []
    code_language = ""
    section_open = False

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{inline(' '.join(part.strip() for part in paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            output.append(f"</{list_kind}>")
            list_kind = None

    def flush_table() -> None:
        if not table_rows:
            return
        header, *rows = table_rows
        output.append('<div class="table-wrap"><table><thead><tr>')
        output.extend(f"<th>{inline(cell)}</th>" for cell in header)
        output.append("</tr></thead><tbody>")
        for row in rows:
            output.append("<tr>")
            padded = row + [""] * (len(header) - len(row))
            output.extend(f"<td>{inline(cell)}</td>" for cell in padded[: len(header)])
            output.append("</tr>")
        output.append("</tbody></table></div>")
        table_rows.clear()

    def flush_blocks() -> None:
        flush_paragraph()
        close_list()
        flush_table()

    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        fence = re.match(r"^```(.*)$", line)
        if in_code:
            if fence:
                language = f' class="language-{html.escape(code_language, quote=True)}"' if code_language else ""
                output.append(f"<pre><code{language}>{html.escape(chr(10).join(code_lines))}</code></pre>")
                in_code = False
                code_lines.clear()
                code_language = ""
            else:
                code_lines.append(line)
            index += 1
            continue
        if fence:
            flush_blocks()
            in_code = True
            code_language = fence.group(1).strip()
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        ordered = re.match(r"^\d+\.\s+(.+)$", line)
        quote = re.match(r"^>\s?(.*)$", line)
        is_table = line.startswith("|") and line.endswith("|")

        if is_table:
            flush_paragraph()
            close_list()
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            next_is_separator = index + 1 < len(lines) and bool(
                re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", lines[index + 1])
            )
            if next_is_separator:
                table_rows.append(cells)
                index += 2
                continue
            table_rows.append(cells)
            index += 1
            continue
        flush_table()

        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            text = heading.group(2).strip()
            anchor = slug(text)
            if level == 1:
                index += 1
                continue
            if level == 2:
                if section_open:
                    output.append("</section>")
                output.append(f'<section class="primary-section" id="{anchor}" data-primary-section="{anchor}">')
                section_open = True
                output.append(f'<h2>{inline(text)}<a class="anchor" href="#{anchor}" aria-label="Link to {html.escape(text)}">#</a></h2>')
                if text == "Results" and snapshot:
                    output.append(snapshot)
            else:
                output.append(f'<h{level} id="{anchor}">{inline(text)}<a class="anchor" href="#{anchor}" aria-label="Link to {html.escape(text)}">#</a></h{level}>')
        elif bullet or ordered:
            flush_paragraph()
            kind = "ul" if bullet else "ol"
            if list_kind != kind:
                close_list()
                output.append(f"<{kind}>")
                list_kind = kind
            output.append(f"<li>{inline((bullet or ordered).group(1))}</li>")
        elif quote:
            flush_paragraph()
            close_list()
            output.append(f"<blockquote>{inline(quote.group(1))}</blockquote>")
        elif not line.strip():
            flush_paragraph()
            close_list()
        else:
            close_list()
            paragraph.append(line)
        index += 1

    if in_code:
        raise ValueError(f"{source}: unterminated fenced code block")
    flush_blocks()
    if section_open:
        output.append("</section>")
    return "\n".join(output)


def build(source: Path) -> str:
    metadata, markdown = parse_source(source)
    title, _ = inspect_headings(markdown, source)
    entries = [registry_entry(entry_id) for entry_id in registry_ids(metadata.get("registry"))]
    if any(str(entry.get("experiment")) != metadata["experiment"][:4] for entry in entries):
        raise ValueError(f"{source}: registry entry belongs to another experiment")
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    commit, update_date = source_revision(metadata["experiment"])
    body = render_markdown(markdown, source, registry_snapshots(entries))
    experiment_url = f"../../../experiments/{metadata['experiment']}/"
    dashboard_url = "../../android-benchmarks/index.html"
    status_label = metadata["status"].capitalize()
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="robots" content="noindex,nofollow,noarchive">
<link rel="icon" href="data:,">
<title>{html.escape(title)} | experiment</title>
<style>
:root {{ --bg:#eeeae2; --paper:#fffdf8; --ink:#18201e; --muted:#66706c; --line:#d8d4ca; --accent:#006c60; --accent-2:#a44217; --soft:#e5f2ee; --code:#efede7; --shadow:0 18px 60px rgba(30,42,37,.09); }}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; scroll-padding-top:88px; }}
body {{ margin:0; background:linear-gradient(135deg,#e7eee9 0,var(--bg) 42%,#eee6dc 100%); color:var(--ink); font:16px/1.68 system-ui,-apple-system,"Segoe UI",sans-serif; }}
a {{ color:var(--accent); text-underline-offset:3px; }}
a:focus-visible, audio:focus-visible {{ outline:3px solid #f09b65; outline-offset:3px; border-radius:4px; }}
.topbar {{ position:sticky; top:0; z-index:10; border-bottom:1px solid color-mix(in srgb,var(--line) 85%,transparent); background:color-mix(in srgb,var(--paper) 92%,transparent); backdrop-filter:blur(12px); }}
.topbar-inner {{ max-width:1120px; margin:auto; display:flex; align-items:center; justify-content:space-between; gap:18px; padding:13px 24px; }}
.brand {{ color:var(--ink); font-weight:780; text-decoration:none; letter-spacing:-.02em; }}
nav {{ display:flex; gap:6px; flex-wrap:wrap; }}
nav a {{ padding:7px 10px; color:var(--muted); border-radius:999px; font-size:13px; font-weight:650; text-decoration:none; }}
nav a:hover {{ color:var(--accent); background:var(--soft); }}
.shell {{ max-width:1120px; margin:auto; padding:clamp(24px,5vw,66px) 24px 80px; }}
.status-header {{ position:relative; overflow:hidden; padding:clamp(26px,5vw,54px); border:1px solid var(--line); border-radius:24px; background:var(--paper); box-shadow:var(--shadow); }}
.status-header::after {{ content:""; position:absolute; width:230px; height:230px; right:-90px; top:-105px; border-radius:50%; background:var(--soft); }}
.kicker {{ position:relative; z-index:1; display:flex; align-items:center; gap:10px; margin-bottom:18px; color:var(--muted); font-size:13px; font-weight:760; text-transform:uppercase; letter-spacing:.09em; }}
.status {{ display:inline-flex; gap:7px; align-items:center; padding:5px 10px; border:1px solid var(--line); border-radius:999px; color:var(--ink); background:var(--paper); letter-spacing:.04em; }}
.status::before {{ content:""; width:8px; height:8px; border-radius:50%; background:var(--accent-2); }}
h1 {{ position:relative; z-index:1; max-width:18ch; margin:0; font-size:clamp(36px,7vw,70px); line-height:.99; letter-spacing:-.048em; }}
.summary {{ position:relative; z-index:1; max-width:70ch; margin:24px 0 0; font-size:clamp(17px,2vw,21px); color:var(--muted); }}
.header-links {{ position:relative; z-index:1; display:flex; flex-wrap:wrap; gap:9px; margin-top:25px; }}
.header-links a {{ padding:9px 13px; border:1px solid var(--line); border-radius:9px; background:var(--paper); font-size:14px; font-weight:680; text-decoration:none; }}
.provenance {{ position:relative; z-index:1; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 22px; margin:30px 0 0; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace; }}
.provenance span {{ min-width:0; overflow-wrap:anywhere; }}
article {{ max-width:880px; margin:18px auto 0; }}
.primary-section {{ margin-top:18px; padding:clamp(24px,5vw,48px); border:1px solid var(--line); border-radius:20px; background:var(--paper); }}
h2 {{ margin:0 0 19px; font-size:clamp(26px,4vw,38px); line-height:1.1; letter-spacing:-.025em; }}
h3 {{ margin:34px 0 10px; color:var(--accent); font-size:20px; line-height:1.25; }}
.anchor {{ margin-left:9px; opacity:0; font-weight:400; text-decoration:none; }}
h2:hover .anchor,h3:hover .anchor,.anchor:focus {{ opacity:.5; }}
p,ul,ol,blockquote {{ max-width:76ch; }}
li {{ margin:7px 0; }}
code {{ padding:2px 5px; border-radius:5px; background:var(--code); font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace; overflow-wrap:anywhere; }}
pre {{ overflow:auto; padding:18px; border:1px solid var(--line); border-radius:10px; background:var(--code); }}
pre code {{ padding:0; background:none; overflow-wrap:normal; }}
blockquote {{ margin:22px 0; padding:12px 18px; border-left:4px solid var(--accent-2); background:#fbf1e9; color:#62412f; }}
.table-wrap {{ overflow:auto; margin:20px 0; border:1px solid var(--line); border-radius:12px; }}
table {{ width:100%; min-width:620px; border-collapse:collapse; }}
th,td {{ padding:12px 14px; text-align:left; vertical-align:top; border-bottom:1px solid var(--line); }}
th {{ background:var(--soft); color:#174b45; font-size:12px; letter-spacing:.04em; text-transform:uppercase; }}
tr:last-child td {{ border-bottom:0; }}
.registry-card {{ margin:4px 0 30px; padding:18px; border:1px solid #b8d5cc; border-radius:14px; background:var(--soft); }}
.eyebrow {{ margin-bottom:13px; color:var(--accent); font-size:11px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }}
.registry-route {{ display:block; margin-top:4px; color:var(--ink); font-size:13px; letter-spacing:0; text-transform:none; }}
.metrics {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; }}
.metric {{ padding:10px; border:1px solid color-mix(in srgb,var(--accent) 22%,transparent); border-radius:9px; background:var(--paper); }}
.metric span,.audio-card span {{ display:block; color:var(--muted); font-size:11px; line-height:1.35; }}
.metric strong {{ display:block; margin-top:4px; font-size:15px; }}
.audio-card {{ display:grid; grid-template-columns:minmax(160px,1fr) minmax(240px,2fr); align-items:center; gap:18px; margin-top:12px; padding:11px; border-radius:9px; background:var(--paper); }}
audio {{ width:100%; min-height:40px; }}
.unavailable,.shared-media {{ margin:12px 0 0; padding:11px; border-radius:9px; background:var(--paper); font-size:13px; }}
footer {{ max-width:880px; margin:24px auto 0; color:var(--muted); font-size:12px; text-align:center; }}
@media (max-width:760px) {{ .topbar-inner {{ align-items:flex-start; flex-direction:column; padding:10px 16px; }} nav {{ width:100%; overflow:auto; flex-wrap:nowrap; }} .shell {{ padding:18px 10px 55px; }} .status-header,.primary-section {{ border-radius:14px; }} .provenance {{ grid-template-columns:1fr; }} .metrics {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .audio-card {{ grid-template-columns:1fr; }} }}
@media (prefers-color-scheme:dark) {{ :root {{ --bg:#111614; --paper:#19201e; --ink:#eef4f1; --muted:#aeb9b4; --line:#39443f; --accent:#70d7c5; --accent-2:#f09b65; --soft:#19332e; --code:#252c29; --shadow:none; }} body {{ background:linear-gradient(135deg,#15231f,var(--bg)); }} blockquote {{ background:#35271f; color:#efd8c8; }} th {{ color:#bce7df; }} }}
@media print {{ .topbar {{ position:relative; }} body {{ background:white; }} .shell {{ padding:16px; }} .status-header,.primary-section {{ box-shadow:none; break-inside:avoid; }} }}
</style>
</head>
<body>
<header class="topbar"><div class="topbar-inner"><a class="brand" href="{dashboard_url}">VibeVoice Android research</a><nav aria-label="Experiment sections"><a href="#experiment-description">Description</a><a href="#progress">Progress</a><a href="#results">Results</a></nav></div></header>
<main class="shell">
<header class="status-header" data-status-header="true">
<div class="kicker"><span>Experiment {html.escape(metadata['experiment'][:4])}</span><span class="status">{status_label}</span></div>
<h1>{inline(title)}</h1>
<p class="summary">{inline(metadata['summary'])}</p>
<div class="header-links"><a href="{safe_url(experiment_url)}">Owning experiment files</a><a href="{dashboard_url}">Benchmark overview</a></div>
<div class="provenance"><span>last committed evidence update: {html.escape(update_date)}</span><span>evidence commit: {html.escape(commit)}</span><span>page source: docs/experiments/{html.escape(metadata['experiment'])}/page.md</span><span>page source sha256: {source_digest}</span></div>
</header>
<article>{body}</article>
<footer>Generated deterministically from <code>page.md</code> by <code>scripts/generate_experiment_pages.py</code>. The linked experiment files remain the measurement authority.</footer>
</main>
</body>
</html>
'''


def discover() -> list[Path]:
    return sorted(PAGES_ROOT.glob("*/page.md"))


def resolve_targets(targets: list[str]) -> list[Path]:
    if not targets:
        return discover()
    resolved: list[Path] = []
    for target in targets:
        candidate = Path(target)
        if not candidate.is_absolute():
            direct = REPO / candidate
            candidate = direct if direct.exists() else PAGES_ROOT / target / "page.md"
        if candidate.is_dir():
            candidate /= "page.md"
        if not candidate.is_file():
            raise ValueError(f"page source not found: {target}")
        resolved.append(candidate.resolve())
    return sorted(set(resolved))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", help="experiment directory names or page.md paths")
    parser.add_argument("--check", action="store_true", help="fail if generated HTML is missing or stale")
    parser.add_argument("--list", action="store_true", help="list selected sources without generating")
    args = parser.parse_args(argv)
    try:
        sources = resolve_targets(args.targets)
        if not sources:
            raise ValueError("no experiment page sources found")
        if args.list:
            for source in sources:
                print(source.relative_to(REPO))
            return 0
        stale: list[Path] = []
        for source in sources:
            output = source.with_name("index.html")
            rendered = build(source)
            if args.check:
                if not output.exists() or output.read_text(encoding="utf-8") != rendered:
                    stale.append(output)
            else:
                output.write_text(rendered, encoding="utf-8")
                print(output.relative_to(REPO))
        if stale:
            print("stale generated pages:", file=sys.stderr)
            for path in stale:
                print(f"  {path.relative_to(REPO)}", file=sys.stderr)
            return 1
        return 0
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
