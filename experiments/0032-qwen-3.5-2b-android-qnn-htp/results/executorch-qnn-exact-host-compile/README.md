# Exact Qwen3.5-2B host QNN compile

## Result

The official `Qwen/Qwen3.5-2B` checkpoint at revision `15852e8c16360a2fea060d615a32b45270f8a8fc` was converted with ExecuTorch v1.2.0, loaded into the explicit-state adapter without missing or unexpected model parameters, calibrated on the canonical 174-token short prompt, quantized with W4A16 PTQ, and compiled for SM8550 / HTP v73.

The exact 24-layer graph was split at non-compute `llama.fallback` boundaries into four QNN subgraphs. All 4,102 tensor-compute nodes are delegated; the only 71 non-delegated nodes are 68 tuple/index `getitem` nodes and three sharding boundary markers. Each of the four QNN graphs finalized with status `0x0` and serialized successfully. The local-only PTE is 1,994,572,968 bytes with SHA-256 `bfdae1c3327c954566ec0d4a5a0ee8873eb145d0921bc3f9d988a6a2557be6df`.

Before quantization, a one-token eager comparison against ExecuTorch's pinned Qwen3.5 implementation produced exact logits, first-layer recurrent state, and first-layer convolution state (`max_abs = 0.0` for all three), with matching argmax token 5328. This comparison covers both linear-attention state transitions and the full model's mixed attention stack.

## Evidence

- `checkpoint-manifest.json`: pinned official and converted checkpoint hashes; weights remain outside Git.
- `eager-equivalence.json`: exact host eager reference comparison.
- `compile-result.json`: calibration, complete delegation breakdown, compiler target, context sizes, and PTE identity.
- `compiler-proof.log`: curated SM8550/v73, QNN finalize, and context-serialization lines from the hash-bound local compile log.

## Claim boundary

This is **exact-checkpoint host AOT compiler evidence**, not Android or physical-provider evidence. The PTE has not run on the phone. There is no physical QNN RPC, HTP timing/cycle, HVX, output-sanity, or performance claim, and the W4A16 route has not yet had its generated text validated. It is eligible for an experiment-page progress update only, not a benchmark-registry row.
