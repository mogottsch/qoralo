# Experiment 0035: Qwen3.5-2B Android OpenCL GPU offload

## Status

**Complete canonical OpenCL/Adreno GPU-offload campaign.**

This route follows the durable Adreno Vulkan provider blocker in experiment 0030. It is a separately named OpenCL route and never relabels Vulkan evidence. The model, quantization, tokenizer, template, llama.cpp revision, and canonical workloads remain unchanged from 0027/0030.

## Locked route

- Route: `qwen35-2b-unsloth-q4km-llamacpp-opencl-adreno`
- Model: `Qwen3.5-2B-Q4_K_M.gguf`, 1,280,835,840 bytes, SHA-256 `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`
- llama.cpp: commit `0a5ac49bce4c42893368585edf3ffb41a38f0108`, tree `9355e5ebbca69eb403229473bec6ddfb38f055e0`
- OpenCL headers: Khronos commit `6fe718c31a45fe25151362a72ef041c3a1047cbd`, tree `185dae17ab1e5bf078e50a42a2f851ae868465d0`
- Link-only OpenCL ICD loader: Khronos commit `b7bd2803acc779c03d96588e9ca9e9568a18698a`, tree `992f5bd721d4460224aa2a3d3885ddc1ac72b3c9`
- Embedded kernel manifest: 170 source/tool files, SHA-256 `db17a882fcc799e394bc83fedba5f2979e011b132a1441bb6a4e0383e8902b7e`
- Android server: 12,313,808 bytes, SHA-256 `64409e6e96a7d003ed6c68ec12363f3e6d7c34d46af40bc439cb84f060cd4ced`
- Runtime request: `--device GPUOpenCL0 --gpu-layers 25 --split-mode none --main-gpu 0`

Two clean builds in independent directories produced identical stripped server bytes. The executable embeds public OpenCL C sources and dynamically resolves the phone vendor's `libOpenCL.so`; the public Khronos ICD loader is used only to link and is never deployed. Proprietary/precompiled Adreno binary kernels are disabled.

## Claim boundary

A linked OpenCL backend is not GPU evidence. A device run must prove in one server log:

1. an OpenCL platform was selected;
2. the selected/default device identifies Adreno 740;
3. all 25/25 model layers were offloaded;
4. an OpenCL model buffer exists;
5. an OpenCL compute buffer exists;
6. no ignored GPU option, unsupported device, OpenCL build failure, or CPU-only fallback is present.

A passing route is described as **OpenCL GPU offload**, not GPU-exclusive execution. CPU remains responsible for HTTP serving, tokenizer, sampler, scheduling/orchestration, and operations unsupported by the OpenCL backend. The exact individual-operation split is a limitation rather than an inferred claim.

## Provider-bound smoke

A fresh one-request smoke proved the public route on the authorized phone:

- sysfs GPU model: `Adreno740v2`;
- OpenCL driver: `OpenCL 3.0 QUALCOMM build: 0676.77.1 Compiler E031.41.03.64`;
- all `25/25` layers reported offloaded;
- OpenCL model buffer: 813.29 MiB;
- OpenCL KV/recurrent-state buffers: 96.00 / 19.27 MiB;
- OpenCL compute buffer: 166.01 MiB;
- CPU and CPU_REPACK model buffers: 397.85 MiB each; CPU compute buffer: 26.01 MiB;
- 64-token bounded output completed at `max_tokens`, passed the narrow sensible-text check, and cleanup was verified absent.

The CPU buffers and disabled Flash Attention are explicit mixed-execution boundaries. This is not a GPU-exclusive route. Exact smoke evidence is under [`results/android-opencl-smoke/`](results/android-opencl-smoke/).

The smoke was only a milestone. A separate fresh server subsequently completed the full canonical protocol-v2 campaign: one first short, five warm short, five warm medium, and five warm long. All 16 requests reached EOS with successful slot erasure, `cache_n == 0`, full prompt evaluation, positive prefill time, and no truncation.

Canonical evidence is under [`results/android-opencl-campaign/`](results/android-opencl-campaign/). Setup was 17.113 s. Warm median TTFT / prefill / external decode / total were 2.808 s / 64.66 input tok/s / 9.08 output tok/s / 55.205 s for short; 9.186 s / 66.74 / 7.93 / 81.530 s for medium; and 22.969 s / 86.10 / 8.61 / 98.647 s for long. Peak sampled process PSS was 1,365,059,584 bytes. KGSL reached 719 MHz and 99% sampled busy; battery temperature rose from 32.5 °C to 42.5 °C and thermal status from 0 to 3. These conditions and mixed CPU/OpenCL buffers remain explicit rather than normalized away.

Phone operations are restricted to `/data/local/tmp/vibevoice-0035-qwen-3.5-2b-android-opencl-gpu` under `artifacts/locks/phone.lock` continuously through identity, staging, execution, raw capture, and verified cleanup.
