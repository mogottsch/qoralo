# Experiment 0035: Qwen3.5-2B Android OpenCL GPU offload

## Status

**Reproducible public OpenCL artifact is phone-ready; Android GPU inference is not claimed until the provider-bound smoke succeeds.**

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

## Execution plan

The smallest bounded smoke must first prove provider identity, buffers, full layer offload, and one coherent output. It does not complete the experiment. After scoped cleanup, a separate fresh server must execute the complete canonical protocol-v2 campaign: one first short request, five warm short, five warm medium, and five warm long, with full slot erasure before each logical request and no model reload or retained prompt/KV reuse.

Phone operations are restricted to `/data/local/tmp/vibevoice-0035-qwen-3.5-2b-android-opencl-gpu` under `artifacts/locks/phone.lock` continuously through identity, staging, execution, raw capture, and verified cleanup.
