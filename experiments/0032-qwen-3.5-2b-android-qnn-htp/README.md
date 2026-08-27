# Experiment 0032: Qwen3.5-2B Android QNN/HTP

## Status

**Active. The exact official 24-layer Qwen3.5-2B checkpoint has passed host eager equivalence and a complete SM8550/HTP-v73 QNN AOT compile with zero non-delegated tensor compute. Android and physical HTP execution remain pending.**

This is a separate HTP feasibility arm. It does not change or relabel `0027` CPU evidence.

## New route milestone

[`tools/qwen35_qnn_model.py`](tools/qwen35_qnn_model.py) expresses full-attention KV cache and Gated DeltaNet recurrent/causal-convolution state as graph I/O. This avoids mutable-buffer fallback and makes logical-request reset explicit. It also keeps Softplus as one edge operator and maps it to QNN's HTP-supported `ElementWiseNeuron(SOFTPLUS)` operation.

A one-layer synthetic-geometry gate compiled for `SM8550` / HTP v73 as one QNN subgraph: 151 tensor-compute operators were delegated and none remained outside QNN. The compiler finalized and serialized a 110,432-byte context; the generated PTE stays local-only. See [`results/executorch-qnn-structural-probe/result.json`](results/executorch-qnn-structural-probe/result.json).

That first result proved only architecture-route viability. The subsequent exact-checkpoint milestone is retained in [`results/executorch-qnn-exact-host-compile/`](results/executorch-qnn-exact-host-compile/): the official revision was hash-bound and converted, the explicit-state adapter matched ExecuTorch eager logits and first-layer states exactly, and the W4A16 graph compiled as four QNN subgraphs with all 4,102 tensor-compute nodes delegated. All four graphs finalized and serialized for SM8550/HTP v73. The local-only 1,994,572,968-byte PTE has SHA-256 `bfdae1c3327c954566ec0d4a5a0ee8873eb145d0921bc3f9d988a6a2557be6df`.

This remains host AOT evidence. The PTE has not run on Android and produces no physical QNN RPC, HTP timing/cycle, HVX, text-output, or performance claim.

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

## Current next gate

1. Use the cross-compiled single-request explicit-state runner for the bounded viability gate; its host-build and exact-PTE ABI evidence is in [`results/android-explicit-state-runner-host-build/`](results/android-explicit-state-runner-host-build/).
2. Only after Pi explicitly transfers phone priority, stage the hash-bound PTE and scoped runner under `phone.lock`.
3. Run one bounded viability request with physical QNN RPC/accelerator/cycle/HVX proof, generated-token sanity, and verified cleanup.
4. Extend the runner to reuse the loaded route across reset-isolated requests, then run the fixed 1+5+5+5 campaign.

GenieX llama.cpp NPU metrics, the shipped 4B HTP example, direct-Hexagon output without QNN, and CPU-only text output are not substitutes for physical QNN/HTP provider proof.
