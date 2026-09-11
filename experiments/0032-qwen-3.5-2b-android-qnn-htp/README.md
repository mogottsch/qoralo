# Experiment 0032: Qwen3.5-2B Android QNN/HTP

## Status

**PAUSED BY MORITZ (2026-09-11). The bounded QNN-x86 own-state prefix completed positions 0–3, but drift remains: position-1 logit cosine falls to 0.679220 and argmax first diverges at position 2. This does not establish full fidelity or identify current-call versus feedback error. The paired same-input QNN control completed: agreement improves to about 0.888, but residual current-call and prior-state effects both remain. Saved-output analysis exposes discrepancies from layer 0 onward without identifying an operator cause. Physical baseline unchanged.**

Restart handoff: [`PAUSED-20260911.md`](PAUSED-20260911.md). Latest completed result [`06d8332 / same-input FP32`](results/fp32-controlled-position1-20260911/) shows logit cosines only0.505974 (QDQ) /0.492931 (QNN) versus the unquantized same-adapter reference, despite all argmax198. The weight-only discriminator has six small tests but **no prepared request or model call**; it remains [partial source only](results/weight-only-ablation-20260911/). No Ben worker, phone lock or next-heavy-slot reservation remains. Do not resume from older proceed notices; Moritz must explicitly resume the track.

This is a separate HTP feasibility arm. It does not change or relabel `0027` CPU evidence.

## New route milestone

[`tools/qwen35_qnn_model.py`](tools/qwen35_qnn_model.py) expresses full-attention KV cache and Gated DeltaNet recurrent/causal-convolution state as graph I/O. This avoids mutable-buffer fallback and makes logical-request reset explicit. It also keeps Softplus as one edge operator and maps it to QNN's HTP-supported `ElementWiseNeuron(SOFTPLUS)` operation.

A one-layer synthetic-geometry gate compiled for `SM8550` / HTP v73 as one QNN subgraph: 151 tensor-compute operators were delegated and none remained outside QNN. The compiler finalized and serialized a 110,432-byte context; the generated PTE stays local-only. See [`results/executorch-qnn-structural-probe/result.json`](results/executorch-qnn-structural-probe/result.json).

That first result proved only architecture-route viability. The subsequent exact-checkpoint milestone is retained in [`results/executorch-qnn-exact-host-compile/`](results/executorch-qnn-exact-host-compile/): the official revision was hash-bound and converted, the explicit-state adapter matched ExecuTorch eager logits and first-layer states exactly, and the W4A16 graph compiled as four QNN subgraphs with all 4,102 tensor-compute nodes delegated. All four graphs finalized and serialized for SM8550/HTP v73. The local-only 1,994,572,968-byte PTE has SHA-256 `bfdae1c3327c954566ec0d4a5a0ee8873eb145d0921bc3f9d988a6a2557be6df`.

The first physical attempt subsequently loaded this exact PTE through the QNN HTP backend: all four contexts were created and all four graphs retrieved on DSP architecture 73 with FastRPC mappings. ExecuTorch then rejected the method before execution because the runner did not register the three non-compute `llama::fallback.out` sharding boundaries. See [`results/android-qnn-physical-viability-20260827-attempt-01/`](results/android-qnn-physical-viability-20260827-attempt-01/). No graph executed and no output or performance claim exists.

## Cheapest credible route assessment

Qualcomm's public `Qwen3.5-2B` release at revision `bd885dfceb1a1f45564aef4cd69e183085ea9a24` publishes exactly one deployment route: `GENIEX_LLAMACPP` with an Unsloth Q4_0 GGUF. The pinned artifact is 1,214,873,856 bytes with SHA-256 `cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1` and identifies its architecture as `qwen35`.

That is not a usable QNN path with the authorized installed tooling:

- QAIRT 2.49's direct GGUF builder supports `qwen2` and `qwen3`, but not `qwen35`.
- QAIRT separately dispatches `Qwen3_5ForConditionalGeneration` to an HTP ONNX builder, but that route requires a quantized ONNX graph and encodings.
- Qualcomm AI Hub Models v0.61.0 ships only README/manifest/performance/release metadata for `qwen3_5_2b`; there is no `model.py`, `export.py`, `quantize.py`, public ONNX+encodings checkpoint, or QNN context.
- The installed Qwen3.5 builder hardcodes a 4096-wide start point grouped by 256 and explicitly says to update it when variants have different dimensions. Official 2B geometry is 512 for full-attention KV and 2048 for linear keys. Applying the 4B specialization would be unsupported.

Downloading the 1.2 GB GGUF cannot change this architecture-support result, so the expensive download was correctly avoided.

## Bound frontend contract

The pinned official tokenizer/template was reconstructed independently. With thinking disabled, canonical short/medium/long prompts contain 174/597/1926 tokens and all fit a 4096-token context with the 2048-token ceiling. Rendered prompt and token-ID hashes are in [`protocol/experiment-contract.json`](protocol/experiment-contract.json) and [`results/support-assessment/result.json`](results/support-assessment/result.json).

## Physical execution milestone

[`results/android-qnn-physical-viability-20260827-attempt-02/`](results/android-qnn-physical-viability-20260827-attempt-02/) retains the bounded physical execution evidence. The exact route ran all four graphs for each of 174 prompt tokens, with 696 QNN graph starts and 696 status-`0x0` completions. Detailed ETDump data records HTP-v73 RPC, accelerator-cycle, and four-thread HVX observations. The single request took 326.170 seconds; this is viability timing only, not a loaded-route benchmark distribution.

The authorized one-token output was ID 0 (`!`), whereas pre-PTQ host calibration over the same prompt ended at ID 21365 (`Given`). Because a one-token punctuation output cannot support the narrow sanity check, `looks_sensible` is null. No campaign or retry is authorized.

A lower-retention two-process host replay in [`results/host-w4a16-qdq-output-diagnosis/`](results/host-w4a16-qdq-output-diagnosis/) produced W4A16 QDQ argmax token 760 (`The`). PTQ changes the top token materially, but it does not reproduce physical token 0 and therefore is not a complete explanation.

[`results/host-qnn-broadcast-divergence-localization/`](results/host-qnn-broadcast-divergence-localization/) locates the first mismatch at token position zero: layer-0 convolution state still matches QDQ, but recurrent state is corrupt before cross-token transport or later layers. A tiny W4A16 repro showed that QNN wrote only 16 of 128 implicit outer-product values. Explicitly expanding operands restored all values, recurrent-state cosine 1.0, and final-logit maximum error `2.96e-5`.

## Exact repaired-PTE milestone

[`results/exact-qnn-explicit-broadcast-host-validation/`](results/exact-qnn-explicit-broadcast-host-validation/) binds the revised 1,994,754,552-byte PTE. All 4,210 tensor-compute nodes are delegated. QNN-x86 first-token validation improves layer-0 recurrent-state cosine from 0.0064 to 0.999829 and reduces the logit maximum from a 39,209-way tie to one unique value. Overall first-token logits still differ from QDQ, so this is repair validation rather than complete numerical equivalence.

## Repaired-route physical milestone

[`results/android-qnn-physical-viability-20260828-attempt-03/`](results/android-qnn-physical-viability-20260828-attempt-03/) binds the one authorized physical check. All 696 expected QNN graph calls completed on HTP-v73 and the runner exited 0. The single generated token was ID 1206 (`To`). This is no longer the obvious token-0 corruption, but it does not match the QDQ token and is not a sentence-level useful-output or campaign claim.

## HistogramObserver host precision milestone

[`results/host-histogram-precision-20260910/`](results/host-histogram-precision-20260910/) retains the exact W4A16 candidate compile and sequential same-position QDQ/QNN-x86 comparison. Four QNN subgraphs retain all 4,210 delegated nodes with zero tensor-compute fallback. All 24 hidden cosines improve; layer-23 hidden cosine reaches 0.971446 and final-logit cosine reaches 0.947168. Each route uses its own QDQ reference, so this is improved internal agreement, not equivalence to the original float model. Rejected precision variants and resource-interrupted attempts are retained, not discarded.

## Saved-QDQ replay helper readiness

[`results/saved-qdq-replay-helper-readiness/`](results/saved-qdq-replay-helper-readiness/) binds the source-only replay helper and 24 tiny synthetic tests. It enforces the exact 174-input hash/sequence and state semantics, derives output IDs from actual logits, retains per-position raw tensors and an error/interruption journal, and refuses overwrite/resume. No model archive was loaded during these tests and no real HistogramObserver full-prompt replay has run.

## Full-short host QDQ milestone

[`results/host-histogram-full-short-20260910/`](results/host-histogram-full-short-20260910/) binds the completed 174-position teacher-forced replay, journal, final tensor, and independently checked positional tensor hashes/values. The 174 intermediate raw/compressed tensors are **LOCAL-ONLY**: their migration paths are mandatory retention inputs and Git hashes cannot reconstruct their bytes. Token `You` is not a generated response or accuracy evidence.

## QNN trajectory source readiness

[`results/qnn-trajectory-helper-readiness/`](results/qnn-trajectory-helper-readiness/) binds the source-only 73-output trajectory helper, durable own-state checkpoints, and independent deadline/resource supervisor. Thirty tiny synthetic tests cover actual positions/masks, 48-state carry, explicit continuation, reference/hash failures, raw/error retention, and termination/reaping. No real QNN/model load occurred. This measures accumulated own-state drift, not same-state operator error; a full 174-input x86 trajectory is estimated near 5.8 hours, beyond a 7200-second invocation.

## Four-position QNN-x86 trajectory

[`results/host-qnn-trajectory-prefix-000-003-20260910/`](results/host-qnn-trajectory-prefix-000-003-20260910/) retains all four complete 73-output bundles and 48-state checkpoints losslessly, paired QDQ logits, comparisons and cleanup. The segment completed under its 900-second budget with no resume/follow-on. Prefix cosines are 0.947168, 0.679220, 0.784361 and 0.890331; the first argmax divergence is at position 2. This is accumulated **own-state** drift, not same-state causal localization. The same-state inventory binds existing QDQ position-0 outputs to the exact accepted PT2/input/reset configuration and confirms their logits match the full replay's position 0 exactly.

## Position-1 control input/readiness

[`results/controlled-position1-readiness/`](results/controlled-position1-readiness/) retains a materialized **QDQ-origin** 51-input position-1 pack, lossless hashes, independent data checks, and 23 synthetic tests for the dedicated single-call driver. No new model call occurred. The missing full-replay state-byte assumption remains explicit. Exact same-pack attribution would use an optional ONE QDQ position-1 validation call, then a separately reviewed QNN call on the same pack; neither is a 174-token replay or own-state resume.

## One-call QDQ position-1 validation

[`results/controlled-position1-qdq-20260910/`](results/controlled-position1-qdq-20260910/) retains the single QDQ position-1 call on the reviewed 51-input pack. All 73 outputs are finite, inputs were unchanged, and logits are bit-identical to historical position 1 (argmax 198, max/mean absolute error 0). The raw FP32 cosine slightly exceeds 1 from reduction rounding and is not treated as above-perfect agreement. This supplies a real same-pack QDQ reference for a later QNN control; no paired QNN call or full-state byte-identity claim follows yet.

## Paired position-1 control and saved-data decomposition

[`results/controlled-position1-paired-qnn-20260910/`](results/controlled-position1-paired-qnn-20260910/) retains the one QNN call paired with the accepted same-pack QDQ reference, all three 73-output bundles, and a vector—not scalar—decomposition. Runtime logit cosine is 0.887994 versus the original own-state 0.679220. Both current-call and prior-state-effect vectors are nonzero; the historical-reference shift is zero. Layer-0 saved outputs already differ, with later hidden discrepancies accumulating. A retained convolution-history value changes in QDQ while QNN near-preserves it; this is not proof of QNN corruption, causality, or FP32 superiority.

## Convolution-history source metadata audit

[`results/conv-history-encoding-audit-20260910/`](results/conv-history-encoding-audit-20260910/) explains the observed QDQ history value using one saved graph-JSON member and scalar arithmetic only. The common value 23.721895 first clips at the **input** ceiling 22.131834, then requantizes to 22.131550. The **final** output ceiling is 23.721895, not 22.131550. Existing logs construct an input Quantize node; the actual optimized QNN encoding path remains unproved. No whole-model load, weights/constants read, compile or runtime call occurred.

## Tiny boundary probe preparation

[`results/conv-history-probe-readiness-20260910/`](results/conv-history-probe-readiness-20260910/) retains three weight-free CPU references and all independent scalar-oracle tensors. There are **three encoding domains and four full-chain Q/DQ pairs** (history, projection, concat, output); output-only has one pair and aligned has four. All 73,728 output values match their scalar oracles exactly. Pre/post-pass and pre-Compile QNN-wrapper getter hooks have mock coverage only. No QNN import/compile/runtime or full-model load occurred; the proposed 120s compile/60s runtime/240s total per case is not a release.

## Real tiny-QNN adapter readiness

[`results/conv-history-native-adapter-readiness-20260910/`](results/conv-history-native-adapter-readiness-20260910/) adds the real lazy adapter and external one-case guard, with explicit release binding, emitted-kernel/fallback checks and raw-first output retention. Native binding/API introspection and actual tiny CPU exports passed; no manager construction, backend initialization, QNN compile/forward or full-model load occurred. New native-aware hooks handle actual datatype codes and OpOverload metadata; the initial CPU metadata-serialization failure is retained. Native tensor getter/compiled behavior was untested at this readiness milestone; it did not authorize execution.

## First native full-chain observation

[`results/conv-history-native-fullchain-20260910/`](results/conv-history-native-fullchain-20260910/) retains the separately approved one-compile/one-forward host-QNN case and all64 metadata taps. Both early and emitted-plan checks show no ExecuTorch tensor fallback. All24,576 output values are finite; the selected value is23.721897 versus full-chain oracle22.131550. All other values agree with full-chain within1ULP, whereas output-only/aligned differ at all6,144 slot0 values. Both input Quantize wrappers and allthree exact scale/offset domains remain present beforeCompile, so neither global output-only behavior nor frontend omission is supported. Finalized SDK behavior and full-model/physical causality remain unknown. Backend work stopped after this case.

## Frozen-PTE input sweep readiness

[`results/conv-history-sweep-readiness-20260910/`](results/conv-history-sweep-readiness-20260910/) retains39 labelled input values across78 duplicated channels plus the original outlier, full scalar-stage traces and one CPU forward. All24,576 CPU outputs match the fullchain oracle exactly. Decoded endpoints and actual code-clipping onset are bracketed separately; lower-side direct-output/final-range confounds remain explicit. A runtime-only adapter binds a new pack/request to the unchanged firstcase PTE/context and zero-fallback/source receipts. That preparation milestone performed no export, recompile or native call; its historical NOT_APPROVED template is unchanged. A separate runtime-only release produced the outcome below.

## Frozen-PTE native sweep outcome

[`results/conv-history-native-sweep-20260910/`](results/conv-history-native-sweep-20260910/) retains the separately released0-compile/1-load/1-forward host sweep. All24,576 outputs are finite and inputs unchanged, but fullchain numerical equivalence is false. All39 paired rows are bit-identical; all24,498 untouched output positions, including the original anchor, exactly match firstcase. The single-outlier result was specific to the first fixture: the sweep also shows in-range/half-step discrepancies around one output step, no observed transition across the sampled scalar history-clipping onset, rising upper outputs rather than the scalar saturation plateau, and no universal output-only match. Lower-side final-range/clipping confounds remain explicit. Full scalar-stage/array analysis is saved-data-only. Both runtime/controller groups were reaped; no further native/model/phone call is released.

## Offline persistent-state range audit

[`results/persistent-state-range-audit-20260910/`](results/persistent-state-range-audit-20260910/) maps all48 Histogram QDQ state interfaces and five saved p0/p1 output bundles, with no model/weight/native calls. It distinguishes18 recurrence/18conv replacements from6K/6V new-token insertions, and18 shape-only references from numerical consumers. Fifteen domains are identical;29 decoded intervals overhang the next-input range, but only27 output-code grids would clip. Each p0 bundle has11 would-clip transported values across8conv/K/V states; controlled QDQp1 has1 and each QNNp1 set has3. No sampled recurrent value predicts code clipping. These are offline scalar compatibility calculations, not observed SDK clipping or logit causality. Alignment candidates are hypotheses only.

## Persistent K-cache boundary source investigation

[`results/persistent-boundary-source-design-20260911/`](results/persistent-boundary-source-design-20260911/) traces affected K state3 and same-layout control state15 without model/SDK calls. Their incoming cache domains differ from the wider returned-key/Cat domains. Float host insertion/buffer binding is separate from submitted graph Quantize/Dequantize/Convert declarations. Crucially, `UpdateQnnTensorMeta` copies only an id and post-Compile getters do not expose internal finalized encodings; restored context metadata describes public I/O. Actual selected-state native conversions remain unobserved. A single paired, weight-free K-cache consumer probe is designed but not prepared or released; it is not a repeat of the Conv sweep or a full-model causal test.

## Paired K-cache consumer host result

[`results/k-cache-boundary-probe-20260911/`](results/k-cache-boundary-probe-20260911/) retains the first completed weight-free paired consumer: one compile/one load-factory call/one forward, a97,904-byte PTE and oneQnnBackend delegate/zeroET KernelCalls. K3 returns10.02899265 versus fullchain6.85391617; unequal-domain K15 returns1.00014794 versus fullchain0.99984717. All4,194,304 outputs are finite, but only three are nonzero; near-Cat-only agreement is limited to this sparse fixture. Pre-Compile cache Quantize wrappers remain present. Actual execution is **x86-host HtpProvider/RouterX86/libnative**, with the log selecting **v79 despite requestedv73**—not physical Android HTP. No internal-node deletion or full-model/logit-cause claim follows. The factory-load timer is not backend-ready setup. First outcomes, all raw arrays and cleanup are retained; no host retry.

## Same-PTE paired consumer on physical v73

[`results/k-cache-v73-20260911/`](results/k-cache-v73-20260911/) retains one actual SM8550/v73 standalone forward after Janek's app-priority handoff, with unchanged PTE/input bytes and zero warmups. RouterFastRPC, exact V73Stub loading, DSPgraph73, successful transport/graph execution and context free are retained. All4,194,304 output values are finite and **every device output byte equals the host result**. This fixture's mismatch is therefore not solely a hostlibnative-v79 observation. Its K3 native anchor is also much closer to plain float concatenation than to narrow fullchain QDQ, so forcing the clamp is not a demonstrated FP32 repair. Internal finalization/full-model causality remain unproved. A preflight-only Room-binder false positive was preserved and corrected; it performed no staging/forward. The successful slot released its process, private remote root and fullphone.lock without app/data changes.

## Current next step

1. Keep physical PTE `23ac8abd…d2c506` and phone preflight unchanged; the 73-output diagnostic PTE is not compatible with the current 49-output Android runner.
2. The audit, source investigation and paired host/physical-target consumer comparison are complete. No identical rerun is needed. Further work must discriminate full-model FP32 fidelity or a supported quantization-semantics change, not infer a model fix from this sparse consumer. Routine phase approval waits are removed; shared host/device scheduling and evidence safety remain required.
3. No ADB or staging without a new explicit Pi phone slot. Full QNN/physical drift and one-token-only interpretation remain campaign-readiness boundaries.
4. Only after agreed fidelity and state-isolation gates may chunked prefill and the fixed 1+5+5+5 campaign be promoted.

GenieX llama.cpp NPU metrics, the shipped 4B HTP example, direct-Hexagon output without QNN, and CPU-only text output are not substitutes for physical QNN/HTP provider proof.
