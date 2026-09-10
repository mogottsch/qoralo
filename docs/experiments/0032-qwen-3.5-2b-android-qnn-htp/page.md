---
experiment: 0032-qwen-3.5-2b-android-qnn-htp
status: active
summary: The first weight-free host-QNN full-chain case completed with a selected-value mismatch; all other values agree with its oracle within one FP32 ULP. The whole output is not output-only behavior, and the internal QNN path remains unproven.
benchmark: android-llm
---

# Experiment 0032 — Qwen3.5-2B Android QNN/HTP

## Experiment description

Qwen3.5-2B already has a measured Android CPU route, but the first QNN assessment found no usable high-level conversion path for this exact 2B architecture. This experiment tests a separate ExecuTorch route: express the hybrid attention model and all request state explicitly, quantize the exact official checkpoint, compile its tensor computation for the Galaxy S23 Ultra's SM8550/HTP v73 target, and then prove physical execution on the phone.

The explicit-state design makes full-attention KV cache plus Gated DeltaNet recurrent and causal-convolution state graph inputs and outputs. This avoids hidden mutable-buffer fallback and gives a future loaded route an auditable reset boundary. Softplus remains an explicit edge operation mapped to QNN's HTP-supported `ElementWiseNeuron(SOFTPLUS)` operation.

The end-to-end target remains stricter than one physical request: the exact pinned 24-layer text checkpoint must produce credible bounded output through physical QNN/HTP, demonstrate complete loaded-route request-state isolation, and only then run the canonical one-first-plus-five-short/five-medium/five-long campaign. The owning [experiment README](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/protocol/experiment-contract.json), [host compile result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/compile-result.json), [eager comparison](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/executorch-qnn-exact-host-compile/eager-equivalence.json), [Android runner host build](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-explicit-state-runner-host-build/result.json), [first physical attempt](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-qnn-physical-viability-20260827-attempt-01/result.json), [boundary-kernel host fix](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-runner-boundary-fix-host-build/result.json), [physical execution result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-qnn-physical-viability-20260827-attempt-02/result.json), [host W4A16 QDQ diagnosis](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/host-w4a16-qdq-output-diagnosis/result.json), and [host broadcast-divergence localization](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/host-qnn-broadcast-divergence-localization/result.json), [exact repaired-PTE validation](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/exact-qnn-explicit-broadcast-host-validation/result.json), and [repaired-route physical result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/android-qnn-physical-viability-20260828-attempt-03/result.json), and [HistogramObserver host precision result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/host-histogram-precision-20260910/result.json), [saved-QDQ helper readiness](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/saved-qdq-replay-helper-readiness/result.json), and [full-short host QDQ replay](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/host-histogram-full-short-20260910/result.json), [own-state trajectory helper readiness](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/qnn-trajectory-helper-readiness/result.json), and [four-position QNN-x86 trajectory](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/host-qnn-trajectory-prefix-000-003-20260910/result.json) are the evidence authority.

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

The exact deployed PTE was then run through QNN's x86 backend at token position zero with every explicit state input zero. The layer-0 causal-convolution state remained aligned with QDQ at cosine `0.9999996`, while the first Gated Delta recurrent state was already the first large divergence: cosine about `0.0064` and QNN-to-QDQ L2 ratio about `117.81`. The final logits were finite but 39,209 vocabulary entries shared the exact maximum. Because this occurs at position zero, it rules out Android-only behavior, cross-token runner state insertion/copy, later transformer layers, and final argmax as the first cause.

A minimal one-layer W4A16 reproduction isolated the failed operation. QDQ produced 128 nonzero recurrent outer-product values for implicit multiplication `[B,H,K,1] * [B,H,1,V]`; QNN x86 wrote only 16, with cosine `0.353553`. Explicitly expanding decay, key, beta, delta, and query operands to identical static geometry before the recurrence's elementwise multiplications leaves QDQ semantics unchanged and restores QNN to 128/128 values. The corrected minimal probe reached recurrent cosine `1.0`, maximum recurrent error `4.13e-7`, and maximum final-logit error `2.96e-5`.

This identifies implicit QNN elementwise broadcasting as the first divergence and demonstrates a bounded fix in the minimal graph.

The exact 24-layer route is now recompiled with explicit static expansion. The new local-only PTE is 1,994,754,552 bytes with SHA-256 `23ac8abd…c506`. Its four SM8550/v73 QNN subgraphs contain 4,210 delegated tensor-compute nodes, including 120 explicit expand nodes, with zero non-delegated tensor compute; all four graphs finalized and serialized at status `0x0`.

At token position zero, QNN-x86 validation shows the exact repair is present:

- layer-0 recurrent-state cosine improves from about `0.0064` to `0.999829`;
- QNN-to-QDQ recurrent norm ratio improves from `117.81` to `0.9983`;
- layer-0 convolution-state cosine remains about `0.9999996`;
- the previous 39,209-way exact logit maximum becomes one unique maximum.

The result is still not full numerical equivalence. Overall first-token logits have cosine about `0.434`, and QDQ selects token 62 while QNN-x86 selects token 198. The first identified recurrent corruption is repaired, but numeric drift remains beyond that state.

A full 174-token QNN-x86 replay was attempted and stopped at the 3,600-second tool timeout after completing position 29. Four sampled checkpoints at positions 0, 9, 19, and 29 had finite logits and unique maxima, but the replay produced no final canonical-short output. No simulator process remained afterward.

Pi then authorized exactly one repaired-PTE physical check capped at one generated token. Under the full `phone.lock` lifecycle, the authorized SM-S918B/SM8550 identity and every staged hash matched. The pinned 1,994,754,552-byte PTE at SHA-256 `23ac8abd…c506` loaded through QNN HTP v73: four serialized contexts were created, four graphs retrieved, and all 696 expected graph executions completed with status `0x0`. Provider observations record four HVX threads per graph call, 253.641795 seconds aggregate accelerator execution, 255.033891 seconds aggregate RPC execution, and 61,253,612,902 accelerator cycles. The runner exited 0.

The single generated token is ID 1206, exact UTF-8 `To`, SHA-256 `f4b06e…d28146`. This replaces the unrepaired physical token 0 / `!` and removes that obvious punctuation-corruption symptom. It does not match host W4A16 QDQ token 760 / `The`, so output or numerical fidelity is not established. `looks_sensible: true` is only the narrow observation that `To` is an ordinary lexical token rather than obvious corruption; a one-token cap cannot establish sentence-level usefulness, correctness, or quality.

This is one viability observation, not a loaded-route distribution. Setup was 3.777 seconds; TTFT and total were 332.784 seconds; prefill model execution was 332.367 seconds, or 0.524 input tokens/s. Decode throughput is null because there is no after-first-token interval. These figures are not campaign performance.

The 107,315,601-byte raw provider log at SHA-256 `cdf175…d39c` and 56,603,888-byte raw ETDump at SHA-256 `b805d0…8f1a` have committed lossless zstd copies with recovery verified. Cleanup and an independent locked check found the runner process and scoped remote root absent; `phone.lock` was released. No retry or campaign is authorized.

### HistogramObserver host precision — 2026-09-10

Commit `e528f41` tests whether activation-range calibration can reduce the remaining QNN drift without introducing float recurrence or CPU tensor fallback. The exact pinned 24-layer checkpoint retains W4 per-channel Linear/Conv weights, 16-bit activations, quantized recurrence, and context 4,096; HistogramObserver replaces MinMaxObserver for activation calibration.

The comparison uses input token 248045 at position zero, all recurrent/convolution/KV state zero, and an attention mask exposing only the current-token slot. **Each route is compared against its own QDQ reference.** Histogram calibration changes the quantized reference as well as QNN encodings; the result is improved internal agreement, not equivalence to MinMax or the original float model.

| Same-position observation | MinMax QDQ vs QNN-x86 | Histogram QDQ vs QNN-x86 |
|---|---:|---:|
| Layer-23 hidden cosine | 0.491839 | 0.971446 |
| Final-logit cosine | 0.433603 | 0.947168 |
| Final-logit mean absolute error | 1.706004 | 0.483211 |
| Final-logit maximum absolute error | 10.639919 | 2.895951 |
| QDQ / QNN-x86 argmax | 62 / 198 | 198 / 198 |

All 24 hidden-layer cosines improve and all 73 outputs are finite. Not every state or error metric improves: layer-0 recurrent-state cosine decreases from 0.999829 to 0.999788, and layer-0 hidden maximum error increases slightly. The [complete comparison](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/host-histogram-precision-20260910/precision-comparison.json) retains those exceptions. Earlier layer-0 component taps are separately compiled evidence under `prior-components/`, not new internal measurements from this 73-output graph.

The local-only diagnostic PTE is 1,995,463,416 bytes with SHA-256 `7f30be3d…ff3fea`. Four SM8550/v73 QNN subgraphs retain all 4,210 delegated tensor-compute nodes, zero tensor-compute fallback, and four successful `0x0` finalizations. Its 73-output ABI adds 24 hidden tensors to the usual 49 outputs; it must not be staged with the existing 49-output Android runner. The physical PTE `23ac8abd…c506` and phone preflight remain unchanged.

Rejected and interrupted branches remain visible in the [retained host evidence](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/host-histogram-precision-20260910/README.md):

- Unquantized float recurrence left **268** tensor-compute operations outside QNN. The earlier informal total of 214 was incorrect; the retained operator map fixes the count.
- The FP16 recurrence variant left 143 nondelegated layout/cast operations and was rejected, not treated as harmless plumbing.
- MatMul recurrence reductions compiled fully delegated but worsened gated-core agreement; they were not selected.
- Symmetric activations failed QNN preprocessing; no PTE or inference result exists for that branch.
- The August shutdown partial replay and September app-priority compile interruption remain distinct incomplete attempts, not numerical failures.

The successful compile, QDQ evaluation, QNN-x86 evaluation, and report generation ran sequentially and all phase processes were reaped. Eight logs/resource records are losslessly compressed with verified raw-hash recovery. Host durations reflect preparation/evaluation under different load, not a speed comparison.

That comparison-only release did not run a full HistogramObserver prompt replay. Position-zero argmax 198 must not be compared directly with post-position-173 tokens 760 (`The`, MinMax QDQ) or 1206 (`To`, physical baseline). The paired same-position evidence remains separate from the later QDQ-only replay below.

### Saved replay helper and full-short host outcome — 2026-09-10

Source-only readiness commit `6dd1e1a` binds the exact 174 little-endian INT32 input IDs, context capacity, parameter file, and accepted saved QDQ archive before load. The helper starts from zero state, feeds the fixed input IDs in order, and updates recurrent/convolution/KV state at the actual positions while ignoring extra diagnostic outputs. It derives argmax and top logits from returned tensors, not placeholders. Result, journal, final tensor, and per-position checkpoint paths are exclusively reserved; raw logits are persisted before summary/state validation. Load, graph, state, empty/nonfinite output, save, and signal failures retain explicit partial/error evidence without overwrite or retry. Its 24 synthetic tests trap any real `torch.export.load` call; they are not model-run evidence.

After a separate release, `cc6c49c` completed the actual saved-graph replay. The accepted 13,645,661,902-byte HistogramObserver/W4A16 PT2 archive at SHA-256 `30799090…c492364`, parameters, and exact 696-byte/174-ID input were verified. Starting from zero recurrent/convolution/KV state, all input positions `0…173` and all 174 state updates completed. All 174 positional logit tensors were finite. Independent saved-tensor verification reproduced every retained argmax and top-logit value.

This was **teacher-forced prompt processing**: every step consumed its original canonical input token, not a predicted continuation token. At the final input position, argmax was 2523 with unique maximum 18.541059494. The final saved tensor is 994,857 bytes, SHA-256 `38dc3e1f…03ccad`. The pinned tokenizer (`5f9e4d49…81cb42`) decodes that one predicted ID as `You`. This is next-token interpretation only—not an autoregressive response, generated-text sanity, or accuracy evidence. Different final IDs across MinMax, HistogramObserver, and the older physical route are not correctness rankings or QNN/FP32 equivalence.

The helper took 1,802.923 seconds; its supervisor measured 1,810.322 seconds within a separately authorized 7,200-second host limit. Helper time includes hashing, graph loading, all forward/state steps, and durable tensor/journal/checkpoint writes. Execution-only time is null because it was not separately measured. These are host diagnostic wall times, not Android prefill, TTFT, decode throughput, or campaign timings. The child/process group was reaped, owned disk-backed scratch was empty, and no retry, QNN execution, or phone operation occurred.

**Retention is split between Git and required local migration data.** Git contains the full 174-position journal, final tensor, telemetry, and a per-file compression/hash manifest. All 176 raw/compressed recoveries and all 174 positional tensor-value checks passed in the reviewed evidence. The 174 intermediate tensors themselves are LOCAL-ONLY: 173,105,118 raw bytes and 148,995,000 compressed bytes. Do not clean these directories; copy both during migration/handover:

```text
experiments/0032-qwen-3.5-2b-android-qnn-htp/.local/diagnosis/full-short-20260910T092627Z/replay/final-logits.pt.steps/
experiments/0032-qwen-3.5-2b-android-qnn-htp/.local/diagnosis/full-short-20260910T092627Z/retained-compressed/positions/
```

Git hashes, journal entries, and the final tensor cannot reconstruct missing intermediate bytes. A Git-only verifier checks bindings/journal plus the two committed compressed artifacts; it does not recover or numerically verify all intermediate tensors without those local directories. The [retention and verification instructions](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/host-histogram-full-short-20260910/README.md) make that limitation explicit. Postprocessing path normalization was corrected without a model rerun or changed outputs.

The physical PTE `23ac8abd…c506` and phone preflight are unchanged. The completed QDQ replay supplies references for the separately reviewed bounded QNN trajectory below; it is not itself a full-prompt QNN or physical result.

### Own-state QNN trajectory — four positions, host only

Source-only helper commit `26d634b` targets the exact HistogramObserver 73-output PTE: one logit tensor, **48 state outputs**, and 24 hidden diagnostic tensors. It retains all 73 outputs but propagates only QNN's own recurrent/convolution/KV state. Saved QDQ logits are comparison targets; QDQ state is never fed back into this trajectory. Exclusive raw-first output and checkpoint paths, separately recorded forward/update/comparison counts, and PTE/source/input/prefix-bound state checkpoints prevent silent overwrite or relabeling partial work as complete.

An independent supervisor enforces explicit position/time budgets even if a native call blocks: deadline, STOP, or pressure triggers TERM, up to 20 seconds of grace, then group KILL/reap if needed. Thirty tiny synthetic tests cover state transport, reference changes, failures, explicit segmentation and cleanup without loading a real model or QNN. Synthetic segmented equality does not prove native restart equivalence or loaded-route campaign reuse. The planned full-174 cost was about 20,940 seconds, beyond a 7,200-second invocation; the four-position/900-second example was a review proposal, not automatic authorization.

After separate release, result commit `6f66dcb` completed exactly positions **0–3** from zero state on QNN-x86. Four forwards, four state updates, and four comparisons completed in 526.831 seconds within the 900-second limit. Host simulator logs record four contexts/graphs loaded and 16/16 constituent graph executions with status `0x0`; these are not physical HTP observations. All 73 output tensors were finite at each position.

| Position | Input ID | Logit cosine | QDQ argmax | QNN-x86 argmax |
|---|---:|---:|---:|---:|
| 0 | 248045 | 0.947168 | 198 | 198 |
| 1 | 8678 | **0.679220** | 198 | 198 |
| 2 | 198 | 0.784361 | **248045** | **71093** |
| 3 | 2523 | 0.890331 | 2224 | 513 |

Agreement drops sharply at position 1 and only partly recovers; the first argmax mismatch is at position 2. Both backends consume the same teacher-forced prefix but evolve their own states after the initial zero state. These differences measure accumulated trajectory drift, not current-call error under identical state. They cannot by themselves identify a causal operator defect, full fidelity, or accuracy.

The final checkpoint is after position 3 with `next_position=4`, metadata SHA-256 `029e2c37…b07b` and state-file SHA-256 `f2591ab3…efe3c`. Independent checks verified all four 48-state checkpoints against declared output materialization. **No checkpoint was resumed**, and no follow-on segment, full-174 QNN run, autoregressive generation, or phone operation occurred. The worker/group was reaped and disk-backed scratch was empty. The wall time includes preflight/load, tensor/checkpoint writes, and comparison; it is not Android latency or a campaign rate.

Packaging follow-up `2bf929d` is required for the complete evidence state: it adds narrowly scoped ignore exceptions for the four approved checkpoint headers and compressed state files that the repository's checkpoint exclusion initially omitted. Git now retains four complete 73-output bundles, four complete 48-state checkpoints, four paired QDQ logit tensors, and their headers/journal/manifest. Thirteen raw recoveries were verified; compressed payloads total 65,357,246 bytes. This four-position payload is recoverable from Git, not merely described by hashes.

That does **not** change the protected full-174 QDQ archive's LOCAL-ONLY policy or migration paths above. The four paired reference copies are not a replacement for all 174 intermediates. Prefix originals/backups are also protected under `experiments/0032-qwen-3.5-2b-android-qnn-htp/.local/diagnosis/qnn-prefix-20260910T104805Z/`; none were cleaned.

At that prefix milestone, a position-1 identical-QDQ-state control remained a source/inventory plan. It was subsequently prepared and executed through the separate reviews below, not by resuming or rewriting the own-state trajectory. The historical state-byte lineage limitation remains.

### Controlled position-1 pair — 2026-09-10

The follow-up asks how much difference remains when the two backends receive identical submitted inputs, rather than their independently evolved states. It is a single-position control, not a replacement for the four-position trajectory or the complete QDQ replay.

**Preparation (`43ca1eb`).** The [source/data readiness result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/controlled-position1-readiness/result.json) materialized a 51-tensor input pack for position **1**, token **8678**, context 4096. Its 48 state tensors come from saved QDQ position-zero outputs; recurrent/convolution copies, KV insertion at slot zero, future-zero regions and the position/mask were independently checked. This is explicitly **QDQ-origin state, not own-QNN resume**. The raw pack is 121,313,354 bytes, SHA-256 `bfe14bca…98ebe0d`; its logical values/dtypes/shapes digest is `4251bbce…c78e4`, and its reviewed header is `ec381857…43cd392`. The dedicated prepare/verify/single-call driver passed 23 tiny synthetic tests with real model loaders prohibited. Preparation itself made no model call.

The source is a separate saved position-zero call on the accepted PT2/input/reset configuration. The full 174-position replay saved logits, **not state checkpoints**. Matching saved logits does not prove that its missing historical state bytes were identical. The new pair establishes its own identical-input comparison without making that historical claim; it also does not establish FP32 ground truth.

**One QDQ reference call (`0dfd3a6`).** After separate release, the [QDQ validation](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/controlled-position1-qdq-20260910/result.json) ran the accepted `30799090…c492364` PT2 exactly once on that pack. Inputs were unchanged, all 73 outputs were finite, and the new logits were **bit-identical to historical position 1**: max/mean absolute difference zero, argmax 198. The raw FP32 cosine `1.000003695487976` is retained as reduction-rounding overshoot, not above-perfect similarity. Raw result `7137d83a…43519` supplies the actual same-pack reference; this first milestone did not automatically launch QNN.

**One paired QNN call (`6a5dc5b`).** After another review/release, the [paired QNN result and saved-data analysis](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/controlled-position1-paired-qnn-20260910/result.json) ran exact diagnostic PTE `7f30be3d…ff3fea` once at position 1 against that bound QDQ result. Both calls have the same input-values digest and no detected input mutation. New QNN result SHA-256 is `8c41cda7…7c285`, with all 73 outputs retained. Original FP32 logit cosine is **0.887993813**, versus **0.679220080** for the earlier own-state position 1. Max absolute difference remains 6.222187 and mean absolute difference 0.852588; both argmax IDs are 198. Better agreement is not equality or accuracy.

| Separately released host call | Worker wall time | Supervisor wall time | Limit |
|---|---:|---:|---:|
| QDQ position 1 | 143.392 s | 146.954 s | 600 s |
| QNN-x86 position 1 | 123.844 s | 124.709 s | 300 s |

These diagnostic wall times include checks, model/runtime loading and persistence; they are neither Android latency nor a matched speed comparison. Each worker/group was reaped and its disk-backed scratch was empty. No automatic sequence, retry, own-state resume, full-174 replay, autoregressive generation or phone operation followed.

**Saved-vector analysis, not attribution percentages.** Without another model call, analysis compared all 73 outputs in each of three bundles: the new QDQ control, new QNN control, and original own-state QNN position 1. All **219 tensors** were finite. For non-logit outputs, the QDQ reference is the new control: no historical full-replay 73-output bundle exists at this position.

Let `Q_own`, `Q_control`, `D_control`, and `D_historical` denote the retained logit vectors. The saved FP32 difference vectors have these FP64-evaluated L2 magnitudes:

| Logit-vector term | Definition | L2 magnitude |
|---|---|---:|
| Current-call discrepancy | `Q_control - D_control` | 539.396 |
| Prior-state effect through QNN | `Q_own - Q_control` | 719.275 |
| Historical reference shift | `D_control - D_historical` | **0** |
| Original observed difference | `Q_own - D_historical` | 866.342 |

The first three **vectors**, not their norms, sum to the fourth with a retained FP32 rounding residual of at most `4.76837e-7`; independent FP64 recomputation has zero residual. **Norms and cosines are not additive and are not percentages of causal attribution.** Original vectors remain unchanged. Interpreting the second term as a prior-state effect assumes the fixed reviewed PTE/native-runtime stack. The zero reference shift is a logit observation, not proof about missing historical state bytes.

Separate FP64 saved-data comparisons give same-input logit cosine 0.887989275 and own-QNN versus new QDQ cosine 0.679215150. Their small differences from the raw FP32 metrics reflect reporting precision, not new model outputs. Both current-call and prior-state terms remain nonzero.

**Saved layer endpoints and a neutral history observation.** Same-input hidden cosine is 0.997409 after layer 0, 0.856769 after layer 22, and 0.885774 after layer 23. Differences already appear at the first saved layer and remain at later endpoints, but these are not an operator-by-operator trace. At layer-0 convolution-history output slot 2, channel 6053, the common input from prior slot 3 is **23.721895**, QDQ returns **22.131550**, and QNN returns **23.721897**. QDQ changes that retained-history value while QNN nearly preserves it. This observation **does not show that QNN copied incorrectly, that this slot caused the hidden/logit drift, or which route is closer to FP32**. A source/encoding audit was then proposed; its separate result follows below.

**Complete retained bytes.** The input pack and historical reference are losslessly stored in Git, with two raw recoveries verified at preparation. The first QDQ result retains its full output bundle/reference/telemetry with three recoveries verified. The paired package retains all three complete 73-output bundles, the historical logit vector, full difference vectors, all-73 metrics, bindings and logs; six raw recoveries were verified. These are recoverable payloads, not hash-only promises. Original pack/output/prefix files remain protected, and the full-174 LOCAL-ONLY migration requirement above is unchanged. No physical, full-fidelity, accuracy, campaign or registry claim follows.

### Convolution-history audit — metadata/scalars only

Commit `74d5323` adds a [bounded source-metadata audit](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/conv-history-encoding-audit-20260910/result.json). It read only the previously bound PT2's 32,499,235-byte graph-JSON member, SHA-256 `2d879235…20ad86`, now losslessly retained with verified recovery. Archive identity was inherited, not newly rehashed. No weight, constant-tensor or sample-input members were read; no Torch/model/PTE load, compile, runtime call or phone access occurred. Scales and zero points were inline JSON literals.

Input 27, `states_24`, passes through input Q/DQ25/148, concat Q/DQ67/220, then history-slice output Q/DQ68/221. The first encoding uses scale `0.0007933978922665119`, zero point 37640 and codes 0–65535. Metadata type tag 4 is an INT32 container for those 16-bit codes, not 4-bit storage. For common input 23.7218952179, source-bound FP32 scalar arithmetic gives:

| Stage | Unbounded → retained code | Scalar output |
|---|---:|---:|
| Input Q/DQ25/148 | **67539 → 65535**, clipped | 22.1318340302 |
| Concat Q/DQ67/220 | 56511 → 56511 | 22.1318435669 |
| Slice-output Q/DQ68/221 | 63590 → 63590 | 22.1315498352 |

The complete scalar result, **22.131549835205078**, exactly reproduces the saved QDQ endpoint. It is input-range saturation followed by two requantizations. **The final output encoding ceiling is 23.721895, not 22.131550.**

The retained compiler log explicitly constructs an input Quantize node from `states_24`; frontend omission must not be assumed. Final optimized tensor encodings/path were not retained in a readable form. Applying only the final encoding is within one FP32 ULP of QNN's observed value, but remains an **output-only hypothesis**, not the actual backend path, a QNN defect, a cause of hidden/logit drift, or FP32-accuracy proof. The separate [tiny weight-free probe proposal](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/conv-history-encoding-audit-20260910/SYNTHETIC_PROBE_PROPOSAL.md) was unexecuted at this audit milestone. Its later preparation and separately released first case follow below.

### Tiny synthetic QNN probe — first full-chain case

The probe tests the audited history/concat/slice boundaries without loading the 24-layer model. Its synthetic inputs and three fixed encoding domains are controls for one numerical question, not a model-fidelity or Android benchmark.

**CPU references (`5584283`).** The [weight-free harness preparation](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/conv-history-probe-readiness-20260910/result.json) uses history `[1,6144,1,4]` and projection `[1,6144,1,1]`, concatenates them and retains the last four slots. Full-chain has **four Q/DQ pairs across three domains**: history, projection, concat and output; projection shares the output domain. Output-only has one pair, while aligned has four pairs all using the output domain. All **73,728 values across three CPU output tensors** bit-match independent standard-library scalar oracles. Their selected values are 22.131549835205078 for full-chain and 23.721895217895508 for output-only/aligned. Complete inputs, outputs and oracle tensors are retained. An initial venv-launch failure occurred before tests/reference forwards and remains separate from numerical results. No QNN import, compilation or execution occurred at that milestone.

**Adapter readiness (`d687756`).** The [native adapter preparation](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/conv-history-native-adapter-readiness-20260910/result.json) checked binding/API imports and hook installation/restoration with manager construction denied. Actual tiny CPU exports/JSON roundtrips preserve 4/1/4 Q/DQ pairs, one Slice each and 13/7/13 graph nodes. An initial `OpOverload.name` serialization failure is retained; the fix affects only new hooks, not the accepted CPU helpers/evidence. No native manager/tensor wrapper, backend/context, Compile or Run was exercised by this readiness step. Datatype codes such as UFIXED16=1046 and FLOAT32=562 are not encoding-kind or bitwidth metadata.

**One released full-chain case (`b95faa9`).** The [first native result](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/conv-history-native-fullchain-20260910/result.json) binds request `f9ef7075…548e` and performs exactly one high-level compile and one runtime load/forward on **QNN-x86 HTP simulation targeting SM8550/v73**, not a phone:

| Phase | Guard wall time | Bound |
|---|---:|---:|
| One compile | 10.611 s | 120 s |
| Runtime load + one forward | 4.205 s | 60 s |
| Complete case | 14.819 s | 240 s active |

These times include imports, metadata capture and evidence handling, not isolated inference performance. Early delegation has one subgraph with Concat/Slice delegated and only noncompute `getitem` plumbing outside. The final emitted plan has one QnnBackend delegate call and **zero KernelCalls**. This establishes no ExecuTorch tensor-compute fallback for this tiny route, not absence of CPU work inside the host simulator. The runtime graph completed with status `0x0`.

**Complete collection, not numerical equivalence.** All **24,576 FP32 output values** are finite; the 98,304-byte output has SHA-256 `06465f73…9845`. Selected `[0,6053,0,2]` is **23.72189712524414**. Saved-only analysis reconstructs the full scalar oracle and compares every value against the already retained CPU controls; it does not execute output-only/aligned on QNN.

| Saved CPU/oracle reference | Selected expected value | Selected absolute difference | Maximum difference elsewhere |
|---|---:|---:|---:|
| Full-chain | 22.131549835205078 | 1.5903472900 | 5.96046448e-8, at most 1 ULP |
| Output-only / aligned | 23.721895217895508 | 1.90734863e-6, 1 ULP | 0.000817656517 |

Every one of the **24,575 nonselected values** is within one FP32 ULP of full-chain. In contrast, all **6,144 slot-0 values** differ from output-only/aligned: QNN 0.4995890856 versus full-chain 0.4995890558 and output-only/aligned 0.5004067421. Thus the selected near-match does **not** establish global output-only behavior or globally bypassed quantizers. In this fixture, the substantial full-chain discrepancy is confined to the selected out-of-range history value; no numerical acceptance tolerance, SDK defect, full-model/logit cause or FP32-accuracy verdict follows.

**Observed metadata stops at the Compile boundary.** All 64 taps are retained: **50 graph snapshots**, **12 per-consumer configuration taps**, actual native-wrapper encodings and manager IO. Four boundary declarations and all three exact scale/QNN-offset domains survive through pre-Compile capture. Five operator wrappers supply eleven tensor-getter rows; **both input Quantize wrappers are present**. Folding/reinserting Q/DQ changes representation, but no semantic scale/offset change is observed at these captured boundaries, so frontend omission is unsupported.

Native fixed-point datatype is observed, but full encoding-kind/bitwidth fields and the SDK's finalized internal/fused graph remain unknown. Post-Compile manager IO arrays were empty; this is a nullable metadata limitation, not missing logical IO or proof of internal encodings. These captures do not reveal the actual optimized path responsible for the output.

**Retention and stop boundary.** Inputs/output, all CPU/oracle references, all 64 taps and full logs are in Git. The [native-artifact manifest](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/conv-history-native-fullchain-20260910/local-native-artifacts.json) binds a **230,736-byte context** (`33ba1075…2cf1f`) and **232,144-byte PTE** (`0170b6a2…d69c3`), both **LOCAL-ONLY: do not clean; copy their bytes on migration**. They reside under `experiments/0032-qwen-3.5-2b-android-qnn-htp/.local/conv-history-native-executions/fullchain-attempt-01/compile/data/`. Earlier tiny CPU export PT2s are also local-only, inventoried in the [readiness export manifest](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/conv-history-native-adapter-readiness-20260910/local-export-manifest.json). None replaces the protected full-174 reference archive.

The controller and both phase groups were reaped/absent, disk scratch was empty, and the first-case release was consumed. No other native case, retry, full-model or physical run followed. The [history-range sweep](../../../experiments/0032-qwen-3.5-2b-android-qnn-htp/results/conv-history-native-fullchain-20260910/SWEEP_PROPOSAL.md) is source-only: no new sweep input pack or native execution is established here. Follow-up `9954879` makes saved-analyzer tests bytecode-safe without a probe rerun; it does not extend numerical evidence.

## Results

**The experiment is active after one weight-free host-QNN full-chain case.** Call/collection completed, but numerical equivalence is false: one selected history value differs substantially from full-chain, while every other value is within one FP32 ULP. The array does not follow the output-only/aligned controls globally. Earlier paired-call differences and position-2/3 argmax mismatches remain unchanged. No QNN operator defect or cause of hidden/logit drift, missing historical state-byte identity, FP32 accuracy, full-174 QNN fidelity, new physical result, or campaign readiness is established.

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
| Exact old-PTE first divergence | Layer-0 conv state aligned; recurrent state cosine ~0.0064 / ~117.81× QDQ L2; 39,209 logits at exact max |
| Minimal implicit-broadcast repro | QDQ 128 nonzeros vs QNN 16; cosine 0.353553 |
| Minimal explicit-expand fix | QNN 128/128; recurrent cosine 1.0 / max error 4.13e-7; logits max error 2.96e-5 |
| Exact repaired PTE | 1,994,754,552 bytes / SHA `23ac8abd…c506`; 4 subgraphs, 4,210 delegated compute incl. 120 expands, zero tensor fallback |
| Exact repaired first state | Recurrent cosine 0.999829 / norm ratio 0.9983; conv cosine 0.9999996; unique logit max |
| Remaining QNN-x86 drift | Overall logits cosine 0.434; QDQ argmax 62 vs QNN-x86 198; not full equivalence |
| Full-prompt simulator replay | Timed out at 3,600 s after position 29; four checkpoints finite/unique, no final output |
| Repaired physical route | Verified SM-S918B/SM8550; 4 contexts created/retrieved; 696/696 QNN HTP-v73 graph executions status `0x0`; exit 0 |
| Repaired provider profile | 4 HVX threads/call; 253.641795 s accelerator; 255.033891 s RPC; 61,253,612,902 cycles |
| Repaired single output | Token 1206 / `To` / SHA `f4b06e…d28146`; prior obvious token-0/punctuation symptom removed |
| Output-fidelity boundary | Physical `To` differs from host W4A16 QDQ `The`; no equivalence claim |
| Output sanity | `looks_sensible: true`, `issue_notes: null` only for one ordinary lexical token; no sentence-level quality claim |
| Repaired viability timing | Setup 3.777 s; TTFT/total 332.784 s; prefill execute 332.367 s / 0.524 tok/s; single observation only |
| Retained provider evidence | Raw provider log 107,315,601 B and ETDump 56,603,888 B; lossless zstd recovery verified |
| Cleanup | Physical baseline process/root absent; lock released and independently rechecked |
| Histogram comparison scope | Position 0 / token 248045 / zero state; each observer route against its own QDQ reference |
| Hidden/logit agreement | All 24 hidden cosines improve; layer23 0.491839→0.971446; logits 0.433603→0.947168 |
| Logit errors/argmax | Mean abs 1.706004→0.483211; max abs 10.639919→2.895951; QDQ/QNN 62/198→198/198 |
| Exceptions | Layer0 recurrent cosine slightly worse; not all state/error metrics improve; separate prior component taps |
| Histogram host AOT | 4 subgraphs / 4,210 delegated compute / 0 tensor fallback / 4 finalizations `0x0` |
| Diagnostic artifact boundary | 1,995,463,416 B / SHA `7f30be3d…ff3fea`; 73 outputs, incompatible with current 49-output phone runner |
| Rejected branches | Float fallback 268 (not informal 214); FP16 layout/cast fallback 143; MatMul regression; symmetric preprocessing failure |
| Interruption boundary | Shutdown/app-priority partial attempts retained, not numerical failures; successful comparison phases reaped |
| Saved replay helper | Source-only `6dd1e1a`; 24 synthetic tests with real archive-load trap; exclusive raw-first/error/checkpoint retention |
| Full-short host outcome | `cc6c49c`: saved HistogramObserver QDQ, 174 teacher-forced inputs + 174 state updates, positions 0–173, all logits finite |
| Tensor verification | All 174 argmax/top-logit summaries independently reproduced; all 176 raw/compressed recoveries verified |
| Final next-token interpretation | Argmax 2523 / `You`; unique max 18.541059494; not autoregressive text or accuracy evidence |
| Final tensor | 994,857 bytes / SHA `38dc3e1f…03ccad`; retained compressed in Git |
| Diagnostic wall time | Helper 1,802.923 s / guard 1,810.322 s, includes hash/load/persistence; execution-only time null; not Android/campaign timing |
| Critical retention boundary | 174 intermediate raw/compressed tensors LOCAL-ONLY; mandatory migration directories; Git hashes cannot reconstruct them |
| Trajectory helper | `26d634b`: retain 73 outputs, carry only own-QNN 48-state outputs; QDQ references never fed back |
| Four-position host result | `6f66dcb`: positions 0–3, four forwards/updates/comparisons, 16/16 host-simulator graph successes; all outputs finite |
| Logit agreement | Cosines 0.947168 / 0.679220 / 0.784361 / 0.890331; position-1 drop explicit |
| Argmax divergence | First at p2: QDQ 248045 vs QNN 71093; p3: 2224 vs 513; p0/p1 both 198 |
| Causal boundary | Same input prefix, own evolving states; not an identical-state operator or full-fidelity test |
| Budget/cleanup | 526.831 s host wall <900 s; worker/group reaped, scratch empty; no retry/follow-on/phone |
| Checkpoint boundary | Last next_position4; four materialized 48-state checkpoints verified; no native resume executed |
| Complete prefix packaging | `2bf929d`: four full 73-output bundles + four state checkpoints + four paired QDQ logits in Git; 13 recoveries verified |
| Prior archive retention | Full-174 QDQ intermediates remain protected LOCAL-ONLY migration data; prefix Git copies do not replace them |
| Controlled-input preparation | `43ca1eb`: QDQ-origin position 1 / token 8678, 51 tensors including 48 state inputs; pack/header/value hashes verified; not resume |
| Historical lineage | Full replay saved logits, not state checkpoints; the new pair does not prove missing historical state-byte identity |
| QDQ reference validation | `0dfd3a6`: one call, 73 finite outputs, no input mutation; logits bit-identical to historical p1, argmax 198 / max abs 0 |
| FP32 cosine overshoot | QDQ 1.000003695487976 retained as reduction rounding, not above-perfect similarity |
| Paired QNN control | `6a5dc5b`: one call on the identical pack, bound QDQ result `7137d83a…43519`, no mutation; raw cosine 0.887993813 vs own-state 0.679220080 |
| Remaining same-input difference | Max abs 6.222187 / mean abs 0.852588; argmax 198/198 is not numerical equality or accuracy |
| Diagnostic budgets | QDQ supervisor 146.954 s <600 s; QNN 124.709 s <300 s; not matched speed/Android timing |
| Saved-data scope | Three complete 73-output bundles, all 219 tensors finite; all 73 compared against the new QDQ control, not missing historical state outputs |
| Logit-vector magnitudes | Current 539.396 / prior-state 719.275 / original 866.342; reference shift 0; norms/cosines not additive or attribution percentages |
| Vector-identity residual | FP32 max 4.76837e-7 retained; independent FP64 residual 0; original vectors unchanged |
| Layer endpoints | Same-input hidden cosines: layer 0, 0.997409; layer 22, 0.856769; layer 23, 0.885774; no isolated operator diagnosis |
| Conv-history observation | Input 23.721895 → QDQ 22.131550 / QNN 23.721897; not QNN-corruption, drift-causality, or FP32-closeness proof |
| Controlled-chain retention | Complete input pack and paired output/difference vectors in Git; six paired-package recoveries; protected full-174 archive unchanged |
| Metadata/scalar audit | `74d5323`: input code 67539 clips to 65535, then concat/output requantization exactly reproduces QDQ 22.131549835205078; final ceiling 23.721895 |
| QNN path limitation | Compiler log constructs input Quantize; optimized encodings/path unobserved; output-only near-QNN calculation is a hypothesis, not backend-defect or drift-causality proof |
| Tiny CPU references | `5584283`: three variants, 4/1/4 Q/DQ pairs; all 73,728 CPU values bit-match full scalar oracles; no QNN at this milestone |
| Adapter readiness | `d687756`: imports/hooks and tiny CPU exports only; initial serialization failure retained; no backend init/Compile/Run at this milestone |
| First synthetic QNN case | `b95faa9`: one full-chain compile 10.611 s + one load/forward 4.205 s; total 14.819 s; host simulation only |
| Tiny delegation/execution | One subgraph; early tensor fallback absent; final one QnnBackend call / zero KernelCalls; runtime status `0x0`, not CPU-free host simulation |
| Output classification | 24,576 finite FP32 values; collection complete, numerical equivalence false |
| Selected mismatch | QNN 23.7218971252 vs full-chain 22.1315498352; absolute difference 1.5903472900 |
| Whole-array constraint | All 24,575 other values within 1 ULP of full-chain; all 6,144 slot-0 values differ from output-only/aligned by 0.000817656517 |
| Actual metadata capture | 50 graph snapshots + 12 config taps + native wrappers/manager IO; four boundaries/three domains preserved before Compile; both input Quantize wrappers present |
| Unknown native details | Full encoding-kind/bitwidth and finalized internal graph; empty manager IO arrays remain a null limitation, not missing logical IO |
| Tiny artifact retention | Raw IO/taps/references/logs in Git; context 230,736 B and PTE 232,144 B LOCAL-ONLY, mandatory migration bytes |
| Next investigation | Source-only history-range sweep proposal; no sweep pack or swept native cases, output-only/aligned still CPU references only |
| Remaining candidate evidence | No QNN root cause for hidden/logit drift, full-174 QNN fidelity, FP32/physical equivalence, autoregressive text, or campaign |
| Android LLM registry row | None; bounded host control/analysis evidence is not registry-eligible |

Attempt 03 remains the unchanged bounded physical baseline. The new pair tests identical submitted inputs and separates nonzero current-call and prior-state logit-vector terms at one position; it does not retroactively turn the four-position own-state trajectory into a same-state test. Neither the neutral convolution-history observation, matching argmax IDs nor the QDQ token interpretation `You` establishes an individual operator cause, full QNN/FP32 fidelity or answer accuracy. No loaded-route performance campaign exists.

A CPU-only response, GenieX NPU metric, direct-Hexagon output without QNN proof, or the dimension-incompatible shipped 4B example cannot satisfy this experiment. Neither can one lexical but mismatching token justify output fidelity, usefulness, sentence quality, or a campaign. No 0032 row belongs in the Android LLM registry until a complete valid physical Android canonical campaign establishes exact route identity, provider/no-fallback proof, state isolation, retained outputs, and a loaded-route performance distribution.
