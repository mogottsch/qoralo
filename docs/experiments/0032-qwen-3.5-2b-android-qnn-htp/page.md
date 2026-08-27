---
experiment: 0032-qwen-3.5-2b-android-qnn-htp
status: active
summary: A synthetic one-layer explicit-state Qwen3.5 decode graph passed a bounded host QNN compile gate; exact 2B compilation and physical-phone HTP execution remain open.
benchmark: android-llm
---

# Experiment 0032 — Qwen3.5-2B Android QNN/HTP

## Experiment description

Qwen3.5-2B already has a measured Android CPU route, but the first QNN assessment found no credible way to convert this exact 2B architecture with the installed high-level QAIRT path. This experiment now tests a different idea: express the model's attention and recurrent state explicitly in an ExecuTorch graph, then ask Qualcomm's QNN delegate to compile that graph for the Galaxy S23 Ultra's SM8550/HTP v73 target without silently leaving tensor computation on the CPU.

The explicit-state design makes full-attention KV cache plus Gated DeltaNet recurrent and causal-convolution state graph inputs and outputs. That is important for a future loaded route because request reset must be provable rather than hidden in mutable framework state. Softplus remains an explicit edge operation mapped to QNN's HTP-supported `ElementWiseNeuron(SOFTPLUS)` operation.

This is still a feasibility arm, not a performance result. The end-to-end target remains the exact pinned 24-layer Qwen3.5-2B text checkpoint, physical QNN/HTP provider proof on the authorized phone, a bounded text-generation request, proven loaded-route isolation, and only then the canonical one-first-plus-five-short/five-medium/five-long campaign. The owning [experiment README](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/protocol/experiment-contract.json), and [structural-probe result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-structural-probe/result.json) are the evidence authority.

## Progress

The original support assessment pinned the official model, tokenizer, native template, hybrid architecture geometry, and canonical prompt hashes. It also established that the public GenieX llama.cpp GGUF is not a QNN input, installed QAIRT's direct GGUF builder does not support `qwen35`, and its separate Qwen3.5 ONNX builder assumes a 4B-derived width that is incompatible with the 2B model. That high-level conversion route remains blocked and its evidence is preserved rather than rewritten.

A new ExecuTorch 1.2 adapter now represents one-token Qwen3.5 decode with explicit graph state. A bounded host ahead-of-time probe used one linear-attention layer, tiny deterministic synthetic geometry and weights, context 16, and relaxed FP16 lowering. The compiler targeted SM8550/HTP v73 through the Qualcomm QNN delegate and completed with:

- one QNN subgraph;
- 151 delegated tensor-compute nodes;
- zero non-delegated tensor-compute nodes;
- three non-delegated `getitem` nodes identified as ExecuTorch tuple plumbing;
- successful finalization and a serialized 110,432-byte QNN context inside a 116,576-byte local-only PTE.

The committed [compiler excerpt](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-structural-probe/compiler-proof.log) and [checksum manifest](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-structural-probe/SHA256SUMS) bind this milestone. The restricted generated PTE/context remains outside Git and is referenced only by its recorded hash.

The next gate is substantially larger: download and hash-bind the exact pinned checkpoint, map its text weights into the explicit-state implementation, verify eager numerical equivalence, and compile all 24 layers while retaining zero tensor-compute fallback. Phone staging remains gated on that exact-model compile. A physical viability request must then prove QNN RPC, accelerator, cycle, and HVX activity under `phone.lock` before any canonical campaign can begin.

## Results

**The experiment is active, and only the bounded host structural gate has passed.** The result establishes that the new explicit-state architecture can be accepted by this ExecuTorch/QNN compiler path for a synthetic one-layer Gated DeltaNet decode graph. It removes the earlier blanket “no converter implementation” boundary for that alternate route, but it does not establish that the exact Qwen3.5-2B checkpoint compiles or runs.

| Evidence boundary | Current result |
|---|---|
| Host AOT structural compilation | Passed for the synthetic one-layer graph |
| QNN partition in that probe | 1 subgraph; 151 tensor-compute nodes delegated; 0 tensor-compute fallback |
| Exact 24-layer Qwen3.5-2B checkpoint | Not yet converted or compiled |
| Android / physical HTP execution | Not attempted; no claim |
| Generated text or output sanity | Unavailable; no inference ran |
| Setup, TTFT, prefill, decode, memory, thermal, or power | Unavailable; no Android campaign ran |
| Android LLM registry row | None; the result is not registry-eligible |

The host compiler's serialized context is not evidence that the phone executed HTP work. A text response from CPU, GenieX NPU metrics, direct-Hexagon output without QNN proof, or the dimension-incompatible shipped 4B example would not satisfy this route. Likewise, “zero tensor-compute fallback” applies only to the committed synthetic probe; it is not yet a no-fallback claim for the full model.

No current QNN blocker or host-only milestone appears in the Android LLM benchmark registry. Publication there remains conditional on a complete, valid physical Android canonical campaign with exact route identity, provider/no-fallback proof, request-state isolation, outputs, and performance evidence.
