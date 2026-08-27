# Plan: Qwen3.5-2B QNN/HTP

## Status

Active. The former installed QAIRT ONNX/GGUF route remains blocked, but a separate ExecuTorch explicit-state QNN route passed a bounded structural compile gate.

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

## Current work

1. Bind and download the exact pinned official Qwen3.5-2B text weights.
2. Verify the pinned ExecuTorch conversion and explicit-state eager numerics.
3. Compile the exact 24-layer route. Use graph sharding if required by host or HTP context limits, but retain full QNN assignment.
4. Build the Android QNN runtime/runner and perform a scoped physical viability gate only after exact compilation succeeds.
5. Capture provider, RPC, accelerator time/cycles, and HVX evidence; a text response alone is insufficient.
6. Prove loaded-route reset, then run the canonical 1+5+5+5 campaign.

Do not use CPU fallback, borrow the 4B config, relabel direct Hexagon/GenieX evidence as QNN, or publish before the complete route satisfies the benchmark contract.
