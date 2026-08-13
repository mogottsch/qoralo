#!/usr/bin/env python3
"""Render the current Android TTS results and listening gate into the share preview."""
from __future__ import annotations

import html
import json
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP8 = HERE.parent
REPO = EXP8.parents[1]
EXP9 = REPO / "experiments/0009-android-tts-optimization"
BASELINE_REPORT = EXP8 / "results/measured-decision.json"
THREAD_REPORT = EXP9 / "thread-sweep/results/measured-thread-sweep.json"
QUALITY_REPORT = EXP9 / "kokoro-int8/reports/quality-gate.json"
BLIND_REPORT = EXP9 / "kokoro-int8/reports/blind-package.json"
CORPUS = EXP9 / "kokoro-int8/corpus.json"
QNN_CHECKPOINT = REPO / "experiments/0010-supertonic-qnn-htp-feasibility/results/host-checkpoint.json"
BLIND_ZIP = EXP9 / "kokoro-int8/generated/blind/kokoro-int8-listening.zip"
OUTPUTS = [
    REPO / "artifacts/progress-preview/index.html",
    REPO / "artifacts/progress-preview/published-index.html",
]
NAMES = {"pocket": "Pocket TTS", "kokoro": "Kokoro 82M", "supertonic_3": "Supertonic 3"}


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def mb(value: int) -> str:
    return f"{value / 1_000_000:.1f} MB"


def mib(value: int) -> str:
    return f"{value / 2**20:.1f} MiB"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def representative_samples(report: dict) -> dict[str, tuple[Path, str]]:
    """Resolve the first canonical warm WAV for each candidate by pinned hash."""
    samples: dict[str, tuple[Path, str]] = {}
    for candidate in report["canonical_one_thread"]:
        result = load(EXP8 / candidate["manifest"])
        warm = next(run for run in result["runs"] if run["kind"] == "warm")
        evidence = next(
            row for row in result["evidence"]
            if row["sha256"] == warm["wav_sha256"] and row["relative_path"].endswith(".wav")
        )
        source = REPO / evidence["relative_path"]
        if not source.is_file():
            raise SystemExit(f"representative Android WAV is missing: {source}")
        filename = f"android-{candidate['candidate_id'].replace('_', '-')}-warm.wav"
        samples[candidate["candidate_id"]] = (source, filename)
    return samples


def baseline_sections(report: dict, samples: dict[str, tuple[Path, str]]) -> tuple[str, str]:
    rows: list[str] = []
    cards: list[str] = []
    for candidate in report["canonical_one_thread"]:
        candidate_id = candidate["candidate_id"]
        name = NAMES[candidate_id]
        decision = candidate["decision"].replace("_", " ")
        cold = candidate["cold"]
        rows.append(
            f"<tr><td><strong>{e(name)}</strong><small>{e(candidate['deployment_variant'])}</small></td>"
            f"<td><span class='badge {e(candidate['decision'])}'>{e(decision)}</span></td>"
            f"<td>{candidate['load_wall_seconds']:.3f}s</td><td>{cold['rtf']:.3f}</td>"
            f"<td><strong>{candidate['warm_median_rtf']:.3f}</strong></td>"
            f"<td>{mb(candidate['memory_bytes']['sampled_peak_pss'])}</td>"
            f"<td>{candidate['audio']['sample_rate_hz']/1000:g} kHz · 4/4 valid</td></tr>"
        )
        warm_rtfs = ", ".join(f"{item['rtf']:.3f}" for item in candidate["warm"])
        sample_url = f"audio/{samples[candidate_id][1]}"
        cards.append(
            f"<article class='card'><header><div><h3>{e(name)}</h3><p>{e(candidate['deployment_variant'])}</p></div>"
            f"<span class='badge {e(candidate['decision'])}'>{e(decision)}</span></header>"
            f"<div class='metrics'><div><b>{candidate['load_wall_seconds']:.3f}s</b><span>load</span></div>"
            f"<div><b>{cold['rtf']:.3f}</b><span>cold RTF</span></div>"
            f"<div><b>{candidate['warm_median_rtf']:.3f}</b><span>warm median</span></div>"
            f"<div><b>{mb(candidate['memory_bytes']['sampled_peak_pss'])}</b><span>peak PSS</span></div></div>"
            f"<label class='audio-label'>Representative Android warm output</label>"
            f"<audio controls preload='metadata' src='{e(sample_url)}'></audio>"
            f"<p class='run'>Warm RTFs: {warm_rtfs}</p>"
            f"<ul>{''.join(f'<li>{e(item)}</li>' for item in candidate['limitations'])}</ul></article>"
        )
    return "".join(rows), "".join(cards)


def thread_section(report: dict) -> str:
    by_key = {(row["candidate"], row["threads"]): row for row in report["configurations"]}
    comparisons = {row["candidate"]: row for row in report["thread_comparisons"]}
    rows: list[str] = []
    for candidate_id in ("pocket", "kokoro", "supertonic_3"):
        comparison = comparisons[candidate_id]
        cells: list[str] = []
        for threads in (1, 2, 4):
            row = by_key[(candidate_id, threads)]
            best = threads == comparison["best_observed_threads"]
            cells.append(
                f"<td class='thread-cell{' best' if best else ''}'><strong>{row['warm_median_rtf']:.3f}</strong>"
                f"<small>cold {row['cold_rtf']:.3f} · {mib(row['memory_summary']['maximum_sampled_peak_pss_bytes'])}</small></td>"
            )
        rows.append(
            f"<tr><td><strong>{e(NAMES[candidate_id])}</strong><small>Warm median RTF</small></td>"
            f"{''.join(cells)}<td>{comparison['best_observed_threads']} threads</td></tr>"
        )
    return "".join(rows)


def listening_section(blind: dict, corpus: dict, user_listening: dict | None) -> str:
    text_by_id = {row["id"]: row["text"] for row in corpus["evaluation"]}
    votes = {row["pair"]: row for row in (user_listening or {}).get("observations", [])}
    cards: list[str] = []
    for pair in blind["pairs"]:
        pair_id = pair["pair"]
        text = text_by_id[pair["utterance_id"]]
        vote = votes.get(pair_id)
        if vote:
            assignment = vote["revealed_assignment"]
            confidence = f" · confidence {vote['confidence']}/5" if vote["confidence"] else ""
            result = (
                "Tie" if vote["preference"] == "tie" else
                f"Preferred {vote['preference']} → {vote['preferred_variant'].upper()}"
            )
            ballot = (
                f"<div class='reveal'><strong>Revealed:</strong> A = {e(assignment['A'].upper())} · "
                f"B = {e(assignment['B'].upper())} · <strong>Your vote:</strong> {e(result)}{e(confidence)}</div>"
            )
        else:
            ballot = f"""<div class='ballot-row'><fieldset><legend>Preference</legend>
            <label><input type='radio' name='{e(pair_id)}-preference' value='A'> A</label>
            <label><input type='radio' name='{e(pair_id)}-preference' value='B'> B</label>
            <label><input type='radio' name='{e(pair_id)}-preference' value='tie'> Tie</label>
          </fieldset><label>Confidence <select class='confidence'><option value=''>—</option>{''.join(f'<option>{n}</option>' for n in range(1, 6))}</select></label>
          <label class='notes'>Notes <input type='text' placeholder='Prosody, artifacts, pacing…'></label></div>"""
        cards.append(f"""
        <article class='listen-card' data-pair='{e(pair_id)}'>
          <h3>{e(pair_id.replace('-', ' ').title())}</h3><p class='transcript'>{e(text)}</p>
          <div class='ab-grid'>
            <div><label class='audio-label'>Sample A</label><audio controls preload='metadata' src='kokoro-int8/{e(pair_id)}/A.wav'></audio></div>
            <div><label class='audio-label'>Sample B</label><audio controls preload='metadata' src='kokoro-int8/{e(pair_id)}/B.wav'></audio></div>
          </div>
          {ballot}
        </article>""")
    return "".join(cards)


def render() -> str:
    baseline = load(BASELINE_REPORT)
    threads = load(THREAD_REPORT)
    quality = load(QUALITY_REPORT)
    blind = load(BLIND_REPORT)
    corpus = load(CORPUS)
    qnn = load(QNN_CHECKPOINT)
    samples = representative_samples(baseline)
    baseline_rows, baseline_cards = baseline_sections(baseline, samples)
    thread_rows = thread_section(threads)
    user_listening = quality["quality_gate"].get("user_listening")
    listening_cards = listening_section(blind, corpus, user_listening)
    listening_passed = quality["status"] == "passed_user_listening"
    candidate = quality["candidate"]
    optional = baseline["optional_two_thread"][0]
    disclosures = baseline["campaign_disclosures"]
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><link rel='icon' href='data:,'>
<meta name='robots' content='noindex,nofollow,noarchive'><title>Android TTS Benchmark — Galaxy S23 Ultra</title>
<style>
:root{{--bg:#0b0e13;--panel:#131923;--line:#293446;--text:#edf2f8;--muted:#9ca8b9;--blue:#73adff;--green:#55d4a0;--amber:#ffc96b;--red:#ff8787}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:34px 22px 70px}}h1{{font-size:clamp(30px,5vw,44px);line-height:1.05;margin:0 0 10px}}h2{{margin:42px 0 14px}}h3{{margin:0}}p{{margin-top:0}}.lead,.muted,.card header p,.run,small{{color:var(--muted)}}.lead{{max-width:820px}}.summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:24px 0}}.hero,.card,.notice,.table-wrap,.listen-card{{background:var(--panel);border:1px solid var(--line);border-radius:12px}}.hero{{padding:18px}}.hero b{{display:block;font-size:28px}}.hero span{{color:var(--muted)}}table{{width:100%;border-collapse:collapse}}th,td{{padding:12px 10px;text-align:left;border-bottom:1px solid var(--line)}}th{{color:var(--muted);font-size:11px;text-transform:uppercase}}td small{{display:block;font-size:10px}}.table-wrap{{overflow:auto}}.thread-cell.best{{background:#18352c}}.thread-cell.best strong{{color:var(--green)}}.badge{{display:inline-block;border-radius:99px;padding:4px 8px;background:#19382d;color:var(--green);font:bold 10px ui-monospace,monospace;text-transform:uppercase;white-space:nowrap}}.badge.works_with_limitations,.badge.awaiting{{background:#3b301b;color:var(--amber)}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.card{{padding:17px}}.card header{{display:flex;justify-content:space-between;gap:12px}}.card header p{{font-size:10px;margin:3px 0 0}}.metrics{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:16px 0}}.metrics div{{border-top:1px solid var(--line);padding-top:7px}}.metrics b,.metrics span{{display:block}}.metrics span{{font-size:10px;color:var(--muted);text-transform:uppercase}}audio{{display:block;width:100%;margin:7px 0 12px}}.audio-label{{display:block;color:var(--muted);font:700 10px ui-monospace,monospace;text-transform:uppercase}}.run{{font-size:12px;margin:7px 0}}ul{{padding-left:19px}}li+li{{margin-top:6px}}.notice{{padding:17px;border-left:3px solid var(--blue);margin:12px 0}}.notice.warn{{border-color:var(--amber)}}a{{color:var(--blue)}}.listen-list{{display:grid;gap:12px}}.listen-card{{padding:18px}}.transcript{{margin:8px 0 14px;color:#cbd4df}}.ab-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.ballot-row{{display:flex;align-items:end;gap:18px;flex-wrap:wrap}}fieldset{{border:0;padding:0;margin:0}}legend,.ballot-row>label{{font-size:11px;color:var(--muted);text-transform:uppercase;font-weight:700}}fieldset label{{margin-right:12px;color:var(--text);font-size:14px;text-transform:none;font-weight:400}}select,input[type=text]{{background:#0c1119;color:var(--text);border:1px solid var(--line);border-radius:6px;padding:7px}}.notes{{flex:1;min-width:240px}}.notes input{{display:block;width:100%;margin-top:3px}}.reveal{{background:#0d1715;border:1px solid #285b49;border-radius:8px;padding:10px;color:#bcebd8}}button,.download{{display:inline-block;background:var(--blue);color:#07101d;border:0;border-radius:7px;padding:10px 14px;font-weight:800;text-decoration:none;cursor:pointer;margin:8px 8px 0 0}}footer{{border-top:1px solid var(--line);margin-top:38px;padding-top:16px;color:var(--muted);font-size:12px}}@media(max-width:820px){{.summary,.cards,.ab-grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<header><h1>Android TTS benchmark</h1><p class='lead'>Measured locally on a Samsung Galaxy S23 Ultra with pinned sherpa-onnx v1.13.5 CPU deployments. RTF below 1.0 is faster than real time. This page is the current human-facing report.</p></header>
<section class='summary'><div class='hero'><b>0.362</b><span>Best sweep RTF · Supertonic 2 threads</span></div><div class='hero'><b>9 / 9</b><span>Thread configurations succeeded</span></div><div class='hero'><b>36 / 36</b><span>Sweep WAVs validated</span></div></section>
<section><h2>CPU thread sweep</h2><div class='table-wrap'><table><thead><tr><th>Candidate</th><th>1 thread</th><th>2 threads</th><th>4 threads</th><th>Best observed</th></tr></thead><tbody>{thread_rows}</tbody></table></div>
<div class='notice warn'><strong>Interpretation:</strong> Kokoro showed the only large useful scaling: four threads reached RTF 0.753. Pocket and Supertonic were lowest at two threads, but their gains over one thread were under 10% and remain inconclusive. Pocket became slower at four threads. One rotated campaign and a user-authorized thermal policy change after sequence six limit causal attribution.</div></section>
<section><h2>Kokoro INT8 quality gate</h2><div class='notice'><span class='badge'>{'passed user listening' if listening_passed else 'awaiting your listening'}</span><p style='margin-top:10px'>The selected exact-v1.0 candidate is <strong>{candidate['size_reduction_fraction']*100:.1f}% smaller</strong> ({mb(candidate['source_model_bytes'])} → {mb(candidate['model_bytes'])}). Your finalized blind ballot had <strong>four ties, one INT8 preference, and one FP32 preference</strong>; both directional votes were confidence 2/5. No systematic INT8 degradation was detected, so the host gate passed. This is not proof of strict perceptual equivalence or INT8 superiority, and Android performance remains unmeasured for this candidate.</p><a class='download' href='kokoro-int8/kokoro-int8-listening.zip' download>Download complete blind package</a><a class='download' href='user-listening-ballot.csv' download>Your ballot.csv</a></div>
<div class='listen-list'>{listening_cards}</div></section>
<section><h2>Original one-thread baseline</h2><div class='table-wrap'><table><thead><tr><th>Candidate</th><th>Decision</th><th>Load</th><th>Cold RTF</th><th>Warm median</th><th>Peak PSS</th><th>Audio</th></tr></thead><tbody>{baseline_rows}</tbody></table></div></section>
<section><h2>Baseline audio and details</h2><div class='cards'>{baseline_cards}</div></section>
<section><h2>Earlier optional Kokoro two-thread run</h2><div class='notice'><strong>Warm median RTF {optional['warm_median_rtf']:.3f}</strong> (cold {optional['cold']['rtf']:.3f}) · load {optional['load_wall_seconds']:.3f}s · peak PSS {mb(optional['sampled_peak_pss_bytes'])}. The newer complete sweep supersedes this as the thread comparison.</div></section>
<section><h2>Qualcomm QNN / HTP checkpoint</h2><div class='notice warn'><span class='badge awaiting'>paused for tomorrow</span><p style='margin-top:10px'>The Supertonic component-first track completed host fixture work and a reusable Android arm64 ONNX Runtime 1.27.1 + QAIRT 2.49 QNN build. The resulting local-only <code>libonnxruntime.so</code> is {mb(qnn['android_ort_qnn_build']['libonnxruntime']['bytes'])}, SHA-256 <code>{e(qnn['android_ort_qnn_build']['libonnxruntime']['sha256'][:12])}…</code>.</p><ul><li>A Q8 re-quantized vocoder derivative failed the host numerical gate and will not go to the phone.</li><li>Host HTP attempts did not produce valid output or profiles; they are not HTP proof.</li><li>Only phone identity was captured. No QNN model has run on the S23 Ultra, and no speedup is claimed.</li><li>Next: run a tiny QDQ control with CPU fallback disabled and detailed profiling, then consider the exact fixed released vocoder.</li></ul><a href='qnn-host-checkpoint.json'>Raw checkpoint JSON</a></div></section>
<section><h2>Important limits</h2><div class='notice warn'><ul><li>Pocket used packaged Bria, not requested Alba. Its production licensing remains unresolved.</li><li>These are sherpa-onnx Android deployment variants, not the host PyTorch workflows.</li><li>{e(disclosures['order_bias'])}</li><li>No listening verdict is claimed until you return the blind Kokoro ballot.</li><li>Differences below 5–10% in the thread sweep are inconclusive.</li></ul></div></section>
<footer><a href='measured-decision.json'>Baseline JSON evidence</a> · <a href='measured-thread-sweep.json'>Thread-sweep JSON evidence</a> · <a href='quality-gate.json'>INT8 gate JSON evidence</a> · <a href='https://github.com/mogottsch/vibevoice-android-spike'>Repository</a></footer>
</main><script>
const ballotButton=document.getElementById('download-ballot');
if(ballotButton) ballotButton.addEventListener('click',()=>{{
 const esc=v=>'"'+String(v??'').replaceAll('"','""')+'"';
 const rows=[['pair','preference','confidence','notes']];
 document.querySelectorAll('[data-pair]').forEach(card=>{{
  const pair=card.dataset.pair;
  const preference=card.querySelector(`input[name="${{pair}}-preference"]:checked`)?.value||'';
  rows.push([pair,preference,card.querySelector('.confidence').value,card.querySelector('.notes input').value]);
 }});
 const csv=rows.map(row=>row.map(esc).join(',')).join('\\n')+'\\n';
 const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}})); a.download='kokoro-int8-ballot.csv'; a.click(); URL.revokeObjectURL(a.href);
}});
</script></body></html>"""


def stage_assets(root: Path) -> None:
    baseline = load(BASELINE_REPORT)
    audio_dir = root / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for source, filename in representative_samples(baseline).values():
        shutil.copyfile(source, audio_dir / filename)

    shutil.copyfile(
        EXP9 / "kokoro-int8/reports/user-listening-ballot.csv",
        root / "user-listening-ballot.csv",
    )
    listening_dir = root / "kokoro-int8"
    listening_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BLIND_ZIP, listening_dir / BLIND_ZIP.name)
    with zipfile.ZipFile(BLIND_ZIP) as archive:
        for name in archive.namelist():
            parts = Path(name).parts
            if len(parts) == 2 and parts[0].startswith("pair-") and parts[1] in {"A.wav", "B.wav"}:
                target = listening_dir.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)


def main() -> None:
    page = render()
    for output in OUTPUTS:
        output.parent.mkdir(parents=True, exist_ok=True)
        stage_assets(output.parent)
        output.write_text(page, encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
