---
experiment: 0032-qwen-3.5-2b-android-qnn-htp
status: active
summary: Physical QNN HTP execution produced `!`; a matching host W4A16 QDQ replay produced `The`, proving PTQ changes the top token but does not explain the physical zero-token result.
benchmark: android-llm
---

# Experiment 0032 — Qwen3.5-2B Android QNN/HTP

## Experiment description

Qwen3.5-2B already has a measured Android CPU route, but the first QNN assessment found no usable high-level conversion path for this exact 2B architecture. This experiment tests a separate ExecuTorch route: express the hybrid attention model and all request state explicitly, quantize the exact official checkpoint, compile its tensor computation for the Galaxy S23 Ultra's SM8550/HTP v73 target, and then prove physical execution on the phone.

The explicit-state design makes full-attention KV cache plus Gated DeltaNet recurrent and causal-convolution state graph inputs and outputs. This avoids hidden mutable-buffer fallback and gives a future loaded route an auditable reset boundary. Softplus remains an explicit edge operation mapped to QNN's HTP-supported `ElementWiseNeuron(SOFTPLUS)` operation.

The end-to-end target remains stricter than one physical request: the exact pinned 24-layer text checkpoint must produce credible bounded output through physical QNN/HTP, demonstrate complete loaded-route request-state isolation, and only then run the canonical one-first-plus-five-short/five-medium/five-long campaign. The owning [experiment README](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/protocol/experiment-contract.json), [host compile result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/compile-result.json), [eager comparison](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/eager-equivalence.json), [Android runner host build](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-explicit-state-runner-host-build/result.json), [first physical attempt](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-qnn-physical-viability-20260827-attempt-01/result.json), [boundary-kernel host fix](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-runner-boundary-fix-host-build/result.json), [physical execution result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-qnn-physical-viability-20260827-attempt-02/result.json), and [host W4A16 QDQ diagnosis](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/host-w4a16-qdq-output-diagnosis/result.json) are the evidence authority.

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

No retry was performed. The runner process and experiment-scoped remote root were verified absent, `phone.lock` was released, and Pi independently rechecked cleanup.

The missing boundary registration is now addressed in a host-only rebuild. The revised Android arm64 runner whole-archive links ExecuTorch v1.2.0's `custom_ops` target and pinned `op_fallback.cpp` implementation at SHA-256 `90933290…8c4d`. That implementation resizes and verifies an identical output shape/type, then copies the input bytes; it is an identity boundary between QNN shards rather than arithmetic model computation. The stripped binary embeds the exact `llama::fallback.out` registration name.

The revised runner is 3,446,144 bytes with SHA-256 `0b5bef79…1fc5`, and the guarded phone script rejects any other runner hash while keeping the PTE SHA-256 `bfdae1c3…e6df` unchanged.

Pi authorized exactly one retry capped at one generated token. Exact runner, PTE, prompt, and QNN library hashes matched on the authorized SM8550 phone. The revised method loaded and all four HTP-v73 graphs executed once for each of the 174 prompt tokens: the provider evidence records 696 graph starts and 696 status-`0x0` completions.

Native-unit ETDump observations cover those 696 graph calls:

- four HVX threads used per graph execution;
- 241.087632 seconds aggregate QNN accelerator execute time;
- 242.457724 seconds aggregate RPC execute time;
- 61,322,321,662 aggregate accelerator cycles.

These are physical provider observations for one viability request, not a benchmark distribution. Route setup was 3.661 seconds. The request's TTFT and total were both 326.170 seconds; prefill model execution was 325.745 seconds, or 0.534 input tokens/s. With a one-token cap there is no after-first-token decode interval, so decode throughput is null.

The request completed at `max_tokens` with token ID 0, which the pinned tokenizer decodes to exact one-byte UTF-8 `!` at SHA-256 `bb7208bc…3b62`. The pre-PTQ host calibration over the same short prompt ended at token 21365, `Given`; the physical token does not match. The evidence does not choose whether quantization, state/input transport, shard boundaries, or output handling caused the difference.

Because the authorized output is only one punctuation token, it cannot support the narrow text screen. Output sanity is correctly `looks_sensible: null` and `issue_notes: null`; no sensible, useful, correct, or quality claim exists.

The 104,402,838-byte provider log and 55,018,400-byte ETDump are retained as lossless zstd files with raw/compressed hashes and verified decompression recovery. The process and scoped root were verified absent, `phone.lock` was released, and Pi independently rechecked cleanup. No additional phone run or campaign is authorized; diagnosis proceeds on the host.

A lower-retention host diagnosis replayed the exact 174-token canonical short prompt through the same PT2E W4A16 QDQ recipe used for the physical compile. Preparation and replay ran in separate processes: the first exported, calibrated, converted, and persisted the graph before exiting; the second loaded only that QDQ graph and explicit-state templates. The 13,644,225,801-byte QDQ artifact remains local-only at SHA-256 `be0c1a0a…7563`.

The exact three-way top-token result is:

- pre-PTQ host calibration: token 21365, `Given`;
- host W4A16 QDQ: token 760, `The`;
- physical QNN HTP: token 0, `!`.

PTQ materially changes the top token, but host QDQ does not reproduce physical token 0, so PTQ alone is not a complete explanation. The first post-QDQ divergence remains to be localized among QNN lowering/runtime, explicit state or input transport, shard boundaries, and final output handling.

The host replay took 2,467.044 seconds and its observed peak RSS was 6,094,088 KiB. Those values describe one diagnostic replay and host resource requirement, not Android or benchmark performance.

## Results

**The experiment is active after bounded physical execution, with host diagnosis excluding a PTQ-only explanation for the output mismatch.** All expected QNN graph calls completed through HTP v73, but pre-PTQ, host QDQ, and physical QNN select three different top tokens. Physical provider execution is established; the first downstream divergence, output fidelity, and campaign readiness are not.

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
| Attempt-01 model execution boundary | Method load failed on 3 missing non-compute `llama::fallback.out` registrations; 0 graph executes |
| Host boundary-kernel fix | Whole-archive linked pinned identity implementation; revised runner 3,446,144 bytes / SHA `0b5bef79…1fc5` |
| Bounded physical graph execution | 4 HTP-v73 graphs × 174 prompt tokens: 696 starts and 696 status-`0x0` completions |
| Native provider profile | 4 HVX threads/call; 241.087632 s accelerator execute; 242.457724 s RPC; 61,322,321,662 cycles |
| Single-request viability timing | Setup 3.661 s; TTFT/total 326.170 s; prefill execute 325.745 s / 0.534 tok/s; not campaign performance |
| W4A16 output | Physical token 0 / `!` / SHA `bb7208bc…3b62` |
| Three-way host/phone diagnosis | Pre-PTQ 21365 / `Given`; host W4A16 QDQ 760 / `The`; physical QNN 0 / `!` |
| Diagnostic conclusion | PTQ changes the top token but does not reproduce or explain physical token 0 |
| Host QDQ replay boundary | 2,467.044 s, peak RSS 6,094,088 KiB, 13.64 GB local-only artifact; diagnostic, not performance |
| Output sanity | `looks_sensible: null`, `issue_notes: null`; one punctuation token is insufficient to check |
| Cleanup | Process and scoped root verified absent; lock released and independently rechecked |
| Android LLM registry row | None; host AOT evidence is not registry-eligible |

Attempt 02 proves bounded physical execution of the exact route through QNN HTP v73, including accelerator/RPC/cycle/HVX observations. It does not prove quantized numerical fidelity or credible generated text. The host QDQ replay narrows the diagnosis by showing that PTQ changes the pre-PTQ top token but still does not produce the physical result; it does not identify the downstream cause. Physical and host timings are respectively one max-new-tokens-1 viability observation and one diagnostic replay, not loaded-route campaign performance. The single-request runner remains campaign-ineligible.

A CPU-only response, GenieX NPU metric, direct-Hexagon output without QNN proof, or the dimension-incompatible shipped 4B example cannot satisfy this experiment. Neither can one mismatching punctuation token justify output sanity, usefulness, quality, or a campaign. No 0032 row belongs in the Android LLM registry until a complete valid physical Android canonical campaign establishes exact route identity, provider/no-fallback proof, state isolation, retained outputs, and a loaded-route performance distribution.
