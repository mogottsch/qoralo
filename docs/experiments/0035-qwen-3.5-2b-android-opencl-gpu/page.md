---
experiment: 0035-qwen-3.5-2b-android-opencl-gpu
status: completed
summary: Qwen3.5-2B completed the canonical Android campaign through provider-proven llama.cpp OpenCL offload on Adreno 740. The route is mixed CPU/OpenCL execution, not GPU-exclusive.
benchmark: android-llm
registry: 0035-qwen35-2b-unsloth-q4km-llamacpp-opencl-adreno
---

# Experiment 0035 — Qwen3.5-2B Android OpenCL GPU offload

## Experiment description

This experiment asks whether the exact Qwen3.5-2B Q4_K_M model used by the CPU route can complete the canonical Android workload through public llama.cpp OpenCL offload on the Galaxy S23 Ultra's Adreno 740. It follows experiment 0030's durable Vulkan provider blocker but is a separately named backend route. Nothing here relabels the failed Vulkan attempts as successful GPU evidence.

The route uses the third-party Unsloth `Qwen3.5-2B-Q4_K_M.gguf`, **1,280,835,840 bytes** with SHA-256 `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`. The Android llama.cpp build is **12,313,808 bytes**, SHA-256 `64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced`, from build 10627 at commit `0a5ac49bce4c42893368585edf3ffb41a38f0108`. It requests `GPUOpenCL0`, 25 GPU layers, no split, and GPU index 0. Thinking is disabled and temperature `-1` reaches the pinned greedy argmax path.

The accepted claim is deliberately **OpenCL GPU offload**, not GPU-exclusive execution. Provider proof requires one server process to select Adreno 740, report the Qualcomm OpenCL driver and Adreno-optimized source kernels, offload all 25/25 model layers, and allocate exact OpenCL model and compute buffers. CPU and CPU_REPACK model buffers and a CPU compute buffer remain; HTTP serving, tokenizer, sampler, scheduling/orchestration, and unsupported operations are CPU-side. The owning [experiment README](../../../experiments/0035-qwen-3.5-2b-android-opencl-gpu/README.md), [route contract](../../../experiments/0035-qwen-3.5-2b-android-opencl-gpu/protocol/experiment-contract.json), and [canonical result](../../../experiments/0035-qwen-3.5-2b-android-opencl-gpu/results/android-opencl-campaign/result.json) bind those boundaries.

## Progress

Two clean builds in independent directories produced byte-identical server artifacts. The executable embeds 170 pinned public OpenCL C source/tool files, dynamically resolves the phone vendor's `libOpenCL.so`, and does not deploy the link-only Khronos ICD loader or proprietary precompiled Adreno kernels.

A fresh one-request smoke proved viability: sysfs identified `Adreno740v2`; the provider reported `OpenCL 3.0 QUALCOMM build: 0676.77.1 Compiler E031.41.03.64`; Adreno-optimized kernels were selected; all 25/25 layers were offloaded; and OpenCL model, KV/recurrent-state, and compute buffers were allocated. The smoke completed a bounded 64-token output and verified cleanup, but remained a one-request milestone rather than canonical benchmark evidence.

A separate fresh server then completed the protocol-v2 campaign: one first short request followed by five loaded-route requests for each of short, medium, and long. One loaded server and slot remained alive. Before every logical request, a separately timed `POST /slots/0?action=erase` succeeded. Every request disabled prompt caching, reported `cache_n == 0`, evaluated the full independently counted prompt with positive prefill time, avoided truncation, ended at EOS, and retained its exact output. No model reload, remap, accelerator recompilation, or prompt/KV reuse occurred between requests. The scoped stage was removed and verified absent. The [69-file checksum manifest](../../../experiments/0035-qwen-3.5-2b-android-opencl-gpu/results/android-opencl-campaign/SHA256SUMS) binds the evidence.

## Results

Setup took **17.113 seconds**, measured from immediately before remote server launch through the first healthy response after provider initialization, vendor OpenCL kernel compilation, model offload, and context readiness. The first short request reached its first token in **2.294 seconds**, processed 174 input tokens at **78.85 input tok/s**, externally decoded at **10.13 output tok/s**, and completed at EOS in **49.268 seconds**.

| Tier | Loaded-route requests | Input / output tokens | Median TTFT | Median prefill | Median external decode | Median total | Median slot erase |
|---|---:|---:|---:|---:|---:|---:|---:|
| short | 5 | 174 / 477 | 2.808 s | 64.66 input tok/s | 9.08 output tok/s | 55.205 s | 0.0137 s |
| medium | 5 | 597 / 575 | 9.186 s | 66.74 input tok/s | 7.93 output tok/s | 81.530 s | 0.0174 s |
| long | 5 | 1,926 / 645 | 22.969 s | 86.10 input tok/s | 8.61 output tok/s | 98.647 s | 0.0179 s |

Peak sampled process PSS was **1,365,059,584 bytes** and process VmHWM was **1,377,951,744 bytes**. Sampling can miss brief peaks and does not isolate vendor-driver or GPU-private allocation. KGSL observations ranged from 220 MHz to 719 MHz and reached 99% sampled busy; those values are operating evidence, not calibrated energy.

The campaign began at thermal status 0 and ended at status 3. Battery temperature rose from 32.5 °C to 42.5 °C while the phone remained USB powered at 91%. Likely thermal throttling is a limitation, and no calibrated external or OS energy measurement was available. Flash Attention is disabled on this route, and the exact operation-by-operation OpenCL/CPU split is unavailable.

The post-prefill-to-first-token split remains null because llama.cpp reports aggregate prefill time but no alignable server-clock first-token timestamp. External decode starts at first generated-token delivery and excludes that first token from its numerator; WSL-to-Windows ADB forwarding remains inside delivery timing. All 16 exact outputs passed the narrow sensible-text corruption check, which is not a correctness, grounding, usefulness, style, or acceptance evaluation.
