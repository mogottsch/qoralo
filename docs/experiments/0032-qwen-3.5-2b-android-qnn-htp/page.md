---
experiment: 0032-qwen-3.5-2b-android-qnn-htp
status: active
summary: The exact official 24-layer Qwen3.5-2B checkpoint passed host eager equivalence and compiled into four SM8550/HTP-v73 QNN subgraphs with zero non-delegated tensor compute; physical execution remains pending.
benchmark: android-llm
---

# Experiment 0032 — Qwen3.5-2B Android QNN/HTP

## Experiment description

Qwen3.5-2B already has a measured Android CPU route, but the first QNN assessment found no usable high-level conversion path for this exact 2B architecture. This experiment tests a separate ExecuTorch route: express the hybrid attention model and all request state explicitly, quantize the exact official checkpoint, compile its tensor computation for the Galaxy S23 Ultra's SM8550/HTP v73 target, and then prove physical execution on the phone.

The explicit-state design makes full-attention KV cache plus Gated DeltaNet recurrent and causal-convolution state graph inputs and outputs. This avoids hidden mutable-buffer fallback and gives a future loaded route an auditable reset boundary. Softplus remains an explicit edge operation mapped to QNN's HTP-supported `ElementWiseNeuron(SOFTPLUS)` operation.

The end-to-end target remains stricter than compilation: the exact pinned 24-layer text checkpoint must run through physical QNN/HTP on the authorized phone, retain provider/RPC/accelerator/cycle/HVX proof, produce bounded text, demonstrate complete request-state isolation, and only then run the canonical one-first-plus-five-short/five-medium/five-long campaign. The owning [experiment README](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/protocol/experiment-contract.json), [exact host compile summary](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/README.md), [compile result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/compile-result.json), and [eager comparison](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/eager-equivalence.json) are the evidence authority.

## Progress

The original support assessment remains valid for the rejected high-level route. Public GenieX llama.cpp GGUF material is not a QNN context; installed direct-GGUF conversion does not support `qwen35`; and the installed Qwen3.5 ONNX specialization assumes a 4B-derived width incompatible with the 2B model. Those findings are preserved rather than relabeled.

A new ExecuTorch 1.2 adapter introduced explicit graph state. Its first bounded structural probe used one tiny synthetic linear-attention layer and compiled into one QNN subgraph with 151 delegated tensor-compute nodes and zero non-delegated tensor compute. That proved only architecture-route viability and did not establish exact-model compilation or runtime behavior.

The exact official `Qwen/Qwen3.5-2B` revision `15852e8c…` was then downloaded and hash-bound outside Git. Its single 4,548,221,488-byte official weight file has SHA-256 `aa33250c…0b1`; the ExecuTorch Qwen3.5 converter produced a 3,763,756,713-byte local checkpoint at SHA-256 `a2640184…e86`. No model weights are committed.

Before quantization, a one-token host eager comparison checked the explicit-state adapter against ExecuTorch v1.2.0's pinned Qwen3.5 implementation. Logits, first-layer recurrent state, and first-layer convolution state all had maximum and mean absolute difference `0.0`; both paths selected token 5328. This exact comparison covers the full mixed attention stack and a representative linear-attention state transition, but it is pre-quantization host evidence, not W4A16 output validation or Android execution.

The route was calibrated for 174 tokens on the canonical short prompt and quantized using W4A16 PTQ with per-channel Linear/Conv weights and 16-bit activations, including Gated DeltaNet recurrence. The exact 24-layer graph then compiled through the ExecuTorch Qualcomm QNN delegate and QAIRT 2.49.0 for SM8550/HTP v73:

- four QNN subgraphs;
- 4,102 delegated tensor-compute nodes;
- zero non-delegated tensor-compute nodes;
- 71 non-delegated non-compute nodes: 68 tuple/index `getitem` operations and three explicit sharding boundary markers;
- all four QNN graphs finalized with status `0x0` and serialized successfully.

The generated local-only PTE is 1,994,572,968 bytes with SHA-256 `bfdae1c3…e6df`. Its four serialized QNN payloads are individually recorded in the compile result. The complete local compile log remains outside Git; a curated [compiler proof](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/compiler-proof.log), [checkpoint manifest](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/checkpoint-manifest.json), and [checksum manifest](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/SHA256SUMS) bind the committed milestone.

The next work is host-only runner preparation while the shared phone remains assigned elsewhere. Phone staging remains prohibited until Pi explicitly transfers priority. Under `phone.lock`, the first device gate must be one bounded viability request with exact artifact identity and physical QNN/HTP proof; a canonical campaign cannot begin until that request succeeds and loaded-route reset is proven.

## Results

**The experiment is active, with exact-checkpoint host AOT compilation complete and physical execution pending.** The result establishes exact official checkpoint identity, exact host eager behavior before quantization, and complete tensor-compute delegation for the W4A16 host compiler route.

| Evidence boundary | Current result |
|---|---|
| Exact official Qwen3.5-2B checkpoint | Downloaded, hash-bound, and converted outside Git |
| Pre-quantization eager comparison | Exact logits and checked state transitions; matching argmax |
| Exact-model host QNN AOT | 4 SM8550/HTP-v73 QNN subgraphs; all finalized and serialized |
| Tensor-compute delegation | 4,102 delegated; 0 non-delegated tensor compute |
| Non-compute boundary nodes | 68 `getitem` tuple/index nodes plus 3 sharding markers |
| W4A16 PTE | 1,994,572,968 bytes, hash-bound, local-only |
| Android / physical QNN or HTP execution | Not attempted; no RPC, cycle, accelerator, or HVX claim |
| W4A16 generated text and output sanity | Unavailable; the compiled route has not run |
| Setup, TTFT, prefill, decode, memory, thermal, or power | Unavailable; no Android campaign ran |
| Android LLM registry row | None; host AOT evidence is not registry-eligible |

“All tensor compute delegated” describes the host-compiled graph partition, not physical execution. The four serialized QNN graphs have not been loaded on Android, and no text response or device provider evidence exists. The exact eager comparison occurred before W4A16 quantization, so it does not establish numerical equivalence, output sanity, quality, or correctness for the compiled route.

A CPU-only response, GenieX NPU metric, direct-Hexagon output without QNN proof, or the dimension-incompatible shipped 4B example cannot satisfy this experiment. No 0032 host-only milestone belongs in the Android LLM registry; publication there remains conditional on a complete valid physical Android canonical campaign with exact route identity, provider/no-fallback proof, state isolation, retained outputs, and performance evidence.
