# Plan: Qwen3.5-2B QNN/HTP

## Status

Active. The repaired exact route physically executes through QNN/HTP and now produces token 1206 (`To`) instead of token 0 (`!`). The obvious corruption symptom is removed, but physical output still differs from host W4A16 QDQ token 760 (`The`) and campaign readiness remains unproven.

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

## Current work

1. Preserve the repaired PTE and strict phone preflight hashes.
2. Do not use ADB or `phone.lock`; no retry or campaign is authorized.
3. Keep residual QDQ-versus-physical drift and the one-token output ceiling explicit.
4. Only after a separately agreed fidelity/output gate, prepare loaded-route multi-request reset/reuse and request a campaign handoff.

Do not use CPU fallback, borrow the 4B config, relabel direct Hexagon/GenieX evidence as QNN, or publish before the complete route satisfies the benchmark contract.
