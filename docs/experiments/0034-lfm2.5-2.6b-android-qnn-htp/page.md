---
experiment: 0034-lfm2.5-2.6b-android-qnn-htp
status: active
summary: The exact LFM2.5-2.6B source now has an architecture-aware Q4 ONNX export and bounded host CPU viability result; QNN AOT compilation and physical-phone HTP proof remain open.
benchmark: android-llm
---

# Experiment 0034 — LFM2.5-2.6B Android QNN/HTP

## Experiment description

LFM2.5-2.6B has complete Android CPU and OpenCL benchmark routes, but its first QNN assessment stopped because the installed high-level QAIRT tools did not understand the model's `lfm2` architecture. This experiment now tests a separately authorized path: export the exact model to architecture-aware Q4 ONNX, preserve both kinds of recurrent state, and prepare it for fallback-disabled QNN compilation targeting the Galaxy S23 Ultra's SM8550/HTP v73.

LFM2 is not a renamed Llama-like transformer. Its 30 layers combine 22 recurrent short-convolution layers with 8 full-attention layers, so a credible route must preserve convolutional state and attention KV state, bind their layout and reset behavior, and prove that claimed model computation executes through QNN HTP rather than silently falling back to CPU. A generic SM8550 target or a serialized context alone would not provide that proof.

The exact route uses `LiquidAI/LFM2.5-2.6B` revision `ab006873…`, the architecture-aware `Liquid4All/onnx-export` exporter at commit `9a23ddd…`, symmetric block-32 INT4 weights, and Qualcomm-maintained ONNX Runtime QNN EP 2.5.0 with QNN runtime 2.49.0 as the candidate provider. Moritz reviewed and authorized the Qualcomm AI Stack License for the named public QNN packages; packages, source weights, large ONNX data, and future license-controlled contexts remain outside Git. The owning [experiment README](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/protocol/experiment-contract.json), [export provenance](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/export-provenance/result.json), and [host-smoke result](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/host-export-smoke/result.json) are the evidence authority.

## Progress

The earlier support assessment remains valid for the rejected high-level route: installed QAIRT 2.49 has no `lfm2` direct-GGUF support, HTP factory dispatch, Genie configuration, or public Qualcomm recipe/context. Rather than weakening model identity or ignoring recurrent state, the experiment moved to the separately bound architecture-aware exporter.

The exact source shards and exporter revision were hash-bound. The initial Q4 export contained the expected architecture inventory: 22 convolution nodes, 8 `GroupQueryAttention` nodes, and 167 `MatMulNBits` nodes. Its 1,855,348,736-byte external tensor file remains outside Git with SHA-256 `d3cf0985…f457`.

The exporter emitted 76 `SimplifiedLayerNormalization` nodes in the standard ONNX domain even though that operator is a Microsoft contrib operation, so ONNX Runtime 1.26 rejected the raw graph before any provider selection. A committed rewrite replaces those nodes and the final skip-RMSNorm with the equivalent standard-ONNX expression:

```text
x * scale / sqrt(reduce_mean(pow(x, 2), axis=-1) + 1e-5)
```

The rewritten 410,142-byte graph has SHA-256 `c2020ab7…d157`, still references the exact external tensor file, and passes the ONNX checker. The committed provenance records 1,129 graph nodes, 451 initializers, 41 inputs, 39 outputs, the recurrent/attention operator inventory, quantization details, source hashes, and rewrite boundary.

A bounded host CPU smoke then loaded that exact rewritten export through ONNX Runtime 1.26 and processed the canonical short workload without truncation. The prompt contained 171 input tokens. Generation was deliberately capped at 16 tokens rather than the canonical 2,048-token ceiling; it retained 88 output bytes at SHA-256 `f048f924…518`, and the narrow exact-output sanity screen marked them sensible. The recorded host load and request timings remain host-only viability observations and cannot become Android, QNN, HTP, or performance evidence.

The next committed gates are to build static prefill and one-token decode profiles with a shared 4,096-token KV capacity and explicit 22-layer convolution state, lower every operation into an HTP-owned form, compile fallback-disabled SM8550/v73 contexts with framework-operation tracing, and validate host equivalence plus complete state reset. Only after those gates pass may a bounded physical-phone viability request run under `phone.lock`; a canonical campaign comes later.

## Results

**The experiment is active, and exact-model export viability has passed on the host.** This milestone establishes that the exact pinned LFM2.5-2.6B source can be represented as an architecture-aware, checker-valid Q4 ONNX graph retaining its 22 recurrent-convolution and 8 attention layers, and that the rewritten export can return bounded text through host CPU execution.

| Evidence boundary | Current result |
|---|---|
| Exact-model Q4 ONNX export | Completed and hash-bound; checker passed after the standard RMSNorm rewrite |
| Architecture/state inventory | 22 recurrent-convolution layers and 8 GQA layers retained |
| Bounded canonical-short host CPU smoke | Completed at a 16-token cap; exact output retained and superficially sensible |
| QNN provider / fallback-disabled AOT context | Not yet established |
| Android / physical HTP execution | Not attempted; no claim |
| Canonical 1+5+5+5 campaign and Android performance | Not run; no setup, TTFT, prefill, decode, memory, thermal, or power result |
| Android LLM registry row | None; host export viability is not registry-eligible |

The host smoke's sensible-looking text is not quality, correctness, grounding, usefulness, or acceptance. It also does not prove QNN compatibility: CPUExecutionProvider ran the smoke, no QNN provider was selected, no AOT context was produced, and no phone was accessed. “Exact model” describes source/export identity only at this milestone, not exact-model HTP execution.

The historical high-level QAIRT architecture blocker is now a rejected route rather than the experiment's overall stopping point. The active route still must fail closed if any model/state operator remains outside HTP, full reset cannot be proven, the phone cannot load the exact contexts, or a new licensing/export/paid-service checkpoint appears. No 0034 host-only or blocked evidence appears in the Android LLM registry.
