---
experiment: 0033-lfm2.5-2.6b-android-loaded-route
status: completed
summary: LFM2.5-2.6B completed separate canonical persistent Android CPU and provider-proven OpenCL campaigns with full slot isolation. The GPU route is mixed offload, not GPU-exclusive.
benchmark: android-llm
registry: 0033-lfm25-26b-liquidai-q4km-llamacpp-cpu, 0033-lfm25-26b-liquidai-q4km-llamacpp-opencl-adreno
---

# Experiment 0033 — LFM2.5-2.6B Android loaded routes

## Experiment description

This experiment supplies the persistent loaded-route evidence that experiment 0029 intentionally did not attempt. Experiment 0029 remains a one-request Android CPU viability smoke through `llama-completion`; it is not relabeled, upgraded, or used as a campaign distribution. Experiment 0033 instead uses one persistent llama-server and one reusable slot for separate canonical CPU and OpenCL/Adreno campaigns.

Both completed arms use LiquidAI's official `LFM2.5-2.6B-Q4_K_M.gguf`, **1,674,455,040 bytes** with SHA-256 `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`. The pinned tokenizer produces 171 short, 600 medium, and 1,922 long input tokens. The native template and reasoning continuation are preserved, including one BOS and the `<think>` generation prefix. Every prompt fits the 8,192-token route context with the fixed 2,048-token output ceiling.

Both arms use llama.cpp build 10627 at commit `0a5ac49bce4c42893368585edf3ffb41a38f0108`. The CPU-only server is **9,844,576 bytes**, SHA-256 `8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217`, with `--device none` and zero GPU layers. The OpenCL server is **12,313,808 bytes**, SHA-256 `64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced`, requesting `GPUOpenCL` and 31 GPU layers. Each arm used its own fresh server, setup boundary, operating evidence, and canonical campaign. The owning [experiment README](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/README.md), [route contract](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/protocol/experiment-contract.json), [CPU result](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/results/android-cpu-campaign/result.json), and [OpenCL result](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/results/android-opencl-campaign/result.json) bind the two routes.

## Progress

Experiment 0029 first established that the exact official artifact could execute one bounded request on Android. Its one-shot executable reloads the model and cannot satisfy loaded-route campaign semantics. That predecessor remains honest viability evidence only.

Experiment 0033 moved to a newer pinned persistent llama-server revision. For each arm, a single loaded server and slot completed one first short request plus five loaded-route requests for each of short, medium, and long. Before every request, a separately timed `POST /slots/0?action=erase` succeeded. Every request disabled prompt caching, reported `cache_n == 0`, evaluated its full prompt with positive prefill time, avoided input truncation, and retained exact output bytes. No model remap/reload, accelerator recompilation, or prompt/KV reuse occurred between requests. The CPU [68-file manifest](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/results/android-cpu-campaign/SHA256SUMS) and OpenCL [69-file manifest](../../../experiments/0033-lfm2.5-2.6b-android-loaded-route/results/android-opencl-campaign/SHA256SUMS) bind the two fresh campaigns.

The OpenCL campaign also proved its provider in the measured server process: sysfs identified `Adreno740v2`; the driver reported Qualcomm OpenCL 3.0 compiler `E031.41.03.64`; public Adreno-optimized kernels were selected; all 31/31 offloadable layers were placed on GPU; and OpenCL model, KV, recurrent-state, and compute buffers were allocated. Exact observed OpenCL sizes were 1,384.03 MiB model, 128.00 MiB KV, 0.34 MiB recurrent state, and 546.01 MiB compute. CPU model and CPU_REPACK buffers of 205.08 MiB each plus a 26.01 MiB CPU compute buffer remained. The accepted claim is therefore mixed **OpenCL GPU offload**, never GPU-exclusive execution.

## Results

The table compares medians from the five loaded-route requests in each tier. The CPU and OpenCL rows are independent campaigns; their outputs and stop lengths can differ because backend-dependent floating-point execution is not required to be byte-identical.

| Backend / tier | Input / output tokens | Stop | Median TTFT | Median prefill | Median external decode | Median total |
|---|---:|---|---:|---:|---:|---:|
| CPU short | 171 / 997 | EOS | 5.821 s | 30.36 input tok/s | 8.75 output tok/s | 118.926 s |
| CPU medium | 600 / 1,672 | EOS | 20.378 s | 30.34 input tok/s | 7.94 output tok/s | 230.932 s |
| CPU long | 1,922 / 2,048 | max tokens | 68.271 s | 29.01 input tok/s | 6.87 output tok/s | 366.145 s |
| OpenCL short | 171 / 1,488 | EOS | 2.888 s | 61.97 input tok/s | 7.98 output tok/s | 189.261 s |
| OpenCL medium | 600 / 2,048 | max tokens | 10.282 s | 60.53 input tok/s | 7.14 output tok/s | 296.002 s |
| OpenCL long | 1,922 / 2,023 | EOS | 31.328 s | 63.65 input tok/s | 7.04 output tok/s | 317.972 s |

CPU setup took **15.806 seconds**; peak sampled process PSS was **3,559,703,552 bytes**, and VmHWM was **3,560,947,712 bytes**. OpenCL setup took **20.764 seconds**; process PSS peaked at **675,495,936 bytes**, and VmHWM at **758,554,624 bytes**. The OpenCL process metrics exclude isolated vendor-driver and GPU-private memory and cannot be treated as total-memory parity with CPU. Sampling can miss brief peaks, and VmHWM is cumulative.

The CPU campaign moved from thermal status 1 to 4 with battery temperature 38.3 °C to 44.7 °C. OpenCL moved from status 1 to 3 and 38.4 °C to 43.8 °C. Likely thermal throttling limits comparison. Both were USB powered; neither has calibrated external or OS energy evidence. OpenCL KGSL observations ranged from 220 to 719 MHz and reached 99% sampled busy, which is operating context rather than power measurement.

All 32 logical requests completed. CPU short/medium and OpenCL short/long ended at EOS. CPU long and OpenCL medium validly reached the exact 2,048-token output ceiling with `max_tokens`; no input was truncated. Post-prefill-to-first-token remains null because llama.cpp exposes no alignable server-clock first-token timestamp. Output sanity only screens exact retained text for obvious corruption or gibberish and is not a quality, correctness, grounding, usefulness, or acceptance judgment.
