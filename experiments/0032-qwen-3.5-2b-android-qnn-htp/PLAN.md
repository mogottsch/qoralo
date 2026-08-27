# Plan: Qwen3.5-2B QNN/HTP

## Status

Active. The ExecuTorch route has passed exact-checkpoint host compilation and physical QNN/HTP context loading. The first phone attempt failed before model execution because three non-compute sharding-boundary kernels were not registered in the runner.

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

## Current work

1. Wait for a new explicit Pi phone-priority transfer; ADB and staging are prohibited until then.
2. Keep the revised runner hash and exact-PTE/runtime hashes fixed for the bounded retry.
3. Under `phone.lock`, perform at most one newly authorized physical viability retry and require actual graph execution plus provider/RPC/accelerator evidence.
4. Only after viability, extend the runner for loaded-route multi-request reuse, prove full explicit-state reset, and run the canonical 1+5+5+5 campaign.

Do not use CPU fallback, borrow the 4B config, relabel direct Hexagon/GenieX evidence as QNN, or publish before the complete route satisfies the benchmark contract.
