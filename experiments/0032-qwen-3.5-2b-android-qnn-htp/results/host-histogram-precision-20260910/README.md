# HistogramObserver: bounded host precision decision

**Positive at input position zero; full-prompt and physical validation remain pending.** The exact pinned 24-layer Qwen3.5-2B checkpoint was recompiled with HistogramObserver activation calibration instead of MinMaxObserver. W4 per-channel Linear/Conv weights, 16-bit activations, quantized recurrence, context 4096, and the four-shard QNN route were retained. No FP16 island or CPU tensor fallback is used by this candidate.

## Same-position comparison

Both diagnostic graphs receive input token 248045 at position 0, zero recurrent/convolution/KV state, and a mask exposing only the current-token slot. Each backend is compared with **its own quantized QDQ reference**; HistogramObserver changes the reference as well as QNN encodings.

| Observation | MinMax | Histogram |
|---|---:|---:|
| Final-logit cosine, QDQ vs QNN-x86 | 0.433603 | **0.947168** |
| Final-logit mean absolute error | 1.706004 | **0.483211** |
| Final-logit maximum absolute error | 10.639919 | **2.895951** |
| QDQ / QNN-x86 argmax | 62 / 198 | **198 / 198** |
| Layer-0 hidden cosine | 0.987449 | **0.992777** |
| Layer-23 hidden cosine | 0.491839 | **0.971446** |

All 24 hidden-layer cosines improve. All 73 outputs are finite. State-a cosine improves in 22/24 layers and state-b in 23/24; **not every state or error metric improves**. For example, layer-0 recurrent-state cosine changes from 0.999829 to 0.999788, and layer-0 hidden maximum error is slightly higher. Complete curves and errors are in `precision-comparison.json`, with full source reports retained beside it.

Earlier, separately compiled layer-0 attention diagnostics showed recurrence-core cosine 0.999333 → 0.999527 and gated-normalization cosine 0.993601 → 0.996718. Those observations are retained under `prior-components/`; they are not new internal taps from the current 73-output graph. The evidence supports reducing accumulated quantization drift through activation-range calibration, not identification of another discrete lowering defect.

## Compile and execution evidence

- Candidate PTE: **1,995,463,416 bytes**, SHA-256 `7f30be3d57b601af0804cdd50dd8968e271d673b710ea249a754fcd2f4ff3fea`.
- Four SM8550/HTP-v73 QNN subgraphs, **4,210 delegated nodes**, zero nondelegated tensor compute, four successful graph finalizations.
- Diagnostic output ABI: 73 outputs (49 standard outputs plus 24 hidden tensors). **Do not stage this diagnostic PTE with the existing 49-output Android runner.**
- PTE size increased 701,424 bytes relative to the MinMax *hidden-diagnostic* PTE. It is distinct from the physically executed baseline PTE.
- Host calibration took 658.896 s; QNN lowering/compile took 417.946 s; total supervised preparation took 1,332.785 s. These durations include a different host load/thread configuration and are not a speed comparison.
- Compile, QDQ evaluation, QNN-x86 evaluation, and report generation ran sequentially. Every phase exited 0 and was reaped. Low CPU/I/O priority and sampled memory/I/O pressure guards protected app work.

`artifact-manifest.json` binds the checkpoint, PTE, PT2 QDQ archive, tensor outputs, parameters, input tokens, and source tools. Large model and tensor artifacts stay local. `compression-manifest.json` binds lossless compressed logs/resource observations and verified raw-byte hash recovery. Exact commands and environment wrappers are retained in `current/` and `reproduction/`.

## Rejected and interrupted work

- MatMul recurrence reductions remained fully delegated but worsened gated-core agreement; not selected.
- Unquantized float recurrence left **268** tensor-compute operations outside QNN. The earlier informal count of 214 was an arithmetic error; the retained operator map is authoritative.
- Explicit FP16 recurrence left 143 nondelegated layout/cast operations; rejected, not treated as harmless plumbing.
- Symmetric activations failed QNN preprocessing; no PTE or inference claim.
- The August shutdown partial full-prompt replay and September app-priority compile interruption are retained under `interrupted/`. Neither is a completed result or numerical failure. No full-prompt replay was started under the latest comparison-only release.

The exact compiler used for these experiments is committed with explicit diagnostic/experimental flags. MinMax remains the default; only `--histogram-activations --diagnostic-hidden-states` was enabled for the current candidate. Rejected switches are not approved deployment paths. Reproduction scripts record the executed attempt paths; use new output directories when rerunning, never overwrite prior attempts.

## Claim boundary and next gate

This is a host-only precision candidate, not exact numerical equivalence or text-quality evidence. The post-position173 tokens 760 (`The`, MinMax QDQ) and 1206 (`To`, physical repaired baseline) are not comparable with these position-zero argmax values. There is no full 174-token HistogramObserver result, Android HistogramObserver result, chunked-prefill speedup, loaded-route reset/isolation result, or campaign/registry claim.

Keep physical PTE `23ac8abd…d2c506` and its preflight unchanged. Await Pi release for a serial full-short HistogramObserver QDQ replay before considering another fidelity gate. No phone access or full replay is authorized by this commit.
