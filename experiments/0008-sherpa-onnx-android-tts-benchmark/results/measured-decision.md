# Measured Android decision

**Experiment 0008 is complete.** On the Galaxy S23 Ultra, the pinned Supertonic 3 INT8 deployment is the strongest measured default. Pocket also runs faster than real time, but only with the packaged Bria reference rather than the requested Alba voice and with unresolved license messaging. Exact Kokoro v1.0 is slower than real time with the canonical one-thread setting; its protocol-triggered two-thread run narrowly reaches faster-than-real-time median RTF.

These conclusions apply only to sherpa-onnx `v1.13.5` Android CPU deployments on the measured `SM-S918B`. They are not measurements of the different host PyTorch/model workflows in experiment 0007.

## Decisions

| Candidate and pinned Android variant | Decision | Basis |
|---|---|---|
| Pocket `sherpa-onnx-pocket-tts-int8-2026-01-26` | **works_with_limitations** | Warm median RTF 0.389 and four valid WAVs, but the actual reference is Bria, not requested Alba; license messaging is unresolved; no manual listening |
| Kokoro exact `kokoro-multi-lang-v1_0`, SID 3/`af_heart` | **works_with_limitations** | Four valid WAVs, but canonical one-thread warm median RTF 1.195 is slower than real time; optional two-thread median is 0.963; no manual listening |
| Supertonic 3 `sherpa-onnx-supertonic-3-tts-int8-2026-05-11`, SID 5/M1, English | **works** | Warm median RTF 0.370, lowest sampled peak PSS, and four valid WAVs; no manual listening |

`works` here means the pinned deployment completed the measurement contract and generated valid audio at a warm median RTF below 1. It is not a production quality or licensing approval.

## Canonical one-thread comparison

All values below are observations from fresh-process CPU campaigns. `Callback` is synthesis start to first non-empty callback, not playback latency. PSS and RSS are sampled or boundary process measurements; `VmHWM` is the cumulative process-lifetime high-water mark, not an independent phase peak.

| Candidate | Load (s) | Cold wall / audio / RTF / callback (s) | Warm 1 wall / audio / RTF / callback (s) | Warm 2 | Warm 3 | Warm median RTF | Boundary PSS / RSS | Sampled peak PSS / RSS | Cumulative VmHWM | Audio |
|---|---:|---|---|---|---|---:|---:|---:|---:|---|
| Pocket | 0.659 | 5.874 / 13.478 / 0.436 / 0.840 | 5.208 / 13.582 / 0.383 / 0.568 | 5.362 / 13.797 / 0.389 / 0.602 | 5.320 / 13.668 / 0.389 / 0.565 | **0.389** | 683.1 / 750.9 MB | 683.6 / 751.4 MB | 751.4 MB | 24 kHz; 4/4 valid |
| Kokoro | 1.303 | 15.780 / 13.283 / 1.188 / 6.198 | 15.874 / 13.287 / 1.195 / 6.317 | 15.882 / 13.288 / 1.195 / 6.352 | 16.002 / 13.282 / 1.205 / 6.396 | **1.195** | 930.0 / 994.8 MB | 929.7 / 994.7 MB | 995.1 MB | 24 kHz; 4/4 valid |
| Supertonic 3 | 0.765 | 6.379 / 16.548 / 0.385 / 6.376 | 6.118 / 16.548 / 0.370 / 6.117 | 6.128 / 16.548 / 0.370 / 6.126 | 6.169 / 16.548 / 0.373 / 6.167 | **0.370** | 462.6 / 530.7 MB | 463.0 / 531.2 MB | 531.3 MB | 44.1 kHz; 4/4 valid |

MB values above are decimal MB derived from measured bytes. The [machine-readable decision](measured-decision.json) retains the exact byte and floating-point values.

All twelve canonical WAVs decoded fully with an independent PCM WAV reader. Their recorded frame counts, rates, durations, byte sizes, and SHA-256 values agree; all are non-silent and unclipped. Every candidate produced four different WAV hashes, so output is described only as nondeterministic within these campaigns. Manual listening was **not performed**.

## Optional two-thread comparison

Only Kokoro triggered this separate run because its valid canonical warm median RTF exceeded 1.0. It does not replace the one-thread table.

| Candidate | Load (s) | Cold wall / audio / RTF / callback (s) | Warm RTFs | Warm median RTF | Sampled peak PSS | Thermal wait | Validation |
|---|---:|---|---|---:|---:|---:|---|
| Kokoro, 2 CPU threads | 1.224 | 12.193 / 13.296 / 0.917 / 4.703 | 0.963, 0.976, 0.945 | **0.963** | 924.6 MB | 120 s | 4/4 WAVs valid |

Pocket and Supertonic did not trigger a two-thread run because their one-thread warm medians were already below 1.0.

## Voice and licensing limits

Pocket did **not** use Alba. The pinned public archive contains no provenance-verifiable Alba reference, so the predeclared packaged `test_wavs/bria.wav` fallback was used (`voice_match=false`, SHA-256 `85f46d6f0642f657a6bd689ddaa52d5a5f53e4314715e1032704c80917392181`). Bria must not be presented as Alba.

Pocket remains research-only for this decision. Its package workflow/README describes non-commercial use while its bundled model license says CC BY 4.0. This experiment preserves both statements and does not resolve which terms govern production use.

Kokoro's SID 3 to `af_heart` and Supertonic's SID 5 to M1 mappings are provenance-backed. Neither was guessed.

## Thermal, order, and failures

The canonical order was fixed: Pocket, Kokoro, Supertonic. Each successful run began at Android thermal status `NONE` and within the 34.3 °C campaign baseline allowance: 34.8 °C, 34.5 °C, and 34.3 °C respectively. No canonical run waited. Kokoro's optional two-thread run polled 35.6 °C and 35.4 °C, then became eligible at 35.0 °C after 120 seconds.

Fixed order was not randomized. The eligibility gate reduces but cannot remove order, charging, or residual thermal bias, so this is not a randomized cross-model hardware study.

Earlier Pocket and Kokoro attempts reached cold synthesis and aborted with `SIGABRT`: the Kotlin callback bridge exposed the wrong JNI signature. Their native-crash manifests and raw hashes remain retained. The successful campaigns followed a correction to the concrete Java callback bridge; these failures are harness failures, not model `does_not_work` outcomes.

## Evidence

- [Machine-readable measured decision](measured-decision.json)
- [Pocket one-thread result](pocket/one-thread-result.json) and [retained crash](pocket/native-crash.failure.json)
- [Kokoro one-thread result](kokoro/one-thread-result.json), [two-thread result](kokoro/two-thread-result.json), and [retained crash](kokoro/native-crash.failure.json)
- [Supertonic one-thread result](supertonic-3/one-thread-result.json)
- [Device preflight](../preflight/galaxy-s23-ultra.json)
- [Historical experiment 0007](../../0007-mobile-podcast-preview-bakeoff/README.md)

VibeVoice Realtime 0.5B, Inflect Nano v1, and Kitten TTS Mini 80M v0.8 remain historical-only. They are not pending Android follow-up.
