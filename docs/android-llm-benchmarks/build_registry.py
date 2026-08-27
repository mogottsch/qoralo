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


def sort_number(value) -> str:
    return "" if value is None else str(value)


def memory(entry: dict) -> tuple[str, str, str]:
    data = entry["memory"]
    if data["peak_pss_bytes"] is not None:
        value = data["peak_pss_bytes"]
        measurement = "peak PSS"
    elif data["peak_vm_hwm_bytes"] is not None:
        value = data["peak_vm_hwm_bytes"]
        measurement = "VmHWM / ru_maxrss"
    else:
        return "—", "", "No committed peak process-memory measurement is available."
    mib = value / (1024 ** 2)
    display = f"{mib / 1024:.2f} GiB" if mib >= 1024 else f"{mib:.1f} MiB"
    detail = f"{measurement}: {value} bytes. {data['method']} Lifecycle: {data['lifecycle']}"
    return f"{display}<br><small>{measurement}</small>", str(value), detail


def sanity(entry: dict) -> tuple[str, str, str]:
    values = [run["output_sanity"]["looks_sensible"] for run in entry["runs"]]
    sensible = sum(value is True for value in values)
    failed = sum(value is False for value in values)
    unchecked = sum(value is None for value in values)
    if failed:
        display = f"{failed} issue / {sensible} sensible / {unchecked} unchecked"
    elif sensible:
        display = f"{sensible} sensible / {unchecked} unchecked"
    else:
        display = f"{unchecked} unchecked"
    # Ascending order puts fewer failed and unchecked outputs first. The visible
    # counts and title retain the exact bounded meaning of this smoke check.
    sort_value = str(failed * 1_000_000 + unchecked * 1_000 - sensible)
    detail = (
        f"Exact-output sanity counts: {sensible} looks_sensible=true, "
        f"{failed} false, {unchecked} unchecked. This is not quality, correctness, "
        "grounding, usefulness, or acceptance."
    )
    return display, sort_value, detail


def render_rows(entries: list[dict]) -> str:
    rows: list[str] = []
    for entry in entries:
        medium = entry["aggregates"]["by_tier"]["medium"]
        identity = entry["model_identity"]
        model = (
            f'<a href="{esc(identity["url"])}" target="_blank" rel="noopener">'
            f'{esc(entry["model"])}</a>'
            f'<br><small>{esc(identity["name"])}</small>'
        )
        route = (
            f'{esc(entry["route"])}'
            f'<br><small>{esc(entry["runtime"]["name"])} {esc(entry["runtime"]["version"])}</small>'
        )
        provider = esc(entry["runtime"]["provider"])
        status = esc(entry["attempt_status"])
        status_class = entry["attempt_status"].replace("_", "-")
        memory_display, memory_sort, memory_detail = memory(entry)
        sanity_display, sanity_sort, sanity_detail = sanity(entry)
        setup = entry["setup"]["seconds"]
        ttft = medium["median_request_to_first_token_seconds"]
        prefill = medium["median_prefill_tokens_per_second"]
        decode = medium["median_decode_tokens_per_second"]
        rows.append(
            f'<tr data-route-id="{esc(entry["id"])}">'
            f'<td data-sort="{esc(entry["experiment"])}">{esc(entry["experiment"])}</td>'
            f'<td data-sort="{esc(entry["model"])}">{model}</td>'
            f'<td data-sort="{esc(entry["route"])}">{route}</td>'
            f'<td data-sort="{esc(entry["quantization"]["name"])}">{esc(entry["quantization"]["name"])}</td>'
            f'<td data-sort="{status}"><span class="status {esc(status_class)}">{status}</span></td>'
            f'<td data-sort="{provider}">{provider}</td>'
            f'<td data-sort="{sort_number(setup)}" title="{esc(entry["setup"]["boundary"])}">{seconds(setup)}</td>'
            f'<td data-sort="{sort_number(ttft)}" title="Loaded-route medium median request-to-first-token.">{seconds(ttft)}<br><small>medium median</small></td>'
            f'<td data-sort="{sort_number(prefill)}" title="Loaded-route medium median prefill throughput.">{rate(prefill)}<br><small>medium median</small></td>'
            f'<td data-sort="{sort_number(decode)}" title="Loaded-route medium median decode throughput.">{rate(decode)}<br><small>medium median</small></td>'
            f'<td data-sort="{memory_sort}" title="{esc(memory_detail)}">{memory_display}</td>'
            f'<td data-sort="{sanity_sort}" title="{esc(sanity_detail)}">{esc(sanity_display)}</td>'
            "</tr>"
        )
    return "\n".join(rows)


def build(registry: dict) -> str:
    entries = registry["entries"]
    if entries:
        content = f"""
<section class="table-panel" id="routes-panel" aria-labelledby="routes-title">
<div class="table-toolbar">
<div><h2 id="routes-title">Benchmark routes</h2><p class="scroll-hint" id="routes-scroll-hint">More columns are available horizontally when the table is wider than the window. Swipe, use a trackpad, or hold Shift while scrolling. Vertical scrolling stays with the page. Fullscreen uses the table's own vertical scroll.</p></div>
<div class="table-actions"><button type="button" class="table-control" id="routes-fullscreen" aria-controls="routes-panel" aria-pressed="false">Fullscreen table</button></div>
</div>
<div class="sticky-table-header" id="routes-sticky-header" aria-hidden="true" hidden><table id="routes-sticky-table"><thead></thead></table><div class="sticky-first-column-header">Experiment ↕</div></div>
<div class="table-viewport">
<div class="table-wrap" id="routes-scroll" tabindex="0" role="region" aria-label="Android LLM benchmark routes, horizontally scrollable; page controls vertical scrolling" aria-describedby="routes-scroll-hint">
<table id="routes"><thead><tr>
<th scope="col" data-type="text"><button type="button" class="sort-button">Experiment</button></th>
<th scope="col" data-type="text"><button type="button" class="sort-button">Model</button></th>
<th scope="col" data-type="text"><button type="button" class="sort-button">Route</button></th>
<th scope="col" data-type="text"><button type="button" class="sort-button">Quantization</button></th>
<th scope="col" data-type="text"><button type="button" class="sort-button">Status</button></th>
<th scope="col" data-type="text"><button type="button" class="sort-button">Provider</button></th>
<th scope="col" data-type="number"><button type="button" class="sort-button">Setup</button></th>
<th scope="col" data-type="number" aria-sort="ascending"><button type="button" class="sort-button">TTFT</button></th>
<th scope="col" data-type="number"><button type="button" class="sort-button">Prefill</button></th>
<th scope="col" data-type="number"><button type="button" class="sort-button">Decode</button></th>
<th scope="col" data-type="number"><button type="button" class="sort-button">Peak memory</button></th>
<th scope="col" data-type="number"><button type="button" class="sort-button">Output sanity</button></th>
</tr></thead><tbody>{render_rows(entries)}</tbody></table>
</div>
</div>
<p class="sr-only" id="routes-sort-status" aria-live="polite"></p>
</section>
"""
        script = """
<script>
const table=document.getElementById('routes');
const body=table.tBodies[0];
const headers=[...table.tHead.rows[0].cells];
const panel=document.getElementById('routes-panel');
const scrollRegion=document.getElementById('routes-scroll');
const fullscreenButton=document.getElementById('routes-fullscreen');
const sortStatus=document.getElementById('routes-sort-status');
const stickyHeader=document.getElementById('routes-sticky-header');
const stickyTable=document.getElementById('routes-sticky-table');
const stickyHead=table.tHead.cloneNode(true);
stickyTable.tHead.replaceWith(stickyHead);
const stickyHeaders=[...stickyHead.rows[0].cells];
stickyHead.querySelectorAll('button').forEach(button=>{button.tabIndex=-1;button.setAttribute('aria-hidden','true');});
function updateSortLabels(){
 headers.forEach(header=>{
  const button=header.querySelector('.sort-button');
  const direction=header.getAttribute('aria-sort');
  const suffix=direction?`. Current order: ${direction}. Activate to sort ${direction==='ascending'?'descending':'ascending'}.`:'. Activate to sort ascending.';
  button.setAttribute('aria-label',`Sort by ${button.textContent.trim()}${suffix}`);
 });
}
function sortTable(index,direction,announce=true){
 const type=headers[index].dataset.type;
 const rows=[...body.rows];
 rows.sort((a,b)=>{
  const av=a.cells[index].dataset.sort??'';
  const bv=b.cells[index].dataset.sort??'';
  if(av===''&&bv==='')return 0;
  if(av==='')return 1;
  if(bv==='')return -1;
  const cmp=type==='number'?Number(av)-Number(bv):av.localeCompare(bv,undefined,{numeric:true,sensitivity:'base'});
  return direction==='ascending'?cmp:-cmp;
 });
 body.append(...rows);
 headers.forEach(header=>header.removeAttribute('aria-sort'));
 stickyHeaders.forEach(header=>header.removeAttribute('aria-sort'));
 headers[index].setAttribute('aria-sort',direction);
 stickyHeaders[index].setAttribute('aria-sort',direction);
 updateSortLabels();
 if(announce)sortStatus.textContent=`Sorted by ${headers[index].querySelector('.sort-button').textContent.trim()}, ${direction}; unavailable values last.`;
}
headers.forEach((header,index)=>{
 const button=header.querySelector('.sort-button');
 button.addEventListener('click',()=>{
  const next=header.getAttribute('aria-sort')==='ascending'?'descending':'ascending';
  sortTable(index,next);
 });
});
function syncStickyHeader(){
 const sourceHead=table.tHead.getBoundingClientRect();
 const tableRect=table.getBoundingClientRect();
 const regionRect=scrollRegion.getBoundingClientRect();
 const show=document.fullscreenElement!==panel&&sourceHead.bottom<0&&tableRect.bottom>44;
 stickyHeader.hidden=!show;
 if(!show)return;
 stickyHeader.style.left=`${regionRect.left}px`;
 stickyHeader.style.width=`${regionRect.width}px`;
 stickyTable.style.width=`${table.scrollWidth}px`;
 stickyTable.style.transform=`translateX(${-scrollRegion.scrollLeft}px)`;
 headers.forEach((header,index)=>{stickyHeaders[index].style.width=`${header.getBoundingClientRect().width}px`;});
}
let stickyFrame=0;
function scheduleStickyHeader(){
 if(stickyFrame)return;
 stickyFrame=requestAnimationFrame(()=>{stickyFrame=0;syncStickyHeader();});
}
function updateScrollState(){
 const overflow=scrollRegion.scrollWidth>scrollRegion.clientWidth+1;
 const atStart=scrollRegion.scrollLeft<=1;
 const atEnd=table.getBoundingClientRect().right<=scrollRegion.getBoundingClientRect().right+1;
 panel.classList.toggle('has-overflow',overflow);
 panel.classList.toggle('at-start',atStart);
 panel.classList.toggle('at-end',atEnd);
 scheduleStickyHeader();
}
function jumpHorizontal(left){
 const previous=scrollRegion.style.scrollBehavior;
 scrollRegion.style.scrollBehavior='auto';
 scrollRegion.scrollLeft=left;
 scrollRegion.style.scrollBehavior=previous;
 updateScrollState();
}
scrollRegion.addEventListener('scroll',updateScrollState,{passive:true});
scrollRegion.addEventListener('keydown',event=>{
 if(event.target!==scrollRegion)return;
 const step=Math.max(160,Math.round(scrollRegion.clientWidth*.65));
 if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();scrollRegion.scrollBy({left:event.key==='ArrowLeft'?-step:step});}
 if(event.key==='Home'||event.key==='End'){event.preventDefault();jumpHorizontal(event.key==='Home'?0:scrollRegion.scrollWidth);}
});
async function toggleFullscreen(){
 try{
  if(document.fullscreenElement===panel)await document.exitFullscreen();
  else await panel.requestFullscreen({navigationUI:'hide'});
 }catch(error){sortStatus.textContent=`Fullscreen could not be opened: ${error.message}`;}
}
fullscreenButton.addEventListener('click',toggleFullscreen);
document.addEventListener('fullscreenchange',()=>{
 const active=document.fullscreenElement===panel;
 fullscreenButton.setAttribute('aria-pressed',String(active));
 fullscreenButton.textContent=active?'Exit fullscreen':'Fullscreen table';
 fullscreenButton.setAttribute('aria-label',active?'Exit table fullscreen; Escape also exits':'Open table fullscreen');
 updateScrollState();
 scheduleStickyHeader();
});
document.addEventListener('fullscreenerror',()=>{sortStatus.textContent='The browser refused table fullscreen.';});
if(!document.fullscreenEnabled){fullscreenButton.disabled=true;fullscreenButton.title='Fullscreen is not supported by this browser.';}
if('ResizeObserver' in window)new ResizeObserver(updateScrollState).observe(scrollRegion);
window.addEventListener('resize',updateScrollState);
window.addEventListener('scroll',scheduleStickyHeader,{passive:true});
sortTable(7,'ascending',false);
updateScrollState();
</script>
"""
    else:
        content = """
<section class="empty">
<h2>No committed LLM benchmark rows yet</h2>
<p>The protocol, validator, and publication path are ready. This dashboard will remain empty until a numbered experiment commits normalized route evidence.</p>
</section>
"""
        script = ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<link rel="icon" href="data:,">
<title>Android LLM benchmark registry</title>
<style>
:root {{--bg:#0f172a;--panel:#172033;--panel-strong:#1e293b;--line:#334155;--ink:#e5e7eb;--muted:#94a3b8;--accent:#67e8f9;--focus:#fbbf24}}
* {{box-sizing:border-box}}
html,body {{min-width:0}}
body {{margin:0;overflow-x:hidden;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
main {{width:100%;max-width:none;margin:0;padding:22px 24px}}
h1 {{font-size:24px;line-height:1.2;margin:0 0 10px}}
h2 {{font-size:20px;margin:30px 0 12px}}
small {{color:var(--muted)}}
a {{color:var(--accent)}}
button {{font:inherit}}
button:focus-visible,a:focus-visible,.table-wrap:focus-visible {{outline:3px solid var(--focus);outline-offset:3px}}
code {{color:#bae6fd}}
.lede {{max-width:82ch;margin:0;color:var(--muted)}}
.notice {{max-width:1000px;margin:18px 0;padding:14px 16px;border-left:4px solid var(--accent);background:#111b2d}}
.notice strong {{color:#bae6fd}}
.links {{display:flex;flex-wrap:wrap;gap:10px 18px;margin:16px 0 24px}}
.sr-only {{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}}
.empty {{margin-top:30px;padding:26px;border:1px solid var(--line);border-radius:12px;background:var(--panel)}}
.empty h2 {{margin-top:0}}
.table-panel {{width:100%;min-width:0;border:1px solid var(--line);border-radius:12px;background:var(--panel)}}
.table-toolbar {{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:12px 14px;border-bottom:1px solid var(--line);background:#111b2d;border-radius:12px 12px 0 0}}
.table-toolbar h2 {{margin:0;font-size:17px}}
.scroll-hint {{margin:3px 0 0;color:var(--muted);font-size:12px}}
.table-actions {{display:flex;justify-content:flex-end}}
.table-control {{min-height:36px;padding:7px 11px;border:1px solid #475569;border-radius:8px;background:var(--panel-strong);color:var(--ink);cursor:pointer}}
.table-control:hover:not(:disabled) {{border-color:var(--accent);color:var(--accent)}}
.table-control:disabled {{opacity:.42;cursor:not-allowed}}
.sticky-table-header {{position:fixed;z-index:100;top:0;overflow:hidden;border:1px solid var(--line);border-top:0;background:var(--panel-strong);box-shadow:0 8px 22px rgba(0,0,0,.32);pointer-events:none}}
.sticky-table-header[hidden] {{display:none}}
#routes-sticky-table {{table-layout:fixed;background:var(--panel-strong)}}
#routes-sticky-table th {{position:static;padding:0;background:var(--panel-strong);color:#bae6fd;white-space:nowrap}}
.sticky-first-column-header {{position:absolute;z-index:2;inset:0 auto 0 0;width:90px;padding:12px 13px;border-right:1px solid var(--line);background:var(--panel-strong);color:#bae6fd;font-weight:700;white-space:nowrap}}
.table-viewport {{position:relative;min-width:0}}
.table-viewport::before,.table-viewport::after {{content:"";position:absolute;z-index:5;top:0;bottom:14px;width:34px;pointer-events:none;opacity:0;transition:opacity .15s ease}}
.table-viewport::before {{left:0;background:linear-gradient(90deg,rgba(15,23,42,.95),transparent)}}
.table-viewport::after {{right:0;background:linear-gradient(270deg,rgba(15,23,42,.95),transparent)}}
.table-panel.has-overflow:not(.at-start) .table-viewport::before,.table-panel.has-overflow:not(.at-end) .table-viewport::after {{opacity:1}}
.table-wrap {{width:100%;min-width:0;max-height:none;overflow-x:auto;overflow-y:visible;overscroll-behavior-x:contain;border-radius:0 0 12px 12px;scroll-behavior:smooth}}
.table-wrap::-webkit-scrollbar {{width:14px;height:14px}}
.table-wrap::-webkit-scrollbar-track {{background:#0b1220}}
.table-wrap::-webkit-scrollbar-thumb {{border:3px solid #0b1220;border-radius:10px;background:#64748b}}
.table-wrap::-webkit-scrollbar-thumb:hover {{background:var(--accent)}}
table {{border-collapse:collapse;background:var(--panel)}}
#routes {{width:100%;min-width:1815px;table-layout:fixed}}
th,td {{padding:12px 13px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}
#routes td {{overflow-wrap:anywhere}}
#routes th:nth-child(1) {{width:90px}}
#routes th:nth-child(2) {{width:170px}}
#routes th:nth-child(3) {{width:205px}}
#routes th:nth-child(4) {{width:220px}}
#routes th:nth-child(5) {{width:85px}}
#routes th:nth-child(6) {{width:260px}}
#routes th:nth-child(7) {{width:100px}}
#routes th:nth-child(8) {{width:120px}}
#routes th:nth-child(9) {{width:130px}}
#routes th:nth-child(10) {{width:130px}}
#routes th:nth-child(11) {{width:135px}}
#routes th:nth-child(12) {{width:170px}}
#routes th {{position:sticky;z-index:3;top:0;padding:0;background:var(--panel-strong);color:#bae6fd;white-space:nowrap}}
#routes th:first-child {{z-index:4;left:0}}
#routes td:first-child {{position:sticky;z-index:2;left:0;background:var(--panel)}}
.sort-button {{display:block;width:100%;min-height:44px;padding:12px 13px;border:0;background:transparent;color:inherit;text-align:left;white-space:nowrap;cursor:pointer}}
.sort-button:hover {{background:#26364d}}
.sort-button::after {{content:' ↕';color:#64748b}}
th[aria-sort="ascending"] .sort-button::after {{content:' ↑';color:var(--accent)}}
th[aria-sort="descending"] .sort-button::after {{content:' ↓';color:var(--accent)}}
.status {{border-radius:99px;padding:3px 9px;font-size:12px;font-weight:700;white-space:nowrap}}
.ran {{background:#064e3b;color:#a7f3d0}}
.blocked,.deferred,.not-run {{background:#713f12;color:#fde68a}}
.partial {{background:#164e63;color:#a5f3fc}}
footer {{margin-top:16px;color:var(--muted);font-size:12px}}
.table-panel:fullscreen {{display:flex;width:100vw;height:100vh;padding:14px;border:0;border-radius:0;background:var(--bg);flex-direction:column}}
.table-panel:fullscreen .table-toolbar {{flex:0 0 auto;border:1px solid var(--line);border-radius:10px 10px 0 0}}
.table-panel:fullscreen .table-viewport {{flex:1 1 auto;min-height:0;border:1px solid var(--line);border-top:0}}
.table-panel:fullscreen .table-wrap {{height:100%;max-height:none;overflow:auto;overscroll-behavior:contain;border-radius:0}}
@media(max-width:700px) {{main {{padding:10px 8px 24px}}h1 {{font-size:21px}}.table-toolbar {{align-items:stretch;flex-direction:column}}.table-actions {{display:block}}.table-control {{width:100%}}.scroll-hint {{max-width:58ch}}}}
@media(prefers-reduced-motion:reduce) {{.table-wrap {{scroll-behavior:auto}}.table-viewport::before,.table-viewport::after {{transition:none}}}}
</style>
</head>
<body>
<main>
<h1>Android LLM benchmark registry</h1>
<p class="lede">Generic fixed-prompt inference measurements for local Android language-model routes. The dashboard keeps setup, TTFT, prefill, decode, memory, provenance, and raw-output sanity separate.</p>
<div class="notice"><strong>Output sanity is not quality.</strong> <code>looks_sensible</code> only screens each exact output hash for obvious corruption or gibberish. It does not establish correctness, grounding, transcript usefulness, or acceptance. Accelerator rows prove only their recorded provider/offload boundary; process PSS/VmHWM does not establish total GPU-private or vendor memory.</div>
<div class="links"><a href="registry.json">Registry JSON</a><a href="schema.json">Schema</a><a href="README.md">Registry documentation</a><a href="../../protocols/android-llm-benchmark/README.md">Benchmark protocol</a><a href="../android-benchmarks/index.html">TTS benchmarks</a></div>
{content}
<footer>Use the column buttons to sort; unavailable values always sort last. TTFT, prefill, and decode show loaded-route medium medians and remain tokenizer/route-specific. {len(entries)} normalized route entries. Generated by <code>docs/android-llm-benchmarks/build_registry.py</code> from committed registry evidence.</footer>
</main>
{script}</body>
</html>
"""


def main() -> None:
    subprocess.run([sys.executable, str(HERE / "validate.py")], cwd=ROOT, check=True)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    OUTPUT.write_text(build(registry), encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
