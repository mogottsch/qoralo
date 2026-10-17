#!/usr/bin/env python3
"""Regenerate the stop-score chart in docs/qoralo-blog/index.html from bos-zero-replay.json.

Run from the repository root:  python3 docs/qoralo-blog/evidence/build-chart.py
Only the block between the chart:start/chart:end markers is replaced.
"""
import json, re
from pathlib import Path

root = Path("docs/qoralo-blog")
data = json.loads((root / "evidence/bos-zero-replay.json").read_text())
L = data["logits"]
series = {"android": L["android_original_retained"], "zero": L["all_zero_bos_replay"], "nan": L["correct_nan_bos_replay"]}
YMIN, YMAX, XMAX = -15, 9, 133
for name, v in series.items():
    assert YMIN < min(v) and max(v) < YMAX, name
H = YMAX - YMIN
pct = lambda v: round((YMAX - v) / H * 100, 2)
def pts(v): return " ".join(f"{i},{YMAX - x:.3f}" for i, x in enumerate(v))
thr = YMAX - data["full_trajectory"]["max_logit"]["eos_threshold"]
yticks = "".join(f'<span class="tick y" style="top:{pct(t)}%">{str(t).replace("-", chr(0x2212))}</span>' for t in (-12, -8, -4, 0, 4, 8))
xticks = "".join(f'<span class="tick x" style="left:{round(x / XMAX * 100, 2)}%">{x}</span>' for x in (0, 53, 133))
html = f'''<!-- chart:start -->
          <div class="chart-wrap">
            <div class="chart" role="img" aria-label="Stop score for each generated frame. The phone's retained run stays between about minus 14 and minus 7 for all 134 frames. A zero-input desktop replay follows it. A NaN-input replay rises above the minus 4 threshold at frame 53 and stops.">
              <svg viewBox="0 0 {XMAX} {H}" preserveAspectRatio="none" aria-hidden="true">
                <line class="threshold" x1="0" x2="{XMAX}" y1="{thr}" y2="{thr}"/>
                <polyline class="series android" points="{pts(series["android"])}"/>
                <polyline class="series zero" points="{pts(series["zero"])}"/>
                <polyline class="series nan" points="{pts(series["nan"])}"/>
                <line id="step-marker" class="marker" x1="53" x2="53" y1="0" y2="{H}" hidden/>
              </svg>
              {yticks}{xticks}
              <span class="note threshold-note" style="top:{pct(-4)}%">stop threshold</span>
              <span class="note stop-note" style="left:{round(53 / XMAX * 100, 2)}%">stops at frame 53</span>
              <span class="axis-name y">Stop score</span><span class="axis-name x">Generated frame (cap 134)</span>
            </div>
          </div>
          <ul class="legend"><li class="android">Phone, retained run</li><li class="zero">Desktop replay, zero first input</li><li class="nan">Desktop replay, NaN first input</li></ul>
          <div class="scrub enhanced" hidden><label for="why-step">Frame</label><input id="why-step" type="range" min="0" max="{XMAX}" value="53" step="1" aria-describedby="why-readout"></div>
          <script type="application/json" id="trajectories">{json.dumps({k: [round(x, 3) for x in v] for k, v in series.items()}, separators=(",", ":"))}</script>
<!-- chart:end -->'''
p = root / "index.html"
s = p.read_text()
new, n = re.subn(r"<!-- chart:start -->.*?<!-- chart:end -->", lambda m: html, s, flags=re.S)
assert n == 1
p.write_text(new)
print("chart regenerated:", {k: len(v) for k, v in series.items()})
