#!/usr/bin/env python3
"""Build readable HTML mirrors of the project history and current plan.

The Markdown files remain the sources of truth. This script uses only Python's
standard library, so the mirrors need no project environment to regenerate.
"""
from __future__ import annotations

import hashlib
import html
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = (
    REPO / "docs" / "history.md",
    REPO / "docs" / "plan.md",
)


def inline(text: str) -> str:
    """Render the small inline Markdown subset used by the plan."""
    escaped = html.escape(text, quote=True)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(
        r"\[([^]]+)]\(([^)]+)\)",
        r'<a href="\2">\1</a>',
        escaped,
    )
    return escaped


def slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value or "section"


def source_date(source: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "log", "-1", "--format=%cs", "--", str(source.relative_to(REPO))],
            cwd=REPO,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or "uncommitted"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def render_markdown(markdown: str) -> tuple[str, list[tuple[int, str, str]]]:
    lines = markdown.splitlines()
    output: list[str] = []
    headings: list[tuple[int, str, str]] = []
    used_ids: dict[str, int] = {}
    paragraph: list[str] = []
    list_kind: str | None = None
    table_rows: list[list[str]] = []

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
        output.append("<div class=\"table-wrap\"><table><thead><tr>")
        output.extend(f"<th>{inline(cell)}</th>" for cell in header)
        output.append("</tr></thead><tbody>")
        for row in rows:
            output.append("<tr>")
            output.extend(f"<td>{inline(cell)}</td>" for cell in row)
            output.append("</tr>")
        output.append("</tbody></table></div>")
        table_rows.clear()

    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        ordered = re.match(r"^\d+\.\s+(.+)$", line)
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
            base = slug(re.sub(r"[*`]", "", text))
            count = used_ids.get(base, 0)
            used_ids[base] = count + 1
            anchor = base if count == 0 else f"{base}-{count + 1}"
            headings.append((level, text, anchor))
            output.append(f"<h{level} id=\"{anchor}\">{inline(text)}<a class=\"anchor\" href=\"#{anchor}\" aria-label=\"Link to this section\">#</a></h{level}>")
        elif bullet or ordered:
            flush_paragraph()
            kind = "ul" if bullet else "ol"
            if list_kind != kind:
                close_list()
                output.append(f"<{kind}>")
                list_kind = kind
            output.append(f"<li>{inline((bullet or ordered).group(1))}</li>")
        elif not line.strip():
            flush_paragraph()
            close_list()
        else:
            close_list()
            paragraph.append(line)
        index += 1

    flush_paragraph()
    close_list()
    flush_table()
    return "\n".join(output), headings


def build(source: Path) -> str:
    markdown = source.read_text(encoding="utf-8")
    digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    body, headings = render_markdown(markdown)
    title = next((text for level, text, _ in headings if level == 1), source.stem.title())
    relative_source = source.relative_to(REPO)
    output_name = source.with_suffix(".html").name
    navigation = "\n".join(
        f'<a class="toc-level-{level}" href="#{anchor}">{inline(text)}</a>'
        for level, text, anchor in headings
        if level <= 3
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>{html.escape(title)} | visual mirror</title>
<style>
:root {{ --bg:#f4f2ed; --paper:#fffefa; --ink:#20231f; --muted:#686d65; --line:#d9d5cb; --accent:#225e52; --accent-soft:#e3efeb; --warn:#8b5a16; --warn-soft:#fff2d5; --code:#f0eee8; }}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.62 system-ui,-apple-system,"Segoe UI",sans-serif; }}
a {{ color:var(--accent); }}
.shell {{ max-width:1280px; margin:0 auto; display:grid; grid-template-columns:250px minmax(0,1fr); gap:24px; padding:24px; }}
nav {{ position:sticky; top:18px; align-self:start; max-height:calc(100vh - 36px); overflow:auto; padding:18px; background:var(--paper); border:1px solid var(--line); border-radius:10px; }}
nav strong {{ display:block; margin-bottom:10px; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
nav a {{ display:block; padding:5px 7px; border-radius:5px; color:var(--muted); text-decoration:none; font-size:13px; line-height:1.3; }}
nav a:hover {{ color:var(--accent); background:var(--accent-soft); }}
nav .toc-level-1 {{ display:none; }}
nav .toc-level-3 {{ padding-left:19px; font-size:12px; }}
main {{ min-width:0; background:var(--paper); border:1px solid var(--line); border-radius:10px; padding:clamp(24px,5vw,62px); box-shadow:0 12px 36px rgba(38,39,34,.06); }}
.mirror-note {{ margin:0 0 34px; padding:14px 16px; border-left:4px solid var(--warn); background:var(--warn-soft); color:#5e451e; }}
.mirror-note strong {{ display:block; }}
.meta {{ display:flex; flex-wrap:wrap; gap:8px 18px; margin-top:6px; font:12px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace; color:#79623e; }}
h1 {{ margin:0 0 8px; font-size:clamp(34px,6vw,58px); line-height:1.03; letter-spacing:-.035em; }}
h2 {{ margin:54px 0 14px; padding-top:18px; border-top:1px solid var(--line); font-size:26px; line-height:1.2; }}
h3 {{ margin:32px 0 10px; font-size:18px; color:var(--accent); }}
.anchor {{ margin-left:8px; opacity:0; font-weight:400; text-decoration:none; }}
h1:hover .anchor,h2:hover .anchor,h3:hover .anchor {{ opacity:.45; }}
p {{ max-width:78ch; }}
ul,ol {{ max-width:82ch; padding-left:24px; }}
li {{ margin:6px 0; padding-left:3px; }}
strong {{ font-weight:720; }}
code {{ padding:2px 5px; border-radius:4px; background:var(--code); font:13px ui-monospace,SFMono-Regular,Consolas,monospace; }}
.table-wrap {{ overflow:auto; margin:18px 0; border:1px solid var(--line); border-radius:8px; }}
table {{ width:100%; border-collapse:collapse; min-width:650px; }}
th,td {{ padding:11px 13px; text-align:left; vertical-align:top; border-bottom:1px solid var(--line); }}
th {{ background:var(--accent-soft); color:#17463d; font-size:12px; text-transform:uppercase; letter-spacing:.035em; }}
tr:last-child td {{ border-bottom:0; }}
.source-footer {{ margin-top:58px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }}
@media (max-width:850px) {{ .shell {{ display:block; padding:10px; }} nav {{ position:relative; top:0; max-height:none; margin-bottom:10px; }} main {{ padding:24px 20px; }} }}
@media print {{ body {{ background:white; }} .shell {{ display:block; padding:0; }} nav {{ display:none; }} main {{ border:0; box-shadow:none; padding:0; }} .mirror-note {{ border:1px solid #bbb; }} }}
</style>
</head>
<body>
<div class="shell">
<nav aria-label="Document sections"><strong>Sections</strong>{navigation}</nav>
<main>
<div class="mirror-note"><strong>Visual mirror of <code>{relative_source}</code></strong>The Markdown file is the source of truth.<div class="meta"><span>source commit date: {source_date(source)}</span><span>source sha256: {digest[:16]}…</span></div></div>
<article>{body}</article>
<footer class="source-footer">Generated as <code>{output_name}</code> by <code>scripts/build_docs_html.py</code>. Edit <code>{relative_source}</code>, then regenerate both human-readable mirrors.</footer>
</main>
</div>
</body>
</html>
"""


def main() -> None:
    for source in SOURCES:
        output = source.with_suffix(".html")
        output.write_text(build(source), encoding="utf-8")
        print(output.relative_to(REPO))


if __name__ == "__main__":
    main()
