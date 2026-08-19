#!/usr/bin/env python3
"""Build the cross-experiment Android benchmark registry and dashboard.

The normalized registry is intentionally hand-curated from committed result files.
No estimate is introduced: unavailable values stay JSON null and are explained in
missing-fields.md. Run from the repository root:

    python3 docs/android-benchmarks/build_registry.py
"""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "android-benchmarks"
MEDIA = OUT / "media"

DEVICE = {"model": "SM-S918B", "soc": "SM8550", "serial": "R5CW81PR8SY", "abi": "arm64-v8a"}
NULL_METRICS = {
    "load_seconds": None,
    "cold_rtf": None,
    "warm_median_rtf": None,
    "peak_pss_bytes": None,
    "peak_vm_hwm_bytes": None,
}


def row(id, experiment, model, route, status, *, attempted, provider=None,
        precision=None, threads=None, metrics=None, wav=None, summary="",
        limitations=(), sources=(), missing=None, variant=None):
    m = dict(NULL_METRICS)
    if metrics:
        m.update(metrics)
    # Status describes execution only. Quality/listening decisions stay in evidence.
    status = {"success": "ran", "rejected": "ran"}.get(status, status)
    return {
        "id": id,
        "experiment": experiment,
        "model": model,
        "route": route,
        "deployment_variant": variant,
        "attempt_status": status,
        "android_attempted": attempted,
        "provider": provider,
        "precision": precision,
        "threads": threads,
        "device": DEVICE if attempted else None,
        "metrics": m,
        "wav": wav,
        "summary": summary,
        "limitations": list(limitations),
        "sources": list(sources),
        "missing_reasons": {
            **({"wav": "No locally verified Android WAV was retained for this route."} if wav is None else {}),
            **(missing or {}),
        },
    }


# Every route is represented, including deferred routes and routes stopped before
# session creation. Do not remove null rows: they document the evidence boundary.
ROWS = [
    row("0002-executorch-full", "0002", "VibeVoice 1.5B", "ExecuTorch/XNNPACK full generation", "partial", attempted=True, provider="XNNPACK", precision="FP32", metrics={"warm_median_rtf": None, "peak_vm_hwm_bytes": 1650288 * 1024}, summary="Component Android execution worked, but the complete fixed-shape generation was rejected: only 2.04% of the locked reference was covered, audio was effectively silent, and the package was about 9.1 GB.", limitations=("Not a practical end-to-end deployment.", "Final RTF is protocol-wall RTF; VibeVoice is not numerically accepted as useful speech."), sources=("experiments/0002-vibevoice-1.5b-executorch-android/README.md", "experiments/0002-vibevoice-1.5b-executorch-android/results/complete-build-final.json"), missing={"load_seconds": "Result has stage timings but no single normalized session-load value.", "cold_rtf": "The final report does not expose one cold-generation RTF.", "warm_median_rtf": "The published 109.26 value is protocol/prefix RTF without a retained normalized audio-duration denominator."}, variant="ExecuTorch 1.2 / XNNPACK"),
    row("0002-executorch-acoustic-decoder", "0002", "VibeVoice 1.5B", "ExecuTorch acoustic decoder component", "partial", attempted=True, provider="XNNPACK", precision="FP32", metrics={"load_seconds": 0.024192292, "cold_rtf": None, "warm_median_rtf": None, "peak_pss_bytes": 1401425 * 1024, "peak_vm_hwm_bytes": 1602328 * 1024}, summary="The fixed-shape acoustic-decoder probe loaded and executed on Android with numerical agreement, but it is a component probe, not complete speech generation.", limitations=("1.375 GB PTE; non-streaming; no end-to-end claim.",), sources=("experiments/0002-vibevoice-1.5b-executorch-android/results/acoustic-decoder-android.json",), missing={"cold_rtf": "Component result reports inference seconds, not audio duration or RTF.", "warm_median_rtf": "Component result reports inference seconds, not audio duration or RTF.", "wav": "The output is a PCM tensor probe, not a retained WAV."}, variant="ExecuTorch 1.2 / XNNPACK"),
    row("0003-litert-deferred", "0003", "VibeVoice 1.5B", "LiteRT Android conversion", "deferred", attempted=False, summary="A LiteRT conversion was documented as deferred; no Android deployment was run.", sources=("experiments/0003-vibevoice-1.5b-litert-android/README.md",), missing={"android_attempted": "README status is deferred; no phone run exists.", "all": "No Android measurements or audio can be inferred from the plan."}, variant="LiteRT"),
    row("0004-onnx-deferred", "0004", "VibeVoice 1.5B", "ONNX Runtime Mobile", "deferred", attempted=False, summary="The ONNX Runtime Mobile route was deferred before conversion and phone execution.", sources=("experiments/0004-vibevoice-1.5b-onnx-android/README.md",), missing={"android_attempted": "README status is deferred; no phone run exists.", "all": "No Android measurements or audio can be inferred from the plan."}, variant="ONNX Runtime Mobile"),
    row("0005-qnn-deferred", "0005", "VibeVoice 1.5B", "Direct Qualcomm QNN", "deferred", attempted=False, summary="The direct QNN route remained planned and blocked on a correct portable implementation.", sources=("experiments/0005-vibevoice-1.5b-qnn-android/README.md",), missing={"android_attempted": "README says planned and blocked; no phone run exists.", "all": "No Android measurements or audio can be inferred from the plan."}, variant="QNN"),
    row("0006-realtime-feasibility", "0006", "VibeVoice Realtime 0.5B", "Android feasibility inventory", "not_run", attempted=False, summary="The smaller VibeVoice model has feasibility and package estimates only; conversion and Android execution did not begin.", sources=("experiments/0006-vibevoice-realtime-0.5b-android/README.md", "experiments/0006-vibevoice-realtime-0.5b-android/feasibility-inventory.json"), missing={"android_attempted": "Inventory explicitly says no conversion has begun.", "all": "Host evidence is not Android evidence."}, variant="Feasibility only"),
    row("0008-pocket-cpu-t1", "0008", "Pocket TTS", "sherpa-onnx CPU", "success", attempted=True, provider="CPU", precision="INT8", threads=1, metrics={"load_seconds": 0.658703801, "cold_rtf": 0.4358031003580019, "warm_median_rtf": 0.38864718496483114, "peak_pss_bytes": 683577344, "peak_vm_hwm_bytes": 751427584}, summary="Pinned Pocket INT8 generated valid audio on the Galaxy S23 Ultra.", limitations=("Requested Alba was unavailable; packaged Bria was used and voice_match=false.", "Listening was not performed."), sources=("experiments/0008-sherpa-onnx-android-tts-benchmark/results/pocket/one-thread-result.json", "experiments/0008-sherpa-onnx-android-tts-benchmark/README.md"), missing={"wav": "The retained WAV is ignored and is not present in this checkout; its committed hash remains in the source result."}, variant="sherpa-onnx v1.13.5"),
    row("0008-kokoro-cpu-t1", "0008", "Kokoro", "sherpa-onnx CPU", "success", attempted=True, provider="CPU", precision="FP32", threads=1, metrics={"load_seconds": 1.303446875, "cold_rtf": 1.187996273027265, "warm_median_rtf": 1.1952115332875515, "peak_pss_bytes": 929677312, "peak_vm_hwm_bytes": 995078144}, summary="Exact Kokoro v1.0 SID 3/af_heart generated valid Android audio.", limitations=("Warm RTF is slower than real time.", "Listening was not performed."), sources=("experiments/0008-sherpa-onnx-android-tts-benchmark/results/kokoro/one-thread-result.json", "experiments/0008-sherpa-onnx-android-tts-benchmark/README.md"), missing={"wav": "The retained WAV is ignored and is not present in this checkout; its committed hash remains in the source result."}, variant="sherpa-onnx v1.13.5"),
    row("0008-supertonic-cpu-t1", "0008", "Supertonic 3", "sherpa-onnx CPU", "success", attempted=True, provider="CPU", precision="INT8", threads=1, metrics={"load_seconds": 0.765107603, "cold_rtf": 0.3854677480612432, "warm_median_rtf": 0.3703028479158501, "peak_pss_bytes": 463003648, "peak_vm_hwm_bytes": 531345408}, summary="Pinned Supertonic 3 INT8 with proven M1/SID5 generated valid Android audio and became the technical reference.", limitations=("Listening was not performed in the benchmark.",), sources=("experiments/0008-sherpa-onnx-android-tts-benchmark/results/supertonic-3/one-thread-result.json", "experiments/0008-sherpa-onnx-android-tts-benchmark/README.md"), missing={"wav": "The retained WAV is ignored and is not present in this checkout; its committed hash remains in the source result."}, variant="sherpa-onnx v1.13.5"),
    row("0009-pocket-cpu-t1", "0009", "Pocket TTS", "thread sweep CPU", "success", attempted=True, provider="CPU", precision="INT8", threads=1, metrics={"cold_rtf": 0.42988398361088564, "warm_median_rtf": 0.4080034914012739, "peak_pss_bytes": 682866688, "peak_vm_hwm_bytes": 748761088}, summary="Thread-sweep configuration succeeded with valid audio.", limitations=("This is an optimization sweep, not a new model baseline.",), sources=("experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json",), missing={"load_seconds": "The normalized configuration records load memory but not a load-wall scalar.", "wav": "Raw sweep WAV is ignored and is not present in this checkout."}, variant="sherpa-onnx Pocket / 1 thread"),
    row("0009-pocket-cpu-t2", "0009", "Pocket TTS", "thread sweep CPU", "success", attempted=True, provider="CPU", precision="INT8", threads=2, metrics={"cold_rtf": 0.37352320781966003, "warm_median_rtf": 0.3674131144286632, "peak_pss_bytes": 683354112, "peak_vm_hwm_bytes": 756277248}, summary="Thread-sweep configuration succeeded with valid audio.", limitations=("This is an optimization sweep, not a new model baseline.",), sources=("experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json",), missing={"load_seconds": "No normalized load-wall scalar.", "wav": "Raw sweep WAV is ignored and is not present in this checkout."}, variant="sherpa-onnx Pocket / 2 threads"),
    row("0009-pocket-cpu-t4", "0009", "Pocket TTS", "thread sweep CPU", "success", attempted=True, provider="CPU", precision="INT8", threads=4, metrics={"cold_rtf": 0.46249131178160924, "warm_median_rtf": 0.5114196852678572, "peak_pss_bytes": 683707392, "peak_vm_hwm_bytes": 757727232}, summary="Thread-sweep configuration succeeded with valid audio.", limitations=("This is an optimization sweep, not a new model baseline.",), sources=("experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json",), missing={"load_seconds": "No normalized load-wall scalar.", "wav": "Raw sweep WAV is ignored and is not present in this checkout."}, variant="sherpa-onnx Pocket / 4 threads"),
    row("0009-kokoro-cpu-t1", "0009", "Kokoro", "thread sweep CPU", "success", attempted=True, provider="CPU", precision="FP32", threads=1, metrics={"cold_rtf": 1.4208191257721876, "warm_median_rtf": 1.4237948396671942, "peak_pss_bytes": 918390784, "peak_vm_hwm_bytes": 992514048}, summary="Thread-sweep configuration succeeded with valid audio.", limitations=("This is an optimization sweep, not a new model baseline.",), sources=("experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json",), missing={"load_seconds": "No normalized load-wall scalar.", "wav": "Raw sweep WAV is ignored and is not present in this checkout."}, variant="sherpa-onnx Kokoro / 1 thread"),
    row("0009-kokoro-cpu-t2", "0009", "Kokoro", "thread sweep CPU", "success", attempted=True, provider="CPU", precision="FP32", threads=2, metrics={"cold_rtf": 1.0029200771472806, "warm_median_rtf": 1.038915274000276, "peak_pss_bytes": 930012160, "peak_vm_hwm_bytes": 995672064}, summary="Thread-sweep configuration succeeded with valid audio.", limitations=("This is an optimization sweep, not a new model baseline.",), sources=("experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json",), missing={"load_seconds": "No normalized load-wall scalar.", "wav": "Raw sweep WAV is ignored and is not present in this checkout."}, variant="sherpa-onnx Kokoro / 2 threads"),
    row("0009-kokoro-cpu-t4", "0009", "Kokoro", "thread sweep CPU", "success", attempted=True, provider="CPU", precision="FP32", threads=4, metrics={"cold_rtf": 0.8998508937883544, "warm_median_rtf": 0.7525562116011203, "peak_pss_bytes": 922871808, "peak_vm_hwm_bytes": 993865728}, summary="Thread-sweep configuration succeeded with valid audio.", limitations=("This is an optimization sweep, not a new model baseline.",), sources=("experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json",), missing={"load_seconds": "No normalized load-wall scalar.", "wav": "Raw sweep WAV is ignored and is not present in this checkout."}, variant="sherpa-onnx Kokoro / 4 threads"),
    row("0009-supertonic-cpu-t1", "0009", "Supertonic 3", "thread sweep CPU", "success", attempted=True, provider="CPU", precision="INT8", threads=1, metrics={"cold_rtf": 0.3888269229689508, "warm_median_rtf": 0.4009924891977482, "peak_pss_bytes": 459816960, "peak_vm_hwm_bytes": 532070400}, summary="Thread-sweep configuration succeeded with valid audio.", limitations=("This is an optimization sweep, not a new model baseline.",), sources=("experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json",), missing={"load_seconds": "No normalized load-wall scalar.", "wav": "Raw sweep WAV is ignored and is not present in this checkout."}, variant="sherpa-onnx Supertonic 3 / 1 thread"),
    row("0009-supertonic-cpu-t2", "0009", "Supertonic 3", "thread sweep CPU", "success", attempted=True, provider="CPU", precision="INT8", threads=2, metrics={"cold_rtf": 0.3550179197115431, "warm_median_rtf": 0.3624899421101892, "peak_pss_bytes": 460242944, "peak_vm_hwm_bytes": 534097920}, summary="Thread-sweep configuration succeeded with valid audio.", limitations=("This is an optimization sweep, not a new model baseline.",), sources=("experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json",), missing={"load_seconds": "No normalized load-wall scalar.", "wav": "Raw sweep WAV is ignored and is not present in this checkout."}, variant="sherpa-onnx Supertonic 3 / 2 threads"),
    row("0009-supertonic-cpu-t4", "0009", "Supertonic 3", "thread sweep CPU", "success", attempted=True, provider="CPU", precision="INT8", threads=4, metrics={"cold_rtf": 0.37137720493651893, "warm_median_rtf": 0.3985584226377708, "peak_pss_bytes": 461868032, "peak_vm_hwm_bytes": 532111360}, summary="Thread-sweep configuration succeeded with valid audio.", limitations=("This is an optimization sweep, not a new model baseline.",), sources=("experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json",), missing={"load_seconds": "No normalized load-wall scalar.", "wav": "Raw sweep WAV is ignored and is not present in this checkout."}, variant="sherpa-onnx Supertonic 3 / 4 threads"),
    row("0009-kokoro-int8-not-deployed", "0009", "Kokoro", "mixed INT8 host candidate", "not_run", attempted=False, provider="CPU", precision="INT8", summary="The selected mixed INT8 Kokoro candidate passed host and listening gates but was not deployed to Android in this experiment.", sources=("experiments/0009-android-tts-optimization/kokoro-int8/README.md", "experiments/0009-android-tts-optimization/kokoro-int8/reports/quality-gate.json"), missing={"android_attempted": "README explicitly says it has not been deployed to Android.", "all": "No Android timing, memory, or WAV exists."}, variant="Kokoro v1.0 mixed INT8"),
    row("0010-supertonic-cpu", "0010", "Supertonic 3", "official sherpa CPU control", "success", attempted=True, provider="CPU", precision="INT8", threads=1, metrics={"warm_median_rtf": 6.06733 / (729746 / 44100), "peak_vm_hwm_bytes": 459432 * 1024}, wav={"path":"media/0010-supertonic-cpu.wav","sha256":"7e83537630b3e354f7586b9887f7a8359d62e438c9addeea61d87d878b2a84ff","bytes":1459536,"sample_rate_hz":44100,"channels":1,"duration_seconds":729746/44100}, summary="CPU control for the fixed transcript-to-WAV HTP feasibility comparison.", limitations=("Fixed transcript/shape; CPU control for a diagnostic, not the 0008 benchmark replacement.",), sources=("experiments/0010-supertonic-qnn-htp-feasibility/results/e2e-hybrid-cpu-checkpoint.json",), missing={"load_seconds": "The checkpoint records component session creation but no single normalized load scalar for this row.", "cold_rtf": "The checkpoint records four run totals but does not label one as cold RTF."}, variant="Supertonic 3 fixed-shape CPU"),
    row("0010-supertonic-hybrid-htp", "0010", "Supertonic 3", "mixed QNN HTP + CPU fallback", "rejected", attempted=True, provider="QNN HTP + CPU fallback", precision="INT8", threads=None, metrics={"load_seconds": 26.965, "warm_median_rtf": 3.80935 / (729746 / 44100), "peak_vm_hwm_bytes": 1154172 * 1024}, wav={"path":"media/0010-supertonic-hybrid-htp.wav","sha256":"9b0d488776b144c972e8be4e9434fac14ce3ceddfcfa5a10d137fca41b772668","bytes":1459536,"sample_rate_hz":44100,"channels":1,"duration_seconds":729746/44100}, summary="Physical HTP execution worked and reduced warm latency 37.215%, but vector execution retained CPU fallback and the frozen waveform gate failed.", limitations=("Not full HTP; fixed shape; numerical gate failed (cosine 0.405431).", "ru_maxrss is cumulative process high-water memory."), sources=("experiments/0010-supertonic-qnn-htp-feasibility/results/e2e-hybrid-cpu-checkpoint.json",), missing={"cold_rtf": "The checkpoint reports run totals but does not label one as cold RTF."}, variant="Supertonic 3 QNN/HTP hybrid"),
    row("0011-supertonic-official-cpu", "0011", "Supertonic 3", "official FP32 ONNX CPU", "success", attempted=True, provider="CPUExecutionProvider", precision="FP32", threads=None, metrics={"load_seconds": 0.721546, "cold_rtf": 6.52928 / (729746 / 44100), "warm_median_rtf": 6.87038 / (729746 / 44100), "peak_vm_hwm_bytes": 569196 * 1024}, wav={"path":"media/0011-supertonic-official-fp32-cpu.wav","sha256":"8db92db13567b86be503d204fe367f2052b54dbfc99c0f7bfc5b23d9fd431da7","bytes":1459536,"sample_rate_hz":44100,"channels":1,"duration_seconds":729746/44100}, summary="Complete official FP32 ONNX chain ran on the authorized phone CPU and produced valid mono PCM16 WAV audio.", limitations=("Fixed T239/L238 contract; ru_maxrss is cumulative; no QNN events.",), sources=("experiments/0011-supertonic-official-fp32-phone-comparison/results/step1-phone-cpu-checkpoint.json",), missing={}, variant="Official Supertonic 3 FP32"),
    row("0011-supertonic-all-htp", "0011", "Supertonic 3", "all-HTP rewritten vector + CPU orchestration", "rejected", attempted=True, provider="QNNExecutionProvider (fallback disabled)", precision="FP32", threads=None, metrics={"load_seconds": 22.8147, "cold_rtf": 3.09085 / 16.547528344671203, "warm_median_rtf": 2.81831 / 16.547528344671203, "peak_vm_hwm_bytes": 1374408 * 1024}, wav={"path":"media/0011-supertonic-all-htp.wav","sha256":"47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c","bytes":1459536,"sample_rate_hz":44100,"channels":1,"duration_seconds":729746/44100}, summary="All four neural components physically ran on HTP with fallback disabled, but the frozen numerical policy failed (cosine 0.92668 < 0.95).", limitations=("Preprocessing/orchestration/WAV encoding remain CPU; rewritten vector is not the official graph; not numerically accepted.",), sources=("experiments/0011-supertonic-official-fp32-phone-comparison/results/softplus-matched-e2e-checkpoint.json", "experiments/0011-supertonic-official-fp32-phone-comparison/README.md"), missing={}, variant="Official Supertonic 3 FP32 + stable Softplus rewrite"),
    row("0011-supertonic-htp-fail-closed", "0011", "Supertonic 3", "original full HTP route", "blocked", attempted=True, provider="QNN (not executed)", precision="FP32", summary="The original full HTP route was stopped fail-closed after host/provider compatibility checks; no complete phone HTP synthesis was attempted.", sources=("experiments/0011-supertonic-official-fp32-phone-comparison/results/step2-fail-closed-htp-checkpoint.json",), missing={"metrics": "Fail-closed stop occurred before complete Android timing or WAV output.", "wav": "No complete route output exists."}, variant="Official Supertonic 3 original FP32 HTP"),
    row("0012-pocket-onnx-cpu", "0012", "Pocket TTS", "derived FP ONNX Runtime CPU", "success", attempted=True, provider="CPU", precision="FP32", threads=1, metrics={"load_seconds": 1.079322708, "cold_rtf": 0.912939803, "warm_median_rtf": 0.630365451, "peak_vm_hwm_bytes": 1586080 * 1024}, wav={"path":"media/0012-pocket-onnx-onnx-cpu.wav","sha256":"40634981606f37c59a91c14d99cecb3ef4cc21b1391882e870940b0716857d22","bytes":299564,"sample_rate_hz":24000,"channels":1,"duration_seconds":6.24}, summary="Five exact-source-derived FP ONNX components completed text-to-WAV on Android CPU; six outputs were byte-identical and warm median RTF was 0.630.", limitations=("Derived ONNX representation; no QNN/HTP claim; VmHWM is cumulative.",), sources=("experiments/0012-pocket-onnx-vs-executorch-android/results/comparison.json", "experiments/0012-pocket-onnx-vs-executorch-android/work/android-result.json", "experiments/0012-pocket-onnx-vs-executorch-android/RESULTS.md"), missing={}, variant="Pocket five-component FP ONNX"),
    row("0012-pocket-executorch", "0012", "Pocket TTS", "ExecuTorch route", "blocked", attempted=False, summary="Text conditioner and flow step exported, but essential recurrent FlowLM and Mimi decoder exports failed before any Android package or phone run.", sources=("experiments/0012-pocket-onnx-vs-executorch-android/results/comparison.json", "experiments/0012-pocket-onnx-vs-executorch-android/provenance/executorch-screen.json"), missing={"android_attempted": "Route was blocked before Android; no phone run was authorized.", "all": "No Android timing, memory, or WAV exists."}, variant="ExecuTorch"),
    row("0013-kokoro-onnx-bootstrap", "0013", "Kokoro", "derived FP32 ONNX Runtime CPU bootstrap", "blocked", attempted=True, provider="CPU (session not created)", precision="FP32", metrics={"load_seconds": None}, summary="Two authorized phone launches stopped at app asset bootstrap/scoped-storage visibility; no ONNX Runtime session or inference was created.", limitations=("Bootstrap/path failure only; not evidence of ONNX Runtime incompatibility.",), sources=("experiments/0013-kokoro-onnx-vs-executorch-android/results/phone-onnx-bootstrap-checkpoint.json",), missing={"load_seconds": "No session was created.", "cold_rtf": "No inference was attempted.", "warm_median_rtf": "No inference was attempted.", "peak_pss_bytes": "No inference process measurement exists.", "peak_vm_hwm_bytes": "No inference process measurement exists.", "wav": "No audio was produced."}, variant="Kokoro exact-source-derived FP32 ONNX"),
    row("0013-kokoro-onnx-cpu", "0013", "Kokoro", "exact-source-derived FP32 ONNX Runtime CPU", "success", attempted=True, provider="CPUExecutionProvider", precision="FP32", threads=1, metrics={"load_seconds": 0.797719, "cold_rtf": 0.982091, "warm_median_rtf": 0.979973, "peak_vm_hwm_bytes": 897974272}, wav={"path":"media/0013-kokoro-onnx-cpu.wav","sha256":"c046e8337b86ccf221ecd91db7dba90845f7c20b0ab1d8c248a36146c4eaecd3","bytes":364844,"sample_rate_hz":24000,"channels":1,"duration_seconds":7.6}, summary="The exact-source-derived FP32 ONNX route completed six Android CPU generations; all node events were CPU-only and the phase-tolerant acoustic gate passed. The preserved strict waveform screen remains a descriptive failure, not a listening verdict.", limitations=("Fixed T125/style123/duration-sum304 contract.", "VmHWM is cumulative process high-water memory.", "No ExecuTorch comparison output exists."), sources=("experiments/0013-kokoro-onnx-vs-executorch-android/results/phone-onnx-cpu-checkpoint.json", "experiments/0013-kokoro-onnx-vs-executorch-android/README.md"), missing={}, variant="Kokoro exact-source-derived FP32 ONNX"),
    row("0013-kokoro-executorch", "0013", "Kokoro", "ExecuTorch full model", "blocked", attempted=False, summary="The complete ExecuTorch route was blocked at host export/lowering and never reached Android.", sources=("experiments/0013-kokoro-onnx-vs-executorch-android/results/executorch-export-checkpoint.json", "experiments/0013-kokoro-onnx-vs-executorch-android/README.md"), missing={"android_attempted": "Required complex STFT/full wrapper lowering failed before Android.", "all": "No Android timing, memory, or WAV exists."}, variant="ExecuTorch"),
]


def verify_media():
    for r in ROWS:
        wav = r["wav"]
        if not wav:
            continue
        p = OUT / wav["path"]
        if not p.is_file():
            raise SystemExit(f"missing registry media: {p}")
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        if digest != wav["sha256"]:
            raise SystemExit(f"WAV hash mismatch for {r['id']}: {digest} != {wav['sha256']}")
        with wave.open(str(p), "rb") as f:
            observed = {"bytes": p.stat().st_size, "sample_rate_hz": f.getframerate(), "channels": f.getnchannels(), "duration_seconds": f.getnframes() / f.getframerate()}
        for key in ("bytes", "sample_rate_hz", "channels"):
            if observed[key] != wav[key]:
                raise SystemExit(f"WAV metadata mismatch for {r['id']}: {key}")
        if abs(observed["duration_seconds"] - wav["duration_seconds"]) > 1e-9:
            raise SystemExit(f"WAV duration mismatch for {r['id']}")
        wav["verified"] = True


def build_missing():
    lines = ["# Missing Android benchmark fields", "", "This report is generated by `build_registry.py`. `null` means the source evidence did not provide a measurement; it is not zero or an estimate.", ""]
    for r in ROWS:
        missing = r["missing_reasons"]
        if not missing:
            continue
        lines += [f"## `{r['id']}` — {r['model']} / {r['route']}", "", f"- Status: **{r['attempt_status']}**; Android attempted: **{str(r['android_attempted']).lower()}**"]
        for field, reason in missing.items():
            lines.append(f"- `{field}`: {reason}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_memory(metrics):
    if metrics["peak_pss_bytes"] is not None:
        value = metrics["peak_pss_bytes"]
        measurement = "peak PSS"
    elif metrics["peak_vm_hwm_bytes"] is not None:
        value = metrics["peak_vm_hwm_bytes"]
        measurement = "VmHWM / ru_maxrss"
    else:
        return "—", ""
    mib = value / (1024 * 1024)
    display = f"{mib / 1024:.2f} GiB" if mib >= 1024 else f"{mib:.1f} MiB"
    return f'{display}<br><small>{measurement}</small>', str(value)


def build_html(registry):
    entries = registry["entries"]
    trs = []
    players = []
    for e in entries:
        m = e["metrics"]
        rtf = "—" if m["warm_median_rtf"] is None else f'{m["warm_median_rtf"]:.3f}'
        if e["wav"]:
            anchor = f'audio-{e["id"]}'
            wav = f'<a href="#{html.escape(anchor)}">Listen</a>'
            players.append(
                f'<article class="player" id="{html.escape(anchor)}">'
                f'<div><b>{html.escape(e["model"])}</b><br><small>{html.escape(e["route"])}</small></div>'
                f'<audio controls preload="metadata" src="{html.escape(e["wav"]["path"])}"></audio>'
                f'<a class="back" href="#routes">Back to table</a>'
                f'</article>'
            )
        else:
            wav = "—"
        cls = e["attempt_status"].replace("_", "-")
        sort_rtf = "" if m["warm_median_rtf"] is None else str(m["warm_median_rtf"])
        audio_sort = "1" if e["wav"] else "0"
        memory, sort_memory = format_memory(m)
        provider = html.escape(e["provider"] or "—")
        if e["threads"] is not None:
            suffix = "thread" if e["threads"] == 1 else "threads"
            provider += f'<br><small>{e["threads"]} {suffix}</small>'
        trs.append(f'<tr><td data-sort="{html.escape(e["experiment"])}">{html.escape(e["experiment"])}</td><td data-sort="{html.escape(e["model"] + " " + e["route"])}"><b>{html.escape(e["model"])}</b><br><small>{html.escape(e["route"])}</small></td><td data-sort="{html.escape(e["attempt_status"])}"><span class="status {cls}">{html.escape(e["attempt_status"])}</span></td><td data-sort="{html.escape(e["provider"] or "")} {e["threads"] or ""}">{provider}</td><td data-sort="{sort_rtf}">{rtf}</td><td data-sort="{sort_memory}">{memory}</td><td data-sort="{audio_sort}">{wav}</td><td data-sort="{html.escape(e["summary"])}">{html.escape(e["summary"])}</td></tr>')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Android benchmark registry</title><style>
:root{{--bg:#0f172a;--panel:#172033;--line:#334155;--ink:#e5e7eb;--muted:#94a3b8;--accent:#67e8f9}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1500px;margin:auto;padding:22px 24px}}h1{{font-size:24px;line-height:1.2;margin:0 0 16px}}small{{color:var(--muted)}}a{{color:var(--accent)}}.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:12px}}table{{border-collapse:collapse;width:100%;min-width:1320px;background:var(--panel)}}th,td{{padding:12px 13px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}th{{position:sticky;top:0;background:#1e293b;color:#bae6fd;white-space:nowrap;user-select:none;cursor:pointer}}th:hover{{background:#26364d}}th::after{{content:' ↕';color:#64748b}}th[aria-sort="ascending"]::after{{content:' ↑';color:var(--accent)}}th[aria-sort="descending"]::after{{content:' ↓';color:var(--accent)}}td:nth-child(8){{min-width:350px;color:#cbd5e1}}.status{{border-radius:99px;padding:3px 9px;font-size:12px;font-weight:700;white-space:nowrap}}.ran{{background:#064e3b;color:#a7f3d0}}.blocked,.deferred,.not-run{{background:#713f12;color:#fde68a}}.partial{{background:#164e63;color:#a5f3fc}}code{{color:#bae6fd}}h2{{font-size:20px;margin:30px 0 12px}}.players{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}}.player{{scroll-margin-top:16px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}.player:target{{outline:2px solid var(--accent)}}.player audio{{display:block;width:100%;margin:11px 0 8px}}.back{{font-size:12px}}footer{{margin-top:16px;color:var(--muted);font-size:12px}}</style></head><body><main><h1>Android benchmark registry</h1><div class="table-wrap"><table id="routes"><thead><tr><th data-type="text">Experiment</th><th data-type="text">Model / route</th><th data-type="text">Status</th><th data-type="text">Provider</th><th data-type="number" aria-sort="ascending">Warm median RTF</th><th data-type="number">Peak memory</th><th data-type="number">Audio</th><th data-type="text">Evidence summary</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div><h2 id="audio-samples">Audio samples</h2><div class="players">{''.join(players)}</div><footer>Click a column heading to sort. Missing values sort last. Details: <a href="README.md">README</a> · <a href="missing-fields.md">missing fields</a>.</footer></main><script>
const table=document.getElementById('routes'), body=table.tBodies[0], headers=[...table.tHead.rows[0].cells];
function sortTable(index,direction){{
 const type=headers[index].dataset.type, rows=[...body.rows];
 rows.sort((a,b)=>{{
  const av=a.cells[index].dataset.sort??'', bv=b.cells[index].dataset.sort??'';
  if(av===''&&bv==='')return 0;if(av==='')return 1;if(bv==='')return -1;
  const cmp=type==='number'?Number(av)-Number(bv):av.localeCompare(bv,undefined,{{numeric:true,sensitivity:'base'}});
  return direction==='ascending'?cmp:-cmp;
 }});
 body.append(...rows);headers.forEach(h=>h.removeAttribute('aria-sort'));headers[index].setAttribute('aria-sort',direction);
}}
headers.forEach((header,index)=>header.addEventListener('click',()=>{{const next=header.getAttribute('aria-sort')==='ascending'?'descending':'ascending';sortTable(index,next)}}));
sortTable(4,'ascending');
</script></body></html>'''


def main():
    verify_media()
    registry = {
        "schema_version": 1,
        "registry_id": "android-benchmarks-v1",
        "device": DEVICE,
        "source_policy": "Normalize committed experiment evidence only; preserve null for unavailable fields; do not infer Android results from host evidence.",
        "entries": ROWS,
    }
    (OUT / "registry.json").write_text(json.dumps(registry, indent=2, sort_keys=False) + "\n")
    (OUT / "missing-fields.md").write_text(build_missing())
    dashboard = build_html(registry)
    (OUT / "index.html").write_text(dashboard)
    (OUT / "dashboard.html").write_text(dashboard)
    print(f"wrote {len(ROWS)} routes and {sum(bool(r['wav']) for r in ROWS)} verified WAV references")


if __name__ == "__main__":
    main()
