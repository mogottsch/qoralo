#!/usr/bin/env python3
"""Render the measured experiment 0008 decision into the local status preview."""
from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
REPORT = EXP / "results/measured-decision.json"
OUTPUTS = [
    REPO / "artifacts/progress-preview/index.html",
    REPO / "artifacts/progress-preview/published-index.html",
]


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def mb(value: int) -> str:
    return f"{value / 1_000_000:.1f} MB"


def render() -> str:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    rows = []
    details = []
    names = {"pocket": "Pocket TTS", "kokoro": "Kokoro 82M", "supertonic_3": "Supertonic 3"}
    for candidate in report["canonical_one_thread"]:
        name = names[candidate["candidate_id"]]
        decision = candidate["decision"].replace("_", " ")
        cold = candidate["cold"]
        memory = candidate["memory_bytes"]
        rows.append(
            f"<tr><td><strong>{e(name)}</strong><small>{e(candidate['deployment_variant'])}</small></td>"
            f"<td><span class='badge {e(candidate['decision'])}'>{e(decision)}</span></td>"
            f"<td>{candidate['load_wall_seconds']:.3f} s</td><td>{cold['rtf']:.3f}</td>"
            f"<td><strong>{candidate['warm_median_rtf']:.3f}</strong></td>"
            f"<td>{mb(memory['sampled_peak_pss'])}</td><td>{candidate['audio']['sample_rate_hz']/1000:g} kHz · 4/4 valid</td></tr>"
        )
        warm = candidate["warm"]
        warm_rtfs = ", ".join(f"{item['rtf']:.3f}" for item in warm)
        details.append(
            f"<article class='card'><header><div><h3>{e(name)}</h3><p>{e(candidate['deployment_variant'])}</p></div>"
            f"<span class='badge {e(candidate['decision'])}'>{e(decision)}</span></header>"
            f"<div class='metrics'><div><b>{candidate['load_wall_seconds']:.3f}s</b><span>load</span></div>"
            f"<div><b>{cold['rtf']:.3f}</b><span>cold RTF</span></div>"
            f"<div><b>{candidate['warm_median_rtf']:.3f}</b><span>warm median RTF</span></div>"
            f"<div><b>{mb(candidate['memory_bytes']['sampled_peak_pss'])}</b><span>peak PSS</span></div></div>"
            f"<p class='run'>Cold: {cold['wall_seconds']:.3f}s wall / {cold['audio_seconds']:.3f}s audio · callback {cold['callback_seconds']:.3f}s</p>"
            f"<p class='run'>Warm RTFs: {warm_rtfs}</p>"
            f"<ul>{''.join(f'<li>{e(item)}</li>' for item in candidate['limitations'])}</ul></article>"
        )
    optional = report["optional_two_thread"][0]
    disclosures = report["campaign_disclosures"]
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<meta name='robots' content='noindex,nofollow,noarchive'><title>Android TTS Benchmark — Galaxy S23 Ultra</title>
<style>
:root{{--bg:#0b0e13;--panel:#131923;--line:#293446;--text:#edf2f8;--muted:#9ca8b9;--blue:#73adff;--green:#55d4a0;--amber:#ffc96b}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:34px 22px 70px}}h1{{font-size:clamp(30px,5vw,44px);line-height:1.05;margin:0 0 10px}}h2{{margin:38px 0 14px}}h3{{margin:0}}p{{margin-top:0}}.lead,.muted,.card header p,.run,small{{color:var(--muted)}}.lead{{max-width:780px}}.summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:24px 0}}.hero,.card,.notice,.table-wrap{{background:var(--panel);border:1px solid var(--line);border-radius:12px}}.hero{{padding:18px}}.hero b{{display:block;font-size:28px}}.hero span{{color:var(--muted)}}table{{width:100%;border-collapse:collapse}}th,td{{padding:12px 10px;text-align:left;border-bottom:1px solid var(--line)}}th{{color:var(--muted);font-size:11px;text-transform:uppercase}}td small{{display:block;font-size:10px}}.table-wrap{{overflow:auto}}.badge{{display:inline-block;border-radius:99px;padding:4px 8px;background:#19382d;color:var(--green);font:bold 10px ui-monospace,monospace;text-transform:uppercase;white-space:nowrap}}.badge.works_with_limitations{{background:#3b301b;color:var(--amber)}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.card{{padding:17px}}.card header{{display:flex;justify-content:space-between;gap:12px}}.card header p{{font-size:10px;margin:3px 0 0}}.metrics{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:16px 0}}.metrics div{{border-top:1px solid var(--line);padding-top:7px}}.metrics b,.metrics span{{display:block}}.metrics span{{font-size:10px;color:var(--muted);text-transform:uppercase}}.run{{font-size:12px;margin:7px 0}}ul{{padding-left:19px}}li+li{{margin-top:6px}}.notice{{padding:17px;border-left:3px solid var(--blue);margin:12px 0}}a{{color:var(--blue)}}footer{{border-top:1px solid var(--line);margin-top:38px;padding-top:16px;color:var(--muted);font-size:12px}}@media(max-width:820px){{.summary,.cards{{grid-template-columns:1fr}}}}
</style></head><body><main>
<header><h1>Android TTS benchmark</h1><p class='lead'>Measured locally on a Samsung Galaxy S23 Ultra, Android 16, using pinned sherpa-onnx v1.13.5 CPU deployments. RTF below 1.0 is faster than real time.</p></header>
<section class='summary'><div class='hero'><b>0.370</b><span>Best warm RTF · Supertonic 3</span></div><div class='hero'><b>3 / 3</b><span>Models produced valid audio</span></div><div class='hero'><b>16 / 16</b><span>Measured WAVs validated</span></div></section>
<section><h2>Canonical one-thread comparison</h2><div class='table-wrap'><table><thead><tr><th>Candidate</th><th>Decision</th><th>Load</th><th>Cold RTF</th><th>Warm median</th><th>Peak PSS</th><th>Audio</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section><h2>Measured details</h2><div class='cards'>{''.join(details)}</div></section>
<section><h2>Optional Kokoro two-thread run</h2><div class='notice'><strong>Warm median RTF {optional['warm_median_rtf']:.3f}</strong> (cold {optional['cold']['rtf']:.3f}) · load {optional['load_wall_seconds']:.3f}s · peak PSS {mb(optional['sampled_peak_pss_bytes'])}. This run was triggered because canonical one-thread Kokoro exceeded RTF 1.0; it does not replace the canonical table.</div></section>
<section><h2>Important limits</h2><div class='notice'><ul><li>Pocket used packaged Bria, not requested Alba. Its production licensing remains unresolved.</li><li>These are INT8/ONNX Android deployment variants, not the host PyTorch workflows from experiment 0007.</li><li>{e(disclosures['order_bias'])}</li><li>{e(disclosures['listening'])}</li><li>Earlier callback-bridge crashes were harness failures and remain retained as evidence; successful campaigns used the corrected bridge.</li></ul></div></section>
<footer><a href='/experiments/0008-sherpa-onnx-android-tts-benchmark/results/measured-decision.md'>Full measured report</a> · <a href='/experiments/0008-sherpa-onnx-android-tts-benchmark/results/measured-decision.json'>Machine-readable report</a> · <a href='https://github.com/mogottsch/vibevoice-android-spike'>Repository</a></footer>
</main></body></html>"""


def main() -> None:
    page = render()
    for output in OUTPUTS:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(page, encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
