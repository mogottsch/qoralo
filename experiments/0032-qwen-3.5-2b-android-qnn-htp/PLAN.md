# Plan: Qwen3.5-2B QNN/HTP

## Status

Active. QNN-x86 own-state positions 0–3 completed but exposed substantial drift: position-1 cosine 0.679220 and first argmax divergence at position 2. Full fidelity and current-call versus feedback attribution remain unresolved. The paired identical-input QNN call completed and exposes both residual current-call discrepancy and prior-state effects. Saved data shows a QDQ conv-history value change where QNN near-preserves the input; no individual operator or FP32-correctness claim yet. Physical baseline unchanged.

## Completed

1. Kept `0027` immutable and created independent `0032` ownership.
2. Re-verified the canonical Android LLM protocol and workload hashes.
3. Bound the official Qwen3.5-2B revision, hybrid architecture geometry, tokenizer, template, and canonical 174/597/1926-token prompt inventories.
4. Audited the public Qualcomm release and QAIRT 2.49 support:
   - only a pinned `qwen35` Q4_0 GenieX llama.cpp artifact is public;
   - direct installed GGUF conversion does not support `qwen35`;
   - installed ONNX HTP factory dispatch exists but requires absent quantized ONNX+encodings;
   - public QAIHM v0.61.0 has no 2B model/export/quantize implementation;
   - installed Qwen3.5 specialization hardcodes a 4096-wide start point incompatible with 2B geometry.
5. Stopped before a pointless download of the public Q4_0 artifact when no QNN route existed, an authenticated service job, or phone access.
6. Reopened conversion through public ExecuTorch 1.2 Qwen3.5 support and its Qualcomm QNN delegate.
7. Implemented explicit graph I/O for full-attention KV state and Gated DeltaNet recurrent/causal-convolution state, plus an HTP Softplus visitor.
8. Compiled a tiny one-layer Gated DeltaNet graph as one SM8550/v73 QNN subgraph with 151 delegated tensor-compute nodes and zero tensor-compute fallback. Retained the compiler-finalize/context evidence and kept generated QNN artifacts out of Git.
9. Downloaded and hash-bound the exact official revision outside Git, converted it with ExecuTorch v1.2.0, and matched the pinned eager implementation exactly for logits and state transitions.
10. Calibrated W4A16 PTQ on the canonical short prompt and compiled the exact 24-layer model as four SM8550/HTP-v73 QNN subgraphs. All 4,102 tensor-compute nodes were delegated, all four graphs finalized with status `0x0`, and the hash-bound PTE remains outside Git.
11. Cross-compiled a single-request Android arm64 runner for the exact 51-input/49-output PTE ABI. It performs greedy token generation and explicit KV/recurrent/convolution state advancement, but remains not campaign-eligible.
12. Ran one explicitly authorized bounded phone attempt. Exact local/remote hashes matched; physical QNN HTP v73 initialized and loaded/retrieved all four exact contexts through FastRPC. Method loading then failed before execution on three missing `llama::fallback.out` identity boundary registrations. No retry occurred, and root/process cleanup was verified.
13. Whole-archive linked ExecuTorch's pinned non-compute `llama::fallback.out` implementation, cross-compiled the Android runner, verified the registration name is embedded, and hash-bound the revised binary in the guarded phone script—all host-only.
14. Ran the one authorized retry. All 696 expected QNN graph calls completed with status `0x0`; ETDump proves HTP accelerator cycles, RPC time, and four HVX threads per graph call. The route produced token 0 (`!`) rather than pre-PTQ host-reference token 21365 (`Given`), and scoped cleanup was independently verified.
15. Preserved the complete physical evidence with lossless compression and verified raw-hash recovery, then replayed the exact W4A16 PT2E QDQ graph in a separate lower-retention host process. QDQ produced token 760 (`The`), proving PTQ changes the top token but does not by itself explain physical token 0.
16. Ran the exact deployed PTE through QNN's x86 backend at token position zero and localized the first large mismatch to layer-0 recurrent state while convolution state remained aligned. A tiny repro confirmed implicit outer-product broadcasting wrote only 16/128 values; explicit static expansion restored full state and near-exact logits.
17. Recompiled the exact 24-layer W4A16 route with 120 delegated explicit expands and zero tensor-compute fallback. Revised-PTE QNN-x86 validation restores layer-0 recurrent cosine to 0.999829 and removes the 39,209-way logit saturation. A full simulator prompt is impractically slow and stopped after 30 tokens at one hour.
18. Ran exactly one separately authorized repaired-PTE physical check. All 696 HTP graph calls completed and token 1206 (`To`) replaced the unrepaired token 0 (`!`), but it does not match host QDQ token 760 (`The`). Cleanup was independently verified before priority transferred away.

19. Completed a fresh guarded HistogramObserver hidden-diagnostic compile after retaining the app-priority interruption. Four QNN subgraphs have zero tensor-compute fallback. Sequential position-zero QDQ/QNN-x86 comparison improves all 24 hidden cosines, final-logit cosine 0.433603→0.947168, and agrees on argmax 198. Rejected MatMul/float/FP16/symmetric branches remain documented.

20. Finished the saved-QDQ helper with 24 synthetic-only tests for exact inputs/masks/state transport, computed logits/argmax, raw partial/error retention, signals, and no overwrite. No model archive was loaded; helper review and heavy-slot rotation are still required before real replay.

21. Completed the accepted 174-position HistogramObserver QDQ replay under a 7200-second host guard. All logits/state-update counts and positional tensor hashes/top values were checked. Bound final token 2523 (`You`) to the pinned tokenizer as interpretation only; retained the full journal/final tensor in Git and all intermediate bytes in mandatory local migration storage. Process reaped and disk-backed scratch empty.

22. Prepared the source-only 73-output QNN-x86 trajectory helper with 48-state carry, exclusive raw/state checkpoints, explicit prefix-bound continuation, independent runtime/pressure limits, and 30 synthetic tests. No real PTE/PT2/QNN load occurred. A four-position/900-second example is review-only; full174 estimated cost exceeds a7200-second invocation.

23. Completed exactly one released four-position QNN-x86 segment from zero state in526.831s; all four outputs/state checkpoints/comparisons retained and verified. All73 tensors were finite, but argmax diverges at position2. Last checkpoint is next_position4 and was not resumed. Source-only inventory located exact saved QDQposition0 outputs for a possible position1 control; no new QDQ replay or controlled QNN call ran.

24. Materialized/hash-bound the51-input QDQ-origin position1 pack from saved position0 outputs, independently checked48 state mappings, and added a dedicated prepare/verify/single-call driver with23 synthetic tests. No new model call occurred. Exact same-pack attribution requires a separately budgeted optionalONE QDQp1 validation before paired QNNp1; historical-only comparison retains the source-lineage assumption and vector reference-shift term.

25. Completed the separately authorized ONE QDQ position1 call on the exact pack in146.954s under600s. Inputs were unchanged, all73 outputs finite, and logits exactly equal historicalp1 (max/mean error0,argmax198). Raw FP32 cosine overshoot retained as rounding, not above-perfect agreement. Result/reference hash is ready for review; no paired QNN call ran.

26. Completed ONE separately released QNNposition1 call paired to the accepted QDQ input/result. No mutation, same input digest,1 call/124.709s under300s. Cosine .887994 versus prior own-state .679220; all3×73 saved tensors finite. Saved-vector decomposition retains nonzero current/state terms, zero historical-reference shift and explicit rounding residual; no scalar cosine/norm addition. Layer0 discrepancies and neutral conv-history observations retained. No further runtime run.

27. Audited only the retained32.5MB graphJSON and existing source/logs. Exact scalar FP32 input-Q/DQ clipping to22.131834 then concat/output requantization yields observed22.131550; final output ceiling is23.721895. Existing compiler log shows inputQuantize construction, so the final QNN path remains unproved. No weights/constants/model load, compile or runtime call. Separate tiny synthetic probe proposed, not executed.

28. Prepared three tiny weight-free CPU controls with raw inputs, outputs and full scalar-oracle tensors: three encoding domains, four fullchain Q/DQ pairs (history/projection/concat/output), one outputonly pair, four aligned pairs. All73,728 output values match independent scalar arithmetic. Implemented pre/post-pass, selected-encoding and pre-Compile wrapper getter hooks;21 CPU/mock tests pass. Retained a separate venv-launch setup failure. No QNN import/compile/runtime/full-model/phone work; native delegation/hooks remain unverified.

29. Implemented the real lazy tiny-QNN adapter and single-case external guards, with release binding, early delegation plus final emitted-kernel checks, and raw-first runtime retention. Native binding/API inspection and hook installation used a manager-construction denial guard; no backend init/Compile/Run. Tiny CPU exports retain4/1/4 Q/DQ pairs, one Slice each and no weights. Preserved/fixed the CPU metadata serialization failure in new hooks only; OpOverload callables are not FXNode string names. First-case execution remained unapproved at this readiness milestone.

30. Completed the separately released first fullchain host-QNN case:1 compile/1 forward,14.819s active, zero emitted KernelCalls. All24,576 values finite; selected mismatch1.590347, but every other value matches fullchain within1ULP. Outputonly/aligned references disagree at all6,144 slot0 values. All50 graph snapshots and actual pre-Compile wrappers preserve the exact domains; both input Quantize wrappers present. Retained64 taps, native counts, raw IO/context/PTE and full logs. No global output-only/SDKdefect/fullmodel/physical verdict. Stopped native work; range-sweep proposal is source-only.

31. Prepared an immutable range sweep:39 labelled values on78 duplicated channels plus originaloutlier,40rows/35distinctFP32bitpatterns. One tinyCPUforward equals all24,576 scalar outputs; upper decodedendpoint and actual clippingonset differ. Lower stage/direct-output confounds retained. New runtime-only adapter/request reuses exact232,144BPTE/230,736Bcontext and reviewed zero-fallback/source receipts. Source/CPU/mock only; no export/Compile/native calls or execution release.

32. Executed the separately released frozen-PTE sweep:0compile/1load/1forward,5.808s controller/5.207s worker. All24,576 outputs finite and inputs unchanged;39paired rows bit-identical and24,498 untouched outputs exactly match firstcase. In-range/half-step differences (~one output step), no sampled scalar-onset transition, rising upper outputs and no universal output-only match narrow the old single-outlier interpretation to its first fixture. Lower confounds retained; independent stdlib per-stage/full-array analysis only after cleanup. Release consumed; no SDKpath/model/physical cause or follow-on claimed.

33. Completed an offline48-state range audit of retained Histogram QDQ metadata/five p0-p1 output bundles:15identical domains,29decoded overhangs but27code-grid clipping exposures. Bothp0 sets have11 would-clip values/8conv-K-V states; controlledQDQp1 has1conv value and bothQNNp1 sets3conv values. No sampledrecurrent value predicts clipping. Explicit clone-replace vsK/Vposition insertion,18shape-only uses and per-consumer/unknown records retained. No model/weights/fullcache/compile/native/phone load; alignment hypotheses only.

## Current work

1. Preserve physical baseline/preflight hashes, diagnostic artifacts, and both LOCAL-ONLY positional tensor directories listed in the full-short result. Do not clean them; copy them on migration/handover.
2. Review the offline48-state range/transport audit and bounded alignment hypotheses. No model/encoding changes, calibration, compiler/native or phone release. Runtime-only sweep release stays consumed; APP holds first physical priority.
3. Do not use ADB or the phone without an explicit scheduled slot. Host teacher-forced completion is not QNN/physical fidelity or a campaign authorization.
4. After agreed fidelity follow-up gates, validate chunked-prefill state semantics/delegation and loaded-route reset/isolation before the canonical campaign.

Do not use CPU fallback, borrow the 4B config, relabel direct Hexagon/GenieX evidence as QNN, or publish before the complete route satisfies the benchmark contract.
