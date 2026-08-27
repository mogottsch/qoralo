---
experiment: 0032-qwen-3.5-2b-android-qnn-htp
status: active
summary: The authorized phone initialized QNN HTP v73 and loaded all four exact contexts, then stopped before model execution because three non-compute sharding-boundary kernels were not registered.
benchmark: android-llm
---

# Experiment 0032 — Qwen3.5-2B Android QNN/HTP

## Experiment description

Qwen3.5-2B already has a measured Android CPU route, but the first QNN assessment found no usable high-level conversion path for this exact 2B architecture. This experiment tests a separate ExecuTorch route: express the hybrid attention model and all request state explicitly, quantize the exact official checkpoint, compile its tensor computation for the Galaxy S23 Ultra's SM8550/HTP v73 target, and then prove physical execution on the phone.

The explicit-state design makes full-attention KV cache plus Gated DeltaNet recurrent and causal-convolution state graph inputs and outputs. This avoids hidden mutable-buffer fallback and gives a future loaded route an auditable reset boundary. Softplus remains an explicit edge operation mapped to QNN's HTP-supported `ElementWiseNeuron(SOFTPLUS)` operation.

The end-to-end target remains stricter than compilation or context loading: the exact pinned 24-layer text checkpoint must execute through physical QNN/HTP on the authorized phone, retain provider/RPC/accelerator/cycle/HVX proof, produce bounded text, demonstrate complete request-state isolation, and only then run the canonical one-first-plus-five-short/five-medium/five-long campaign. The owning [experiment README](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/protocol/experiment-contract.json), [exact host compile summary](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/README.md), [compile result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/compile-result.json), [eager comparison](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/eager-equivalence.json), [Android runner host-build result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-explicit-state-runner-host-build/result.json), and [first physical attempt](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-qnn-physical-viability-20260827-attempt-01/result.json) are the evidence authority.

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

A single-request explicit-state runner is now host-built for Android arm64-v8a API 30 with NDK r28b. The stripped local-only executable is 3,444,472 bytes with SHA-256 `4b05bf24…aec58`; its exact QNN backend dependency and curated build proof are also hash-bound. Metadata-only inspection ties the runner to the exact PTE SHA-256 `bfdae1c3…e6df` and its `forward` ABI:

- 51 inputs: token, 4,096-position attention mask, position, and 48 explicit state inputs;
- 49 outputs: logits plus 48 next-state outputs;
- 121,298,952 input bytes and 21,661,696 output bytes per invocation;
- full-attention K/V insertion into the next explicit cache;
- complete Gated DeltaNet recurrent and causal-convolution state copy;
- zero initialization of all 48 state inputs for request reset;
- greedy generated token IDs, QNN runtime profile/log controls, ETDump, and request/model-step timings.

The runner intentionally supports only one logical request per process. It is suitable only for a bounded physical viability gate; it does not implement the loaded-route multi-request reuse required by the canonical campaign.

Pi explicitly transferred phone priority for one attempt capped at one generated token. Under the full `phone.lock` lifecycle, the authorized SM-S918B/SM8550 matched the expected identity, and every deployed runner, PTE, backend, HTP, system, v73 stub, and v73 skeleton hash matched locally and remotely.

Physical provider initialization reached a meaningful but pre-execution boundary. The retained 126,807-byte QNN log records four `kHtpBackend` markers, DSP architecture 73 for all four graphs, 21 successful FastRPC memory-map markers, four serialized contexts created, and all four QNN graphs retrieved with status `0x0`. It also reports the HTP/HVX configuration for each graph.

ExecuTorch then rejected the method before any graph execution because the runner had not linked or registered exactly three `llama::fallback.out` instructions. These are the non-compute identity boundaries used to join the four QNN shards; the failure is runner linkage, not tensor-compute fallback. The log contains zero graph-execute markers, and the attempt generated zero tokens, outputs, ETDump files, metrics, or performance evidence. Output sanity remains null.

No retry was performed. The runner process and experiment-scoped remote root were verified absent, `phone.lock` was released, and Pi independently rechecked cleanup. Work returns to host-only linkage of the three boundary kernels. Any retry requires a new explicit Pi phone-priority handoff; no campaign is authorized.

## Results

**The experiment is active after proving physical QNN/HTP-v73 provider initialization and loading all four exact contexts, but before model execution.** The durable evidence now establishes exact phone artifact identity, FastRPC mappings, context creation, and QNN graph retrieval. The missing non-compute boundary registrations prevented the ExecuTorch method and every model graph from executing.

| Evidence boundary | Current result |
|---|---|
| Exact official Qwen3.5-2B checkpoint | Downloaded, hash-bound, and converted outside Git |
| Pre-quantization eager comparison | Exact logits and checked state transitions; matching argmax |
| Exact-model host QNN AOT | 4 SM8550/HTP-v73 QNN subgraphs; all finalized and serialized |
| Tensor-compute delegation | 4,102 delegated; 0 non-delegated tensor compute |
| Non-compute boundary nodes | 68 `getitem` tuple/index nodes plus 3 sharding markers |
| W4A16 PTE | 1,994,572,968 bytes, hash-bound, local-only |
| Android runner host build | arm64-v8a API 30; 3,444,472 bytes; stripped and hash-bound outside Git |
| Exact PTE ABI inspection | 51 inputs / 49 outputs, including 48 explicit state inputs and outputs |
| Physical provider/context loading | QNN HTP backend and DSP arch 73 identified; FastRPC mapped; 4 contexts created and 4 graphs retrieved `0x0` |
| Model execution boundary | Method load failed on 3 missing non-compute `llama::fallback.out` registrations; 0 graph executes |
| W4A16 generated text and output sanity | 0 tokens; no output; sanity null |
| Cleanup | Process and scoped root verified absent; lock released and independently rechecked |
| Setup, TTFT, prefill, decode, memory, thermal, or power | Unavailable; no Android campaign ran |
| Android LLM registry row | None; host AOT evidence is not registry-eligible |

“All tensor compute delegated” describes the host-compiled partition. The phone evidence now proves physical QNN/HTP provider initialization and exact serialized-context loading/retrieval, but not physical model inference: no graph-execute marker exists. The boundary-kernel failure occurred after context loading and before the method could run. The exact eager comparison occurred before W4A16 quantization, so it does not establish numerical equivalence, output sanity, quality, or correctness for the compiled route. The single-request runner is not campaign-eligible.

A CPU-only response, GenieX NPU metric, direct-Hexagon output without QNN proof, or the dimension-incompatible shipped 4B example cannot satisfy this experiment. No 0032 host-only milestone belongs in the Android LLM registry; publication there remains conditional on a complete valid physical Android canonical campaign with exact route identity, provider/no-fallback proof, state isolation, retained outputs, and performance evidence.
