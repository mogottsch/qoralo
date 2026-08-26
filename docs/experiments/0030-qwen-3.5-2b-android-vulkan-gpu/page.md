---
experiment: 0030-qwen-3.5-2b-android-vulkan-gpu
status: blocked
summary: The Qwen3.5-2B Vulkan arm is blocked before inference because three controlled builds reach the same Adreno compute-pipeline failure. Zero logical requests ran and no GPU performance claim exists.
benchmark: android-llm
---

# Experiment 0030 — Qwen3.5-2B Android Vulkan GPU offload

## Experiment description

This experiment asks whether the Qwen3.5-2B Q4_K_M model already proven on Android CPU can execute through a reproducible public llama.cpp Vulkan route on the Galaxy S23 Ultra's Adreno 740. It is a separate backend assessment and does not modify or relabel experiment 0027's CPU evidence. The intended end-to-end result was real Vulkan offload proof, a bounded viability request, one loaded server route with proven slot reset, and the canonical one-first-plus-five-short/five-medium/five-long campaign.

The route pins the same third-party Unsloth `Qwen3.5-2B-Q4_K_M.gguf`: **1,280,835,840 bytes**, SHA-256 `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`. It uses llama.cpp build 10627 at commit `0a5ac49bce4c42893368585edf3ffb41a38f0108`, an Android NDK r28b build with Vulkan enabled, and requests `Vulkan0`, 25 GPU layers, no split, and GPU index 0.

A valid result had to fail closed unless the same server process proved Adreno 740 initialization, all 25/25 offloadable layers moved to GPU, both Vulkan model and compute buffers, and no ignored-option or initialization-failure evidence. Even with that proof, the accepted claim would have been **Vulkan GPU offload**, not GPU-exclusive execution: server, tokenizer, sampler, orchestration, and unsupported operations can remain CPU-side. The owning [experiment README](../../../experiments/0030-qwen-3.5-2b-android-vulkan-gpu/README.md), [route contract](../../../experiments/0030-qwen-3.5-2b-android-vulkan-gpu/protocol/experiment-contract.json), and [provider diagnostic](../../../experiments/0030-qwen-3.5-2b-android-vulkan-gpu/results/vulkan-provider-diagnostics/result.json) bind those boundaries.

## Progress

The baseline Android server was reproduced byte-for-byte in two clean build directories at 34,242,152 bytes and SHA-256 `b806fc03df6510eb7a141aea093cec7a878a2aa7456ea076a84791fadec68c00`. Its generated SPIR-V used the pinned NDK shader compiler. A separately hash-bound diagnostic server used public Ubuntu glslc/shaderc 2023.8 and was likewise reproducible at 38,398,232 bytes with SHA-256 `b666bd38aedb2d0c3008348f1866caee8f9168aa4655083fc1eb716342e57ce0`.

Three fresh, controlled phone attempts changed one relevant variable at a time:

| Variant | Controlled change | Provider observation |
|---|---|---|
| baseline NDK glslc | pinned baseline | `mul_mat_vec_q5_k_f32_f32` rejected with `ErrorUnknown` |
| baseline plus `GGML_VK_DISABLE_F16=1` | F16 disabled only | same pipeline and error |
| Ubuntu glslc/shaderc 2023.8 | newer pinned shader compiler only | same pipeline and error |

In every attempt, local and remote hashes matched and the Adreno driver failed during compute-pipeline creation before health or model readiness. llama.cpp then terminated on an uncaught `vk::SystemError`. The run never reached prompt rendering, tokenization, or a logical inference request. Each attempt held the phone lock across staging and evidence capture, removed the exact scoped remote root, verified it absent, and left no server process. The [diagnostic checksum manifest](../../../experiments/0030-qwen-3.5-2b-android-vulkan-gpu/results/vulkan-provider-diagnostics/SHA256SUMS) binds all three variants.

## Results

**The Vulkan route is blocked before inference.** The canonical campaign did not start and the canonical request count is **zero**. There is no output, sanity result, setup boundary through readiness, TTFT, prefill, decode, memory, thermal campaign, or performance metric. Required proofs for 25/25 layer offload, a Vulkan model buffer, and a Vulkan compute buffer are all absent. This experiment is not completed and has **no leaderboard row**.

The durable blocker is `vk::Device::createComputePipeline: ErrorUnknown` for `mul_mat_vec_q5_k_f32_f32` during Vulkan provider initialization. Disabling F16 and changing to the bounded newer shader compiler did not change that failure class, so broad compiler roulette stopped rather than producing an unbounded series of incomparable attempts.

The retained [llama.cpp issue #19746 context](../../../experiments/0030-qwen-3.5-2b-android-vulkan-gpu/results/vulkan-provider-diagnostics/upstream-issue-19746.json) reports a related Adreno 740 shader/pipeline failure and says OpenCL worked on that issue author's device. It is context only: it uses another device/model path and does not prove that this exact Qwen route works through OpenCL. Any OpenCL investigation belongs to the separately named experiment 0035 and must have its own pinned runtime, provider proof, evidence, and campaign. It must never be relabeled as a successful Vulkan result.

The Vulkan experiment is stopped pending a new provider decision. A future retry would require a specific evidence-backed Vulkan driver/backend change and fresh authorization; the already failed variants must not be promoted to GPU execution or performance evidence.
