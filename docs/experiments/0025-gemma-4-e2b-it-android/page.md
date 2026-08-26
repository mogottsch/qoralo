---
experiment: 0025-gemma-4-e2b-it-android
status: completed
summary: The official Gemma 4 E2B IT generic LiteRT-LM artifact completed distinct canonical Android CPU and provider-proven GPU campaigns. Both retain one loaded Engine and use fresh-Session isolation.
benchmark: android-llm
registry: 0025-gemma-4-e2b-it-litert-lm-cpu, 0025-gemma-4-e2b-it-litert-lm-generic-gpu
---

# Experiment 0025 — Gemma 4 E2B IT on Android

## Experiment description

The project wanted trustworthy CPU and GPU measurements for an official Gemma mobile deployment on the Galaxy S23 Ultra without mistaking cached prompt work or a fallback route for real performance. The final experiment therefore answers two linked questions: can the official Gemma 4 E2B IT LiteRT-LM artifact complete the fixed Android campaign on each neural backend, and can every repeated request be isolated while the expensive model and Engine remain loaded?

Following an explicitly approved route amendment, both published arms use the official generic `gemma-4-E2B-it.litertlm` artifact: **2,588,147,712 bytes**, SHA-256 `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`. The CPU arm uses four threads. The GPU arm requests `Backend::GPU`, with `kGpu` as the only LiteRT hardware accelerator bit and no CPU fallback bit. Both use LiteRT-LM v0.16.1, an 8,192-token route capacity, thinking disabled, and the runtime's exact greedy-equivalent CPU `TOP_P(k=1)` sampler. The embedded tokenizer produces 171 short, 595 medium, and 1,930 long input tokens, all fitting with the unchanged 2,048-token output ceiling.

Each arm retains one loaded Engine, destroys the prior Session, and creates a fresh Session before every later logical request. Session creation is measured separately and excluded from TTFT, prefill, decode, and total-request timing. The owning [experiment README](../../../experiments/0025-gemma-4-e2b-it-android/README.md), [route contract](../../../experiments/0025-gemma-4-e2b-it-android/protocol/experiment-contract.json), [canonical CPU result](../../../experiments/0025-gemma-4-e2b-it-android/results/android-cpu-campaign/result.json), and [canonical GPU result](../../../experiments/0025-gemma-4-e2b-it-android/results/android-gpu-campaign/result.json) preserve the exact route and claim boundaries.

## Progress

The experiment first pinned the model, deployment, tokenizer/template, runtime, runner, libraries, workload hashes, and authorized SM-S918B device. Host and 64-token phone smokes established bounded viability only; neither is used as a canonical campaign distribution.

The first 16-request CPU attempt exposed a critical reset problem. `RewindToStep(0)` retained reusable prompt/KV state and produced impossible repeated-prompt prefill rates. The diagnostic was rejected. Bounded probes showed that retaining one Engine while creating a fresh Session restores full prompt work, and Moritz approved that protocol-v2 isolation strategy. The final CPU campaign then completed one first short plus five loaded-route requests per tier. All 16 requests used the correct input counts, ended at EOS, retained exact output bytes, and passed the narrow sensible-text check. Its [42-file manifest](../../../experiments/0025-gemma-4-e2b-it-android/results/android-cpu-campaign/SHA256SUMS) binds the evidence.

The original dedicated `gemma-4-E2B-it-gpu.litertlm` Artisan artifact was assessed first. LiteRT-LM switched the request to `GPU_ARTISAN` but the pinned open-source runtime lacked the required legacy TFLite engine, so execution stopped before inference. No request ran, no provider bound, and no metric was published. That durable [Artisan blocker](../../../experiments/0025-gemma-4-e2b-it-android/results/android-gpu-blocker/result.json) remains historical rather than being overwritten by the amended route.

Moritz then approved the official generic artifact with `Backend::GPU`. A provider-bound one-request smoke established viability only. The first canonical launch attempt stopped before any request because its configured cache directory did not exist; the [missing-cache diagnostic](../../../experiments/0025-gemma-4-e2b-it-android/results/android-gpu-missing-cache-diagnostic/result.json) is non-counted. A completely fresh succeeding campaign write-probed the cache and completed the canonical 1+5+5+5 shape. From that campaign process, provider binding is proven by the GPU-only/no-fallback accelerator mask, fully delegated single-delegate hint, mapped `libLiteRtGpuAccelerator.so` and Qualcomm/Adreno OpenCL/GLES libraries, and open `/dev/kgsl-3d0`. All 16 requests ended at EOS with exact retained outputs and fresh-Session isolation. Its [47-file manifest](../../../experiments/0025-gemma-4-e2b-it-android/results/android-gpu-campaign/SHA256SUMS) binds the result.

## Results

The table compares medians from the five loaded-route requests in each tier. CPU and GPU are distinct normalized rows even though they share the same official generic artifact.

| Backend / tier | Input / output tokens | Median TTFT | Median prefill | Median decode | Median total | Median Session recreation |
|---|---:|---:|---:|---:|---:|---:|
| CPU short | 171 / 421 | 3.044 s | 58.33 input tok/s | 10.57 output tok/s | 42.822 s | 0.201 ms |
| CPU medium | 595 / 700 | 7.560 s | 80.08 input tok/s | 10.28 output tok/s | 75.569 s | 0.342 ms |
| CPU long | 1,930 / 756 | 28.663 s | 67.65 input tok/s | 8.65 output tok/s | 115.812 s | 0.278 ms |
| GPU short | 171 / 392 | 0.649 s | 320.90 input tok/s | 12.32 output tok/s | 32.378 s | 0.146 ms |
| GPU medium | 595 / 640 | 1.339 s | 485.17 input tok/s | 13.16 output tok/s | 50.804 s | 0.197 ms |
| GPU long | 1,930 / 756 | 2.076 s | 981.43 input tok/s | 16.30 output tok/s | 48.311 s | 0.179 ms |

CPU setup took **6.474 seconds**; peak sampled process PSS was **5,726,960,640 bytes**, and VmHWM/`ru_maxrss` reached **5,887,778,816 bytes**. GPU setup took **10.520 seconds**; peak sampled process PSS was **1,003,954,176 bytes**, and VmHWM/`ru_maxrss` reached **1,016,340,480 bytes**. Process PSS/VmHWM does not independently measure private GPU memory. The 100 ms PSS sampler can miss brief peaks, while VmHWM and `ru_maxrss` are cumulative process high-water marks.

Operating conditions limit direct interpretation. The CPU campaign began warm at 45.4 °C AP / 39.7 °C skin and ended at Android thermal status 3, 51.7 °C AP / 45.0 °C skin. The GPU campaign began at status 0, 44.0 °C AP / 38.1 °C skin and ended at status 3, 50.1 °C AP / 44.5 °C skin. Likely sustained thermal throttling is therefore explicit. Both runs were USB powered, and neither has calibrated external power evidence.

All 32 canonical outputs across the two arms record `looks_sensible: true` with null issue notes. This only checks exact retained text for obvious corruption or gibberish; it is not a judgment of correctness, grounding, usefulness, transcript quality, or acceptance. The two rows establish the official generic LiteRT-LM artifact on distinct CPU and provider-proven GPU execution backends. They make no NPU or HTP claim.
