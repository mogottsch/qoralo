# Plan: Qwen3.5-2B QNN/HTP

## Status

Active. QNN-x86 own-state positions 0–3 completed but exposed substantial drift: position-1 cosine 0.679220 and first argmax divergence at position 2. Full fidelity and current-call versus feedback attribution remain unresolved. Physical baseline unchanged; a source-only identical-QDQ-state position-1 control awaits review.

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

## Current work

1. Preserve physical baseline/preflight hashes, diagnostic artifacts, and both LOCAL-ONLY positional tensor directories listed in the full-short result. Do not clean them; copy them on migration/handover.
2. Review the materialized QDQ-origin input pack/header, dedicated driver and separate single-call budgets (proposed QDQ600s then QNN300s for exact pairing). No model/QNN execution or automatic sequence until release; never relabel the pack as own-QNN resume.
3. Do not use ADB or the phone without an explicit scheduled slot. Host teacher-forced completion is not QNN/physical fidelity or a campaign authorization.
4. After agreed fidelity follow-up gates, validate chunked-prefill state semantics/delegation and loaded-route reset/isolation before the canonical campaign.

Do not use CPU fallback, borrow the 4B config, relabel direct Hexagon/GenieX evidence as QNN, or publish before the complete route satisfies the benchmark contract.
