# Experiment 0033: LFM2.5-2.6B Android loaded routes

## Status

**CPU and OpenCL loaded-route artifacts are host-ready. Phone execution waits for experiment 0035 to finish and explicit priority. Neither arm has canonical evidence yet.**

This experiment closes the gap left intentionally by experiment 0029. The earlier experiment contains one bounded CPU viability request through `llama-completion`; it is not a loaded-route campaign and remains immutable. Experiment 0033 uses the same exact official LiquidAI model, tokenizer, template, and canonical workloads but a newer pinned llama.cpp persistent server required for protocol-v2 isolation and the public OpenCL backend.

## Shared model route

- Official model: `LiquidAI/LFM2.5-2.6B-GGUF` revision `84022ce711b28455e8c4fc364ce68c00cf995875`
- Artifact: `LFM2.5-2.6B-Q4_K_M.gguf`, 1,674,455,040 bytes
- SHA-256: `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`
- Native model source revision: `ab00687315bc1298e9d54e9c4b611dde9867ccc2`
- Native template: 5,443 bytes, SHA-256 `ea663864491de7ade391839479860ca95541f892f72665c73251fbd4643b1bef`
- Prompt tokens: short 171, medium 600, long 1,922
- Route context: 8,192; every prompt plus the 2,048 output ceiling fits
- Native reasoning continuation is preserved; every rendered generation prompt must end in `<|im_start|>assistant\n<think>`.

## Persistent runtime

Both arms use llama.cpp commit `0a5ac49bce4c42893368585edf3ffb41a38f0108`, tree `9355e5ebbca69eb403229473bec6ddfb38f055e0`, through one loaded `llama-server` and one reused slot. This differs from 0029's commit `5c0d188…` because the prior executable is one-shot and cannot satisfy protocol-v2 loaded-route reuse; the current revision also supplies the public Adreno OpenCL backend. No 0029 observation is relabeled.

Before every request, the runner separately times `POST /slots/0?action=erase`. Every completion must prove `cache_n == 0`, full prompt evaluation, positive prefill time, no truncation, no model reload, and no retained prompt/KV reuse. The embedded tokenizer's BOS addition remains overridden off because the native template already emits BOS.

## Arm 1: CPU-only

- Server: 9,844,576 bytes, SHA-256 `8ce2767eba7480326682d69963eeb483204ee1541c3b5b0c0ef409068ea2b217`
- Runtime: `--device none --gpu-layers 0`, four inference and batch threads
- Dynamic dependencies: Android `libc.so`, `libdl.so`, and `libm.so`
- Remote root: `/data/local/tmp/vibevoice-0033-lfm2.5-2.6b-android-loaded-route-cpu`

This arm runs first and is a distinct CPU result, never a fallback row.

## Arm 2: OpenCL/Adreno GPU offload

- Server: 12,313,808 bytes, SHA-256 `64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced`
- Runtime: `--device GPUOpenCL --gpu-layers 31 --split-mode none --main-gpu 0`
- Public Khronos headers/loader and 170 embedded OpenCL source/tool files are pinned in the contract
- Proprietary/precompiled binary kernels are disabled
- Remote root: `/data/local/tmp/vibevoice-0033-lfm2.5-2.6b-android-loaded-route-opencl`

GPU evidence requires `Adreno740v2` sysfs identity, the QUALCOMM OpenCL driver, Adreno-optimized source kernels, all 31/31 offloadable layers, and OpenCL model and compute buffers. CPU server/tokenizer/sampler/scheduling and unsupported operations remain in the route, so this is not GPU-exclusive.

## Required sequence

Each arm must start from a separate fresh server and complete its own canonical `1+5+5+5` campaign. Setup, timings, memory, thermal state, output hashes, and distributions are never mixed across arms. CPU runs first; OpenCL runs only after CPU cleanup and handoff. A smoke is at most a milestone and cannot complete either arm.
