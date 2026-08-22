---
experiment: 0021-supertonic-canonical-v2-android-cpu
status: completed
summary: The canonical-v2 released-INT8 CPU route ran end to end on the Galaxy S23 Ultra, stayed below real time, and its exact representative WAV was accepted by Moritz.
registry: 0021-supertonic-int8-cpu-v2
---

# Experiment 0021 — Supertonic canonical-v2 Android CPU benchmark

## Experiment description

Experiment 0021 established a clean Android CPU baseline for Supertonic 3 using the project's exact canonical-v2 transcript. Earlier Supertonic measurements used the legacy-v1 text, so this was deliberately recorded as a new route rather than used to rewrite those rows.

The route pinned the released INT8 ONNX archive and sherpa-onnx 1.13.5 Android runtime. It used the official M1 voice (semantic SID5), English, one inference thread, and the CPU provider on the authorized Samsung Galaxy S23 Ultra (`SM-S918B`, Snapdragon 8 Gen 2 / `SM8550`). The exact 226-byte transcript had no trailing newline and SHA-256 `424b3807…db67`; the official Unicode indexer mapped it to 226 IDs with packed-ID hash `32fc2695…fc5f1`.

The timing contract kept setup separate, measured one first generation and five additional same-session warm generations, and divided generation time by each output's actual duration. One `OfflineTts` instance was reused, but every timed iteration made an independent generation call without carrying a model cache, state tensor, or output object into the next call.

The only adaptation from the frozen historical Android implementation changed verified input storage to the app's internal files directory for Android 16 scoped-storage compatibility. Runtime, frontend, timing, memory collection, output validation, and WAV writing stayed frozen. See the [route policy](../../../experiments/0021-supertonic-canonical-v2-android-cpu/protocol/benchmark-policy.json), [frontend provenance](../../../experiments/0021-supertonic-canonical-v2-android-cpu/results/frontend-provenance.json), and [build/staging provenance](../../../experiments/0021-supertonic-canonical-v2-android-cpu/results/build-and-stage-provenance.json).

## Progress

1. **August 20, 2026: contract frozen.** The experiment recorded the exact archive, runtime, transcript, voice, device, timing boundaries, thermal gate, state-reset rule, and phone-safety procedure before execution.
2. **August 20, 2026: Android route completed.** Inputs were hash-checked before and after the app-UID copy, setup completed once, and all six requested generations finished. Evidence was pulled with a binary-safe Windows ADB path before app data, package, and staging paths were removed and their absence verified.
3. **August 20, 2026: representative reviewed.** The warm-median run was retained, matched its recorded hash, and Moritz reviewed that exact WAV with the verdict “good.” The acceptance is scoped to this route and this file hash.

The durable final state is recorded in the [experiment README](../../../experiments/0021-supertonic-canonical-v2-android-cpu/README.md), [normalized phone result](../../../experiments/0021-supertonic-canonical-v2-android-cpu/results/phone-cpu-result.json), and [transport and cleanup record](../../../experiments/0021-supertonic-canonical-v2-android-cpu/results/transport-and-cleanup.json). No follow-up action is required for the frozen 0021 route.

## Results

The route completed technically and produced structurally valid audio. Setup took **0.853867 seconds**. The first generation took **6.246927 seconds** for 15.794172 seconds of audio, an RTF of **0.395521**. The five warm RTF values were `0.390631`, `0.391386`, `0.395615`, `0.395708`, and `0.397157`; their median was **0.395615**. These are route-specific results, not a claim about every Supertonic deployment.

| Evidence class | What 0021 established |
|---|---|
| Technical execution | Six complete Android CPU generations ran with the pinned descriptor, engine, model archive, and one-thread configuration. |
| Structural audio | Every output was finite, non-silent, unclipped mono PCM16 at 44.1 kHz, with exactly 696,523 frames. |
| Numerical/acoustic comparison | No reference-signal similarity campaign was part of this route; the committed evidence establishes structure and per-run performance, not general acoustic equivalence. |
| Exact-sample listening | Moritz accepted the retained warm-median WAV (`201f8e79…87df`) as “good” on August 20, 2026. The verdict does not transfer to another WAV or route. |

Peak sampled PSS was **480,366,592 bytes** (458.1 MiB), boundary PSS reached 479,744,000 bytes, and cumulative process VmHWM reached **548,986,880 bytes** (523.6 MiB). The pre-launch thermal gate reported Android status `NONE` at 33.8 °C, with no device tuning.

The historical sherpa harness did not emit an ONNX Runtime provider profile. CPU provenance therefore comes from the pinned `provider=cpu` descriptor and fail-closed engine contract, not an ORT profiling trace. That limitation is explicit in the [source result](../../../experiments/0021-supertonic-canonical-v2-android-cpu/results/phone-cpu-result.json). The retained dashboard copy is available through the audio control above; it is linked rather than duplicated here.
