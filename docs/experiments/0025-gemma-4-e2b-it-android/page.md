---
experiment: 0025-gemma-4-e2b-it-android
status: completed
summary: The project needed a trustworthy Android baseline for the official Gemma 4 E2B mobile package. After rejecting a reset method that silently reused prompt state, the CPU route completed the full campaign with a loaded Engine and fresh Session isolation.
benchmark: android-llm
registry: 0025-gemma-4-e2b-it-litert-lm-cpu
---

# Experiment 0025 — Gemma 4 E2B IT on Android

## Experiment description

The project wanted to measure an official Gemma mobile deployment on the Galaxy S23 Ultra without mistaking cached prompt work for real performance. The experiment therefore asked two linked questions: could the official Gemma 4 E2B IT LiteRT-LM CPU route complete the fixed Android workload, and could every repeated request be isolated while the expensive model and Engine remained loaded?

The published arm uses the official `gemma-4-E2B-it.litertlm` CPU artifact, LiteRT-LM v0.16.1, four CPU threads, an 8,192-token route capacity, thinking disabled, and an exact greedy-equivalent `TOP_P(k=1)` sampler. Gemma's embedded tokenizer produced 171 short, 595 medium, and 1,930 long input tokens. Every prompt still fit with the unchanged 2,048-token output ceiling.

Isolation matters for this result. The route retained one loaded Engine, but destroyed the prior Session and created a fresh Session before every later logical request. Session creation was measured separately and excluded from TTFT, prefill, decode, and total-request timing. The owning [experiment README](../../../experiments/0025-gemma-4-e2b-it-android/README.md), [route contract](../../../experiments/0025-gemma-4-e2b-it-android/protocol/experiment-contract.json), and [canonical CPU result](../../../experiments/0025-gemma-4-e2b-it-android/results/android-cpu-campaign/result.json) preserve the exact route and claim boundaries.

## Progress

The experiment first pinned the official base and deployment revisions, CPU and GPU artifact identities, tokenizer and template hashes, LiteRT-LM runtime, Android runner and libraries, workload hashes, and the authorized SM-S918B device. A bounded host smoke proved only that the CPU package could load and generate. A later 64-token phone smoke established Android CPU viability, but neither smoke was a canonical leaderboard campaign.

The first 16-request CPU attempt exposed a critical reset problem. `RewindToStep(0)` reset the logical step while retaining reusable prompt/KV state, causing repeated prompts to report microsecond prefill and impossible multi-million-token-per-second rates. That complete run remains a diagnostic and was not published as performance evidence.

Two bounded host probes separated the reset choices. Rewinding one Session reproduced prefix reuse, while retaining the Engine and creating a fresh Session forced full prefill again. Moritz approved that narrower protocol-v2 isolation strategy. The runner was rebuilt and hash-bound so every later request measures fresh-Session creation separately without remapping the model or recompiling the route.

The final CPU campaign then completed one first short request plus five loaded-Engine requests for each of short, medium, and long. All 16 requests used the correct input counts, completed at EOS, retained their exact raw outputs, and passed the narrow sensible-text check. The scoped remote stage was removed and verified absent. The [42-file checksum manifest](../../../experiments/0025-gemma-4-e2b-it-android/results/android-cpu-campaign/SHA256SUMS) binds the retained campaign evidence.

## Results

Setup took **6.474 seconds**, from before model assets were created through one Engine and the initial Session being ready with its KV capacity. The first short request reached its first token in **6.452 seconds**, processed 171 input tokens at **59.76 input tok/s**, decoded at **13.01 output tok/s**, and completed in **38.741 seconds**.

| Tier | Loaded-route requests | Input / output tokens | Median TTFT | Median prefill | Median decode | Median total | Median Session recreation |
|---|---:|---:|---:|---:|---:|---:|---:|
| short | 5 | 171 / 421 | 3.044 s | 58.33 input tok/s | 10.57 output tok/s | 42.822 s | 0.201 ms |
| medium | 5 | 595 / 700 | 7.560 s | 80.08 input tok/s | 10.28 output tok/s | 75.569 s | 0.342 ms |
| long | 5 | 1,930 / 756 | 28.663 s | 67.65 input tok/s | 8.65 output tok/s | 115.812 s | 0.278 ms |

Peak sampled process PSS was **5,726,960,640 bytes** (about 5,461 MiB). Process VmHWM and `ru_maxrss` reached **5,887,778,816 bytes**. PSS was sampled every 100 ms and can miss brief peaks; VmHWM and `ru_maxrss` are cumulative process high-water marks rather than isolated model or KV memory.

The operating conditions materially limit comparison. The phone began warm at 45.4 °C AP and 39.7 °C skin, then ended at Android thermal status 3 with 51.7 °C AP and 45.0 °C skin. Sustained thermal throttling likely affected later observations, so these are the measured campaign values rather than thermally normalized model constants. The phone was USB powered, but no calibrated external power measurement was collected.

All 16 exact outputs recorded `looks_sensible: true` with null issue notes. This only checks for obvious corruption or gibberish; it is not a judgment of correctness, grounding, usefulness, transcript quality, or acceptance. The result establishes the official CPU artifact on this LiteRT-LM route. The distinct official GPU artifact was not run and has no published row.
