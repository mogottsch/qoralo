# Experiment 0027 — Qwen3.5-2B on Android CPU

## Status

**Android CPU smoke passed on historical server artifact revision 1. The first full campaign was interrupted after eight complete requests and is retained only as diagnostic evidence. Reproducible UI-disabled server artifact revision 2 is staged for a fresh canonical campaign after the required scoped stale-stage cleanup.**

This experiment measures the public post-trained `Qwen/Qwen3.5-2B` on the authorized Galaxy S23 Ultra under the repository's fixed short/medium/long LLM workload. It is text-only performance evidence, not a vision test or a podcast-quality evaluation.

The complete machine-readable route is in [`protocol/experiment-contract.json`](protocol/experiment-contract.json).

## Why this route

The official Qwen repository provides Transformers weights, not a ready Android deployment artifact. A fast feasibility check also found no official LiteRT-LM Qwen3.5 route to use: the LiteRT-LM [supported-model table](https://ai.google.dev/edge/litert-lm/overview#supported-models), last updated August 12, 2026, lists Qwen2.5-0.5B, Qwen2.5-1.5B, and Qwen3-0.6B, but not Qwen3.5-2B or Qwen3.5-4B. A recent Qwen3.5 Jinja file in LiteRT-LM testdata proves template parsing, not model architecture/export support, a deployable artifact, or Android execution.

The selected route therefore uses llama.cpp on CPU with a pinned Unsloth Q4_K_M GGUF that already loaded and generated successfully. This was the shortest credible path to a valid Android number, but the tradeoffs stay explicit:

- the deployed GGUF and quantization are third-party Unsloth work, not official Qwen artifacts;
- the exact Unsloth converter/quantizer commit is not published in the pinned repository or GGUF metadata;
- this route is CPU-only;
- runtime and quantization differ from the Gemma experiment, so any cross-family comparison is confounded and must not be described as an architecture-only result.

If official LiteRT-LM Qwen3.5 support and deployment artifacts arrive, they should be measured as a new arm rather than retroactively changing this route.

## Locked route

- Official source model: `Qwen/Qwen3.5-2B@15852e8c16360a2fea060d615a32b45270f8a8fc`, public, ungated, Apache-2.0.
- Deployment artifact: third-party `unsloth/Qwen3.5-2B-GGUF@f6d5376be1edb4d416d56da11e5397a961aca8ae`, file `Qwen3.5-2B-Q4_K_M.gguf`, 1,280,835,840 bytes, SHA-256 `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`.
- Quantization: Q4_K_M with an importance matrix; the GGUF names `unsloth_calibration_Qwen3.5-2B.txt`, 186 entries, and 80 chunks. The separately published matrix has SHA-256 `0661bad5…fbca`.
- Runtime: llama.cpp `0a5ac49bce4c42893368585edf3ffb41a38f0108`, GGML CPU, four threads, one 8,192-token slot.
- Android server artifact revision 2: NDK r28b, arm64-v8a/API 31, `armv8.7-a`, no embedded web UI, 9,844,576 bytes, stripped binary SHA-256 `8ce2767e…b217`.
- Historical server artifact revision 1: 12,969,392 bytes, SHA-256 `4d54e7b0…adbd`; it remains bound only to the committed smoke and interrupted evidence.
- Greedy generation: temperature-only sampler chain with temperature normalized to zero and neutral penalties. The pinned sampler implementation keeps the maximum-logit token when temperature is at most zero.
- Request isolation: reuse one loaded llama-server route and slot/session, separately time a successful slot erase before every request outside total-request timing, set `cache_prompt=false`, require runtime `cache_n=0`, and prohibit model reload/remap, accelerator recompilation, or retained prompt/KV reuse.

## Tokenizer, template, and non-thinking proof

The tokenizer comes from the pinned official Qwen revision and is embedded in the deployed GGUF. The experiment pins the official tokenizer/config/vocabulary hashes and the exact embedded template hash.

The upstream chat template and embedded GGUF template are not byte-identical: the conversion changes only iteration over tool-call argument mappings, an unreachable branch for the canonical system-plus-user workload. Rendered bytes and token IDs are therefore recorded for every tier rather than assuming equivalence.

Thinking is explicitly disabled twice: the server uses `--reasoning off`, and every request supplies `{"enable_thinking": false}` to the model-native template. Each rendered prompt must end with the exact empty block `<think>\n\n</think>\n\n`; a nonempty thinking prefix is fatal.

The host inventory proved that every prompt plus the unchanged 2,048-token output ceiling fits the 8,192-token deployed context:

- short: 174 tokens, rendered SHA-256 `afed1eb6…1371e`, token-ID SHA-256 `dcfd3c24…048f4`;
- medium: 597 tokens, rendered SHA-256 `0559ad81…b42a5`, token-ID SHA-256 `8b07ff28…2c5e2`;
- long: 1,926 tokens, rendered SHA-256 `c48e00cf…01135`, token-ID SHA-256 `a36f8139…785ca`.

## Host viability gate

The exact Q4_K_M artifact loaded through the pinned llama.cpp CPU runtime and generated a bounded 64-token canonical-short response. The output is retained at [`results/host-smoke/outputs/smoke-short-01.txt`](results/host-smoke/outputs/smoke-short-01.txt), SHA-256 `e430570558f4d3e883629820affd9b4dd65b34ab9cffd44ac42c0e7cd22e773f`, and looks like sensible prose under the narrow corruption/gibberish check.

The host observed 93.51 input tokens/s and 22.99 generated tokens/s in the retained persistence-first smoke. These are viability observations only and are not Android evidence.

## First Android result

The bounded 64-token short smoke passed on the exact SM-S918B/SM8550 running Android 16. Setup took 2.247 seconds. The 174-token prompt reached the first generated token in 2.315 seconds; llama.cpp reported 76.12 input tokens/s and 16.41 generated tokens/s. The request completed in 6.163 seconds at the smoke ceiling without truncation or prompt-cache reuse. Peak sampled process PSS was 2,803,700,736 bytes and VmHWM was 2,805,694,464 bytes, with the documented sampling limitations.

The exact sensible-prose output is SHA-256 `0f0d70ee…086c8`. The phone stage was hash-matched and `/data/local/tmp/vibevoice-0027-qwen-3.5-2b-android` was verified absent before the lock was released. This is viability evidence, not the required 1+5+5+5 publication campaign.

## Interrupted full campaign

A fresh full campaign subsequently completed the first short request, all five repeated short requests, and two medium requests. Every one of those eight complete requests proved explicit slot erase, `cache_n == 0`, full prompt evaluation, and positive prefill time. The process was interrupted during `medium-03`, before the medium and long tiers, after-state collection, and cleanup record completed. It is therefore not canonical and must not be published.

The pulled partial result, outputs, events, server log, and memory samples are retained under [`results/android-cpu-campaign-interrupted-20260825/`](results/android-cpu-campaign-interrupted-20260825/). Rerun the complete campaign from the start. Because cleanup could not be verified after interruption, the next phone owner must first inspect only the scoped remote path/process and verify `/data/local/tmp/vibevoice-0027-qwen-3.5-2b-android` is absent before staging.

## Reproducible Android artifact revision 2

[`tools/build_android.sh`](tools/build_android.sh) reconstructs the route from pinned inputs: llama.cpp commit `0a5ac49b…0108` and tree `9355e5eb…5e0`, explicit build number 10627, NDK `28.1.13356709`, and the exact model URL/size/hash above. It uses the repository heavy-RAM lock, prefix-maps checkout/build paths, disables ccache and OpenSSL, statically links llama/GGML plus `c++_static`, and verifies that only Android `libm`, `libdl`, and `libc` remain dynamic.

The new server disables both `LLAMA_BUILD_UI` and `LLAMA_USE_PREBUILT_UI`. The runner always passes `--no-webui`, so embedded UI bytes do not support an inference claim. Removing them prevents llama.cpp's mutable `latest` UI fallback from changing the executable. A bounded attempt to reproduce revision 1 with the August 25 `b10625` UI archive (3,086,917 bytes, SHA-256 `6d7c0ed6…16d70`) did not match: it produced 12,971,760 bytes / `943db6a4…9811d`. No historical evidence was relabeled. Two clean revision-2 builds produced the exact staged hash above.

## Android execution discipline

[`tools/run_phone.sh`](tools/run_phone.sh) holds the repository phone lock across identity checks, scoped staging, execution, raw evidence capture, and verified cleanup. It stages only under `/data/local/tmp/vibevoice-0027-qwen-3.5-2b-android`, verifies the artifact-revision-2 binary and model hashes remotely, uses ADB forwarding to one persistent llama.cpp server with `--no-webui`, and deletes only that experiment-owned root.

[`tools/run_client.py`](tools/run_client.py) writes each SSE event and output chunk durably before deriving optional metrics. Android begins with a bounded short smoke. The publication campaign then uses a fresh loaded server for one first short request followed by five loaded-route requests each for short, medium, and long, always in canonical order. The same slot/session is reused, but a proven full conversation/KV erase is separately timed before every request and excluded from total-request timing.

Missing internal splits or optional operating telemetry remain null with reasons; wrong identity, truncation, thinking, sampler, reset, workload, or artifact state fails closed without discarding captured evidence.

## Claim boundaries

- A host result is not Android performance evidence.
- Q4_K_M is a third-party quantized route and must not be called an official Qwen Android artifact.
- CPU process PSS/VmHWM does not isolate model mappings, KV state, or individual runtime workspaces.
- The superficial sensible-text check is not quality, correctness, grounding, transcript usefulness, or acceptance.
- The separate Qwen3.5-4B experiment must retain its own artifacts, phone evidence, outputs, and publication handoff.
