---
experiment: 0033-lfm2.5-2.6b-android-loaded-route
status: active
summary: LFM2.5-2.6B completed its canonical persistent Android CPU campaign with proven slot isolation. The separate OpenCL GPU arm remains active and pending.
benchmark: android-llm
registry: 0033-lfm25-26b-liquidai-q4km-llamacpp-cpu
---

# Experiment 0033 — LFM2.5-2.6B Android loaded routes

## Experiment description

This experiment supplies the persistent loaded-route evidence that experiment 0029 intentionally did not attempt. Experiment 0029 remains a one-request Android CPU viability smoke through `llama-completion`; it is not relabeled, upgraded, or used as a campaign distribution. Experiment 0033 instead uses one persistent llama-server and one reusable slot for separate canonical CPU and OpenCL/Adreno arms.

Both arms use LiquidAI's official `LFM2.5-2.6B-Q4_K_M.gguf`, **1,674,455,040 bytes** with SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`. The pinned tokenizer produces 171 short, 600 medium, and 1,922 long input tokens. The native template and reasoning continuation are preserved, including one BOS and the `<think>` generation prefix. Every prompt fits the 8,192-token route context with the fixed 2,048-token output ceiling.

The completed CPU arm uses llama.cpp build 10627 at commit `0a5ac49bce4c42893368585edf3ffb41a38f0108`, four inference and batch threads, `--device none`, and `--gpu-layers 0`. Its server is **9,844,576 bytes**, SHA-256 `8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217`. Before every request the runner separately times a full slot erase, disables prompt caching, and requires `cache_n == 0`, the full independently counted prompt, positive prefill, and no truncation. The owning [experiment README](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/README.md), [route contract](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/protocol/experiment-contract.json), and [CPU result](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/results/android-cpu-campaign/result.json) bind the claim.

## Progress

Experiment 0029 first established that the exact official artifact could execute one bounded request on Android. Its one-shot executable necessarily reloads the model, exposes neither the protocol setup boundary nor caller-observed TTFT, and cannot satisfy loaded-route campaign semantics. That active predecessor remains honest viability evidence only.

Experiment 0033 moved to a newer pinned persistent llama-server revision. The CPU-only server was independently bound and launched on the authorized Galaxy S23 Ultra with no accelerator device and zero GPU layers. A single loaded server and slot then completed one first short request plus five loaded-route requests for each of short, medium, and long.

All 16 requests successfully erased the slot before execution, excluded reset time from request totals, reported zero cached prompt tokens, evaluated each full prompt with positive prefill time, and retained exact output bytes. No model remap/reload, accelerator recompilation, or prompt/KV reuse occurred between requests. Short and medium requests ended at EOS. Every long request validly reached the exact 2,048-token output ceiling with `max_tokens`; no input was truncated, so this is a valid protocol stop rather than a failed request. Cleanup verified the scoped remote root absent. The [68-file checksum manifest](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/results/android-cpu-campaign/SHA256SUMS) binds the campaign.

The second arm remains active and pending. It will use a separately launched OpenCL server and must independently prove the Qualcomm driver, `Adreno740v2`, Adreno-optimized source kernels, all 31/31 offloadable layers, exact OpenCL buffers, request isolation, and its own fresh canonical campaign. No GPU row or result is implied by the completed CPU work.

## Results

CPU setup took **15.806 seconds**, from immediately before remote server launch through the first healthy response after model and context readiness. The first short request reached its first token in **3.400 seconds**, processed 171 input tokens at **52.12 input tok/s**, externally decoded at **11.33 output tok/s**, and completed at EOS in **91.329 seconds**.

| Tier | Loaded-route requests | Input / output tokens | Stop | Median TTFT | Median prefill | Median external decode | Median total |
|---|---:|---:|---|---:|---:|---:|---:|
| short | 5 | 171 / 997 | EOS | 5.821 s | 30.36 input tok/s | 8.75 output tok/s | 118.926 s |
| medium | 5 | 600 / 1,672 | EOS | 20.378 s | 30.34 input tok/s | 7.94 output tok/s | 230.932 s |
| long | 5 | 1,922 / 2,048 | max tokens | 68.271 s | 29.01 input tok/s | 6.87 output tok/s | 366.145 s |

Peak sampled process PSS was **3,559,703,552 bytes** and process VmHWM was **3,560,947,712 bytes**. Sampling began just after process launch, can miss brief peaks, and does not isolate model or KV memory. VmHWM is a cumulative process-lifetime high-water mark.

Operating conditions materially limit comparisons. Thermal status moved from 1 to 4 and battery temperature rose from 38.3 °C to 44.7 °C; sustained throttling likely affected later requests. The phone was USB powered, but no calibrated external or OS energy measurement was available.

The post-prefill-to-first-token split remains null because llama.cpp reports aggregate prompt time without an alignable server-clock first-token timestamp. External decode excludes the first generated token and includes the WSL-to-Windows ADB delivery boundary. All 16 outputs passed only the narrow exact-hash sensible-text corruption check, not a quality, correctness, grounding, usefulness, or acceptance evaluation.

This normalized row establishes the canonical persistent **CPU-only** route. The experiment page remains active until its independently evidenced OpenCL arm completes or is explicitly stopped; that arm currently has no leaderboard row.
