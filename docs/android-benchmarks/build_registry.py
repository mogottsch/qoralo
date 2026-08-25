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
    row("0012-pocket-onnx-cpu", "0012", "Pocket TTS", "derived FP ONNX Runtime CPU", "success", attempted=True, provider="CPU", precision="FP32", threads=1, metrics={"load_seconds": 1.079322708, "cold_rtf": 0.912939803, "warm_median_rtf": 0.630365451, "peak_vm_hwm_bytes": 1586080 * 1024}, wav={"path":"media/0012-pocket-onnx-onnx-cpu.wav","sha256":"40634981606f37c59a91c14d99cecb3ef4cc21b1391882e870940b0716857d22","bytes":299564,"sample_rate_hz":24000,"channels":1,"duration_seconds":6.24}, summary="Five exact-source-derived FP ONNX components completed text-to-WAV on Android CPU; six outputs were byte-identical and warm median RTF was 0.630. Later root-cause evidence proved this route used an invalid audio-cloning contract whose no-voice-cloning checkpoint returned an all-zero voice embedding.", limitations=("Derived ONNX representation; no QNN/HTP claim; VmHWM is cumulative.", "All 42 Mimi encoder/encoder-transformer tensors (9,224,736 elements) in the pinned checkpoint were zero; source/ONNX numerical equivalence validated the broken contract, not speech quality.", "Experiment 0012 and its route/sample rejection remain historical evidence; the recovered fixed-Alba route is separate."), sources=("experiments/0012-pocket-onnx-vs-executorch-android/results/comparison.json", "experiments/0012-pocket-onnx-vs-executorch-android/RESULTS.md", "experiments/0014-pocket-fp-onnx-qnn-htp/results/zero-voice-encoder-root-cause.json", "experiments/0014-pocket-fp-onnx-qnn-htp/results/alba-quality-recovery.json"), missing={}, variant="Pocket five-component FP ONNX / invalid cloning contract"),
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
    row("0017-kokoro-qnn-host-blocked", "0017", "Kokoro", "canonical-v2 staged QNN host structural gate", "blocked", attempted=False, provider="QNNExecutionProvider (host staged gate only)", precision="FP32 source graphs; QNN lowering precision not established", threads=1, summary="Terminal canonical-v2 host gate: all 18 fallback-disabled stages finalized and executed with 18 QNN and 0 CPU provider events, but duration changed from the frozen CPU sum 602 to 605 and the final 361,200-sample finite float output was structurally invalid (SHA-256 2992f71911b8af233841af4058e8218e8705c987a51643d1d709d96545b60a08; peak 87296.0078125; RMS 61982.49650008212; 360,921 samples with abs >= 1). Phone eligibility is false, so no Android run, WAV, listening review, RTF, or physical HTP claim exists.", limitations=("Complete fallback-disabled host QNN stage execution is provider/host feasibility evidence, not Android execution or physical phone HTP RPC/HVX proof.", "Summed stage session/run times and maximum separate-process ru_maxrss are host observations, not end-to-end Android setup, RTF, PSS, or VmHWM metrics; normalized benchmark fields remain null.", "The invalid ignored float tensor is not a WAV or listening sample. No listening verdict exists, and the accepted experiment-0013 CPU verdict does not transfer.", "Stage 1 bert is the earliest non-bit-exact output; stage 4 duration_alignment is the earliest material/discrete boundary. The evidence localizes divergence but root cause remains unknown.", "Historical noncanonical monolithic/staged evidence, canonical CPU baselines, interrupted/operator-stopped attempts, and their claim boundaries remain preserved as distinct sources."), sources=("experiments/0017-kokoro-onnx-qnn-htp-android/results/host-gate-checkpoint.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/qnn-compat-cpu-equivalence.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/stage-decomposition-provenance.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/stage-cpu-equivalence.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/staged-host-qnn-feasibility.json", "experiments/0017-kokoro-onnx-qnn-htp-android/protocol-canonical-v2-stage-decomposition.json", "experiments/0017-kokoro-onnx-qnn-htp-android/protocol-canonical-v2-reconstruction-baseline.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-frontend-provenance.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-cpu-reconstruction-baseline.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-host-qnn-interrupted-checkpoint.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-rerun-operator-cancelled-pre-gate.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-native-rerun-1-operator-stopped.json", "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-host-qnn-gate.json", "experiments/0017-kokoro-onnx-qnn-htp-android/README.md", "experiments/0017-kokoro-onnx-qnn-htp-android/RESULTS.md"), missing={"android_attempted": "The failed host structural audio gate made the route phone-ineligible; no phone staging or execution occurred.", "load_seconds": "Only sums of 18 separate host-stage session creations exist; they are not an Android route setup measurement.", "cold_rtf": "No Android generation or valid audio duration exists.", "warm_median_rtf": "No Android first/warm generation campaign occurred.", "proof_run_rtf": "Host provider execution is not a physical phone accelerator proof run and the output failed structure.", "first_post_setup_rtf": "No Android route setup or post-setup generation existed.", "peak_pss_bytes": "No Android process PSS campaign occurred; host resource evidence has different semantics.", "peak_vm_hwm_bytes": "No Android process VmHWM campaign occurred; host maximum separate-process ru_maxrss is not this field.", "wav": "The host output is an ignored structurally invalid float tensor, not a retained WAV.", "physical_rpc_accelerator_cycle_hvx": "No phone access or physical HTP execution occurred; host QNN profiling does not establish phone proof.", "listening": "No valid WAV exists and no listening review or verdict was requested."}, variant="Canonical v2 / fixed FP32 18-stage host QNN structural gate"),
    row("0018-moss-tts-nano-cpu", "0018", "MOSS-TTS-Nano", "official ONNX Runtime CPU", "ran", attempted=True, provider="CPUExecutionProvider", precision="FP32", threads=4, metrics={"load_seconds": 1.712838853, "cold_rtf": 1.1383426748803827, "warm_median_rtf": 1.1248052010167464, "peak_vm_hwm_bytes": 5828526080}, wav={"path":"media/0018-moss-tts-nano-onnx-cpu.wav","sha256":"173850781b055e70a606fb561d93b70e6d8c6318db1b29b2324f83506c21ad6b","bytes":1605164,"sample_rate_hz":48000,"channels":1,"duration_seconds":16.72}, summary="Official MOSS-TTS-Nano completed text-to-WAV on CPUExecutionProvider only with 543,972/543,972 CPU node events. The full decoded output is 16.72 s, with non-streaming first decoded PCM semantics; setup was 1.71284 s and the process VmHWM reached 5,828,526,080 bytes.", limitations=("4 intra-op / 1 inter-op threads; the route is non-streaming and first decoded PCM means full audio-tokenizer decode returned PCM, not a streaming chunk.", "VmHWM is cumulative process high-water memory, not component-isolated memory.", "An initial exec-out stdin staging attempt hung and was aborted; the successful fast-push staging caveat is not included in benchmark latency."), sources=("experiments/0018-moss-tts-nano-onnx-android/results/phone-cpu-checkpoint.json", "experiments/0018-moss-tts-nano-onnx-android/results/source-inventory.json", "experiments/0018-moss-tts-nano-onnx-android/README.md"), missing={}, variant="MOSS-TTS-Nano official ONNX"),
    row("0019-moss-tts-nano-qnn-blocked", "0019", "MOSS-TTS-Nano", "reusable dynamic decode QNN HTP host gate", "blocked", attempted=False, provider="QNNExecutionProvider (host gate)", precision="FP32 official ONNX", metrics={}, summary="Blocked before Android: reusable dynamic decode failed closed at 52/1,091 optimized nodes across 13 partitions with 1,039 unsupported nodes. No phone, physical HTP, timing, memory, or audio evidence exists.", limitations=("Fixed-shape rewrites made prefill/local/codec and all 209 observed decode shapes fully QNN-assignable on host, but 209 sessions required 1,052.77 s total host session creation and do not form a reusable deployable route.", "Decoder redesign requires fixed-capacity KV-cache/state topology with fixed outputs and dynamic valid-length masking; this is not a narrow operator rewrite.", "No QNN physical phone claim, CPU fallback, quantization, timing, memory, or WAV claim is made."), sources=("experiments/0019-moss-tts-nano-qnn-htp-android/results/host-checkpoint.json", "experiments/0019-moss-tts-nano-qnn-htp-android/results/decode-static-gate-matrix.json", "experiments/0019-moss-tts-nano-qnn-htp-android/results/source-lock.json", "experiments/0019-moss-tts-nano-qnn-htp-android/README.md"), missing={"android_attempted": "Host gate failed closed before Android and no phone staging occurred.", "all": "No Android timing, memory, physical HTP, or audio evidence exists."}, variant="MOSS-TTS-Nano QNN HTP host feasibility"),
    row("0020-supertonic-refresh-bootstrap", "0020", "Supertonic 3", "historical CPU refresh bootstrap", "blocked", attempted=True, provider="CPU (inference not started)", precision="INT8", threads=1, summary="A refreshed attempt preserved the exact historical 0008 contract and passed the Windows-ADB device gate, but Android 16 denied the app access to shell-owned scoped-storage inputs; inference never started and every refreshed metric remains unavailable. The original 0008 measurements remain separate historical evidence.", limitations=("This is staging-ownership evidence only, not model/runtime compatibility or refreshed performance evidence.", "Earlier zero-device readiness observations remain valid for their timestamps; a later Windows-ADB readiness check reached the exact canonical phone.", "Prepared build and archive hashes do not establish execution."), sources=("experiments/0020-historic-android-benchmark-refresh/results/registry-audit.json", "experiments/0020-historic-android-benchmark-refresh/results/device-readiness.json", "experiments/0020-historic-android-benchmark-refresh/results/device-readiness-attempt-2.json", "experiments/0020-historic-android-benchmark-refresh/results/device-readiness-windows-adb.json", "experiments/0020-historic-android-benchmark-refresh/results/supertonic-build-provenance.json", "experiments/0020-historic-android-benchmark-refresh/results/supertonic-bootstrap-attempt.json"), missing={"load_seconds": "The refreshed route stopped at app bootstrap before model/session setup.", "cold_rtf": "Inference did not start.", "warm_median_rtf": "Inference did not start; no refreshed warm campaign exists.", "peak_pss_bytes": "No inference process measurement exists.", "peak_vm_hwm_bytes": "No inference process measurement exists.", "wav": "No refreshed audio was produced."}, variant="Exact 0008 Supertonic CPU refresh attempt"),
    row("0021-supertonic-int8-cpu-v2", "0021", "Supertonic 3", "canonical-v2 released-INT8 CPU", "ran", attempted=True, provider="CPU", precision="INT8", threads=1, metrics={"load_seconds": 0.853867031, "cold_rtf": 0.39552098915111206, "warm_median_rtf": 0.3956153837777073, "first_post_setup_rtf": 0.39552098915111206, "peak_pss_bytes": 480366592, "peak_vm_hwm_bytes": 548986880}, wav={"path":"media/0021-supertonic-int8-cpu-v2.wav","sha256":"201f8e79d39e2fbb9db8a64a9f139641db9e27fabb828bcc039286a49c8987df","bytes":1393090,"sample_rate_hz":44100,"channels":1,"duration_seconds":696523/44100}, summary="New canonical-v2 Supertonic 3 INT8 Android CPU route: exact 226-byte transcript SHA 424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67, official unicode-indexer frontend mapping, one created OfflineTts, one first generation, and five warm same-session independent generate calls. Every output had 696,523 samples (15.794172 s). Warm median RTF was 0.395615 from [0.390631, 0.391386, 0.395615, 0.395708, 0.397157].", limitations=("This is a new canonical-v2 route, not a rewrite of or matched performance delta against legacy-v1 Supertonic rows; the transcript and output duration differ.", "The first-post-setup and cold RTF fields refer to the same first complete generation, not two observations.", "Pinned archive SHA 82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427, AAR SHA 6419cd8bc983e0c4fab06067f0fe0313fdc0f7103818ac1e7a08d50787b7a82b, sherpa revision 3dc7c569f31ca2cd4a20ed6f7db780327e6714c5, M1/SID5, English, one CPU thread.", "Peak PSS is sampled process PSS; peak boundary PSS was 479,744,000 bytes; VmHWM is cumulative process-lifetime high-water memory.", "The historical harness does not emit an ORT provider profile; provider=CPU is established by the pinned descriptor and engine. Thermal gate was NONE at 33.8°C, USB powered, with no device tuning.", "The representative PCM16 WAV is structurally valid but not reviewed; no legacy Supertonic listening verdict transfers."), sources=("experiments/0021-supertonic-canonical-v2-android-cpu/results/phone-cpu-result.json", "experiments/0021-supertonic-canonical-v2-android-cpu/results/frontend-provenance.json", "experiments/0021-supertonic-canonical-v2-android-cpu/results/build-and-stage-provenance.json", "experiments/0021-supertonic-canonical-v2-android-cpu/results/transport-and-cleanup.json", "experiments/0021-supertonic-canonical-v2-android-cpu/README.md"), missing={"proof_run_rtf": "No separate instrumented proof run was collected; this CPU route uses the unprofiled first and five warm timing campaign.", "provider_profile": "The historical harness does not enable ORT provider profiling; CPU provider provenance is established by the pinned descriptor/engine contract."}, variant="Canonical v2 / Supertonic released INT8 ONNX / CPU"),
    row("0022-supertonic-t239-padding-blocked", "0022", "Supertonic 3", "canonical-v2 exact-T239 precompiled-context compatibility gate", "blocked", attempted=False, provider=None, precision=None, threads=None, summary="Terminal negative host compatibility result: canonical v2 plus the complete <en>...</en> wrapper produced semantic T235. Four zero-masked right-padding slots made filler payload irrelevant, but changing the text extent to frozen T239 materially changed duration (max_abs 0.2244882583618164) and the first 235 text-embedding positions (max_abs 0.11101388931274414, RMSE 0.006290534672319703, cosine 0.9998871625637002). The exact frozen T239 graphs reproduced that altered T239 calculation, not the dynamic T235 canonical-v2 oracle, so the frozen policy required a stop before runner implementation, EPContext generation, output, or phone access.", limitations=("This proves only that exact canonical-v2 T235 semantics and the exact frozen T239 graph identities are jointly incompatible; it is not a general Supertonic, ONNX Runtime, QNN, HTP, or Android incompatibility claim.", "The compatibility proof ran on host ONNX Runtime CPU. It is not route provider assignment, Android execution, or physical QNN/HTP proof.", "No runner, QNN context, route session, timing campaign, memory measurement, audio output, WAV, phone access, or listening review exists.", "Legacy-transcript substitution and differently hashed graph re-specialization were forbidden; either would define different semantics or a different route."), sources=("experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/results/t235-t239-masked-padding-compatibility.json", "experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/protocol/padding-compatibility-policy.json", "experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/protocol/experiment-contract.json", "experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/results/preflight-state.json", "experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/README.md"), missing={"android_attempted": "The terminal host compatibility gate failed before phone staging or access.", "provider": "No route runner, QNN session, or EPContext was created; host CPU compatibility evidence is not route provider assignment.", "precision": "No QNN/HTP execution or lowering occurred, so provider arithmetic precision is not established.", "threads": "No route runner or benchmark session existed.", "load_seconds": "Stopped before runner implementation, QNN session creation, or EPContext generation.", "cold_rtf": "No generation or audio output occurred.", "warm_median_rtf": "No first or warm generation campaign occurred.", "proof_run_rtf": "No Android or physical accelerator proof run occurred.", "first_post_setup_rtf": "No route setup or post-setup generation existed.", "peak_pss_bytes": "No route benchmark process or memory campaign existed.", "peak_vm_hwm_bytes": "No route benchmark process or memory campaign existed.", "wav": "Stopped before output generation; no WAV exists.", "physical_rpc_accelerator_cycle_hvx": "No phone access or physical accelerator execution occurred.", "listening": "No WAV exists and no listening review was requested or recorded."}, variant="Canonical v2 / exact frozen T239 graph identity / terminal host compatibility gate"),
    row("0023-supertonic-source-onnx-htp", "0023", "Supertonic 3", "legacy-v1 all-HTP source-ONNX compilation arm", "ran", attempted=True, provider="QNNExecutionProvider (fallback disabled; source ONNX)", precision="FP32 source graphs / QNN HTP internal precision not established", threads=1, metrics={"load_seconds": 21.6129, "cold_rtf": 0.131628, "warm_median_rtf": 0.130773, "first_post_setup_rtf": 0.131628, "peak_pss_bytes": 1374329 * 1024, "peak_vm_hwm_bytes": 1380480 * 1024}, wav={"path":"media/0023-supertonic-stable-softplus-qnn-context.wav","sha256":"47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c","bytes":1459536,"sample_rate_hz":44100,"channels":1,"duration_seconds":729746/44100}, summary="Matched physical-phone source-ONNX arm for the accepted legacy-v1 experiment-0011 stable-Softplus route. Three fresh processes measured four-session source compilation at [22.1599, 21.6129, 20.9571] s (median 21.6129 s); setup-only sampled PSS ranged 1,341,123–1,354,631 KiB. A separate persistent-session process ran one first generation (RTF 0.131628) plus five warm generations (median RTF 0.130773). Its float output and WAV were byte-identical to the matched context arm and the exact Moritz-accepted 0011 all-HTP WAV.", limitations=("Legacy-v1 230-byte transcript/T239/L238 route; not canonical v2 and not comparable as a matched canonical-v2 result.", "The current retained ORT 1.27.1 + QAIRT 2.49 Android runtime was used identically for both 0023 arms; the historical 0011 binary was unavailable, so no binary-identity claim is made.", "Setup is the median of three fresh setup-only processes from immediately before duration-session construction until all four sessions were ready; it excludes inference, teardown, and offline context generation.", "The separate profiled physical proof used the context arm only; do not transfer its RPC/accelerator/cycle/HVX evidence to this source arm.", "Peak PSS/VmHWM fields use the separate E2E process high-water observations; setup-only PSS is preserved in the summary. Parser repair was offline evidence handling over byte-preserved stdout and did not rerun the phone."), sources=("experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/phone-result.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/sha256-manifest.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/protocol/experiment-contract.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/protocol/phone-transport-contract.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/results/host-context-smoke/host-context-functional-smoke.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/results/clean-host-setup/clean-setup-result.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/README.md", "experiments/0011-supertonic-official-fp32-phone-comparison/results/softplus-matched-e2e-checkpoint.json"), missing={"proof_run_rtf": "The separate profiled physical proof was collected only for the context arm; no source-arm proof-run RTF exists."}, variant="Legacy v1 / stable-Softplus source ONNX / fallback-disabled QNN HTP"),
    row("0023-supertonic-external-context-htp", "0023", "Supertonic 3", "legacy-v1 all-HTP external EPContext arm", "ran", attempted=True, provider="QNNExecutionProvider (fallback disabled; external EPContext; source absent)", precision="FP32 source lineage / QNN HTP internal precision not established", threads=1, metrics={"load_seconds": 0.497816, "cold_rtf": 0.130393, "warm_median_rtf": 0.130153, "proof_run_rtf": 0.197667, "first_post_setup_rtf": 0.130393, "peak_pss_bytes": 162665 * 1024, "peak_vm_hwm_bytes": 166072 * 1024}, wav={"path":"media/0023-supertonic-stable-softplus-qnn-context.wav","sha256":"47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c","bytes":1459536,"sample_rate_hz":44100,"channels":1,"duration_seconds":729746/44100}, summary="Matched physical-phone external-EPContext arm for the accepted legacy-v1 experiment-0011 stable-Softplus route. With source ONNX unavailable, three fresh processes loaded four external contexts in [0.785324, 0.496524, 0.497816] s (median 0.497816 s), 21.115084 s less than source compilation: 43.4154× faster and a 97.6967% setup reduction. Setup-only sampled PSS ranged 162,301–162,649 KiB. A separate E2E process measured first RTF 0.130393 and five-warm median RTF 0.130153. A separate profiled run proved QNN-only ORT nodes plus matching RPC, accelerator-time, accelerator-cycle, and four-HVX-thread evidence for all neural calls. Output was byte-identical to the source arm and exact accepted 0011 WAV.", limitations=("Legacy-v1 230-byte transcript/T239/L238 route; not canonical v2 and intentionally independent of experiment 0022's overconstrained T235/T239 gate.", "The 43.4154× / 97.6967% claim applies only to the matched 0023 four-session readiness boundary on the authorized phone; offline context-generation cost is separate and excluded from context startup.", "The current retained ORT 1.27.1 + QAIRT 2.49 Android runtime was used identically for both arms; no binary-identity claim to historical 0011 is made.", "Profiled proof RTF 0.197667 is instrumentation-bearing physical evidence, not the unprofiled warm performance headline.", "Peak PSS/VmHWM fields use the E2E process high-water observations; setup-only PSS is preserved in the summary. Parser repair was offline evidence handling over byte-preserved stdout; device execution and cleanup had passed and no phone rerun occurred."), sources=("experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/phone-result.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/sha256-manifest.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/protocol/experiment-contract.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/protocol/phone-transport-contract.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/results/host-context-smoke/host-context-functional-smoke.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/results/clean-host-setup/clean-setup-result.json", "experiments/0023-supertonic-qnn-precompiled-context-startup/README.md", "experiments/0011-supertonic-official-fp32-phone-comparison/results/softplus-matched-e2e-checkpoint.json"), missing={}, variant="Legacy v1 / stable-Softplus external EPContext / fallback-disabled QNN HTP"),
    row(
        "0024-pocket-reconstruction-source-onnx-htp",
        "0024",
        "Pocket TTS",
        "canonical-v2 reconstruction-derivative source-ONNX QNN arm",
        "ran",
        attempted=True,
        provider="QNNExecutionProvider (fallback disabled; 0024 derivative source ONNX)",
        precision="FP32 0024 reconstruction derivative / QNN HTP internal precision not established",
        threads=1,
        metrics={
            "load_seconds": 27.0767,
            "cold_rtf": 0.172432,
            "warm_median_rtf": 0.168605,
            "proof_run_rtf": 0.566431,
            "peak_vm_hwm_bytes": 2568248 * 1024,
        },
        wav={
            "path": "media/0024-pocket-reconstruction-source-onnx-htp.wav",
            "sha256": "028f8a1e1861f8004619294738d9aa14509b2c3e5e5e626d99113700ab574241",
            "bytes": 625964,
            "sample_rate_hz": 24000,
            "channels": 1,
            "duration_seconds": 13.04,
        },
        summary="Matched canonical-v2 Pocket source-ONNX arm for the deterministic 0024 reconstruction derivative—not the exact 0014 graph set. Three fresh processes measured eight-session setup at [27.0767, 23.8668, 28.6125] s (median 27.0767 s), median first-generation RTF 0.172432, and pooled 15-warm median RTF 0.168605. A separate profiled process proved 344 QNN / 0 CPU calls with exactly matching RPC, accelerator, cycle, and HVX event counts. All benchmark generations reached EOS 160, emitted 163 frames / 312,960 samples / 13.04 s, and produced the same structurally valid WAV within this arm. The exact WAV is not reviewed.",
        limitations=(
            "This is a new deterministic 0024 reconstruction derivative whose controlled and specialized ONNX hashes differ from 0014; never relabel it as the exact 0014 graphs or transfer 0014 metrics/verdicts.",
            "Setup is the median of three fresh process lifetimes around all eight session creations. Offline context generation is separate and excluded; no minimum speedup gate was applied.",
            "The warm headline is the pooled median of 15 warm generations across three fresh processes, five warm generations per process with full state reset. The cold RTF field is the median of the three first complete generations, not a single designated run.",
            "Profiled proof RTF 0.566431 is instrumentation-bearing physical evidence excluded from setup/first/warm distributions.",
            "VmHWM is cumulative process-lifecycle high-water including sessions, mappings, caches, buffers, and completed generations; it is not isolated model/DSP memory. Peak PSS was not recorded.",
            "The campaign spans two phone windows because of an excluded external disconnect. Order/date/thermal differences are disclosed confounders; verified tri-state cleanup closure preceded resumed staging.",
            "The source and context WAVs are byte-distinct (correlation 0.453032; source-over-difference SNR -0.356050 dB). This is descriptive and neither sample has a listening verdict.",
        ),
        sources=(
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/result.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/phone-campaign/evidence-manifest.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/phone-campaign/physical/source/physical-analysis.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/phone-campaign/cleanup-resume/cleanup-resume.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/reconstruction.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/protocol/experiment-contract.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/README.md",
        ),
        missing={
            "first_post_setup_rtf": "The result publishes three first-generation RTFs and their median; no single run is designated as the normalized first_post_setup_rtf field.",
            "peak_pss_bytes": "Only cumulative process VmHWM was recorded; no sampled peak PSS campaign exists.",
        },
        variant="Canonical v2 / fixed Alba / 0024 reconstruction derivative / source ONNX QNN HTP",
    ),
    row(
        "0024-pocket-reconstruction-external-context-htp",
        "0024",
        "Pocket TTS",
        "canonical-v2 reconstruction-derivative external EPContext QNN arm",
        "ran",
        attempted=True,
        provider="QNNExecutionProvider (fallback disabled; external EPContext; source ONNX absent)",
        precision="FP32 0024 source lineage / QNN HTP internal precision not established",
        threads=1,
        metrics={
            "load_seconds": 1.01122,
            "cold_rtf": 0.16733,
            "warm_median_rtf": 0.164032,
            "proof_run_rtf": 0.609813,
            "peak_vm_hwm_bytes": 201616 * 1024,
        },
        wav={
            "path": "media/0024-pocket-reconstruction-external-context-htp.wav",
            "sha256": "7c3fc41d320e391ed39c10398f9c013d01cba93b9c733d3df546d31a0d006d81",
            "bytes": 625964,
            "sample_rate_hz": 24000,
            "channels": 1,
            "duration_seconds": 13.04,
        },
        summary="Matched canonical-v2 Pocket external-EPContext arm for the deterministic 0024 reconstruction derivative—not the exact 0014 graph set. With source ONNX absent, three fresh processes measured eight-session context reload at [0.729463, 1.26412, 1.01122] s (median 1.01122 s): 26.06548 s less than the source arm, 26.7763× faster, and a 96.26535% setup reduction. Median first-generation RTF was 0.167330 and pooled 15-warm median RTF was 0.164032. A separate profiled process proved 344 QNN / 0 CPU calls with exactly matching RPC, accelerator, cycle, and HVX event counts. All benchmark generations reached EOS 160, emitted 163 frames / 312,960 samples / 13.04 s, and produced the same structurally valid WAV within this arm. The exact WAV is not reviewed.",
        limitations=(
            "This is a new deterministic 0024 reconstruction derivative whose controlled and specialized ONNX hashes differ from 0014; never relabel it as the exact 0014 graphs or transfer 0014 metrics/verdicts.",
            "The 26.7763× / 96.26535% claim applies only to the matched eight-session 0024 readiness boundary on the authorized phone. Offline context generation is separate and excluded; no minimum speedup gate was applied.",
            "Every context reload and the physical proof ran with source ONNX unavailable. The warm headline is the pooled median of 15 warm generations across three fresh processes, five per process with full state reset. The cold RTF field is the median of three first complete generations.",
            "Profiled proof RTF 0.609813 is instrumentation-bearing physical evidence excluded from setup/first/warm distributions.",
            "VmHWM is cumulative process-lifecycle high-water including sessions, mappings, caches, buffers, and completed generations; it is not isolated model/DSP memory. Peak PSS was not recorded.",
            "The campaign spans two phone windows because of an excluded external disconnect. Order/date/thermal differences are disclosed confounders; verified tri-state cleanup closure preceded resumed staging.",
            "The source and context WAVs are byte-distinct (correlation 0.453032; source-over-difference SNR -0.356050 dB). This is descriptive and neither sample has a listening verdict.",
        ),
        sources=(
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/result.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/phone-campaign/evidence-manifest.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/phone-campaign/physical/context/physical-analysis.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/phone-campaign/cleanup-resume/cleanup-resume.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/reconstruction.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/protocol/experiment-contract.json",
            "experiments/0024-pocket-tts-qnn-precompiled-context-startup/README.md",
        ),
        missing={
            "first_post_setup_rtf": "The result publishes three first-generation RTFs and their median; no single run is designated as the normalized first_post_setup_rtf field.",
            "peak_pss_bytes": "Only cumulative process VmHWM was recorded; no sampled peak PSS campaign exists.",
        },
        variant="Canonical v2 / fixed Alba / 0024 reconstruction derivative / external EPContext QNN HTP",
    ),
    row("0014-pocket-alba-cpu-v2", "0014", "Pocket TTS", "canonical-v2 fixed-Alba text64/cache512 Android CPU", "ran", attempted=True, provider="CPUExecutionProvider", precision="FP32", threads=1, metrics={"load_seconds": 2.597, "cold_rtf": 0.412321, "warm_median_rtf": 0.414234, "first_post_setup_rtf": 0.412321, "peak_vm_hwm_bytes": 1412276 * 1024}, wav={"path":"media/0014-pocket-alba-cpu-v2.wav","sha256":"2e9021b972d69e05e5cd301973e2dc17cb8143f2a029bc027ef619a3460c34bd","bytes":625964,"sample_rate_hz":24000,"channels":1,"duration_seconds":13.04}, summary="Distinct canonical-v2 Pocket fixed-Alba text64/cache512 Android CPU route. Exact v2 text produced 64 token IDs; one persistent session set ran one first plus five warm generations with full state reset. All six reached EOS step 160, emitted 163 frames/312,960 samples (13.04 s), and were byte-identical. Warm median RTF was 0.414234 from [0.412642, 0.406708, 0.414234, 0.416536, 0.419467]. Moritz accepted the exact representative WAV as good.", limitations=("This text64/cache512 derivative is distinct from every text26/cache256 route and does not relabel or inherit their metrics or verdicts.", "Exact official fixed Alba state SHA e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c, temperature 0.3, seed 0, fixed voice—not voice cloning.", "First-post-setup and cold RTF refer to the same first complete generation, not two observations.", "VmHWM is cumulative process lifecycle high-water; no peak PSS was recorded. Android OS and CPU affinity were not captured/pinned; normal scheduler/DVFS applies.", "Batch runner exposes no honest streaming first-audio latency. Thermal status stayed 0; AP 35.8→50.4°C and skin 33.8→35.7°C."), sources=("experiments/0014-pocket-fp-onnx-qnn-htp/results/canonical-v2-benchmark.json", "experiments/0014-pocket-fp-onnx-qnn-htp/canonical-benchmark-protocol.json", "experiments/0014-pocket-fp-onnx-qnn-htp/RESULTS.md"), missing={"proof_run_rtf": "No separate instrumented proof run applies to the CPU route.", "peak_pss_bytes": "Only cumulative process VmHWM was recorded.", "android_os": "Not captured in the completed campaign; no further phone use was authorized for metadata-only collection.", "cpu_affinity": "Not pinned; normal Android scheduler/DVFS applies.", "first_audio_latency": "Batch runner produces complete output after latent generation/decoding and exposes no honest streaming first-audio boundary."}, variant="Canonical v2 / fixed Alba / text64-cache512 / CPU"),
    row("0014-pocket-alba-qnn-htp-v2", "0014", "Pocket TTS", "canonical-v2 fixed-Alba text64/cache512 full QNN/HTP", "ran", attempted=True, provider="QNNExecutionProvider (fallback disabled; CPU orchestration only)", precision="FP32 source graphs / QNN HTP", threads=1, metrics={"load_seconds": 62.2327, "cold_rtf": 0.191013, "warm_median_rtf": 0.181643, "proof_run_rtf": 0.57369, "first_post_setup_rtf": 0.191013, "peak_vm_hwm_bytes": 2405820 * 1024}, wav={"path":"media/0014-pocket-alba-qnn-htp-v2.wav","sha256":"601cd622dd0598c23dd7275074763aa37ae79b18a9d777ad946b1eaebd2c58e5","bytes":625964,"sample_rate_hz":24000,"channels":1,"duration_seconds":13.04}, summary="Distinct canonical-v2 Pocket fixed-Alba text64/cache512 fallback-disabled QNN/HTP route. Persistent sessions ran one first plus five warm generations with full state reset; all six reached EOS step 160, emitted 163 frames/13.04 s, and were byte-identical. Warm median RTF was 0.181643 from [0.181754, 0.178637, 0.179288, 0.182449, 0.181643]. Separate profiled proof RTF was 0.57369: 344 QNN and 0 CPU neural events exactly matched 344 RPC, accelerator, cycle, and HVX records. Moritz independently accepted the exact representative WAV as good.", limitations=("The profiled 0.57369 RTF is instrumentation-bearing physical proof, not the performance headline or a warm observation.", "All invoked neural sessions were proven on HTP with CPU fallback disabled; CPU only handled fixed fixtures, recurrent tensor ownership, EOS/orchestration, concatenation, and WAV output.", "Exact official fixed Alba state SHA e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c, temperature 0.3, seed 0, fixed voice—not voice cloning.", "First-post-setup and cold RTF refer to the same first complete generation. VmHWM is cumulative lifecycle high-water; the primary field is the unprofiled benchmark maximum 2,463,559,680 bytes, while the separate profiled proof reached 2,580,541,440 bytes.", "Android OS and CPU affinity were not captured/pinned. Batch runner exposes no streaming first-audio latency. Unprofiled thermal status stayed 0; AP 41.2→53.6°C and skin 37.1→39.3°C."), sources=("experiments/0014-pocket-fp-onnx-qnn-htp/results/canonical-v2-benchmark.json", "experiments/0014-pocket-fp-onnx-qnn-htp/canonical-benchmark-protocol.json", "experiments/0014-pocket-fp-onnx-qnn-htp/RESULTS.md"), missing={"peak_pss_bytes": "Only cumulative process VmHWM was recorded.", "android_os": "Not captured in the completed campaign; no further phone use was authorized for metadata-only collection.", "cpu_affinity": "Not pinned; normal Android scheduler/DVFS applies.", "first_audio_latency": "Batch runner produces complete output after latent generation/decoding and exposes no honest streaming first-audio boundary."}, variant="Canonical v2 / fixed Alba / text64-cache512 / fallback-disabled QNN HTP"),
    row("0019-moss-canonical-v2-qnn-phone-blocked", "0019", "MOSS-TTS-Nano", "canonical-v2 fixed-capacity QNN/HTP phone route", "blocked", attempted=True, provider="QNNExecutionProvider (fallback disabled; session not created)", precision="FP32 official ONNX derivatives", summary="Canonical-v2 fixed-capacity MOSS derivatives passed CPU equivalence, fail-closed host QNN assignment, context generation, and context reload gates. On the authorized phone, the final app-UID carrier loaded QNN backend interface 2.38 but CreateDevice returned QNN_DEVICE_ERROR_INVALID_CONFIG before GetCapability, neural session assignment, or inference. No phone benchmark or physical HTP claim exists.", limitations=("The blocker is bounded to the recorded carrier/app UID, Android build, ORT/QNN versions, and phone; it does not prove all Android apps or QNN deployments incompatible.", "Host CPU equivalence, QNN eligibility, and four generated/reloaded context binaries are feasibility evidence only—not Android timing, memory, provider-event, or physical execution evidence.", "Public libcdsprpc declaration, exact native hashes, unique verified V73 skel/RFSA staging, fallback disabled, graph-I/O quantization off, runtime SoC auto-detect, and minimal device options did not move the failure beyond CreateDevice.", "No mixed fallback route, phone inference, audio decode, WAV, or listening verdict exists. Cleanup and lock reacquisition were verified."), sources=("experiments/0019-moss-tts-nano-qnn-htp-android/results/fixed-capacity-phone-blocker.json", "experiments/0019-moss-tts-nano-qnn-htp-android/results/fixed-capacity-cpu-equivalence.json", "experiments/0019-moss-tts-nano-qnn-htp-android/results/fixed-capacity-context-provenance.json", "experiments/0019-moss-tts-nano-qnn-htp-android/results/fixed-capacity-derivative-provenance.json", "experiments/0019-moss-tts-nano-qnn-htp-android/protocol/canonical-v2-tokenization.json", "experiments/0019-moss-tts-nano-qnn-htp-android/README.md"), missing={"load_seconds": "First fail-closed QNN session never created; backend setup is not a completed route setup measurement.", "cold_rtf": "No inference occurred.", "warm_median_rtf": "No first or warm inference occurred.", "proof_run_rtf": "No physical execution proof run occurred; CreateDevice failed before assignment.", "first_post_setup_rtf": "No session or post-setup generation existed.", "peak_pss_bytes": "No benchmark process progressed beyond backend setup.", "peak_vm_hwm_bytes": "No benchmark process progressed beyond backend setup.", "provider_events": "No session assignment or inference occurred.", "physical_rpc_accelerator_cycle_hvx": "CreateDevice failed before execution.", "wav": "No inference or audio decode occurred.", "listening": "No phone WAV exists; listening is not applicable."}, variant="Canonical v2 / fixed-capacity derivative / app-UID QNN phone blocker"),
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
MODEL_METADATA["0017-kokoro-qnn-host-blocked"] = {"model_identity": KOKORO_HF_SOURCE, "quantization": "Unquantized FP32 canonical-v2 fixed-contract staged derivative; zero quantized operators; historical noncanonical derivative evidence remains in sources"}
MODEL_METADATA["0018-moss-tts-nano-cpu"] = {"model_identity": MOSS_HF_SOURCE, "quantization": "Unquantized official ONNX graphs; CPUExecutionProvider only"}
MODEL_METADATA["0019-moss-tts-nano-qnn-blocked"] = {"model_identity": MOSS_HF_SOURCE, "quantization": "Unquantized official ONNX graphs; no quantization or physical Android route was attempted"}
MODEL_METADATA["0019-moss-canonical-v2-qnn-phone-blocked"] = {"model_identity": MOSS_HF_SOURCE, "quantization": "Unquantized official ONNX-derived fixed-capacity graphs; no quantization or calibration; no phone neural session"}
MODEL_METADATA["0020-supertonic-refresh-bootstrap"] = {"model_identity": SUPERTONIC_SOURCE, "quantization": "INT8 ONNX release outputs; exact historical archive contract prepared"}
MODEL_METADATA["0021-supertonic-int8-cpu-v2"] = {"model_identity": SUPERTONIC_SOURCE, "quantization": "Released INT8 ONNX archive SHA 82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427"}
MODEL_METADATA["0022-supertonic-t239-padding-blocked"] = {"model_identity": SUPERTONIC_SOURCE, "quantization": "Unquantized FP32 official-source-derived frozen T239 graphs; no QNN context generation, lowering, quantization, or phone execution occurred"}
for _id in ("0023-supertonic-source-onnx-htp", "0023-supertonic-external-context-htp"):
    MODEL_METADATA[_id] = {"model_identity": SUPERTONIC_SOURCE, "quantization": "Unquantized FP32 official-source graphs with stable-Softplus vector rewrite; QNN HTP internal lowering precision not established"}
for _id in ("0024-pocket-reconstruction-source-onnx-htp", "0024-pocket-reconstruction-external-context-htp"):
    MODEL_METADATA[_id] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Unquantized FP32 deterministic 0024 reconstruction derivative; all eight hashes differ from 0014; QNN HTP internal lowering precision not established"}
MODEL_METADATA["0014-pocket-alba-cpu-v2"] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Unquantized FP32 text64/cache512 ONNX derivative; zero quantization claimed"}
MODEL_METADATA["0014-pocket-alba-qnn-htp-v2"] = {"model_identity": POCKET_HF_SOURCE, "quantization": "Unquantized FP32 source-graph text64/cache512 derivative; no quantized-operator claim"}

STRUCTURAL_AUDIO_OVERRIDES = {
    "0017-kokoro-qnn-host-blocked": {
        "status": "invalid",
        "basis": "Committed canonical-v2 host float32 output failed the structural audio gate; this ignored tensor is not a retained WAV or listening sample.",
        "sample_sha256": "2992f71911b8af233841af4058e8218e8705c987a51643d1d709d96545b60a08",
    },
}


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
    "0022-supertonic-t239-padding-blocked": {
        "status": "fail",
        "summary": "The locked canonical-T235-to-exact-frozen-T239 masked-padding compatibility gate failed, requiring a stop before runner, context, output, or phone work.",
        "comparison_notes": ["Filler-ID payload invariance passed, and the exact frozen T239 graphs reproduced dynamic T239 within specialization limits; dynamic T239 did not preserve the dynamic T235 canonical oracle within any locked duration/text-prefix limit."],
    },
    "0017-kokoro-qnn-host-blocked": {
        "status": "fail",
        "summary": "All 18 fallback-disabled canonical-v2 host QNN stages executed QNN-only, but the duration contract and structural audio gate failed; phone eligibility is false.",
        "comparison_notes": ["Stage 1 is the earliest non-bit-exact output; stage 4 is the earliest material/discrete divergence; root cause is unavailable and no Android, physical HTP, WAV, listening, or benchmark-performance claim follows."],
    },
    "0024-pocket-reconstruction-source-onnx-htp": {
        "status": "descriptive",
        "summary": "Completed canonical-v2 source-ONNX arm of the matched 0024 reconstruction-derivative startup comparison, with separate fallback-disabled physical proof and structurally valid but unreviewed audio.",
        "comparison_notes": ["Matched context reload reduced median eight-session setup by 26.06548 s (96.26535%, 26.7763× source/context). Source/context WAV correlation 0.453032 and SNR -0.356050 dB are descriptive; neither exact hash has a listening verdict."],
    },
    "0024-pocket-reconstruction-external-context-htp": {
        "status": "descriptive",
        "summary": "Completed canonical-v2 external-EPContext arm of the matched 0024 reconstruction-derivative startup comparison, with source ONNX absent, separate fallback-disabled physical proof, and structurally valid but unreviewed audio.",
        "comparison_notes": ["Median eight-session reload setup was 1.01122 s versus source compilation 27.0767 s. Offline context generation is excluded from setup, and no minimum speedup gate was applied."],
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
    "0021-supertonic-int8-cpu-v2": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-20",
        "notes": "good. Exact 0021 canonical-v2 released-INT8 CPU representative only; do not generalize to any other Supertonic route or WAV.", "sample_sha256": "201f8e79d39e2fbb9db8a64a9f139641db9e27fabb828bcc039286a49c8987df",
    },
    "0014-pocket-alba-cpu-v2": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-20",
        "notes": "good. Exact canonical-v2 text64/cache512 Android CPU WAV only; HTP requires fresh verdict.", "sample_sha256": "2e9021b972d69e05e5cd301973e2dc17cb8143f2a029bc027ef619a3460c34bd",
    },
    "0014-pocket-alba-qnn-htp-v2": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-20",
        "notes": "good. Exact canonical-v2 fixed-Alba text64/cache512 fallback-disabled physical QNN/HTP WAV only.", "sample_sha256": "601cd622dd0598c23dd7275074763aa37ae79b18a9d777ad946b1eaebd2c58e5",
    },
    "0023-supertonic-source-onnx-htp": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Byte-identical to the exact experiment-0011 all-HTP WAV previously accepted by Moritz; the verdict applies to this identical retained hash, not to other outputs.", "sample_sha256": "47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c",
    },
    "0023-supertonic-external-context-htp": {
        "status": "accepted", "reviewer": "Moritz", "date": "2026-08-19",
        "notes": "Byte-identical to the exact experiment-0011 all-HTP WAV previously accepted by Moritz; the verdict applies to this identical retained hash, not to other outputs.", "sample_sha256": "47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c",
    },
}

MATCHED_COMPARISON_0024 = {
    "comparison_id": "0024-pocket-reconstruction-source-vs-external-context",
    "source_commit": "b59601ef66d5d24b6af249ab082291f0c53d4b25",
    "route_identity_boundary": "Matched deterministic 0024 reconstruction derivative; all eight graph hashes differ from 0014 and no 0014 identity or verdict transfers.",
    "source_setup_seconds": [27.0767, 23.8668, 28.6125],
    "context_setup_seconds": [0.729463, 1.26412, 1.01122],
    "source_setup_median_seconds": 27.0767,
    "context_setup_median_seconds": 1.01122,
    "source_minus_context_median_seconds": 26.065479999999997,
    "source_over_context_median_ratio": 26.776270247819465,
    "context_setup_reduction_percent": 96.26534991339418,
    "minimum_speedup_gate": None,
    "source_first_rtf": [0.172432, 0.167197, 0.182052],
    "context_first_rtf": [0.167568, 0.16733, 0.165802],
    "source_first_rtf_median": 0.172432,
    "context_first_rtf_median": 0.16733,
    "source_warm_rtf": [0.167737, 0.167383, 0.167914, 0.166717, 0.168605, 0.170602, 0.16466, 0.166384, 0.170978, 0.172556, 0.177048, 0.170004, 0.169318, 0.169183, 0.16854],
    "context_warm_rtf": [0.165296, 0.16402, 0.165763, 0.165462, 0.164016, 0.16418, 0.163039, 0.163203, 0.163868, 0.163095, 0.165363, 0.16382, 0.164594, 0.164763, 0.164032],
    "source_warm_median_rtf": 0.168605,
    "context_warm_median_rtf": 0.164032,
    "offline_context_generation_included": False,
    "proof_runs_excluded_from_benchmark_metrics": True,
    "output_comparison": {
        "byte_identical": False,
        "equal_length": True,
        "correlation": 0.45303178576893793,
        "snr_db_source_over_difference": -0.3560496343804135,
        "interpretation": "descriptive only; both byte-distinct WAVs remain not_reviewed",
    },
}
MATCHED_COMPARISON_OVERRIDES = {
    "0024-pocket-reconstruction-source-onnx-htp": {
        **MATCHED_COMPARISON_0024,
        "arm": "source",
        "peer_route_id": "0024-pocket-reconstruction-external-context-htp",
    },
    "0024-pocket-reconstruction-external-context-htp": {
        **MATCHED_COMPARISON_0024,
        "arm": "context",
        "peer_route_id": "0024-pocket-reconstruction-source-onnx-htp",
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
        "listening_review": {"status": "accepted", "reviewer": "Moritz", "date": "2026-08-20", "notes": "good. Exact 0020 legacy-v1 refresh representative only; do not generalize to any other Supertonic route or WAV.", "sample_sha256": "1cf003d55c81e49983cbe385fdb98868ccdf4b1a6b1482e21bab020c7567ee6e"},
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
TRANSCRIPT_METADATA["0017-kokoro-qnn-host-blocked"] = transcript_metadata("canonical_v2", CANONICAL_V2_SHA256, "protocols/android-tts-benchmark/transcript.txt", "Experiment 0017 exact canonical-v2 bytes and pinned official Kokoro 0.9.4 American-English frontend output.", byte_count=226, trailing_newline=False, effective_frontend={"kind": "official Kokoro 0.9.4 KPipeline American-English frontend", "token_count": 235, "token_ids_encoding": "little-endian int64", "token_ids_sha256": "9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280", "source": "experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-frontend-provenance.json"}, audit_source="experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-host-qnn-gate.json", reason="Exact canonical-v2 host feasibility route; excluded from the compact Android table because the structural gate failed before phone access.")
TRANSCRIPT_METADATA["0021-supertonic-int8-cpu-v2"] = transcript_metadata("canonical_v2", CANONICAL_V2_SHA256, "experiments/0021-supertonic-canonical-v2-android-cpu/protocol/transcript.txt", "Experiment 0021 exact canonical-v2 input and official unicode-indexer mapping.", byte_count=226, trailing_newline=False, effective_frontend={"kind": "official Supertonic unicode_indexer.bin direct codepoint mapping", "mapped_id_count": 226, "mapped_ids_int32le_sha256": "32fc26951a3f521bcf0745117235804bc628e112a48789b355d44eeef62fc5f1", "unicode_indexer_sha256": "8402ca48e5189a8950138580b0fff64db6f072f24ac07cd54ba8b2fbb9883b30", "source": "experiments/0021-supertonic-canonical-v2-android-cpu/results/frontend-provenance.json"}, audit_source="experiments/0021-supertonic-canonical-v2-android-cpu/results/phone-cpu-result.json")
TRANSCRIPT_METADATA["0022-supertonic-t239-padding-blocked"] = transcript_metadata("canonical_v2", CANONICAL_V2_SHA256, "experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/protocol/transcript.txt", "Experiment 0022 exact canonical-v2 bytes plus complete <en>...</en> wrapper and official unicode-indexer mapping produced the locked semantic T235 oracle input.", byte_count=226, trailing_newline=False, effective_frontend={"kind": "official Supertonic unicode-indexer mapping after complete language wrapper", "token_count": 235, "token_ids_sha256": "cf10ba8c539f92c9b0b6a6394ddc6788801bee0e15fb75405a4433c6833cfbba", "token_ids_dtype": "int64", "source": "experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/results/t235-t239-masked-padding-compatibility.json"}, audit_source="experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/results/t235-t239-masked-padding-compatibility.json")
for _id in ("0023-supertonic-source-onnx-htp", "0023-supertonic-external-context-htp"):
    TRANSCRIPT_METADATA[_id] = transcript_metadata("legacy_v1", LEGACY_V1_SHA256, "experiments/0023-supertonic-qnn-precompiled-context-startup/protocol/transcript.txt", "Experiment 0023 exact accepted experiment-0011 legacy-v1 transcript and processed T239 route.", byte_count=230, trailing_newline=False, audit_source="experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/phone-result.json", reason="Exact legacy-v1 matched-arm route; it is not canonical v2 and must not be compared as a canonical-v2 result.")
for _id in ("0024-pocket-reconstruction-source-onnx-htp", "0024-pocket-reconstruction-external-context-htp"):
    TRANSCRIPT_METADATA[_id] = transcript_metadata("canonical_v2", CANONICAL_V2_SHA256, "experiments/0024-pocket-tts-qnn-precompiled-context-startup/protocol/transcript.txt", "Experiment 0024 exact canonical-v2 bytes and Pocket tokenizer output for its deterministic reconstruction derivative.", byte_count=226, trailing_newline=False, effective_frontend={"kind": "Pocket tokenizer", "token_count": 64, "token_ids_encoding": "little-endian int64", "token_ids_sha256": "56d50c958627be19a7f2c86dde68a537a80f3f6d9087c16f55fde58c4d117c82", "tokenizer_sha256": "d461765ae179566678c93091c5fa6f2984c31bbe990bf1aa62d92c64d91bc3f6", "source": "experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/result.json"}, audit_source="experiments/0024-pocket-tts-qnn-precompiled-context-startup/results/result.json", reason="Exact canonical-v2 matched 0024 reconstruction-derivative arms; not the exact 0014 graph identities and no 0014 verdict transfers.")
for _id in ("0014-pocket-alba-cpu-v2", "0014-pocket-alba-qnn-htp-v2"):
    TRANSCRIPT_METADATA[_id] = transcript_metadata("canonical_v2", CANONICAL_V2_SHA256, "protocols/android-tts-benchmark/transcript.txt", "Experiment 0014 canonical-v2 text64/cache512 contract and exact Pocket tokenizer output.", byte_count=226, trailing_newline=False, effective_frontend={"kind": "Pocket tokenizer", "token_count": 64, "token_ids_encoding": "little-endian int64", "token_ids_sha256": "56d50c958627be19a7f2c86dde68a537a80f3f6d9087c16f55fde58c4d117c82", "tokenizer_sha256": "d461765ae179566678c93091c5fa6f2984c31bbe990bf1aa62d92c64d91bc3f6", "source": "experiments/0014-pocket-fp-onnx-qnn-htp/results/canonical-v2-benchmark.json"}, audit_source="experiments/0014-pocket-fp-onnx-qnn-htp/results/canonical-v2-benchmark.json")
TRANSCRIPT_METADATA["0019-moss-canonical-v2-qnn-phone-blocked"] = transcript_metadata("canonical_v2", CANONICAL_V2_SHA256, "experiments/0019-moss-tts-nano-qnn-htp-android/protocol/canonical-v2-transcript.txt", "Experiment 0019 exact canonical-v2 MOSS SentencePiece tokenization.", byte_count=226, trailing_newline=False, effective_frontend={"kind": "MOSS SentencePiece tokenizer", "token_count": 51, "tokenizer_model_sha256": "c353ee1479b536bf414c1b247f5542b6607fb8ae91320e5af1781fee200fddff", "token_ids": [5322,300,642,2160,9813,10364,676,6704,1680,10363,661,10376,530,524,3598,4991,1727,420,273,628,10380,6271,10364,332,10211,1079,7824,2276,2103,1734,3628,10364,606,1217,1107,298,3572,302,8741,5368,10364,311,425,1957,273,2868,831,10104,372,9153,10380], "source": "experiments/0019-moss-tts-nano-qnn-htp-android/protocol/canonical-v2-tokenization.json"}, audit_source="experiments/0019-moss-tts-nano-qnn-htp-android/results/fixed-capacity-phone-blocker.json")


PRESENTATION_SUPPRESSIONS = {
    "0008-pocket-cpu-t1": {
        "dashboard_visible": False,
        "visibility_reason": "Superseded in the compact dashboard by the newer 0009 one-thread Pocket TTS thread-sweep row. The complete 0008 evidence remains unchanged in this registry.",
        "superseded_by": "0009-pocket-cpu-t1",
    },
    "0008-kokoro-cpu-t1": {
        "dashboard_visible": False,
        "visibility_reason": "Superseded in the compact dashboard by the newer 0009 one-thread Kokoro thread-sweep row. The complete 0008 evidence remains unchanged in this registry.",
        "superseded_by": "0009-kokoro-cpu-t1",
    },
    "0008-supertonic-cpu-t1": {
        "dashboard_visible": False,
        "visibility_reason": "Superseded in the compact dashboard by the newer 0009 one-thread Supertonic thread-sweep row. The complete 0008 evidence, nested 0020 refresh, and retained refresh WAV remain unchanged in this registry and accessible on the 0020 experiment page.",
        "superseded_by": "0009-supertonic-cpu-t1",
    },
    "0014-pocket-alba-fixed-qnn-htp": {
        "dashboard_visible": False,
        "visibility_reason": "Superseded in the compact dashboard by the canonical-v2 text64/cache512 full-QNN/HTP route. The older noncanonical fixed-Alba HTP route, exact WAV verdict, metrics, and sources remain unchanged in this registry.",
        "superseded_by": "0014-pocket-alba-qnn-htp-v2",
    },
}


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
    "0023-supertonic-source-onnx-htp", "0023-supertonic-external-context-htp",
    "0024-pocket-reconstruction-source-onnx-htp", "0024-pocket-reconstruction-external-context-htp",
    "0014-pocket-alba-cpu-v2", "0014-pocket-alba-qnn-htp-v2",
}
for _row in ROWS:
    _metadata = MODEL_METADATA.get(_row["id"], {})
    _row["model_identity"] = _metadata.get("model_identity")
    _row["quantization"] = _metadata.get("quantization")
    _row["scope"] = "full_e2e" if _row["id"] in FULL_E2E_IDS else "excluded_non_e2e"
    if _row["id"] in PRESENTATION_SUPPRESSIONS:
        _row["presentation"] = PRESENTATION_SUPPRESSIONS[_row["id"]]
    _row["transcript"] = TRANSCRIPT_METADATA.get(_row["id"])
    if _row["transcript"] is None:
        _row["missing_reasons"].setdefault("transcript", "This excluded/non-E2E route was not classified by the committed visible-route transcript audit.")
    if _row["id"] in REMEASUREMENTS:
        _row["remeasurements"] = REMEASUREMENTS[_row["id"]]
    if _row["id"] in STRUCTURAL_AUDIO_OVERRIDES:
        _row["structural_audio"] = STRUCTURAL_AUDIO_OVERRIDES[_row["id"]]
    if _row["id"] in OBJECTIVE_EVIDENCE_OVERRIDES:
        _row["objective_evidence"] = OBJECTIVE_EVIDENCE_OVERRIDES[_row["id"]]
    if _row["id"] in LISTENING_REVIEWS:
        _row["listening_review"] = LISTENING_REVIEWS[_row["id"]]
    if _row["id"] in MATCHED_COMPARISON_OVERRIDES:
        _row["matched_comparison"] = MATCHED_COMPARISON_OVERRIDES[_row["id"]]
    _row["missing_reasons"].update(_metadata.get("missing", {}))
    if _row["model_identity"] is None:
        _row["missing_reasons"].setdefault("model_identity", "No committed source/model identity is established for this route.")
    if _row["quantization"] is None:
        _row["missing_reasons"].setdefault("quantization", "No committed quantization description is established for this route.")
    for _metric_name, _metric_value in _row["metrics"].items():
        if _metric_value is None:
            _row["missing_reasons"].setdefault(_metric_name, f"No committed normalized {_metric_name} measurement is established for this route.")
# Keep ROWS exhaustive for machine evidence. The presentation layer filters to
# FULL_E2E_IDS and then applies explicit presentation-only suppressions, so
# component/probe attempts and superseded duplicate rows remain queryable without
# appearing in the compact comparison table or audio presentation.


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
    entries = [e for e in registry["entries"] if e["scope"] == "full_e2e" and e.get("presentation", {}).get("dashboard_visible", True)]
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
        listening_badge = f'<span class="status {review_cls}">{html.escape(review_status)}</span>'
        if display_wav:
            listening_label = f'{review_status.replace("_", " ")} listening status; play retained sample for {e["model"]}, {e["route"]}'
            listening = f'<a class="listening-link" href="#{html.escape(anchor)}" aria-label="{html.escape(listening_label, quote=True)}">{listening_badge}</a>'
        else:
            listening = listening_badge
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
:root{{--bg:#0f172a;--panel:#172033;--line:#334155;--ink:#e5e7eb;--muted:#94a3b8;--accent:#67e8f9}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}main{{max-width:1500px;margin:auto;padding:22px 24px}}h1{{font-size:24px;line-height:1.2;margin:0 0 16px}}small{{color:var(--muted)}}a{{color:var(--accent)}}.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:12px}}table{{border-collapse:collapse;width:100%;min-width:1320px;background:var(--panel)}}th,td{{padding:12px 13px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}th{{position:sticky;top:0;background:#1e293b;color:#bae6fd;white-space:nowrap;user-select:none;cursor:pointer}}th:hover{{background:#26364d}}th::after{{content:' ↕';color:#64748b}}th[aria-sort="ascending"]::after{{content:' ↑';color:var(--accent)}}th[aria-sort="descending"]::after{{content:' ↓';color:var(--accent)}}td:nth-child(10){{min-width:350px;color:#cbd5e1}}.status{{border-radius:99px;padding:3px 9px;font-size:12px;font-weight:700;white-space:nowrap}}.listening-link{{display:inline-block;text-decoration:none}}.listening-link:hover .status{{text-decoration:underline}}.listening-link:focus-visible{{outline:2px solid var(--accent);outline-offset:3px;border-radius:99px}}.transcript{{font-weight:700}}.transcript-canonical_v2{{color:#a7f3d0}}.transcript-legacy_v1{{color:#fde68a}}.transcript-noncanonical{{color:#fecaca}}.ran{{background:#064e3b;color:#a7f3d0}}.listening-not-reviewed{{background:#713f12;color:#fde68a}}.listening-accepted{{background:#064e3b;color:#a7f3d0}}.listening-rejected{{background:#7f1d1d;color:#fecaca}}.blocked,.deferred,.not-run{{background:#713f12;color:#fde68a}}.partial{{background:#164e63;color:#a5f3fc}}code{{color:#bae6fd}}h2{{font-size:20px;margin:30px 0 12px}}.timeline-note{{color:var(--muted);margin-top:-4px}}.players{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}}.player{{scroll-margin-top:16px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}.player:target{{outline:2px solid var(--accent)}}.player audio{{display:block;width:100%;margin:11px 0 8px}}.back{{font-size:12px}}footer{{margin-top:16px;color:var(--muted);font-size:12px}}</style></head><body><main><h1>Android benchmark registry</h1><div class="table-wrap"><table id="routes"><thead><tr><th data-type="text">Experiment</th><th data-type="text">Model / route</th><th data-type="text">Quantization</th><th data-type="text">Status</th><th data-type="text">Listening</th><th data-type="text">Provider</th><th data-type="number" aria-sort="ascending" title="Warm median by default; otherwise the designated non-warm headline type is shown in brackets. Hover a value for all RTF evidence and missing reasons.">RTF</th><th data-type="number">Peak memory</th><th data-type="number">Audio</th><th data-type="text">Evidence summary</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div><h2 id="audio-samples">Audio samples</h2><div class="players">{''.join(players)}</div><h2 id="needs-review">Needs review</h2><p class="timeline-note">Playable full-E2E samples with no explicit Moritz listening verdict yet.</p><div class="players">{''.join(needs_review_players)}</div><h2 id="model-timeline">Model release timeline</h2><p class="timeline-note">First public family/model release dates, not later quantized archives or Android package dates. The date basis and source are recorded in <code>registry.json</code>.</p><div class="table-wrap"><table id="timeline"><thead><tr><th>Model</th><th>First public release</th><th>Date basis</th><th>Source</th></tr></thead><tbody>{''.join(timeline_rows)}</tbody></table></div><footer>Click a column heading to sort. Missing values sort last. Details: <a href="README.md">README</a> · <a href="missing-fields.md">missing fields</a>.</footer></main><script>
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
