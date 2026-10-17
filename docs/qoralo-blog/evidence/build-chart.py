#!/usr/bin/env python3
"""Regenerate the stop-score chart in docs/qoralo-blog/index.html from the phone-check raw results.

Run from the repository root:  python3 docs/qoralo-blog/evidence/build-chart.py
Both lines are phone runs from the same controlled window (evidence/phone-bos-check/raw):
the original code (runner_orig-1) and the same code with only the buffer kept alive (runner_fixed-1).
Frame i ends at (i + 1) x 80 ms of speech. Only the block between chart:start and chart:end is replaced.
"""
import json, re
from pathlib import Path

root = Path("docs/qoralo-blog")
raw = root / "evidence/phone-bos-check/raw"
orig = json.loads((raw / "runner_orig-1.json").read_text())["eos_logits"]            # 134 frames, never stops
kept = json.loads((raw / "runner_fixed-1.json").read_text())["eos_logits"][:56]      # 56 emitted frames, stops
THRESHOLD, YMIN, YMAX, XMAX = -4.0, -15, 9, 134
assert len(orig) == 134 and len(kept) == 56 and max(orig) < THRESHOLD < max(kept)
assert YMIN < min(orig + kept) and max(orig + kept) < YMAX
H = YMAX - YMIN
pts = lambda v: " ".join(f"{i + 1},{YMAX - x:.3f}" for i, x in enumerate(v))
pct = lambda v: round((YMAX - v) / H * 100, 2)
secs = lambda frames: f"{frames * 0.08:.1f}".rstrip("0").rstrip(".")
xticks = "".join(f'<span class="tick x{" end" if f == XMAX else ""}" style="left:{round(f / XMAX * 100, 2)}%">{secs(f)} s</span>' for f in (0, 56, 134))
html = f'''<!-- chart:start -->
          <div class="chart-wrap">
            <div class="chart" role="img" aria-label="Stop score over the seconds of speech generated. With the original code the score stays far below the stop line for the whole 10.7 seconds. With the buffer kept alive it crosses the stop line and the model stops at 4.5 seconds.">
              <svg viewBox="0 0 {XMAX} {H}" preserveAspectRatio="none" aria-hidden="true">
                <line class="threshold" x1="0" x2="{XMAX}" y1="{YMAX - THRESHOLD}" y2="{YMAX - THRESHOLD}"/>
                <polyline class="series orig" points="{pts(orig)}"/>
                <polyline class="series kept" points="{pts(kept)}"/>
              </svg>
              {xticks}
              <span class="note threshold-note" style="top:{pct(THRESHOLD)}%">stop line</span>
              <span class="note stop-note" style="left:{round(56 / XMAX * 100, 2)}%">stops here</span>
              <span class="note never-note" style="top:{pct(-5.7)}%">never reaches the stop line</span>
              <span class="axis-name y">Stop score (higher: closer to finishing)</span><span class="axis-name x">Seconds of speech generated</span>
            </div>
          </div>
          <ul class="legend"><li class="orig">Original code</li><li class="kept">Buffer kept alive</li></ul>
<!-- chart:end -->'''
p = root / "index.html"
s = p.read_text()
new, n = re.subn(r"<!-- chart:start -->.*?<!-- chart:end -->", lambda m: html, s, flags=re.S)
assert n == 1
p.write_text(new)
print("chart regenerated: orig", len(orig), "kept", len(kept))
