# Experiment 0032: Qwen3.5-2B Android QNN/HTP

## Status

**Active. The bounded QNN-x86 own-state prefix completed positions 0–3, but drift remains: position-1 logit cosine falls to 0.679220 and argmax first diverges at position 2. This does not establish full fidelity or identify current-call versus feedback error. The physical baseline remains unchanged; a source-only position-1 identical-QDQ-state control is planned for review.**

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

## Current next gate

1. Keep physical PTE `23ac8abd…d2c506` and phone preflight unchanged; the 73-output diagnostic PTE is not compatible with the current 49-output Android runner.
2. Review the source-only position-1 identical-QDQ-state control plan. Use existing saved QDQ outputs to prepare the intended state input; do not mislabel it as own-QNN resume or run a new QDQ/QNN model call without release.
3. No ADB or staging without a new explicit Pi phone slot. Full QNN/physical drift and one-token-only interpretation remain campaign-readiness boundaries.
4. Only after agreed fidelity and state-isolation gates may chunked prefill and the fixed 1+5+5+5 campaign be promoted.

GenieX llama.cpp NPU metrics, the shipped 4B HTP example, direct-Hexagon output without QNN, and CPU-only text output are not substitutes for physical QNN/HTP provider proof.
