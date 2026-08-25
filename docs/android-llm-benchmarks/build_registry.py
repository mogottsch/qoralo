#!/usr/bin/env python3
"""Generate the static Android LLM benchmark dashboard from registry.json."""
from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REGISTRY = HERE / "registry.json"
OUTPUT = HERE / "index.html"


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def seconds(value) -> str:
    return "—" if value is None else f"{value:.3f} s"


def rate(value) -> str:
    return "—" if value is None else f"{value:.2f} tok/s"


def memory(entry: dict) -> str:
    data = entry["memory"]
    if data["peak_pss_bytes"] is not None:
        return f"{data['peak_pss_bytes'] / (1024 ** 2):.1f} MiB PSS"
    if data["peak_vm_hwm_bytes"] is not None:
        return f"{data['peak_vm_hwm_bytes'] / (1024 ** 2):.1f} MiB VmHWM"
    return "—"


def sanity(entry: dict) -> str:
    values = [run["output_sanity"]["looks_sensible"] for run in entry["runs"]]
    sensible = sum(value is True for value in values)
    failed = sum(value is False for value in values)
    unchecked = sum(value is None for value in values)
    if failed:
        return f"{failed} issue / {sensible} sensible / {unchecked} unchecked"
    if sensible:
        return f"{sensible} sensible / {unchecked} unchecked"
    return f"{unchecked} unchecked"


def render_rows(entries: list[dict]) -> str:
    rows: list[str] = []
    for entry in entries:
        medium = entry["aggregates"]["by_tier"]["medium"]
        identity = entry["model_identity"]
        model = f'<a href="{esc(identity["url"])}">{esc(entry["model"])}</a>'
        rows.append(
            "<tr>"
            f"<td>{model}<small>{esc(entry['quantization']['name'])}</small></td>"
            f"<td>{esc(entry['route'])}<small>{esc(entry['runtime']['name'])} {esc(entry['runtime']['version'])} · {esc(entry['runtime']['provider'])}</small></td>"
            f"<td>{esc(entry['execution_target'])}<small>{esc(entry['attempt_status'])}</small></td>"
            f"<td>{seconds(entry['setup']['seconds'])}</td>"
            f"<td>{seconds(medium['median_request_to_first_token_seconds'])}<small>medium tier median</small></td>"
            f"<td>{rate(medium['median_prefill_tokens_per_second'])}<small>medium tier median</small></td>"
            f"<td>{rate(medium['median_decode_tokens_per_second'])}<small>medium tier median</small></td>"
            f"<td>{esc(memory(entry))}</td>"
            f"<td>{esc(sanity(entry))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build(registry: dict) -> str:
    entries = registry["entries"]
    if entries:
        content = f"""
<div class="table-wrap"><table>
<thead><tr><th>Model</th><th>Route</th><th>Target</th><th>Setup</th><th>TTFT</th><th>Prefill</th><th>Decode</th><th>Peak memory</th><th>Output sanity</th></tr></thead>
<tbody>{render_rows(entries)}</tbody>
</table></div>
"""
    else:
        content = """
<section class="empty">
<h2>No committed LLM benchmark rows yet</h2>
<p>The protocol, validator, and publication path are ready. This dashboard will remain empty until a numbered experiment commits normalized route evidence.</p>
</section>
"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<link rel="icon" href="data:,">
<title>Android LLM benchmarks</title>
<style>
:root {{ --bg:#f2f4f7; --paper:#fff; --ink:#1c2430; --muted:#647083; --line:#d8dee8; --accent:#4b3fb2; --soft:#eeecff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1440px; margin:0 auto; padding:clamp(20px,4vw,56px); }}
h1 {{ margin:0; font-size:clamp(34px,6vw,62px); line-height:1; letter-spacing:-.04em; }}
.lede {{ max-width:78ch; color:var(--muted); font-size:17px; }}
.notice {{ margin:26px 0; padding:16px 18px; border-left:4px solid var(--accent); background:var(--soft); }}
a {{ color:var(--accent); }}
.links {{ display:flex; flex-wrap:wrap; gap:16px; margin:18px 0 32px; }}
.empty {{ margin-top:38px; padding:34px; border:1px solid var(--line); border-radius:12px; background:var(--paper); }}
.empty h2 {{ margin-top:0; }}
.table-wrap {{ overflow:auto; margin-top:30px; border:1px solid var(--line); border-radius:12px; background:var(--paper); }}
table {{ border-collapse:collapse; width:100%; min-width:1180px; }}
th,td {{ padding:13px 14px; text-align:left; vertical-align:top; border-bottom:1px solid var(--line); }}
th {{ position:sticky; top:0; background:var(--soft); color:#342a87; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
td small {{ display:block; margin-top:4px; color:var(--muted); }}
footer {{ margin-top:36px; color:var(--muted); font-size:13px; }}
code {{ padding:2px 5px; border-radius:4px; background:#e8ebf0; }}
</style>
</head>
<body><main>
<h1>Android LLM benchmarks</h1>
<p class="lede">Generic fixed-prompt inference measurements for local Android language-model routes. The dashboard keeps setup, TTFT, prefill, decode, memory, provenance, and raw-output sanity separate.</p>
<div class="notice"><strong>Output sanity is not quality.</strong> <code>looks_sensible</code> only screens one exact output hash for obvious corruption or gibberish. It does not establish correctness, grounding, transcript usefulness, or acceptance.</div>
<div class="links"><a href="registry.json">Registry JSON</a><a href="schema.json">Schema</a><a href="README.md">Registry documentation</a><a href="../../protocols/android-llm-benchmark/README.md">Benchmark protocol</a><a href="../android-benchmarks/index.html">TTS benchmarks</a></div>
{content}
<footer>{len(entries)} normalized route entries. Generated by <code>docs/android-llm-benchmarks/build_registry.py</code> from committed registry evidence.</footer>
</main></body></html>
"""


def main() -> None:
    subprocess.run([sys.executable, str(HERE / "validate.py")], cwd=ROOT, check=True)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    OUTPUT.write_text(build(registry), encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
