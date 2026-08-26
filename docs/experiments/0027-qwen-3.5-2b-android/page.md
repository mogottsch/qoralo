---
experiment: 0027-qwen-3.5-2b-android
status: completed
summary: The project needed a credible Android route for Qwen3.5-2B despite having no official ready-to-run mobile artifact. A pinned third-party Q4_K_M GGUF completed the full CPU campaign, with medium-tier medians of 16.689 seconds TTFT and 8.77 output tokens per second.
benchmark: android-llm
registry: 0027-qwen35-2b-unsloth-q4km-llamacpp-cpu
---

# Experiment 0027 — Qwen3.5-2B on Android CPU

## Experiment description

The project wanted to know whether Qwen3.5-2B could run credibly on the Galaxy S23 Ultra and how its local CPU route behaved under the same fixed prompts used for other Android language models. No official ready-to-run Qwen3.5 Android artifact was available, so the experiment tested the shortest reproducible alternative: a pinned Unsloth Q4_K_M GGUF served by a pinned llama.cpp build.

This is a route-level measurement, not a pure model-family comparison. The deployed GGUF and quantization are third-party work, the runtime is CPU-only, and its conversion tool revision is unpublished. The route used one loaded llama-server with four threads and an 8,192-token context. Before every logical request it erased the reused slot, disabled prompt caching, and required `cache_n == 0`, full prompt evaluation, and positive prefill time. Thinking was disabled and every tier retained its rendered-prompt and token-ID hashes.

The canonical workload kept the exact repository prompt bytes and a 2,048-token output ceiling. Qwen's own tokenizer produced 174 short, 597 medium, and 1,926 long input tokens. The phone was the authorized SM-S918B / SM8550 running Android 16. The owning [experiment README](../../../experiments/0027-qwen-3.5-2b-android/README.md), [route contract](../../../experiments/0027-qwen-3.5-2b-android/protocol/experiment-contract.json), and [canonical result](../../../experiments/0027-qwen-3.5-2b-android/results/android-cpu-campaign/result.json) preserve the exact evidence.

## Progress

The experiment first pinned the official Qwen source revision, the Unsloth deployment artifact, tokenizer and template identities, the llama.cpp runtime, and the Android build. A bounded host run proved only that the route could load and generate; those host timings were kept out of the Android leaderboard.

A 64-token phone smoke then established Android viability on an earlier server artifact. The first full campaign did not become leaderboard evidence: it was interrupted after eight complete requests, before the medium and long requirements and cleanup record were complete. A later artifact-revision-2 startup also timed out before inference because a Windows-hosted ADB forward was polled on WSL localhost. Both attempts remain committed as diagnostics rather than being relabeled.

The build was then made reproducible without an embedded web UI, and the client learned the correct forwarding host from `ADB_SERVER_SOCKET`. The final run used the UI-disabled server artifact, SHA-256 `8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217`, and the Q4_K_M model artifact, SHA-256 `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`.

That fresh campaign completed the required shape: one first short request, followed by five loaded-route requests for each of short, medium, and long. All 16 requests reached EOS, performed full prefill with no retained prompt/KV state, and avoided truncation. The experiment-owned phone stage was verified absent after cleanup. The [59-file checksum manifest](../../../experiments/0027-qwen-3.5-2b-android/results/android-cpu-campaign/SHA256SUMS) binds the retained result, raw events, outputs, operating evidence, and rendered prompts.

## Results

Setup took **2.936 seconds**, measured from immediately before remote server launch through the first successful health response. The first short request reached its first token in **2.619 seconds**, processed the prompt at **73.24 input tok/s**, externally decoded at **12.91 output tok/s**, and completed in **42.817 seconds**.

| Tier | Loaded-route requests | Input tokens | Median TTFT | Median prefill | Median external decode | Median total |
|---|---:|---:|---:|---:|---:|---:|
| short | 5 | 174 | 3.876 s | 49.04 input tok/s | 10.34 output tok/s | 53.406 s |
| medium | 5 | 597 | 16.689 s | 38.72 input tok/s | 8.77 output tok/s | 81.022 s |
| long | 5 | 1,926 | 61.837 s | 33.80 input tok/s | 6.40 output tok/s | 243.575 s |

Peak sampled process PSS was **2,833,463,296 bytes** (about 2,702 MiB), and process VmHWM reached **2,835,431,424 bytes**. Sampling targeted 100 ms across the server lifecycle, so it can miss brief peaks; VmHWM is cumulative process RSS rather than isolated model, KV, or workspace memory.

The external decode metric excludes the first generated token from both its numerator and interval. The post-prefill-to-first-token split is unavailable because llama.cpp did not expose an alignable server-clock first-token timestamp. Request delivery timings include the local WSL-to-Windows ADB forwarding path. No calibrated power or OS energy measurement was available. During the campaign, battery temperature rose from 37.0 °C to 44.3 °C and the thermal status code rose from 0 to 3, so the medians are retained observations rather than thermally normalized values.

Every exact output was marked `looks_sensible: true` with null issue notes. That is only a corruption/gibberish smoke check: it does not establish correctness, grounding, usefulness, style, transcript quality, or acceptance. The result supports this specific third-party Q4_K_M llama.cpp CPU route; it does not establish an official Qwen Android artifact or an architecture-only advantage over routes using other runtimes and quantizations.
