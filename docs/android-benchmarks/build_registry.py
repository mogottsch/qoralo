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
    "proof_run_rtf": None,
    "first_post_setup_rtf": None,
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
    structural = {
        "status": "valid" if wav is not None else "unavailable",
        "basis": "verified committed Android WAV container and source result" if wav is not None else None,
        "sample_sha256": wav["sha256"] if wav is not None else None,
    }
    objective = {
        "status": "descriptive",
        "summary": summary,
        "comparison_notes": [],
    }
    return {
        "id": id,
        "experiment": experiment,
        "model": model,
        "route": route,
        "deployment_variant": variant,
        "attempt_status": status,
        "technical_execution": {
            "status": status,
            "android_attempted": attempted,
            "provider": provider,
            "threads": threads,
        },
        "structural_audio": structural,
        "objective_evidence": objective,
        "listening_review": {
            "status": "not_reviewed",
            "reviewer": None,
            "date": None,
            "notes": None,
            "sample_sha256": wav["sha256"] if wav is not None else None,
        },
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
    row("0008-pocket-cpu-t1", "0008", "Pocket TTS", "sherpa-onnx CPU", "success", attempted=True, provider="CPU", precision="INT8", threads=1, metrics={"load_seconds": 0.658703801, "cold_rtf": 0.4358031003580019, "warm_median_rtf": 0.38864718496483114, "peak_pss_bytes": 683577344, "peak_vm_hwm_bytes": 751427584}, summary="Pinned Pocket INT8 generated valid audio on the Galaxy S23 Ultra. A later exact-archive host audit found its distinct encoder input-sensitive and Moritz accepted newly reproduced temperature-0.3 and 0.7 Bria samples; that does not retroactively review the missing historical Android WAVs.", limitations=("Requested Alba was unavailable; packaged Bria was used and voice_match=false.", "The historical Android WAVs were not listened to and remain unavailable; later accepted samples were exact-archive host reproductions, not those historical files.", "The archive encoder is distinct from the invalid zero-encoder 0012 checkpoint, but its tested traced output was fixed at 13 frames and the route remains research-only."), sources=("experiments/0008-sherpa-onnx-android-tts-benchmark/results/pocket/one-thread-result.json", "experiments/0008-sherpa-onnx-android-tts-benchmark/README.md", "experiments/0014-pocket-fp-onnx-qnn-htp/results/alba-quality-recovery.json", "experiments/0014-pocket-fp-onnx-qnn-htp/results/quality-recovery-listening.json"), missing={"wav": "The retained historical Android WAV is ignored and is not present in this checkout; its committed hash remains in the source result. Newly reviewed exact-archive host samples are distinct files."}, variant="sherpa-onnx v1.13.5"),
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
    row("0012-pocket-onnx-cpu", "0012", "Pocket TTS", "derived FP ONNX Runtime CPU", "success", attempted=True, provider="CPU", precision="FP32", threads=1, metrics={"load_seconds": 1.079322708, "cold_rtf": 0.912939803, "warm_median_rtf": 0.630365451, "peak_vm_hwm_bytes": 1586080 * 1024}, wav={"path":"media/0012-pocket-onnx-onnx-cpu.wav","sha256":"40634981606f37c59a91c14d99cecb3ef4cc21b1391882e870940b0716857d22","bytes":299564,"sample_rate_hz":24000,"channels":1,"duration_seconds":6.24}, summary="Five exact-source-derived FP ONNX components completed text-to-WAV on Android CPU; six outputs were byte-identical and warm median RTF was 0.630. Later root-cause evidence proved this route used an invalid audio-cloning contract whose no-voice-cloning checkpoint returned an all-zero voice embedding.", limitations=("Derived ONNX representation; no QNN/HTP claim; VmHWM is cumulative.", "All 42 Mimi encoder/encoder-transformer tensors (9,224,736 elements) in the pinned checkpoint were zero; source/ONNX numerical equivalence validated the broken contract, not speech quality.", "Experiment 0012 and its route/sample rejection remain historical evidence; the recovered fixed-Alba route is separate."), sources=("experiments/0012-pocket-onnx-vs-executorch-android/results/comparison.json", "experiments/0012-pocket-onnx-vs-executorch-android/work/android-result.json", "experiments/0012-pocket-onnx-vs-executorch-android/RESULTS.md", "experiments/0014-pocket-fp-onnx-qnn-htp/results/zero-voice-encoder-root-cause.json", "experiments/0014-pocket-fp-onnx-qnn-htp/results/alba-quality-recovery.json"), missing={}, variant="Pocket five-component FP ONNX / invalid cloning contract"),
    row("0012-pocket-executorch", "0012", "Pocket TTS", "ExecuTorch route", "blocked", attempted=False, summary="Text conditioner and flow step exported, but essential recurrent FlowLM and Mimi decoder exports failed before any Android package or phone run.", sources=("experiments/0012-pocket-onnx-vs-executorch-android/results/comparison.json", "experiments/0012-pocket-onnx-vs-executorch-android/provenance/executorch-screen.json"), missing={"android_attempted": "Route was blocked before Android; no phone run was authorized.", "all": "No Android timing, memory, or WAV exists."}, variant="ExecuTorch"),
    row("0014-pocket-qnn-fp-source", "0014", "Pocket TTS", "full QNN FP-source observed path", "ran", attempted=True, provider="QNNExecutionProvider (observed path; CPU orchestration only)", precision="FP source / QNN FP16 observed", threads=1, metrics={"load_seconds": 236.175, "cold_rtf": None, "proof_run_rtf": 0.781049, "peak_vm_hwm_bytes": 4136636416}, wav={"path":"media/0014-pocket-full-qnn-fp-source.wav","sha256":"467e777879691237472b51f5ccf9a8d43dae337cf63c2344ed3cfb645948c7f3","bytes":384044,"sample_rate_hz":24000,"channels":1,"duration_seconds":8.0}, summary="Observed full-QNN FP-source text-to-WAV path used 216 QNN and 0 CPU provider events with matching physical RPC/accelerator/cycle/HVX proof; setup was 236.175 s and normalized RTF 0.781. CPU remained orchestration/state/WAV work, not neural provider execution.", limitations=("Decoder6 passed a host gate but was unused and has no physical execution proof in this observed path.", "The 0012 comparator had effective temperature 0.7 rather than the prose-declared 0.3 due protocol drift; this is descriptive context, not a rewrite of 0012.", "One profiled generation only; VmHWM is cumulative process high-water memory."), sources=("experiments/0014-pocket-fp-onnx-qnn-htp/results/full-qnn-continuation.json", "experiments/0014-pocket-fp-onnx-qnn-htp/RESULTS.md"), missing={"cold_rtf": "One profiled generation was recorded; no separate cold campaign exists."}, variant="Pocket FP source full-QNN observed path"),
    row("0014-pocket-qnn-int16-flow", "0014", "Pocket TTS", "full QNN INT16-FlowLM observed path", "ran", attempted=True, provider="QNNExecutionProvider (observed path; CPU orchestration only)", precision="INT16 FlowLM / QNN full observed", threads=1, metrics={"load_seconds": 220.405, "cold_rtf": None, "proof_run_rtf": 1.00046, "peak_vm_hwm_bytes": 4147552256}, wav={"path":"media/0014-pocket-full-qnn-int16-flow.wav","sha256":"dcdb36df3d8cb8fc8754257fe060d5a4b2deb7c49983d579b8f90c3aa5035820","bytes":349484,"sample_rate_hz":24000,"channels":1,"duration_seconds":7.28}, summary="Observed full-QNN INT16-FlowLM text-to-WAV path used 201 QNN and 0 CPU provider events with matching physical RPC/accelerator/cycle/HVX proof; setup was 220.405 s and normalized RTF 1.00046. CPU remained orchestration/state/WAV work, not neural provider execution.", limitations=("Decoder6 passed a host gate but was unused and has no physical execution proof in this observed path.", "The 0012 comparator had effective temperature 0.7 rather than the prose-declared 0.3 due protocol drift; this is descriptive context, not a rewrite of 0012.", "One profiled generation only; VmHWM is cumulative process high-water memory."), sources=("experiments/0014-pocket-fp-onnx-qnn-htp/results/full-qnn-continuation.json", "experiments/0014-pocket-fp-onnx-qnn-htp/RESULTS.md"), missing={"cold_rtf": "One profiled generation was recorded; no separate cold campaign exists."}, variant="Pocket calibrated INT16-FlowLM full-QNN observed path"),
    row("0014-pocket-alba-original-dynamic-cpu", "0014", "Pocket TTS", "original dynamic Android CPU with fixed Alba state", "rejected", attempted=True, provider="CPUExecutionProvider", precision="FP32", metrics={"load_seconds": 1.01087, "proof_run_rtf": 0.52625, "peak_vm_hwm_bytes": 712312 * 1024}, wav={"path":"media/0014-pocket-alba-original-dynamic-cpu.wav","sha256":"cdf77f6ecaecdbb1a95992326675972366b57da864864f7359890b7e2df5c4b6","bytes":514604,"sample_rate_hz":24000,"channels":1,"duration_seconds":10.72}, summary="The controlled original dynamic FP ONNX route completed on Android CPU from the official fixed Alba state, but recurrent divergence appeared before the first sampled latent, EOS never fired, the run hit the 134-frame cap, and Moritz rejected this exact sample. Its measured RTF 0.52625 is execution evidence, not a quality verdict.", limitations=("Exact fixed text, official fixed Alba state, seed 0, temperature 0.3, and one capped run only; no voice-cloning claim.", "The dynamic recurrent Android route is a separate platform/runtime fidelity failure; it does not invalidate the recovered fixed-cache derivative.", "VmHWM is cumulative process high-water memory, not isolated model memory."), sources=("experiments/0014-pocket-fp-onnx-qnn-htp/results/android-alba-original-cpu.json", "experiments/0014-pocket-fp-onnx-qnn-htp/results/alba-quality-recovery.json", "experiments/0014-pocket-fp-onnx-qnn-htp/results/quality-recovery-listening.json"), missing={"cold_rtf": "The record contains one controlled run and does not label it a cold campaign.", "warm_median_rtf": "No warm distribution or median was recorded.", "first_post_setup_rtf": "The record does not give the dedicated unprofiled first-post-setup measurement used by the recovered HTP route.", "peak_pss_bytes": "Only cumulative process VmHWM was recorded."}, variant="Original dynamic FP ONNX / official fixed Alba"),
    row("0014-pocket-alba-fixed-cpu", "0014", "Pocket TTS", "fixed-cache Android CPU with fixed Alba state", "ran", attempted=True, provider="CPUExecutionProvider", precision="FP32", metrics={"load_seconds": 2.60302, "proof_run_rtf": 0.411953, "peak_vm_hwm_bytes": 1294420 * 1024}, wav={"path":"media/0014-pocket-alba-fixed-cpu.wav","sha256":"e0638f35870b24fbe675649a0cd49fa69ca6d74060557bfec5336d2d03a21c9a","bytes":215084,"sample_rate_hz":24000,"channels":1,"duration_seconds":4.48}, summary="The QNN-compatible fixed-cache FP derivative completed the canonical fixed-Alba text-to-WAV contract on Android CPU at RTF 0.411953, reached EOS at step 53 with 56 frames, and Moritz accepted this exact sample as sounding good.", limitations=("Exact fixed text, official fixed Alba state SHA e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c, seed 0, temperature 0.3, and one fixed shape only; fixed voice, not voice cloning.", "One run only; no warm median/min/max distribution and no streaming first-audio latency.", "VmHWM is cumulative process high-water memory, not isolated model memory."), sources=("experiments/0014-pocket-fp-onnx-qnn-htp/results/alba-quality-recovery.json", "experiments/0014-pocket-fp-onnx-qnn-htp/results/quality-recovery-listening.json", "experiments/0014-pocket-fp-onnx-qnn-htp/results/zero-voice-encoder-root-cause.json"), missing={"cold_rtf": "The record contains one controlled generation and does not label it a cold campaign.", "warm_median_rtf": "No warm distribution or median was recorded.", "first_post_setup_rtf": "No distinct first-post-setup timing was recorded for the CPU route.", "peak_pss_bytes": "Only cumulative process VmHWM was recorded."}, variant="Fixed-cache FP derivative / official fixed Alba"),
    row("0014-pocket-alba-fixed-qnn-htp", "0014", "Pocket TTS", "fallback-disabled full QNN/HTP with fixed Alba state", "ran", attempted=True, provider="QNNExecutionProvider (fallback disabled; CPU orchestration only)", precision="FP source / QNN HTP FP16", metrics={"load_seconds": 58.1983, "proof_run_rtf": 0.525063, "first_post_setup_rtf": 0.165244, "peak_vm_hwm_bytes": 2447980 * 1024}, wav={"path":"media/0014-pocket-alba-fixed-qnn-htp.wav","sha256":"2c3901ec39a53596759c1d95381a1d67e4f9ca8886cdf39ac03721863c63eb56","bytes":215084,"sample_rate_hz":24000,"channels":1,"duration_seconds":4.48}, summary="Fallback-disabled full QNN/HTP completed the canonical fixed-Alba route with 122 QNN and 0 CPU neural provider events plus matching 122 RPC, accelerator, cycle, and HVX records. The profiled proof run had setup 58.1983 s, RTF 0.525063, and VmHWM 2,506,731,520 bytes; a separate byte-identical unprofiled first complete post-setup generation had setup 66.6948 s, RTF 0.165244, and VmHWM 2,294,972,416 bytes. Moritz independently accepted the exact sample as sounding good.", limitations=("The 0.165244 value is one unprofiled first complete generation after setup, not a warm median or distribution.", "CPU supplied fixed tokens, the prepacked official Alba state, deterministic noise, recurrent tensor ownership, EOS scanning/orchestration, concatenation, and WAV encoding; all invoked neural sessions were physically proven on HTP.", "Exact fixed text, official fixed Alba state SHA e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c, seed 0, temperature 0.3, 56-frame observed path only; fixed voice, not voice cloning.", "No warm median/min/max distribution or streaming first-audio latency; VmHWM is cumulative process high-water including sessions, QNN contexts, caches, buffers, profiles where enabled, and output."), sources=("experiments/0014-pocket-fp-onnx-qnn-htp/results/alba-quality-recovery.json", "experiments/0014-pocket-fp-onnx-qnn-htp/results/quality-recovery-listening.json", "experiments/0014-pocket-fp-onnx-qnn-htp/results/zero-voice-encoder-root-cause.json"), missing={"cold_rtf": "Neither run is labeled a cold campaign.", "warm_median_rtf": "No warm distribution or median exists; the 0.165244 measurement is one first complete post-setup generation.", "peak_pss_bytes": "Only cumulative process VmHWM was recorded; the primary field retains the profiled proof-run VmHWM."}, variant="Fixed-cache FP derivative / full fallback-disabled QNN HTP"),
    row("0016-pocket-qnn-hybrid-cpu", "0016", "Pocket TTS", "mixed QNN HTP + CPU fallback", "ran", attempted=True, provider="QNN HTP + CPU fallback", precision="FP32 source graphs", threads=1, metrics={"load_seconds": 2.829669739, "cold_rtf": 1.202828138, "warm_median_rtf": 1.002830145, "peak_vm_hwm_bytes": 1216598016}, wav={"path":"media/0016-pocket-qnn-hybrid-cpu.wav","sha256":"6cd3a98fb821ad76b0c0ad55a20f910da7be9d3058e511ff807b4a4f694aa45f","bytes":184364,"sample_rate_hz":24000,"channels":1,"duration_seconds":3.84}, summary="Complete Pocket text-to-WAV execution used 45,117 CPU and 1,515 QNN events (3.249% QNN event fraction) with physical HTP execution proven. Normalized warm RTF was 59.1% worse than the 0012 CPU route; EOS ended at 48 versus 78 latent frames and output was not equivalent.", limitations=("Mixed route, not full HTP; QNN internal HTP precision was not established.", "The shorter 3.84 s output is not equivalent to the 0012 6.24 s output.", "VmHWM is cumulative process high-water memory; profiling run was excluded from timing."), sources=("experiments/0016-pocket-onnx-qnn-hybrid-android/results/hybrid-phone.json", "experiments/0016-pocket-onnx-qnn-hybrid-android/protocol.json", "experiments/0016-pocket-onnx-qnn-hybrid-android/RESULTS.md"), missing={}, variant="Pocket exact FP ONNX + QNN HTP/CPU hybrid"),
    row("0013-kokoro-onnx-bootstrap", "0013", "Kokoro", "derived FP32 ONNX Runtime CPU bootstrap", "blocked", attempted=True, provider="CPU (session not created)", precision="FP32", metrics={"load_seconds": None}, summary="Two authorized phone launches stopped at app asset bootstrap/scoped-storage visibility; no ONNX Runtime session or inference was created.", limitations=("Bootstrap/path failure only; not evidence of ONNX Runtime incompatibility.",), sources=("experiments/0013-kokoro-onnx-vs-executorch-android/results/phone-onnx-bootstrap-checkpoint.json",), missing={"load_seconds": "No session was created.", "cold_rtf": "No inference was attempted.", "warm_median_rtf": "No inference was attempted.", "peak_pss_bytes": "No inference process measurement exists.", "peak_vm_hwm_bytes": "No inference process measurement exists.", "wav": "No audio was produced."}, variant="Kokoro exact-source-derived FP32 ONNX"),
    row("0013-kokoro-onnx-cpu", "0013", "Kokoro", "exact-source-derived FP32 ONNX Runtime CPU", "success", attempted=True, provider="CPUExecutionProvider", precision="FP32", threads=1, metrics={"load_seconds": 0.797719, "cold_rtf": 0.982091, "warm_median_rtf": 0.979973, "peak_vm_hwm_bytes": 897974272}, wav={"path":"media/0013-kokoro-onnx-cpu.wav","sha256":"c046e8337b86ccf221ecd91db7dba90845f7c20b0ab1d8c248a36146c4eaecd3","bytes":364844,"sample_rate_hz":24000,"channels":1,"duration_seconds":7.6}, summary="The exact-source-derived FP32 ONNX route completed six Android CPU generations; all node events were CPU-only and the phase-tolerant acoustic gate passed. The preserved strict waveform screen remains a descriptive failure, not a listening verdict.", limitations=("Fixed T125/style123/duration-sum304 contract.", "VmHWM is cumulative process high-water memory.", "No ExecuTorch comparison output exists."), sources=("experiments/0013-kokoro-onnx-vs-executorch-android/results/phone-onnx-cpu-checkpoint.json", "experiments/0013-kokoro-onnx-vs-executorch-android/README.md"), missing={}, variant="Kokoro exact-source-derived FP32 ONNX"),
    row("0013-kokoro-executorch", "0013", "Kokoro", "ExecuTorch full model", "blocked", attempted=False, summary="The complete ExecuTorch route was blocked at host export/lowering and never reached Android.", sources=("experiments/0013-kokoro-onnx-vs-executorch-android/results/executorch-export-checkpoint.json", "experiments/0013-kokoro-onnx-vs-executorch-android/README.md"), missing={"android_attempted": "Required complex STFT/full wrapper lowering failed before Android.", "all": "No Android timing, memory, or WAV exists."}, variant="ExecuTorch"),
    row("0017-kokoro-qnn-host-blocked", "0017", "Kokoro", "fixed-contract QNN HTP host gate", "blocked", attempted=False, provider="QNNExecutionProvider (host assignment gate)", precision="FP32 source graph", threads=1, summary="The bit-exact fixed-contract derivative reached complete host QNN assignment in one partition, but the fallback-disabled host session was OOM-killed during graph sequencing before session finalization or inference; the phone was not accessed.", limitations=("QNN assignment is not execution or physical HTP proof.", "No finalized host session, inference, Android attempt, timing, memory, or audio evidence exists.", "The 18-stage CPU recomposition is host-only equivalence evidence and is not a complete Android route."), sources=("experiments/0017-kokoro-onnx-qnn-htp-android/results/host-gate-checkpoint.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/qnn-compat-cpu-equivalence.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/stage-decomposition-provenance.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/stage-cpu-equivalence.json", "experiments/0017-kokoro-onnx-qnn-htp-android/README.md"), missing={"android_attempted": "The host session did not finalize and the phone was not accessed.", "all": "Host assignment and CPU equivalence do not provide Android timing, memory, physical HTP, or WAV evidence."}, variant="Kokoro exact-source fixed-contract QNN feasibility"),
    row("0018-moss-tts-nano-cpu", "0018", "MOSS-TTS-Nano", "official ONNX Runtime CPU", "ran", attempted=True, provider="CPUExecutionProvider", precision="FP32", threads=4, metrics={"load_seconds": 1.712838853, "cold_rtf": 1.1383426748803827, "warm_median_rtf": 1.1248052010167464, "peak_vm_hwm_bytes": 5828526080}, wav={"path":"media/0018-moss-tts-nano-onnx-cpu.wav","sha256":"173850781b055e70a606fb561d93b70e6d8c6318db1b29b2324f83506c21ad6b","bytes":1605164,"sample_rate_hz":48000,"channels":1,"duration_seconds":16.72}, summary="Official MOSS-TTS-Nano completed text-to-WAV on CPUExecutionProvider only with 543,972/543,972 CPU node events. The full decoded output is 16.72 s, with non-streaming first decoded PCM semantics; setup was 1.71284 s and the process VmHWM reached 5,828,526,080 bytes.", limitations=("4 intra-op / 1 inter-op threads; the route is non-streaming and first decoded PCM means full audio-tokenizer decode returned PCM, not a streaming chunk.", "VmHWM is cumulative process high-water memory, not component-isolated memory.", "An initial exec-out stdin staging attempt hung and was aborted; the successful fast-push staging caveat is not included in benchmark latency."), sources=("experiments/0018-moss-tts-nano-onnx-android/results/phone-cpu-checkpoint.json", "experiments/0018-moss-tts-nano-onnx-android/results/source-inventory.json", "experiments/0018-moss-tts-nano-onnx-android/README.md"), missing={}, variant="MOSS-TTS-Nano official ONNX"),
    row("0019-moss-tts-nano-qnn-blocked", "0019", "MOSS-TTS-Nano", "reusable dynamic decode QNN HTP host gate", "blocked", attempted=False, provider="QNNExecutionProvider (host gate)", precision="FP32 official ONNX", metrics={}, summary="Blocked before Android: reusable dynamic decode failed closed at 52/1,091 optimized nodes across 13 partitions with 1,039 unsupported nodes. No phone, physical HTP, timing, memory, or audio evidence exists.", limitations=("Fixed-shape rewrites made prefill/local/codec and all 209 observed decode shapes fully QNN-assignable on host, but 209 sessions required 1,052.77 s total host session creation and do not form a reusable deployable route.", "Decoder redesign requires fixed-capacity KV-cache/state topology with fixed outputs and dynamic valid-length masking; this is not a narrow operator rewrite.", "No QNN physical phone claim, CPU fallback, quantization, timing, memory, or WAV claim is made."), sources=("experiments/0019-moss-tts-nano-qnn-htp-android/results/host-checkpoint.json", "experiments/0019-moss-tts-nano-qnn-htp-android/results/decode-static-gate-matrix.json", "experiments/0019-moss-tts-nano-qnn-htp-android/results/source-lock.json", "experiments/0019-moss-tts-nano-qnn-htp-android/README.md"), missing={"android_attempted": "Host gate failed closed before Android and no phone staging occurred.", "all": "No Android timing, memory, physical HTP, or audio evidence exists."}, variant="MOSS-TTS-Nano QNN HTP host feasibility"),
    row("0020-supertonic-refresh-bootstrap", "0020", "Supertonic 3", "historical CPU refresh bootstrap", "blocked", attempted=True, provider="CPU (inference not started)", precision="INT8", threads=1, summary="A refreshed attempt preserved the exact historical 0008 contract and passed the Windows-ADB device gate, but Android 16 denied the app access to shell-owned scoped-storage inputs; inference never started and every refreshed metric remains unavailable. The original 0008 measurements remain separate historical evidence.", limitations=("This is staging-ownership evidence only, not model/runtime compatibility or refreshed performance evidence.", "Earlier zero-device readiness observations remain valid for their timestamps; a later Windows-ADB readiness check reached the exact canonical phone.", "Prepared build and archive hashes do not establish execution."), sources=("experiments/0020-historic-android-benchmark-refresh/results/registry-audit.json", "experiments/0020-historic-android-benchmark-refresh/results/device-readiness.json", "experiments/0020-historic-android-benchmark-refresh/results/device-readiness-attempt-2.json", "experiments/0020-historic-android-benchmark-refresh/results/device-readiness-windows-adb.json", "experiments/0020-historic-android-benchmark-refresh/results/supertonic-build-provenance.json", "experiments/0020-historic-android-benchmark-refresh/results/supertonic-bootstrap-attempt.json"), missing={"load_seconds": "The refreshed route stopped at app bootstrap before model/session setup.", "cold_rtf": "Inference did not start.", "warm_median_rtf": "Inference did not start; no refreshed warm campaign exists.", "peak_pss_bytes": "No inference process measurement exists.", "peak_vm_hwm_bytes": "No inference process measurement exists.", "wav": "No refreshed audio was produced."}, variant="Exact 0008 Supertonic CPU refresh attempt"),
    row("0021-supertonic-int8-cpu-v2", "0021", "Supertonic 3", "canonical-v2 released-INT8 CPU", "ran", attempted=True, provider="CPU", precision="INT8", threads=1, metrics={"load_seconds": 0.853867031, "cold_rtf": 0.39552098915111206, "warm_median_rtf": 0.3956153837777073, "first_post_setup_rtf": 0.39552098915111206, "peak_pss_bytes": 480366592, "peak_vm_hwm_bytes": 548986880}, wav={"path":"media/0021-supertonic-int8-cpu-v2.wav","sha256":"201f8e79d39e2fbb9db8a64a9f139641db9e27fabb828bcc039286a49c8987df","bytes":1393090,"sample_rate_hz":44100,"channels":1,"duration_seconds":696523/44100}, summary="New canonical-v2 Supertonic 3 INT8 Android CPU route: exact 226-byte transcript SHA 424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67, official unicode-indexer frontend mapping, one created OfflineTts, one first generation, and five warm same-session independent generate calls. Every output had 696,523 samples (15.794172 s). Warm median RTF was 0.395615 from [0.390631, 0.391386, 0.395615, 0.395708, 0.397157].", limitations=("This is a new canonical-v2 route, not a rewrite of or matched performance delta against legacy-v1 Supertonic rows; the transcript and output duration differ.", "The first-post-setup and cold RTF fields refer to the same first complete generation, not two observations.", "Pinned archive SHA 82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427, AAR SHA 6419cd8bc983e0c4fab06067f0fe0313fdc0f7103818ac1e7a08d50787b7a82b, sherpa revision 3dc7c569f31ca2cd4a20ed6f7db780327e6714c5, M1/SID5, English, one CPU thread.", "Peak PSS is sampled process PSS; peak boundary PSS was 479,744,000 bytes; VmHWM is cumulative process-lifetime high-water memory.", "The historical harness does not emit an ORT provider profile; provider=CPU is established by the pinned descriptor and engine. Thermal gate was NONE at 33.8°C, USB powered, with no device tuning.", "The representative PCM16 WAV is structurally valid but not reviewed; no legacy Supertonic listening verdict transfers."), sources=("experiments/0021-supertonic-canonical-v2-android-cpu/results/phone-cpu-result.json", "experiments/0021-supertonic-canonical-v2-android-cpu/results/frontend-provenance.json", "experiments/0021-supertonic-canonical-v2-android-cpu/results/build-and-stage-provenance.json", "experiments/0021-supertonic-canonical-v2-android-cpu/results/transport-and-cleanup.json", "experiments/0021-supertonic-canonical-v2-android-cpu/README.md"), missing={"proof_run_rtf": "No separate instrumented proof run was collected; this CPU route uses the unprofiled first and five warm timing campaign.", "provider_profile": "The historical harness does not enable ORT provider profiling; CPU provider provenance is established by the pinned descriptor/engine contract."}, variant="Canonical v2 / Supertonic released INT8 ONNX / CPU"),
]


def source_identity(name, url, revision=None):
    return {"name": name, "url": url, "revision": revision}


VIBEVOICE_SOURCE = source_identity(
    "microsoft/VibeVoice-1.5B",
    "https://huggingface.co/microsoft/VibeVoice-1.5B/tree/c00898d257e6b46004e3e2866a47534085fb685a",
    "c00898d257e6b46004e3e2866a47534085fb685a",
)
REALTIME_SOURCE = source_identity(
    "microsoft/VibeVoice-Realtime-0.5B",
    "https://huggingface.co/microsoft/VibeVoice-Realtime-0.5B/tree/6bce5f06044837fe6d2c5d7a71a84f0416bd57e4",
    "6bce5f06044837fe6d2c5d7a71a84f0416bd57e4",
)
POCKET_ARCHIVE_SOURCE = source_identity(
    "sherpa-onnx-pocket-tts-int8-2026-01-26",
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/sherpa-onnx-pocket-tts-int8-2026-01-26.tar.bz2",
)
KOKORO_ARCHIVE_SOURCE = source_identity(
    "kokoro-multi-lang-v1_0 (sherpa-onnx archive)",
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2",
)
SUPERTONIC_SOURCE = source_identity(
    "Supertone/supertonic-3",
    "https://huggingface.co/Supertone/supertonic-3/tree/724fb5abbf5502583fb520898d45929e62f02c0b",
    "724fb5abbf5502583fb520898d45929e62f02c0b",
)
POCKET_HF_SOURCE = source_identity(
    "kyutai/pocket-tts-without-voice-cloning",
    "https://huggingface.co/kyutai/pocket-tts-without-voice-cloning/tree/d29db7978e464fb90cb3359ee0c69a273b9142cc",
    "d29db7978e464fb90cb3359ee0c69a273b9142cc",
)
KOKORO_HF_SOURCE = source_identity(
    "hexgrad/Kokoro-82M",
    "https://huggingface.co/hexgrad/Kokoro-82M/tree/f3ff3571791e39611d31c381e3a41a3af07b4987",
    "f3ff3571791e39611d31c381e3a41a3af07b4987",
)
MOSS_HF_SOURCE = source_identity(
    "OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX",
    "https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX/tree/f52645cb467506d8e18e746ddd59482685b74e58",
    "f52645cb467506d8e18e746ddd59482685b74e58",
)

# This is deliberately separate from display names: each source and precision
# claim below is backed by the owning committed provenance. Unknown values remain
# null and are listed in missing-fields.md.
MODEL_METADATA = {}
for _id in ("0002-executorch-full", "0003-litert-deferred", "0004-onnx-deferred", "0005-qnn-deferred"):
    MODEL_METADATA[_id] = {"model_identity": VIBEVOICE_SOURCE, "quantization": None, "missing": {"quantization": "The committed route evidence does not establish a deployment quantization for this route."}}
MODEL_METADATA["0002-executorch-full"].update({"quantization": "Mixed: Qwen2 backbone dynamic-activation/per-channel-weight INT8; audio components FP32"})
MODEL_METADATA["0002-executorch-full"]["missing"].pop("quantization", None)
MODEL_METADATA["0002-executorch-acoustic-decoder"] = {"model_identity": VIBEVOICE_SOURCE, "quantization": "FP32 acoustic decoder component"}
MODEL_METADATA["0006-realtime-feasibility"] = {"model_identity": REALTIME_SOURCE, "quantization": None, "missing": {"quantization": "Feasibility inventory records package estimates, not an Android quantized deployment."}}
for _id in ("0008-pocket-cpu-t1", "0009-pocket-cpu-t1", "0009-pocket-cpu-t2", "0009-pocket-cpu-t4"):
    MODEL_METADATA[_id] = {"model_identity": POCKET_ARCHIVE_SOURCE, "quantization": "INT8 ONNX components: lm_flow, lm_main, and decoder; encoder and text_conditioner are unquantized ONNX"}
for _id in ("0008-kokoro-cpu-t1", "0009-kokoro-cpu-t1", "0009-kokoro-cpu-t2", "0009-kokoro-cpu-t4"):
    MODEL_METADATA[_id] = {"model_identity": KOKORO_ARCHIVE_SOURCE, "quantization": None, "missing": {"quantization": "Committed Android archive inventory identifies model.onnx but does not establish its quantization scheme."}}
MODEL_METADATA["0009-kokoro-int8-not-deployed"] = {"model_identity": KOKORO_ARCHIVE_SOURCE, "quantization": "Mixed INT8 QDQ: symmetric S8 activations and weights, per-channel weights, MinMax calibration; generator weights remain FP32"}
for _id in ("0008-supertonic-cpu-t1", "0009-supertonic-cpu-t1", "0009-supertonic-cpu-t2", "0009-supertonic-cpu-t4", "0010-supertonic-cpu"):
    MODEL_METADATA[_id] = {"model_identity": SUPERTONIC_SOURCE, "quantization": "INT8 ONNX release outputs"}
MODEL_METADATA["0010-supertonic-hybrid-htp"] = {"model_identity": SUPERTONIC_SOURCE, "quantization": "INT8 ONNX release outputs; shape-specialized graph derivatives used for the QNN route"}
for _id in ("0011-supertonic-official-cpu", "0011-supertonic-all-htp", "0011-supertonic-htp-fail-closed"):
    MODEL_METADATA[_id] = {"model_identity": SUPERTONIC_SOURCE, "quantization": "FP32 ONNX source graph"}
MODEL_METADATA["0012-pocket-onnx-cpu"] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Unquantized FP32 ONNX component export (zero quantization operators)"}
MODEL_METADATA["0014-pocket-qnn-fp-source"] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Unquantized FP32 source graphs; QNN observed-path lowering uses FP16 kernels"}
MODEL_METADATA["0014-pocket-qnn-int16-flow"] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Calibrated INT16-FlowLM QDQ derivative; full observed path QNN-only"}
MODEL_METADATA["0014-pocket-alba-original-dynamic-cpu"] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Unquantized FP32 original dynamic ONNX component export; official pinned fixed Alba state"}
MODEL_METADATA["0014-pocket-alba-fixed-cpu"] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Unquantized FP32 QNN-compatible fixed-cache derivative; official pinned fixed Alba state"}
MODEL_METADATA["0014-pocket-alba-fixed-qnn-htp"] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Unquantized FP32 source tensors; QNN HTP execution uses FP16; official pinned fixed Alba state"}
MODEL_METADATA["0016-pocket-qnn-hybrid-cpu"] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Unquantized FP32 ONNX source graphs; QNN provider mixed offload, internal HTP precision not established"}
MODEL_METADATA["0012-pocket-executorch"] = {"model_identity": POCKET_HF_SOURCE, "quantization": None, "missing": {"quantization": "The route was blocked before an Android representation was produced."}}
for _id in ("0013-kokoro-onnx-bootstrap", "0013-kokoro-onnx-cpu"):
    MODEL_METADATA[_id] = {"model_identity": KOKORO_HF_SOURCE, "quantization": "Unquantized FP32 controlled ONNX export (FLOAT initializers; zero quantized operators)"}
MODEL_METADATA["0013-kokoro-executorch"] = {"model_identity": KOKORO_HF_SOURCE, "quantization": None, "missing": {"quantization": "The route was blocked before an Android representation was produced."}}
MODEL_METADATA["0017-kokoro-qnn-host-blocked"] = {"model_identity": KOKORO_HF_SOURCE, "quantization": "Unquantized FP32 fixed-contract derivative; zero quantized operators"}
MODEL_METADATA["0018-moss-tts-nano-cpu"] = {"model_identity": MOSS_HF_SOURCE, "quantization": "Unquantized official ONNX graphs; CPUExecutionProvider only"}
MODEL_METADATA["0019-moss-tts-nano-qnn-blocked"] = {"model_identity": MOSS_HF_SOURCE, "quantization": "Unquantized official ONNX graphs; no quantization or physical Android route was attempted"}
MODEL_METADATA["0020-supertonic-refresh-bootstrap"] = {"model_identity": SUPERTONIC_SOURCE, "quantization": "INT8 ONNX release outputs; exact historical archive contract prepared"}
MODEL_METADATA["0021-supertonic-int8-cpu-v2"] = {"model_identity": SUPERTONIC_SOURCE, "quantization": "Released INT8 ONNX archive SHA 82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427"}

OBJECTIVE_EVIDENCE_OVERRIDES = {
    "0008-pocket-cpu-t1": {
        "status": "descriptive",
        "summary": "Historical Android execution remains structurally validated but unreviewed; later exact-archive host samples were explicitly accepted and are distinct from the missing historical WAVs.",
        "comparison_notes": ["The later archive audit proved an input-sensitive nonzero encoder distinct from 0012's invalid zero-encoder checkpoint; it does not retroactively attach the reviewed host samples to the historical Android run."],
    },
    "0012-pocket-onnx-cpu": {
        "status": "descriptive",
        "summary": "Later root-cause evidence proved the numerically equivalent route reproduced an invalid zero-voice audio-cloning contract; technical measurements and the exact route/sample rejection remain historical evidence.",
        "comparison_notes": ["All 42 Mimi encoder/encoder-transformer tensors (9,224,736 elements) were zero; numerical equivalence was not evidence of valid speech quality."],
    },
    "0014-pocket-qnn-fp-source": {
        "status": "descriptive",
        "summary": "QNN-only observed-path provider and physical execution evidence; bounded decoder6 and comparator-drift limitations apply.",
        "comparison_notes": ["Decoder6 passed a host gate but was unused and physically unproven; 0012 temperature drift/effective-0.7 divergence is descriptive context only."],
    },
    "0014-pocket-qnn-int16-flow": {
        "status": "descriptive",
        "summary": "QNN-only observed-path provider and physical execution evidence; bounded decoder6 and comparator-drift limitations apply.",
        "comparison_notes": ["Decoder6 passed a host gate but was unused and physically unproven; 0012 temperature drift/effective-0.7 divergence is descriptive context only."],
    },
    "0010-supertonic-hybrid-htp": {
        "status": "descriptive",
        "summary": "Physical HTP and numerical comparison evidence; no listening acceptance.",
        "comparison_notes": ["Post-run single-listener observation that CPU and hybrid samples sounded exactly the same; comparative evidence only, not an acceptance decision."],
    },
}
LISTENING_REVIEWS = {
    "0010-supertonic-cpu": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Good.", "sample_sha256": "7e83537630b3e354f7586b9887f7a8359d62e438c9addeea61d87d878b2a84ff",
    },
    "0010-supertonic-hybrid-htp": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Good.", "sample_sha256": "9b0d488776b144c972e8be4e9434fac14ce3ceddfcfa5a10d137fca41b772668",
    },
    "0011-supertonic-official-cpu": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Good—even a bit more crisp than samples 1 and 2.", "sample_sha256": "8db92db13567b86be503d204fe367f2052b54dbfc99c0f7bfc5b23d9fd431da7",
    },
    "0011-supertonic-all-htp": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Same as sample 3. Perceptual comparison only; not numerical equivalence.", "sample_sha256": "47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c",
    },
    "0012-pocket-onnx-cpu": {
        "status": "rejected", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Unusable repetitive “takakakakakakakaka”. Route-level verdict only; do not generalize to the Pocket family.", "sample_sha256": "40634981606f37c59a91c14d99cecb3ef4cc21b1391882e870940b0716857d22",
    },
    "0014-pocket-qnn-fp-source": {
        "status": "rejected", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Unintelligible mumbling, perhaps only “Android”. Exact route/sample verdict only; do not generalize to the Pocket family.", "sample_sha256": "467e777879691237472b51f5ccf9a8d43dae337cf63c2344ed3cfb645948c7f3",
    },
    "0014-pocket-qnn-int16-flow": {
        "status": "rejected", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Same: unintelligible mumbling, perhaps only “Android”. Exact route/sample verdict only; do not generalize to the Pocket family.", "sample_sha256": "dcdb36df3d8cb8fc8754257fe060d5a4b2deb7c49983d579b8f90c3aa5035820",
    },
    "0014-pocket-alba-original-dynamic-cpu": {
        "status": "rejected", "reviewer": "Moritz", "date": "2026-08-20",
        "notes": "he says it but he says it like he is going fucking insane. it sounds nuts. i am scared hahahaha. Exact route/sample verdict only; RTF does not establish quality.", "sample_sha256": "cdf77f6ecaecdbb1a95992326675972366b57da864864f7359890b7e2df5c4b6",
    },
    "0014-pocket-alba-fixed-cpu": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-20",
        "notes": "sounds good. Exact fixed-cache Android CPU route/sample verdict only.", "sample_sha256": "e0638f35870b24fbe675649a0cd49fa69ca6d74060557bfec5336d2d03a21c9a",
    },
    "0014-pocket-alba-fixed-qnn-htp": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-20",
        "notes": "sounds good. Independently reviewed exact fixed-Alba fallback-disabled HTP route/sample only.", "sample_sha256": "2c3901ec39a53596759c1d95381a1d67e4f9ca8886cdf39ac03721863c63eb56",
    },
    "0016-pocket-qnn-hybrid-cpu": {
        "status": "rejected", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "takataktaka. Exact route/sample verdict only; do not generalize to the Pocket family.", "sample_sha256": "6cd3a98fb821ad76b0c0ad55a20f910da7be9d3058e511ff807b4a4f694aa45f",
    },
    "0013-kokoro-onnx-cpu": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Good.", "sample_sha256": "c046e8337b86ccf221ecd91db7dba90845f7c20b0ab1d8c248a36146c4eaecd3",
    },
    "0018-moss-tts-nano-cpu": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Okay to good, but with a bit of a Chinese accent.", "sample_sha256": "173850781b055e70a606fb561d93b70e6d8c6318db1b29b2324f83506c21ad6b",
    },
}

# Family/model release dates are kept separate from benchmark evidence. Dates use
# authoritative upstream repository/model-page creation or release announcements,
# not the later dated quantized archives used by Android runs.
MODEL_TIMELINE = [
    {"model": "Kokoro-82M", "first_release_date": "2024-12-26", "date_basis": "Hugging Face model API createdAt for the public model repository", "source_url": "https://huggingface.co/hexgrad/Kokoro-82M"},
    {"model": "VibeVoice 1.5B", "first_release_date": "2025-08-25", "date_basis": "Hugging Face model API createdAt for microsoft/VibeVoice-1.5B", "source_url": "https://huggingface.co/microsoft/VibeVoice-1.5B"},
    {"model": "Supertonic (family, before Supertonic 3)", "first_release_date": "2025-11-18", "date_basis": "Public upstream GitHub repository created_at; the first Supertonic family repository", "source_url": "https://github.com/supertone-inc/supertonic"},
    {"model": "Pocket TTS", "first_release_date": "2026-01-13", "date_basis": "Kyutai public release announcement", "source_url": "https://kyutai.org/blog/2026-01-13-pocket-tts"},
    {"model": "MOSS-TTS-Nano", "first_release_date": "2026-04-17", "date_basis": "Hugging Face model API createdAt for the public OpenMOSS-Team ONNX model repository", "source_url": "https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX"},
]

REMEASUREMENTS = {
    "0008-supertonic-cpu-t1": [{
        "id": "0020-supertonic-2026-08-20",
        "experiment": "0020",
        "source_commit": "b717b74b1866b578f02f96e6962563c7567b6e00",
        "remeasured_at": "2026-08-20",
        "status": "ran",
        "original_snapshot": {
            "registry_commit": "40e2cf0b7772ee7afd9feb07c8af14c86665a798",
            "metrics": {"load_seconds": 0.765107603, "cold_rtf": 0.3854677480612432, "warm_median_rtf": 0.3703028479158501, "proof_run_rtf": None, "first_post_setup_rtf": None, "peak_pss_bytes": 463003648, "peak_vm_hwm_bytes": 531345408},
            "wav": None,
        },
        "contract": {
            "match": "exact historical 0008 route contract",
            "transcript": {"classification": "legacy_v1", "path": "experiments/0008-sherpa-onnx-android-tts-benchmark/protocol/transcript.txt", "sha256": "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f", "bytes": 230, "trailing_newline": False, "canonical_v2_sha256": "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67", "comparison_boundary": "Exact historical transcript v1 rerun; not canonical v2 and not directly matched to canonical-v2 routes."},
            "effective_frontend_output": None,
            "archive_sha256": "82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427",
            "aar_sha256": "6419cd8bc983e0c4fab06067f0fe0313fdc0f7103818ac1e7a08d50787b7a82b",
            "sherpa_revision": "3dc7c569f31ca2cd4a20ed6f7db780327e6714c5",
            "voice": "M1",
            "speaker_id": 5,
            "provider": "CPU",
            "threads": 1,
            "timing_boundary": "System.nanoTime around OfflineTts.generate only; WAV write/hash/listening excluded",
            "state_protocol": "one first generation plus three warm generations in the same historical harness",
            "current_global_contract_status": "historical exact rerun; does not satisfy the newer minimum of five warm same-session reset generations",
            "bounded_adapter": "input root only: getExternalFilesDir(null) to getFilesDir(); benchmark engine, configuration, timing, memory, and app-external result output unchanged",
        },
        "metrics": {"load_seconds": 1.003262135, "cold_rtf": 0.4158744479936854, "warm_median_rtf": 0.39308571289407546, "proof_run_rtf": None, "first_post_setup_rtf": None, "peak_pss_bytes": 463911936, "peak_vm_hwm_bytes": 534081536},
        "warm_rtf_values": [0.39110301817879095, 0.39308571289407546, 0.4001901129320338],
        "runs": [
            {"state": "cold", "synthesis_seconds": 6.881694216, "rtf": 0.4158744479936854, "wav_evidence": {"sha256": "6ceb73890f4e78ca5b36379f1d57df877a711be27dbbdfa8daf628341ae11f69", "bytes": 1459536, "channels": 1, "sample_rate_hz": 44100, "sample_width_bytes": 2, "frames": 729746, "duration_seconds": 729746/44100, "finite": True, "non_silent": True, "unclipped": True, "curated_path": None}},
            {"state": "warm", "synthesis_seconds": 6.471788279, "rtf": 0.39110301817879095, "wav_evidence": {"sha256": "2fd9fa27e72a476431b4e20078b4594f696a7655a53959f861b80269e3c5d936", "bytes": 1459536, "channels": 1, "sample_rate_hz": 44100, "sample_width_bytes": 2, "frames": 729746, "duration_seconds": 729746/44100, "finite": True, "non_silent": True, "unclipped": True, "curated_path": None}},
            {"state": "warm", "synthesis_seconds": 6.504596976, "rtf": 0.39308571289407546, "wav_evidence": {"sha256": "1cf003d55c81e49983cbe385fdb98868ccdf4b1a6b1482e21bab020c7567ee6e", "bytes": 1459536, "channels": 1, "sample_rate_hz": 44100, "sample_width_bytes": 2, "frames": 729746, "duration_seconds": 729746/44100, "finite": True, "non_silent": True, "unclipped": True, "curated_path": "media/0020-supertonic-3-int8-cpu-refresh.wav"}},
            {"state": "warm", "synthesis_seconds": 6.622157237, "rtf": 0.4001901129320338, "wav_evidence": {"sha256": "e2cc5b88e4e6fdf35b0e2438eabad4bf4d8532d246e8b9ed2928a66e53a30eca", "bytes": 1459536, "channels": 1, "sample_rate_hz": 44100, "sample_width_bytes": 2, "frames": 729746, "duration_seconds": 729746/44100, "finite": True, "non_silent": True, "unclipped": True, "curated_path": None}},
        ],
        "comparison_to_original": {"setup_relative_change_percent": 31.126933135442904, "cold_rtf_relative_change_percent": 7.888260453793183, "warm_median_rtf_relative_change_percent": 6.152495209381348, "peak_pss_relative_change_percent": 0.19617296838232434, "peak_vm_hwm_relative_change_percent": 0.5149433793544711, "rtf_change_over_10_percent": False, "setup_change_over_10_percent": True, "material_protocol_or_duration_difference": False},
        "thermal": {"initial_status": "STATUS_1", "initial_battery_c": 36.0, "eligible_final_status": "NONE", "eligible_final_battery_c": 34.9, "waited_without_device_tuning": True},
        "representative_wav": {"path":"media/0020-supertonic-3-int8-cpu-refresh.wav","sha256":"1cf003d55c81e49983cbe385fdb98868ccdf4b1a6b1482e21bab020c7567ee6e","bytes":1459536,"sample_rate_hz":44100,"channels":1,"duration_seconds":729746/44100},
        "listening_review": {"status": "not_reviewed", "reviewer": None, "date": None, "notes": None, "sample_sha256": "1cf003d55c81e49983cbe385fdb98868ccdf4b1a6b1482e21bab020c7567ee6e"},
        "sources": ["experiments/0020-historic-android-benchmark-refresh/results/supertonic-3-int8-cpu-refresh.json", "experiments/0020-historic-android-benchmark-refresh/results/supertonic-adapted-build-provenance.json", "experiments/0020-historic-android-benchmark-refresh/results/supertonic-internal-stage-and-cleanup.json", "experiments/0020-historic-android-benchmark-refresh/README.md"],
        "missing_reasons": {"provider_profile": "The exact historical harness does not emit an ONNX Runtime provider profile; provider=CPU is established by the pinned descriptor/runtime contract only.", "effective_frontend_output": "The historical harness preserves the exact input bytes/hash but does not emit effective tokenizer/frontend IDs.", "proof_run_rtf": "The historical CPU harness did not collect a separate instrumented proof run.", "first_post_setup_rtf": "The historical contract labels the first post-setup run as cold_rtf; it is preserved there rather than duplicated."},
    }],
}


TRANSCRIPT_AUDIT_SOURCE = "experiments/0020-historic-android-benchmark-refresh/results/transcript-provenance-audit.json"
CANONICAL_V2_SHA256 = "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67"
LEGACY_V1_SHA256 = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"


def transcript_metadata(classification, sha256, source, basis, *, byte_count=None, trailing_newline=None, effective_frontend=None, audit_source=TRANSCRIPT_AUDIT_SOURCE, reason=None):
    missing = {}
    if byte_count is None:
        missing["bytes"] = "The committed transcript audit establishes the exact hash but does not record a byte count for this noncanonical text."
    if trailing_newline is None:
        missing["trailing_newline"] = "The committed transcript audit does not establish trailing-newline status for this noncanonical text."
    if effective_frontend is None:
        missing["effective_frontend"] = "The committed historical transcript audit does not establish exact effective tokenizer/frontend output for this route."
    return {
        "classification": classification,
        "sha256": sha256,
        "bytes": byte_count,
        "trailing_newline": trailing_newline,
        "source": source,
        "basis": basis,
        "effective_frontend": effective_frontend,
        "canonical_v2_sha256": CANONICAL_V2_SHA256,
        "canonical_v2_match": classification == "canonical_v2",
        "comparison_boundary": reason or ("Exact canonical-v2 transcript match." if classification == "canonical_v2" else "Transcript v1 is legacy matched provenance only; it is not canonical v2."),
        "audit_source": audit_source,
        "missing_reasons": missing,
    }


TRANSCRIPT_METADATA = {}
for _id in ("0008-pocket-cpu-t1", "0008-kokoro-cpu-t1", "0008-supertonic-cpu-t1"):
    TRANSCRIPT_METADATA[_id] = transcript_metadata("legacy_v1", LEGACY_V1_SHA256, "experiments/0008-sherpa-onnx-android-tts-benchmark/protocol/transcript.txt", "Experiment 0008 protocol and normalized route result.", byte_count=230, trailing_newline=False)
for _id in ("0009-pocket-cpu-t1", "0009-pocket-cpu-t2", "0009-pocket-cpu-t4", "0009-kokoro-cpu-t1", "0009-kokoro-cpu-t2", "0009-kokoro-cpu-t4", "0009-supertonic-cpu-t1", "0009-supertonic-cpu-t2", "0009-supertonic-cpu-t4"):
    TRANSCRIPT_METADATA[_id] = transcript_metadata("legacy_v1", LEGACY_V1_SHA256, "experiments/0009-android-tts-optimization/thread-sweep/results/measured-thread-sweep.json", "Experiment 0009 measured thread-sweep provenance.", byte_count=230, trailing_newline=False)
for _id in ("0010-supertonic-cpu", "0010-supertonic-hybrid-htp"):
    TRANSCRIPT_METADATA[_id] = transcript_metadata("legacy_v1", LEGACY_V1_SHA256, "experiments/0010-supertonic-qnn-htp-feasibility/results/e2e-hybrid-cpu-checkpoint.json", "Experiment 0010 end-to-end contract.", byte_count=230, trailing_newline=False)
for _id in ("0011-supertonic-official-cpu", "0011-supertonic-all-htp"):
    TRANSCRIPT_METADATA[_id] = transcript_metadata("legacy_v1", LEGACY_V1_SHA256, "experiments/0011-supertonic-official-fp32-phone-comparison/results/matched-e2e-protocol.json", "Experiment 0011 matched end-to-end protocol.", byte_count=230, trailing_newline=False)
TRANSCRIPT_METADATA["0018-moss-tts-nano-cpu"] = transcript_metadata("legacy_v1", LEGACY_V1_SHA256, "experiments/0018-moss-tts-nano-onnx-android/protocol/transcript.txt", "Experiment 0018 phone checkpoint and committed protocol transcript.", byte_count=230, trailing_newline=False)
TRANSCRIPT_METADATA["0002-executorch-full"] = transcript_metadata("noncanonical", "e971969aff3d1f3e656180adf90e3f727299a842b83b2237a8e3b4c578fdf7d1", "experiments/0001-vibevoice-1.5b-local-reference/transcript.txt", "VibeVoice locked-reference transcript.", reason="Locked-reference text predates and differs from canonical v2; a matched comparison requires a new canonical-v2 reference/export campaign.")
for _id in ("0012-pocket-onnx-cpu", "0014-pocket-qnn-fp-source", "0014-pocket-qnn-int16-flow", "0014-pocket-alba-original-dynamic-cpu", "0014-pocket-alba-fixed-cpu", "0014-pocket-alba-fixed-qnn-htp", "0016-pocket-qnn-hybrid-cpu"):
    TRANSCRIPT_METADATA[_id] = transcript_metadata("noncanonical", "66e1ba2772ca3d534b792e9d9dacb26e37fda422afe40e8cced5aa878404ffb1", "experiment 0012 matched-contract text inherited by 0014 and 0016", "Pocket demo-text route contract.", reason="Pocket demo text differs from canonical v2; compare only within the explicitly matched Pocket route evidence until each route receives a canonical-v2 rerun.")
TRANSCRIPT_METADATA["0013-kokoro-onnx-cpu"] = transcript_metadata("noncanonical", "bec8bf482f4d816f0c95471c289a2607a7a169e33389b8b13e525214ec639461", "experiments/0013-kokoro-onnx-vs-executorch-android/protocol/transcript.txt", "Kokoro fixed-contract transcript.", reason="The fixed-contract Kokoro text differs from canonical v2; a v2 refresh requires a new controlled export/tokenization/duration contract before phone execution.")
TRANSCRIPT_METADATA["0021-supertonic-int8-cpu-v2"] = transcript_metadata("canonical_v2", CANONICAL_V2_SHA256, "experiments/0021-supertonic-canonical-v2-android-cpu/protocol/transcript.txt", "Experiment 0021 exact canonical-v2 input and official unicode-indexer mapping.", byte_count=226, trailing_newline=False, effective_frontend={"kind": "official Supertonic unicode_indexer.bin direct codepoint mapping", "mapped_id_count": 226, "mapped_ids_int32le_sha256": "32fc26951a3f521bcf0745117235804bc628e112a48789b355d44eeef62fc5f1", "unicode_indexer_sha256": "8402ca48e5189a8950138580b0fff64db6f072f24ac07cd54ba8b2fbb9883b30", "source": "experiments/0021-supertonic-canonical-v2-android-cpu/results/frontend-provenance.json"}, audit_source="experiments/0021-supertonic-canonical-v2-android-cpu/results/phone-cpu-result.json")


FULL_E2E_IDS = {
    "0002-executorch-full",
    "0008-pocket-cpu-t1", "0008-kokoro-cpu-t1", "0008-supertonic-cpu-t1",
    "0009-pocket-cpu-t1", "0009-pocket-cpu-t2", "0009-pocket-cpu-t4",
    "0009-kokoro-cpu-t1", "0009-kokoro-cpu-t2", "0009-kokoro-cpu-t4",
    "0009-supertonic-cpu-t1", "0009-supertonic-cpu-t2", "0009-supertonic-cpu-t4",
    "0010-supertonic-cpu", "0010-supertonic-hybrid-htp",
    "0011-supertonic-official-cpu", "0011-supertonic-all-htp",
    "0012-pocket-onnx-cpu", "0014-pocket-qnn-fp-source", "0014-pocket-qnn-int16-flow",
    "0014-pocket-alba-original-dynamic-cpu", "0014-pocket-alba-fixed-cpu", "0014-pocket-alba-fixed-qnn-htp",
    "0016-pocket-qnn-hybrid-cpu", "0013-kokoro-onnx-cpu", "0018-moss-tts-nano-cpu",
    "0021-supertonic-int8-cpu-v2",
}
for _row in ROWS:
    _metadata = MODEL_METADATA.get(_row["id"], {})
    _row["model_identity"] = _metadata.get("model_identity")
    _row["quantization"] = _metadata.get("quantization")
    _row["scope"] = "full_e2e" if _row["id"] in FULL_E2E_IDS else "excluded_non_e2e"
    _row["transcript"] = TRANSCRIPT_METADATA.get(_row["id"])
    if _row["transcript"] is None:
        _row["missing_reasons"].setdefault("transcript", "This excluded/non-E2E route was not classified by the committed visible-route transcript audit.")
    if _row["id"] in REMEASUREMENTS:
        _row["remeasurements"] = REMEASUREMENTS[_row["id"]]
    if _row["id"] in OBJECTIVE_EVIDENCE_OVERRIDES:
        _row["objective_evidence"] = OBJECTIVE_EVIDENCE_OVERRIDES[_row["id"]]
    if _row["id"] in LISTENING_REVIEWS:
        _row["listening_review"] = LISTENING_REVIEWS[_row["id"]]
    _row["missing_reasons"].update(_metadata.get("missing", {}))
    if _row["model_identity"] is None:
        _row["missing_reasons"].setdefault("model_identity", "No committed source/model identity is established for this route.")
    if _row["quantization"] is None:
        _row["missing_reasons"].setdefault("quantization", "No committed quantization description is established for this route.")
    for _metric_name, _metric_value in _row["metrics"].items():
        if _metric_value is None:
            _row["missing_reasons"].setdefault(_metric_name, f"No committed normalized {_metric_name} measurement is established for this route.")
# Keep ROWS exhaustive for machine evidence. The presentation layer filters to
# FULL_E2E_IDS so component/probe attempts remain queryable but never appear in
# the comparison table or audio presentation.


def verify_wav(owner_id, wav):
    p = OUT / wav["path"]
    if not p.is_file():
        raise SystemExit(f"missing registry media: {p}")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    if digest != wav["sha256"]:
        raise SystemExit(f"WAV hash mismatch for {owner_id}: {digest} != {wav['sha256']}")
    with wave.open(str(p), "rb") as f:
        observed = {"bytes": p.stat().st_size, "sample_rate_hz": f.getframerate(), "channels": f.getnchannels(), "sample_width_bytes": f.getsampwidth(), "duration_seconds": f.getnframes() / f.getframerate()}
    if observed["sample_width_bytes"] != 2:
        raise SystemExit(f"WAV metadata mismatch for {owner_id}: expected PCM16 sample width")
    for key in ("bytes", "sample_rate_hz", "channels"):
        if observed[key] != wav[key]:
            raise SystemExit(f"WAV metadata mismatch for {owner_id}: {key}")
    if abs(observed["duration_seconds"] - wav["duration_seconds"]) > 1e-9:
        raise SystemExit(f"WAV duration mismatch for {owner_id}")
    wav["verified"] = True


def verify_media():
    for r in ROWS:
        if r["wav"]:
            verify_wav(r["id"], r["wav"])
        for remeasurement in r.get("remeasurements", []):
            verify_wav(f"{r['id']} / {remeasurement['id']}", remeasurement["representative_wav"])


def build_missing():
    lines = ["# Missing Android benchmark fields", "", "This report is generated by `build_registry.py`. `null` means the source evidence did not provide a measurement; it is not zero or an estimate.", ""]
    for r in ROWS:
        missing = r["missing_reasons"]
        if not missing and not r.get("remeasurements"):
            continue
        lines += [f"## `{r['id']}` — {r['model']} / {r['route']}", "", f"- Status: **{r['attempt_status']}**; Android attempted: **{str(r['android_attempted']).lower()}**"]
        for field, reason in missing.items():
            lines.append(f"- `{field}`: {reason}")
        if r.get("transcript"):
            for field, reason in r["transcript"]["missing_reasons"].items():
                lines.append(f"- `transcript.{field}`: {reason}")
        for refresh in r.get("remeasurements", []):
            for field, reason in refresh["missing_reasons"].items():
                lines.append(f"- `remeasurements.{refresh['id']}.{field}`: {reason}")
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


def format_rtf(entry):
    candidates = (
        ("warm_median_rtf", "warm median", ""),
        ("first_post_setup_rtf", "first post-setup", " (first post-setup)"),
        ("proof_run_rtf", "proof run", " (proof run)"),
        ("cold_rtf", "cold", " (cold)"),
    )
    remeasurements = entry.get("remeasurements", [])
    latest = remeasurements[-1] if remeasurements else None
    metrics = latest["metrics"] if latest else entry["metrics"]
    selected = next(((field, label, suffix, metrics[field]) for field, label, suffix in candidates if metrics[field] is not None), None)
    if selected is None:
        display = "—"
        sort_value = ""
        detail_parts = ["No headline RTF is available."]
    else:
        selected_field, selected_label, suffix, value = selected
        refresh_suffix = " (refresh)" if latest else ""
        display = f"{value:.3f}{refresh_suffix or suffix}"
        sort_value = str(value)
        if latest:
            original = entry["metrics"]
            comparison = latest["comparison_to_original"]
            detail_parts = [
                f"Displayed: {selected_label} RTF {value:.6g}, remeasured {latest['remeasured_at']} ({latest['id']}).",
                f"Frozen original warm median RTF {original['warm_median_rtf']:.6g}; refresh delta {comparison['warm_median_rtf_relative_change_percent']:+.4f}%.",
                f"Original setup {original['load_seconds']:.6g} s; refreshed setup {metrics['load_seconds']:.6g} s; delta {comparison['setup_relative_change_percent']:+.4f}% (over-10% flag: {str(comparison['setup_change_over_10_percent']).lower()}).",
                f"Refresh used {len(latest['warm_rtf_values'])} warm runs under the exact historical contract and does not satisfy the newer five-warm global minimum.",
            ]
        else:
            detail_parts = [f"Displayed: {selected_label} RTF {value:.6g}."]
        secondary = []
        combined_first_cold = metrics["first_post_setup_rtf"] is not None and metrics["first_post_setup_rtf"] == metrics["cold_rtf"] and selected_field not in {"first_post_setup_rtf", "cold_rtf"}
        if combined_first_cold:
            secondary.append(f"first post-setup / cold {metrics['cold_rtf']:.6g} (same run)")
        for field, label, _ in candidates:
            if field == selected_field or metrics[field] is None or (combined_first_cold and field in {"first_post_setup_rtf", "cold_rtf"}):
                continue
            secondary.append(f"{label} {metrics[field]:.6g}")
        if secondary:
            detail_parts.append("Other recorded RTFs for the displayed measurement: " + "; ".join(secondary) + ".")
    missing_reasons = latest.get("missing_reasons", {}) if latest else entry["missing_reasons"]
    missing = []
    for field, label, _ in candidates:
        if metrics[field] is None:
            reason = missing_reasons.get(field)
            if reason:
                missing.append(f"{label}: {reason}")
    if missing:
        detail_parts.append("Unavailable: " + " | ".join(missing))
    transcript = entry["transcript"]
    if transcript:
        detail_parts.append(f"Transcript: {transcript['classification']} ({transcript['sha256']}); {transcript['comparison_boundary']}")
    return display, sort_value, " ".join(detail_parts)


def build_html(registry):
    entries = [e for e in registry["entries"] if e["scope"] == "full_e2e"]
    trs = []
    players = []
    needs_review_players = []
    for e in entries:
        m = e["metrics"]
        latest = e.get("remeasurements", [])[-1] if e.get("remeasurements") else None
        display_wav = latest["representative_wav"] if latest else e["wav"]
        display_review = latest["listening_review"] if latest else e["listening_review"]
        rtf, sort_rtf, rtf_details = format_rtf(e)
        if display_wav:
            anchor = f'audio-{e["id"]}'
            wav = f'<a href="#{html.escape(anchor)}">Listen</a>'
            player_detail = f"{e['route']} · refresh {latest['remeasured_at']}" if latest else e["route"]
            players.append(
                f'<article class="player" id="{html.escape(anchor)}">'
                f'<div><b>{html.escape(e["model"])}</b><br><small>{html.escape(player_detail)}</small></div>'
                f'<audio controls preload="metadata" src="{html.escape(display_wav["path"])}"></audio>'
                f'<a class="back" href="#routes">Back to table</a>'
                f'</article>'
            )
        else:
            wav = "—"
        cls = e["attempt_status"].replace("_", "-")
        audio_sort = "1" if display_wav else "0"
        memory, sort_memory = format_memory(m)
        provider = html.escape(e["provider"] or "—")
        if e["threads"] is not None:
            suffix = "thread" if e["threads"] == 1 else "threads"
            provider += f'<br><small>{e["threads"]} {suffix}</small>'
        transcript = e["transcript"]
        transcript_label = {"canonical_v2": "canonical v2", "legacy_v1": "legacy v1", "noncanonical": "noncanonical"}[transcript["classification"]]
        transcript_badge = f'<br><small class="transcript transcript-{html.escape(transcript["classification"])}" title="{html.escape(transcript["comparison_boundary"] + " SHA-256 " + transcript["sha256"], quote=True)}">Transcript: {html.escape(transcript_label)}</small>'
        identity = e["model_identity"]
        if identity is not None:
            model_cell = f'<a href="{html.escape(identity["url"])}" target="_blank" rel="noopener">{html.escape(e["model"])}</a><br><small>{html.escape(identity["name"])}'
            model_cell += '</small><br><small>' + html.escape(e["route"]) + '</small>' + transcript_badge
        else:
            model_cell = f'<b>{html.escape(e["model"])}</b><br><small>{html.escape(e["route"])}</small>' + transcript_badge
        quantization = html.escape(e["quantization"] or "—")
        review_status = display_review["status"]
        review_cls = "listening-" + review_status.replace("_", "-")
        listening = f'<span class="status {review_cls}">{html.escape(review_status)}</span>'
        if display_wav and review_status == "not_reviewed":
            review_anchor = f"needs-{e['id']}"
            review_detail = f"{e['route']} · refresh {latest['remeasured_at']} · listening review needed" if latest else f"{e['route']} · listening review needed"
            needs_review_players.append(f'<article class="player" id="{html.escape(review_anchor)}"><div><b>{html.escape(e["model"])}</b><br><small>{html.escape(review_detail)}</small></div><audio controls preload="metadata" src="{html.escape(display_wav["path"])}"></audio><a class="back" href="#routes">Back to table</a></article>')
        summary = html.escape(e["summary"])
        if latest:
            delta = latest["comparison_to_original"]
            summary += f'<br><small>Refresh {html.escape(latest["remeasured_at"])} ({html.escape(latest["id"])}): exact historical transcript v1/route rerun; warm median {latest["metrics"]["warm_median_rtf"]:.6f} vs original {e["metrics"]["warm_median_rtf"]:.6f} ({delta["warm_median_rtf_relative_change_percent"]:+.4f}%). Setup drift {delta["setup_relative_change_percent"]:+.4f}% is flagged. Three historical warm runs; not canonical v2 and not the current five-warm protocol.</small>'
        trs.append(f'<tr data-route-id="{html.escape(e["id"])}"><td data-sort="{html.escape(e["experiment"])}">{html.escape(e["experiment"])}</td><td data-sort="{html.escape(e["model"] + " " + e["route"])}">{model_cell}</td><td data-sort="{quantization}">{quantization}</td><td data-sort="{html.escape(e["attempt_status"])}"><span class="status {cls}">{html.escape(e["attempt_status"])}</span></td><td data-sort="{review_status}">{listening}</td><td data-sort="{html.escape(e["provider"] or "")} {e["threads"] or ""}">{provider}</td><td data-sort="{sort_rtf}" title="{html.escape(rtf_details, quote=True)}">{html.escape(rtf)}</td><td data-sort="{sort_memory}">{memory}</td><td data-sort="{audio_sort}">{wav}</td><td data-sort="{html.escape(e["summary"])}">{summary}</td></tr>')
    timeline_rows = []
    for item in MODEL_TIMELINE:
        timeline_rows.append(f'<tr><td>{html.escape(item["model"])}</td><td><time datetime="{html.escape(item["first_release_date"])}">{html.escape(item["first_release_date"])}</time></td><td>{html.escape(item["date_basis"])}</td><td><a href="{html.escape(item["source_url"])}" target="_blank" rel="noopener">Source</a></td></tr>')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Android benchmark registry</title><style>
:root{{--bg:#0f172a;--panel:#172033;--line:#334155;--ink:#e5e7eb;--muted:#94a3b8;--accent:#67e8f9}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1500px;margin:auto;padding:22px 24px}}h1{{font-size:24px;line-height:1.2;margin:0 0 16px}}small{{color:var(--muted)}}a{{color:var(--accent)}}.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:12px}}table{{border-collapse:collapse;width:100%;min-width:1320px;background:var(--panel)}}th,td{{padding:12px 13px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}th{{position:sticky;top:0;background:#1e293b;color:#bae6fd;white-space:nowrap;user-select:none;cursor:pointer}}th:hover{{background:#26364d}}th::after{{content:' ↕';color:#64748b}}th[aria-sort="ascending"]::after{{content:' ↑';color:var(--accent)}}th[aria-sort="descending"]::after{{content:' ↓';color:var(--accent)}}td:nth-child(10){{min-width:350px;color:#cbd5e1}}.status{{border-radius:99px;padding:3px 9px;font-size:12px;font-weight:700;white-space:nowrap}}.transcript{{font-weight:700}}.transcript-canonical_v2{{color:#a7f3d0}}.transcript-legacy_v1{{color:#fde68a}}.transcript-noncanonical{{color:#fecaca}}.ran{{background:#064e3b;color:#a7f3d0}}.listening-not-reviewed{{background:#713f12;color:#fde68a}}.listening-accepted{{background:#064e3b;color:#a7f3d0}}.listening-rejected{{background:#7f1d1d;color:#fecaca}}.blocked,.deferred,.not-run{{background:#713f12;color:#fde68a}}.partial{{background:#164e63;color:#a5f3fc}}code{{color:#bae6fd}}h2{{font-size:20px;margin:30px 0 12px}}.timeline-note{{color:var(--muted);margin-top:-4px}}.players{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}}.player{{scroll-margin-top:16px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}.player:target{{outline:2px solid var(--accent)}}.player audio{{display:block;width:100%;margin:11px 0 8px}}.back{{font-size:12px}}footer{{margin-top:16px;color:var(--muted);font-size:12px}}</style></head><body><main><h1>Android benchmark registry</h1><div class="table-wrap"><table id="routes"><thead><tr><th data-type="text">Experiment</th><th data-type="text">Model / route</th><th data-type="text">Quantization</th><th data-type="text">Status</th><th data-type="text">Listening</th><th data-type="text">Provider</th><th data-type="number" aria-sort="ascending" title="Warm median by default; otherwise the designated non-warm headline type is shown in brackets. Hover a value for all RTF evidence and missing reasons.">RTF</th><th data-type="number">Peak memory</th><th data-type="number">Audio</th><th data-type="text">Evidence summary</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div><h2 id="audio-samples">Audio samples</h2><div class="players">{''.join(players)}</div><h2 id="needs-review">Needs review</h2><p class="timeline-note">Playable full-E2E samples with no explicit Moritz listening verdict yet.</p><div class="players">{''.join(needs_review_players)}</div><h2 id="model-timeline">Model release timeline</h2><p class="timeline-note">First public family/model release dates, not later quantized archives or Android package dates. The date basis and source are recorded in <code>registry.json</code>.</p><div class="table-wrap"><table id="timeline"><thead><tr><th>Model</th><th>First public release</th><th>Date basis</th><th>Source</th></tr></thead><tbody>{''.join(timeline_rows)}</tbody></table></div><footer>Click a column heading to sort. Missing values sort last. Details: <a href="README.md">README</a> · <a href="missing-fields.md">missing fields</a>.</footer></main><script>
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
sortTable(6,'ascending');
</script></body></html>'''


def main():
    verify_media()
    registry = {
        "schema_version": 1,
        "registry_id": "android-benchmarks-v1",
        "device": DEVICE,
        "source_policy": "Keep an exhaustive registry of committed route evidence while presenting only full end-to-end Android routes; preserve null plus a reason for unavailable fields; never infer Android results from host evidence. Component probes, feasibility-only routes, and pre-runtime blockers are retained as excluded_non_e2e entries.",
        "model_timeline": MODEL_TIMELINE,
        "entries": ROWS,
    }
    (OUT / "registry.json").write_text(json.dumps(registry, indent=2, sort_keys=False) + "\n")
    (OUT / "missing-fields.md").write_text(build_missing())
    dashboard = build_html(registry)
    (OUT / "index.html").write_text(dashboard)
    (OUT / "dashboard.html").write_text(dashboard)
    wav_count = sum(bool(r["wav"]) + len(r.get("remeasurements", [])) for r in ROWS)
    print(f"wrote {len(ROWS)} routes and {wav_count} verified WAV references")


if __name__ == "__main__":
    main()
