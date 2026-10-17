#!/usr/bin/env python3
"""Generate the swimlane system-flow figure in index.html (between the flow:start / flow:end markers).

One row per device: Computer, Phone CPU, Phone GPU, Phone NPU. One column per step in the order it happens.
Connectors are exact SVG paths: gap columns are a fixed 14 px and lane rows have fixed heights, so no scaling.
The review chat is two nodes in the same column (you on the CPU, Gemma on the GPU) joined by a two-way arrow.
Facts come from evidence/system-flow-spec.md and the app source (ReviewScreen.kt, GenerationCoordinator.editDraftImpl).
"""
from pathlib import Path
import html

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "index.html"

GAP = 14            # px, fixed gap column between step columns
ROWS = {"computer": 1, "cpu": 2, "gpu": 3, "npu": 4}
ROW_H = {1: 96, 2: 112, 3: 112, 4: 112}
LANES = [  # key, small label above, big label
    ("computer", "", "Computer"),
    ("cpu", "Phone", "CPU"),
    ("gpu", "Phone", "GPU"),
    ("npu", "Phone", "NPU"),
]
WHERE = {"computer": "Computer", "cpu": "Phone CPU", "gpu": "Phone GPU", "npu": "Phone NPU"}

# id, lane, step, title, detail, optional, mobile-only extra line
NODES = [
    ("qflow-h1", "computer", 1, "Adapt ONNX graphs", "Fixed shapes", False, ""),
    ("qflow-h2", "computer", 2, "Compile HTP contexts", "Built once", False, "Copied to the phone for the two NPU steps"),
    ("qflow-p1", "cpu", 1, "Add sources", "Text + instructions", False, ""),
    ("qflow-p2", "gpu", 2, "Write script", "Gemma 4 E2B", False, ""),
    ("qflow-p3", "cpu", 3, "Review & edit", "Chat with Gemma", True, ""),
    ("qflow-p4", "gpu", 3, "Revise script", "Applies your request", True, "Optional loop back to review"),
    ("qflow-p5", "cpu", 4, "Split into chunks", "Sized for the voice model", False, ""),
    ("qflow-p6", "npu", 5, "Predict + encode", "Length + text features", False, ""),
    ("qflow-p7", "npu", 6, "Generate one voice", "Refine, then vocoder", False, ""),
    ("qflow-p8", "cpu", 7, "Join audio", "Adds pauses", False, ""),
    ("qflow-p9", "cpu", 8, "Play / export WAV", "One episode", False, ""),
]
NODE = {n[0]: n for n in NODES}

# Flow edges between consecutive steps (the p3 <-> p4 loop is drawn separately).
EDGES = [("qflow-h1", "qflow-h2"), ("qflow-p1", "qflow-p2"), ("qflow-p2", "qflow-p3"), ("qflow-p3", "qflow-p5"),
         ("qflow-p5", "qflow-p6"), ("qflow-p6", "qflow-p7"), ("qflow-p7", "qflow-p8"), ("qflow-p8", "qflow-p9")]

def col_of_step(step):  # grid column of a step: label=1, step k = 2k
    return 2 * step

def center_y(row, first_row):
    """Vertical centre of a lane row, measured from the top of the span that starts at first_row."""
    return sum(ROW_H[r] for r in range(first_row, row)) + ROW_H[row] / 2

def edge_html(src, dst):
    a, b = NODE[src], NODE[dst]
    ra, rb = ROWS[a[1]], ROWS[b[1]]
    first, last = min(ra, rb), max(ra, rb)
    height = sum(ROW_H[r] for r in range(first, last + 1))
    y1, y2 = center_y(ra, first), center_y(rb, first)
    gap_col = col_of_step(a[2]) + 1
    mid = GAP / 2
    path = f"M0 {y1:g}H{mid:g}V{y2:g}H{GAP - 1:g}" if y1 != y2 else f"M0 {y1:g}H{GAP - 1:g}"
    head = f"M{GAP - 5:g} {y2 - 3.5:g}L{GAP - 0.5:g} {y2:g}L{GAP - 5:g} {y2 + 3.5:g}"
    return (f'<div class="qflow-edge" aria-hidden="true" data-from="{src}" data-to="{dst}" data-y1="{y1:g}" data-y2="{y2:g}" '
            f'style="grid-column:{gap_col};grid-row:{first} / span {last - first + 1}">'
            f'<svg viewBox="0 0 {GAP} {height:g}" preserveAspectRatio="none"><path d="{path}"/><path d="{head}"/></svg></div>')

def node_html(n):
    nid, lane, step, title, detail, optional, extra = n
    cls = f"qflow-node qflow-{lane}" + (" qflow-optional" if optional else "")
    extra_html = f'\n            <span class="qflow-mobile-only">{html.escape(extra)}</span>' if extra else ""
    return (f'          <li class="{cls}" id="{nid}" data-lane="{lane}" data-step="{step}" '
            f'style="--row:{ROWS[lane]};--col:{col_of_step(step)}">\n'
            f'            <strong class="qflow-title">{html.escape(title)}</strong>\n'
            f'            <span class="qflow-detail">{html.escape(detail)}</span>{extra_html}\n'
            f'            <span class="qflow-where">{WHERE[lane]}</span>\n'
            f'          </li>')

def build():
    lanes = "\n".join(
        f'          <div class="qflow-lane qflow-lane-{k}" aria-hidden="true" style="grid-row:{ROWS[k]}">'
        f'<span class="qflow-lane-name">{"<small>" + small + "</small>" if small else ""}{big}</span></div>'
        for k, small, big in LANES)
    nodes = "\n".join(node_html(n) for n in NODES)
    edges = "\n          ".join(edge_html(s, d) for s, d in EDGES)
    # Two-way loop between Review & edit (CPU) and Revise script (GPU), same column, adjacent lanes.
    loop_col = col_of_step(NODE["qflow-p3"][2])
    loop_row = ROWS["cpu"]
    loop = (f'<div class="qflow-loop" aria-hidden="true" style="grid-column:{loop_col};grid-row:{loop_row} / span 2">'
            f'<svg viewBox="0 0 14 {ROW_H[2] + ROW_H[3]}" preserveAspectRatio="none">'
            f'<path d="M7 {ROW_H[2] - 8}V{ROW_H[2] + 8}"/><path d="M3.5 {ROW_H[2] - 4.5}L7 {ROW_H[2] - 9}L10.5 {ROW_H[2] - 4.5}"/>'
            f'<path d="M3.5 {ROW_H[2] + 4.5}L7 {ROW_H[2] + 9}L10.5 {ROW_H[2] + 4.5}"/></svg>'
            f'<span class="qflow-loop-label">optional loop</span></div>')
    # Preparation reaches both NPU steps: a dotted line out of "Compile", along the Computer lane, down to a box around them.
    c_compile = col_of_step(NODE["qflow-h2"][2])
    npu_first, npu_last = col_of_step(NODE["qflow-p6"][2]), col_of_step(NODE["qflow-p7"][2])
    center_col = (npu_first + npu_last) // 2          # the gap column between the two NPU steps
    prov = (f'<div class="qflow-box" aria-hidden="true" style="grid-column:{npu_first} / {npu_last + 1};grid-row:{ROWS["npu"]}"></div>\n'
            f'          <div class="qflow-prov-h" aria-hidden="true" style="grid-column:{c_compile + 1} / {center_col + 1};grid-row:1"></div>\n'
            f'          <div class="qflow-prov-v" aria-hidden="true" style="grid-column:{center_col};grid-row:1 / {ROWS["npu"] + 1}"></div>\n'
            f'          <p class="qflow-prov-label" aria-hidden="true" style="grid-column:{c_compile + 2} / {center_col};grid-row:1">'
            f'Supertonic 3, prepared once and copied to the phone</p>')
    alt = ("Swimlane diagram with one lane per device. On the computer, Supertonic's existing ONNX graphs are adapted and compiled into reusable HTP contexts, "
           "once, before use; they are copied to the phone and used by the two NPU steps. On the phone, the CPU runs the app: you add text or Markdown or JSON sources and instructions. "
           "The GPU runs Gemma 4 E2B, which writes the script. Back on the CPU you can review and edit the script by chatting with Gemma; "
           "each request goes to the GPU, which revises the script, and you can repeat this as often as you like. "
           "The CPU splits the script into chunks sized for the voice model. The NPU runs Supertonic 3 to predict each chunk's length and encode its text, then generate one fixed voice. "
           "The CPU joins the audio with pauses and plays or exports the episode as a WAV file.")
    caption = ("Speech models are prepared once on a computer; episodes are generated on the phone. "
               "The GPU and NPU lanes hold the models, and the CPU lane is the app code around them.")
    return f'''<!-- flow:start (generated by evidence/build-system-flow.py) -->
        <figure class="qflow" id="system-figure" aria-label="Full system flow: one lane per device, from the computer to the phone's CPU, GPU and NPU" aria-describedby="qflow-caption qflow-alt">
          <div class="qflow-swim">
{lanes}
          {prov}
          {edges}
          {loop}
          <ol class="qflow-steps" role="list" aria-label="Steps in order">
{nodes}
          </ol>
          </div>
          <p class="sr-only" id="qflow-alt">{html.escape(alt)}</p>
          <figcaption class="qflow-caption" id="qflow-caption">{html.escape(caption)}</figcaption>
        </figure>
<!-- flow:end -->'''

def main():
    s = INDEX.read_text()
    new = build()
    if "<!-- flow:start" in s:
        a = s.index("<!-- flow:start")
        b = s.index("<!-- flow:end -->") + len("<!-- flow:end -->")
        s = s[:a] + new + s[b:]
    else:
        a = s.index('<figure class="qflow"')
        b = s.index("</figure>", a) + len("</figure>")
        s = s[:a] + new + s[b:]
    INDEX.write_text(s)
    print("system flow regenerated:", len(NODES), "nodes,", len(EDGES) + 1, "edges (incl. loop)")

if __name__ == "__main__":
    main()
