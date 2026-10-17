#!/usr/bin/env python3
"""Regenerate the 'Script writing' table in docs/qoralo-blog/index.html from llm-table.json.

llm-table.json is Thomas's evidence packet (unchanged): exact five-request long-tier medians of
generic text benchmarks (docs/android-llm-benchmarks/registry.json). These are not podcast-script
speed or quality. Run from the repository root:  python3 docs/qoralo-blog/evidence/build-llm-table.py
"""
import json, re
from pathlib import Path

root = Path("docs/qoralo-blog")
rows = json.loads((root / "evidence/llm-table.json").read_text())["rows"]
by = {(r["model"].split(" (")[0].replace(" IT", ""), r["backend"]): r for r in rows}

# (model shown, backend key in packet, backend label, css class, note). Notes only where a reader needs one.
LINES = [
    ("LFM2.5-2.6B", "CPU", "CPU", "cpu", ""),
    ("Qwen3.5-2B", "GPU", "GPU", "gpu", ""),
    ("Gemma 4 E2B", "NPU(HTP)", "NPU", "npu", "Different build. Repeated itself on long prompts"),
    ("Gemma 4 E2B", "CPU", "CPU", "cpu", ""),
    ("LFM2.5-2.6B", "GPU", "GPU", "gpu", ""),
    ("Gemma 4 E2B", "GPU", "GPU", "gpu", "What the app uses"),
    ("Qwen3.5-2B", "CPU", "CPU", "cpu", ""),
]
MODEL_URL = {
    "Gemma 4 E2B": "https://huggingface.co/google/gemma-4-E2B-it",
    "Qwen3.5-2B": "https://huggingface.co/Qwen/Qwen3.5-2B",
    "LFM2.5-2.6B": "https://huggingface.co/LiquidAI/LFM2.5-2.6B",
}
APP_MODEL = "Gemma 4 E2B"

def sort_key(line):
    """Group by model, the app's model first, then the others by name. Inside a model, fastest decode first;
    a route without a comparable decode rate goes last. Models are never ranked against each other."""
    model, key, *_ = line
    decode = by[(model, key)]["writes"]
    return (model != APP_MODEL, model, decode is None, -(decode or 0.0))

LINES.sort(key=sort_key)

def cells(r):
    reads = f'<td data-label="Prefill" data-prefill="{r["reads"]}">{r["reads"]:.0f}</td>'
    if r["writes"] is None:
        writes = '<td class="blocked" data-label="Decode">not comparable</td>'
    else:
        writes = f'<td data-label="Decode" data-decode="{r["writes"]}">{r["writes"]:.1f}</td>'
    return reads, writes

body = []
linked = set()  # a model's name is a link on its first row only; the other rows repeat the plain name
for model, key, label, cls, note in LINES:
    r = by[(model, key)]
    if model in linked:
        name = model
    else:
        linked.add(model)
        name = f'<a class="ref" href="{MODEL_URL[model]}" rel="noopener noreferrer">{model}</a>'
    reads, writes = cells(r)
    body.append(f'            <tr role="row"><th scope="row" role="rowheader">{name}</th><td class="{cls}" data-label="Backend">{label}</td>{reads}{writes}<td data-label="Note">{note}</td></tr>')
assert len(body) == len(rows) == 7
html = '''<!-- llm-table:start -->
        <div class="table-wrap">
          <table class="bench llm" role="table">
            <caption class="sr-only">Prefill and decode speed in tokens per second for three language models on the phone, on CPU, GPU and NPU</caption>
            <thead><tr role="row"><th scope="col" role="columnheader">Model</th><th scope="col" role="columnheader">Backend</th><th scope="col" role="columnheader">Prefill, tokens/s</th><th scope="col" role="columnheader">Decode, tokens/s</th><th scope="col" role="columnheader">Note</th></tr></thead>
            <tbody>
''' + "\n".join(body) + '''
            </tbody>
          </table>
        </div>
<!-- llm-table:end -->'''
p = root / "index.html"
s = p.read_text()
new, n = re.subn(r"<!-- llm-table:start -->.*?<!-- llm-table:end -->", lambda m: html, s, flags=re.S)
assert n == 1
p.write_text(new)
print("llm table regenerated:", len(body), "rows")
