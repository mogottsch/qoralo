# Experiment 0030: Qwen3.5-2B Android Vulkan GPU offload

## Status

**Reproducible Android Vulkan artifact built; awaiting the authorized Adreno 740 device viability gate. No Android GPU-performance claim exists yet.**

This is a separate route from CPU-only experiment 0027. It reuses the exact pinned Qwen3.5-2B Q4_K_M model bytes and canonical workload, but changes the runtime backend to public llama.cpp Vulkan. It does not rewrite or relabel 0027 evidence.

## Locked route

- Route ID: `qwen35-2b-unsloth-q4km-llamacpp-vulkan-adreno`
- Model: `unsloth/Qwen3.5-2B-GGUF` revision `f6d5376be1edb4d416d56da11e5397a961aca8ae`
- Artifact: `Qwen3.5-2B-Q4_K_M.gguf`, 1,280,835,840 bytes, SHA-256 `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223`
- Runtime: llama.cpp commit `0a5ac49bce4c42893368585edf3ffb41a38f0108`, tree `9355e5ebbca69eb403229473bec6ddfb38f055e0`
- Vulkan headers: Khronos `217e93c664ec6704ec2d8c36fa116c1a4a1e2d40`, tree `3617c6a36daa7c2c60dc4e017be821b3e235341b` (tag `v1.3.275`)
- Toolchain: Android NDK `28.1.13356709` (r28b); pinned NDK `glslc` SHA-256 `452a8331070f15d126df5e263fb9f04e78240dac5f1defe6c434b2c2eef0a53a`
- Runtime request: `--device Vulkan0 --gpu-layers 25 --split-mode none --main-gpu 0`
- Android server: 34,242,152 bytes, SHA-256 `b806fc03df6510eb7a141aea093cec7a878a2aa7456ea076a84791fadec68c00`
- Dynamic dependencies: only Android `libc.so`, `libdl.so`, `libm.so`, and `libvulkan.so`

Two clean builds in different build directories produced the exact same stripped server bytes. The build embeds generated SPIR-V and disables web UI, OpenSSL, OpenMP, and unpinned native optimization. The pinned NDK shader compiler did not support optional cooperative-matrix, integer-dot, bfloat16, or FP4 shader extensions, so those optional variants are not compiled; base Vulkan shader variants remain embedded.

## GPU claim boundary

A Vulkan-capable executable is not GPU evidence. The phone run must fail closed unless the same server log proves all of:

1. at least one Vulkan device initialized;
2. device identity contains `Adreno (TM) 740`;
3. llama.cpp reports `offloaded 25/25 layers to GPU`;
4. a `Vulkan0 model buffer` exists;
5. a `Vulkan0 compute buffer` exists;
6. no GPU-option-ignored or Vulkan-initialization-failure evidence appears.

Even when those checks pass, the claim is **Vulkan GPU offload**, not GPU-exclusive execution. CPU remains responsible for the server, tokenizer, sampler, graph scheduling/orchestration, and any operation the Vulkan scheduler does not support. The exact per-operation Vulkan/CPU split is unavailable and will remain an explicit limitation rather than being inferred.

## Protocol

The route uses shared Android LLM protocol v2 and the exact inference-v1 workloads. It keeps one loaded llama-server route and one slot, performs a separately timed full slot erase before every logical request, disables prompt caching, and requires `cache_n == 0`, full prompt evaluation, positive prefill time, and no truncation.

After the smallest bounded smoke proves real Adreno/Vulkan offload and output viability, a fresh server must execute one first short request followed by five warm short, five warm medium, and five warm long requests. All raw outputs, logs, offload proof, timestamps, process memory, KGSL observations, thermal/battery/power context, hashes, and scoped cleanup state must be retained.

## Commands

```bash
experiments/0030-qwen-3.5-2b-android-vulkan-gpu/tools/build_android.sh
ADB_SERVER_SOCKET=tcp:172.27.80.1:5037 \
  experiments/0030-qwen-3.5-2b-android-vulkan-gpu/tools/run_phone.sh smoke
# Only after smoke proof is accepted:
ADB_SERVER_SOCKET=tcp:172.27.80.1:5037 \
  experiments/0030-qwen-3.5-2b-android-vulkan-gpu/tools/run_phone.sh campaign
```

Phone operations are restricted to `/data/local/tmp/vibevoice-0030-qwen-3.5-2b-android-vulkan-gpu` while holding `artifacts/locks/phone.lock` continuously through identity, stage, execution, evidence capture, and cleanup.
