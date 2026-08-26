# Qwen3.5-2B Adreno Vulkan provider diagnostics

## Status

**Blocked/stopped before inference. These are zero-request, non-counted provider diagnostics, not viability smoke results and not Android performance evidence.**

Three fresh, scoped attempts used the same pinned Qwen3.5-2B Q4_K_M bytes, llama.cpp revision, Vulkan0 request, and 25-layer offload request. Every attempt failed during Adreno Vulkan compute-pipeline creation before health, model readiness, prompt rendering, tokenization, or a logical inference request.

## Controlled matrix

| Variant | Server SHA-256 | One changed variable | Observation |
|---|---|---|---|
| `baseline-ndk-glslc` | `b806fc03…8c00` | Baseline pinned NDK shader compiler | `mul_mat_vec_q5_k_f32_f32` pipeline rejected with `ErrorUnknown` |
| `baseline-disable-f16` | `b806fc03…8c00` | Runtime `GGML_VK_DISABLE_F16=1` only | Same pipeline and error |
| `newer-ubuntu-glslc` | `b666bd38…7ce0` | Pinned public Ubuntu glslc/shaderc 2023.8 only | Same pipeline and error |

Both server artifacts were reproduced byte-for-byte in two clean build directories. Local and remote stage hashes matched in every attempt. The first attempt captured a fixed 180-second cooldown without a thermal threshold gate; the later attempts followed long provider/build idle intervals and captured actual conditions without adding indefinite gating. Exact battery and thermal observations are in each `variant.json` and raw dumps.

The process error was identical:

```text
ggml_vulkan: Compute pipeline creation failed for mul_mat_vec_q5_k_f32_f32
ggml_vulkan: vk::Device::createComputePipeline: ErrorUnknown
libc++abi: terminating due to uncaught exception of type vk::SystemError: vk::Device::createComputePipeline: ErrorUnknown
```

Because initialization never completed, none of the required publication proofs exist: no 25/25 layer-offload line, no Vulkan model buffer, no Vulkan compute buffer, and no output. A canonical `1+5+5+5` campaign was therefore neither started nor counted.

## Cleanup and boundary

Each attempt held `artifacts/locks/phone.lock` continuously through identity, staging, failure capture, and cleanup. Only `/data/local/tmp/vibevoice-0030-qwen-3.5-2b-android-vulkan-gpu` was used. Every attempt records `cleanup_state: verified_absent`; the lock was released and no server process remained.

The retained GitHub API response for llama.cpp issue `#19746` documents the same Adreno 740 class of shader/pipeline failure and reports OpenCL working on that device. It is contextual upstream evidence, not proof that OpenCL supports this exact Qwen3.5 route. Per scope, no model, quantization, or workload was changed and no alternative backend was silently relabeled Vulkan. A separately named, pinned OpenCL route is only a proposal pending Pi/user coordination.
