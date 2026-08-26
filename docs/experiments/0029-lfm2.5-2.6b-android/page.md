---
experiment: 0029-lfm2.5-2.6b-android
status: active
summary: The official LFM2.5-2.6B Q4_K_M route has now executed one bounded request on the Galaxy S23 Ultra. This proves Android CPU viability, but a persistent loaded-route runner and the canonical 1+5+5+5 campaign are still future work.
benchmark: android-llm
---

# Experiment 0029 — LFM2.5-2.6B on Android

## Experiment description

The project needed to know whether the official LFM2.5-2.6B GGUF could execute at all on the target Android phone before investing in a full benchmark runner. This experiment therefore started with a deliberately narrow question: can a pinned, bounded llama.cpp CPU route load the exact model, consume the canonical short prompt without truncation or a duplicate BOS token, and return one retained continuation on the Galaxy S23 Ultra?

The route uses LiquidAI's official `LFM2.5-2.6B-Q4_K_M.gguf`, pinned at 1,674,455,040 bytes and SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`. Its model-native template intentionally continues from `<think>`; this is not treated as equivalent to Qwen's non-thinking route. The runtime is llama.cpp build 7446 on GGML CPU with four inference and four batch threads. The stripped Android `llama-completion` binary is 5,074,184 bytes with SHA-256 `88a91aba5511a712f45aca21c566275681de30e2161f10bb99f9ac54f45b979e`.

This binary is suitable only for one bounded viability request. Each process loads the model, so looping it would violate the protocol-v2 requirement to retain one loaded model/runtime route across the canonical campaign. The owning [experiment README](../../../experiments/0029-lfm2.5-2.6b-android/README.md), [route contract](../../../experiments/0029-lfm2.5-2.6b-android/protocol/experiment-contract.json), and [Android smoke result](../../../experiments/0029-lfm2.5-2.6b-android/results/android-smoke/result.json) define that evidence boundary.

## Progress

The experiment first pinned the official model and GGUF revisions, LFM Open License, Q4_K_M tensor inventory, tokenizer files, byte-identical embedded/native template, and rendered prompt and token-ID hashes for all three canonical tiers. The official repository does not disclose an exact converter/quantizer commit or calibration provenance, so those values remain unavailable rather than inferred.

A bounded host smoke and a clean reconstruction proved local feasibility and reproduced the exact host output. Those host observations remain separate from Android evidence. The project then built and hash-bound an AArch64 `llama-completion` executable with NDK r28b and only Android system library dependencies.

Before the successful phone request, a passive cooldown observation retained the actual warm conditions. The first staged attempt then stopped before inference when the Windows-hosted ADB transport disappeared during required remote hash verification. That [pre-inference transport diagnostic](../../../experiments/0029-lfm2.5-2.6b-android/results/android-smoke-pre-inference-transport-failure/result.json) is not counted as a smoke; its scoped stage was subsequently removed and verified absent.

A fresh authorized retry matched the model, binary, and prompt hashes locally and remotely, ran one bounded canonical-short-derived request, exited zero, and retained the raw output and operating evidence. Cleanup again verified the experiment-owned remote root absent, with no experiment process remaining. The [Android smoke checksum manifest](../../../experiments/0029-lfm2.5-2.6b-android/results/android-smoke/SHA256SUMS) binds the successful evidence, while the separate [cooldown manifest](../../../experiments/0029-lfm2.5-2.6b-android/results/android-smoke-cooldown/SHA256SUMS) preserves its context.

## Results

The authorized phone completed exactly one Android CPU viability smoke. The short prompt contained **171 input tokens**, matched rendered-prompt SHA-256 `9e6c713e83f0987f283264b789e102b9704d6067665fc7a0fee652938a3ae622`, was not truncated, and did not receive a second BOS token. Greedy generation reached the bounded **64-token** ceiling and stopped with `max_tokens`.

The retained output is **324 bytes**, SHA-256 `75f52326f67379c63d86b49e4520a074dbbd074329fc0d8d53693340ffc0a0c5`. Its sanity record is `looks_sensible: true` with null issue notes. That observation only excludes obvious corruption or gibberish; it does not establish correctness, grounding, usefulness, transcript quality, or acceptance.

| Runtime observation | Retained value |
|---|---:|
| Prompt evaluation | 13.56415 s |
| Prompt evaluation throughput | 12.61 input tok/s |
| Follow-on model evaluations | 63 runs in 7.13287 s |
| Runtime-reported follow-on rate | 8.83 runs/s |
| Total runtime-reported work | 20.70975 s |
| Peak sampled PSS | 1,870,697 KiB / 1,915,593,728 bytes |
| Process VmHWM | 1,873,176 KiB / 1,918,132,224 bytes |

These runtime internals are not a complete protocol timing record. **Protocol setup is unavailable** because the one-shot executable exposes no readiness boundary separate from its request, and its reported load time overlaps prompt evaluation. **Protocol TTFT is unavailable** because the non-streaming executable provides no caller-observed first-token delivery timestamp. The 63 follow-on evaluations are runtime-internal eval work, not relabeled as protocol decode delivery timing. No missing value is treated as zero or derived from an unrelated clock.

The phone began warm at thermal status 2, AP 47.6 °C, and skin 41.4 °C. It ended at status 2, AP 60.5 °C, and skin 42.5 °C. Battery remained at 95% while USB powered. No external or authoritative device power meter was available. PSS sampling ran approximately every 100–260 ms and may miss brief peaks; mapped model bytes are included.

This page establishes Android CPU viability only. It adds **no leaderboard row** and supports no distribution or cross-route performance ranking. The next technical step is a separately bound persistent loaded-route runner with a proven full in-session reset or fresh-Session strategy, followed by a newly authorized canonical one-first-plus-five-short/five-medium/five-long campaign.
