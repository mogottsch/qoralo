#!/usr/bin/env python3
"""Regenerate the 'What we tried' table in docs/qoralo-blog/index.html from benchmark-table.json.

benchmark-table.json is Thomas's evidence packet (unchanged). The page shows one row per model,
CPU and NPU side by side, because that is the only matched comparison (same model, same test text).
Run from the repository root:  python3 docs/qoralo-blog/evidence/build-table.py
"""
import json, re
from pathlib import Path

root = Path("docs/qoralo-blog")
rows = {r["id"]: r for r in json.loads((root / "evidence/benchmark-table.json").read_text())["rows"]}

def rtf(i):
    r = rows[i]["speed"]["rtf"]
    assert r is not None, i
    return r

# (model, cpu cell, npu cell, what happened). A number cell is ("rtf", row id); a word cell is ("word", text, css class).
LINES = [
    ("Supertonic 3", ("rtf", "supertonic-short-cpu"), ("rtf", "supertonic-short-htp"), "Both tested samples sounded good"),
    ("Pocket TTS", ("rtf", "pocket-short-cpu"), ("rtf", "pocket-short-htp"), "Both tested samples sounded good"),
    ("Kokoro", ("rtf", "kokoro-fixed-cpu"), ("word", "blocked", "blocked"), "The HTP version failed a check before it reached the phone"),
    ("MOSS-TTS-Nano", ("rtf", "moss-short-cpu"), ("word", "blocked", "blocked"), "The HTP runtime failed to initialize on the phone"),
    ("VibeVoice 1.5B", ("word", "no speech", "blocked"), ("word", "not tried", "muted"), "Silent, incomplete output; the package alone was 9.1 GB"),
]
for _, c, n, _ in LINES:
    for cell in (c, n):
        if cell[0] == "rtf":
            assert rows[cell[1]]["speed"]["display"].endswith("warm"), cell  # only warm medians are shown

def cell(label, c, cls):
    if c[0] == "rtf":
        v = rtf(c[1])
        return f'<td class="{cls}" data-label="{label}" data-rtf="{v}">{v:.2f}</td>'
    return f'<td class="{c[2]}" data-label="{label}">{c[1]}</td>'

body = "\n".join(
    f'            <tr role="row"><th scope="row" role="rowheader">{m}</th>{cell("CPU RTF", c, "cpu")}{cell("NPU RTF", n, "npu")}<td data-label="What happened">{w}</td></tr>'
    for m, c, n, w in LINES
)
html = f'''<!-- table:start -->
        <div class="table-wrap">
          <table class="bench" role="table">
            <caption class="sr-only">Real-time factor (RTF, lower is faster) of five speech models on the phone's CPU and NPU</caption>
            <thead><tr role="row"><th scope="col" role="columnheader">Model</th><th scope="col" role="columnheader" class="cpu">CPU RTF</th><th scope="col" role="columnheader" class="npu">NPU RTF</th><th scope="col" role="columnheader">What happened</th></tr></thead>
            <tbody>
{body}
            </tbody>
          </table>
        </div>
<!-- table:end -->'''
p = root / "index.html"
s = p.read_text()
new, n = re.subn(r"<!-- table:start -->.*?<!-- table:end -->", lambda m: html, s, flags=re.S)
assert n == 1
p.write_text(new)
print("table regenerated:", len(LINES), "rows")
