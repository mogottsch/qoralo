# Experiment 0006 — VibeVoice Realtime 0.5B Android feasibility

## Objective and stop condition

Prepare a component-level Android feasibility recommendation for the pinned Realtime model **without converting anything**. The machine-readable result is [`feasibility-inventory.json`](feasibility-inventory.json), governed by [`feasibility-inventory.schema.json`](feasibility-inventory.schema.json).

**Status: recommendations only; no conversion has begun.** Host generation is not mobile evidence. The candidate remains conditional on the user's listening review (`pending_user_review`). If its sound is not acceptable, none of the runtime work below is justified.

This inventory is revalidated against the accepted **protocol-v2** host record (protocol fingerprint `ca0987…45814`, raw SHA-256 `0daa06…28c1`). The checker fails closed if that dependency's status, fingerprint, five diffusion steps, raw hash, or 3,200-sample native chunks drift. This linkage establishes which preview informed the recommendations; it does not turn host evidence into Android or subjective-quality evidence.

## What the checkpoint actually contains

The pinned safetensors header contains 1,017,626,724 learned parameters. The source creates a four-layer text Qwen2 model and a twenty-layer TTS Qwen2 model, but explicitly says the latter's token embedding is unused. The checkpoint nevertheless stores both `[151936, 896]` embeddings.

```text
inactive duplicate = 151,936 × 896 = 136,134,656 parameters
active total       = 1,017,626,724 - 136,134,656 = 881,492,068
```

“0.5B” describes the active Qwen backbone reasonably, not the whole speech checkpoint:

| Boundary | Checkpoint params | Active params | Role |
|---|---:|---:|---|
| Qwen text + TTS backbones | 630,167,424 | 494,032,768 | 4 text layers + 20 recurrent TTS layers |
| Speech connector/type/scalars/EOS | 1,669,251 | 1,669,251 | 64↔896 bridge and stop decision |
| Diffusion head | 42,094,080 | 42,094,080 | four FFN blocks producing 64-wide acoustic latents |
| Acoustic decoder | 343,695,969 | 343,695,969 | causal convolutional 64-wide latent → waveform |
| **Total** | **1,017,626,724** | **881,492,068** | inactive difference is the duplicate embedding |

Counts are exact for the pinned tensor names and shapes, but “active” is a static source-path classification rather than a traced mobile graph. See the inventory for the operator families at each boundary and explicit duplicated constants.

## Streaming state is not yet a fixed Android ABI

The official implementation is bounded but dynamic:

- Qwen KV tensors are appended using dynamic cache orchestration. At the 8,192-position limit, a batch-one BF16 maximum for all 24 layers is:
  `24 layers × 2 K/V × 2 KV heads × 8,192 × 64 head dimension × 2 bytes = 100,663,296 bytes`.
- The acoustic decoder's causal Conv1d and ConvTranspose1d caches settle to bounded contexts, but they live in a Python dictionary keyed by layer and sample. First-call and steady-state slicing differ.
- Each acoustic frame starts from random noise and carries diffusion scheduler state. The config default is 20 steps; the accepted host preview used 5. These must not become competing hidden constants.
- Ratios `8×5×5×4×2×2 = 3,200` explain one 3,200-sample/133.33 ms native chunk, but do not prove a fixed-shape export.

Therefore a future ABI first needs captured KV tensors, convolution caches, valid lengths, phase/reset flags, timesteps, and RNG/noise. The six fixture boundaries and first/steady/reset cases are specified in the inventory.

## Package arithmetic, not a support claim

These estimates cover active learned parameters only. They exclude runtime libraries, tokenizer, alignment, metadata, activation/cache memory and packaging overhead unless stated.

| Storage assumption | Formula | Estimated bytes |
|---|---|---:|
| FP16 | `881,492,068 × 2` | 1,762,984,136 |
| ideal INT8 | `881,492,068 × 1` | 881,492,068 |
| mixed/groupwise INT4 | `ceil(881,492,068/2) × [1.03,1.12]` | 453,968,416–493,635,559 |

The INT4 allowance is an illustrative uncertainty band for scale/zero-point tables, FP16 residual tensors, padding, and alignment. No packing format or group size has been selected. These figures make **no** claim that a runtime supports the graph, that quantization preserves quality, or that Android memory/latency targets pass.

## Narrow runtime recommendation after listening approval

1. **QNN/HTP first, as microprobes only.** Start with one Qwen block/diffusion FFN and probe the ConvTranspose1d acoustic boundary separately on SM8550. For each of `8a8w`, `16a8w`, and blockwise `16a4w`, require: operator-by-operator partition coverage; every CPU fallback and reason; every HTP transfer's direction/shape/dtype/bytes; boundary numerical error; and cold plus synchronized warm p50/p90/p99 latency (at least 30 runs), including per-3,200-sample latency and thermal state. Silent fallback is failure.
2. **LiteRT/LiteRT-LM second.** Confirm the exact 896-wide Qwen2/KV configuration fits a documented LiteRT-LM path before doing work. Keep diffusion and acoustic probes separate; do not assume transposed-convolution coverage.
3. **ONNX Runtime Mobile third.** Use explicit component graphs and a reduced operator configuration as the portable CPU comparison. A QNN Execution Provider run is subject to the same evidence matrix and approval gate as direct QNN.

Any Qualcomm SDK/EULA, account, click-through, redistributed binary, proprietary delegate, or other new proprietary terms are a **stop-for-user-approval gate**. Do not download or accept them speculatively. Public runtime documentation is not evidence that this graph will partition.

## Conditional conclusion

FP16 active-weight arithmetic is under the provisional 2 GB package ceiling, and quantized storage could be materially smaller. That is encouraging but insufficient: Android peak PSS, coverage, transfers, numerical error, first audio, steady latency, thermal behavior, and subjective quality are all unknown. The next action is to stop for listening review. Only an approved candidate proceeds to fixture capture, and only then to an approved narrow accelerator probe.

## Validation

The checker uses only Python's standard library and verifies top-level schema constraints, the pinned protocol-v2 preview dependency, component sums, duplicate arithmetic, storage formulas, chunk/KV formulas, QNN evidence fields, approval gates, and the no-conversion/listening conditions:

```bash
python3 check_inventory.py
python3 -m unittest -v test_inventory.py
```

## Sources

All model claims refer to immutable revisions:

- [Pinned model config](https://huggingface.co/microsoft/VibeVoice-Realtime-0.5B/blob/6bce5f06044837fe6d2c5d7a71a84f0416bd57e4/config.json)
- [Pinned streaming component construction](https://github.com/microsoft/VibeVoice/blob/94da20d98b2fa7688e9cbfaf7692ddb4954f7600/vibevoice/modular/modeling_vibevoice_streaming.py)
- [Pinned inference/cache orchestration](https://github.com/microsoft/VibeVoice/blob/94da20d98b2fa7688e9cbfaf7692ddb4954f7600/vibevoice/modular/modeling_vibevoice_streaming_inference.py)
- [Pinned acoustic tokenizer/cache implementation](https://github.com/microsoft/VibeVoice/blob/94da20d98b2fa7688e9cbfaf7692ddb4954f7600/vibevoice/modular/modular_vibevoice_tokenizer.py)
- [Accepted host-preview record](../0007-mobile-podcast-preview-bakeoff/results/realtime-preview.json) (5 steps, 3,200-sample chunks, host-only metrics, pending listening)
- [Qualcomm AI Engine Direct / QNN](https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk)
- [LiteRT](https://ai.google.dev/edge/litert) and [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM)
- [ONNX Runtime Mobile](https://onnxruntime.ai/docs/tutorials/mobile/) and [QNN Execution Provider](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)
