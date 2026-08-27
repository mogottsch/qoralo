# Experiment 0032: Qwen3.5-2B Android QNN/HTP

## Status

**Active. The exact 24-layer route has been recompiled with explicit Gated Delta broadcasts and validated through QNN's x86 backend. The repaired PTE removes the first-layer recurrent corruption and massive logit saturation, but it has not run physically; any further phone check requires a new explicit Pi handoff.**

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

## Current next gate

1. Keep the revised PTE and phone preflight hash fixed.
2. Do not reacquire `phone.lock`, invoke ADB, or stage anything without a new explicit Pi handoff.
3. If Pi authorizes a separately bounded physical output check, preserve the same strict provider/output/cleanup evidence; no campaign is currently authorized.
4. Only after credible output fidelity is established may the loaded-route multi-request runner and fixed 1+5+5+5 campaign be considered.

GenieX llama.cpp NPU metrics, the shipped 4B HTP example, direct-Hexagon output without QNN, and CPU-only text output are not substitutes for physical QNN/HTP provider proof.
