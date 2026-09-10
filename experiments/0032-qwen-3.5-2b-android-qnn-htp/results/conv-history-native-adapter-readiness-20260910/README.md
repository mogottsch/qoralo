# Real tiny-QNN adapter readiness — no backend execution

**Source/preparation only.** Native Python binding/API inspection and tiny CPU graph exports occurred. No native QnnManager was constructed; no QNN backend/context initialization, Compile, portable runtime load or forward occurred. No full-model or phone access.

## Implemented adapter and one-case guard

`tools/conv_history_qnn_adapter.py` now supplies a real, lazily imported compile/runtime adapter for the fixed weight-free graphs. `tools/conv_history_native_hooks.py` extends the accepted mock hooks without changing the frozen helpers or CPU evidence from `5584283`.

The execution CLI accepts **one case only**. It requires a separate approved release bound to the case, prepared-request SHA-256, exact output directory and approval reference. Preparation does not create this permission. `release-template.fullchain.json` deliberately says **NOT_APPROVED**.

The proposed first case is `fullchain`:

- one high-level compile invocation, at most **120 seconds**;
- one portable runtime load plus one explicit forward, at most **60 seconds**;
- **240 seconds total active time**, with bounded TERM/grace20/KILL/reap cleanup;
- fresh process groups and owned disk scratch, four math threads, nice15/ionice2:7;
- case-root STOP propagation into the active phase guard, actual PSI/memory monitoring, app priority;
- no retry, resume, alternate case or implicit follow-on.

Internal native Compile callbacks are recorded, not conflated with the logical compile phase or assumed to have an exact count. The real compiler uses the pinned SM8550/v73 quantized HTP configuration, with FP16/multi-context/TagQuantIO/saver disabled. No SDK installer or activation path is used.

## Zero-fallback and artifact gates

The compiler retains native context bytes, tap summaries, delegation information and the serialized PTE before result classification. Runtime requires both:

1. an early delegation report with actual delegated nodes/subgraphs and no nondelegated tensor computation (only `getitem` plumbing is exempted);
2. an audit of the **emitted execution plan**: no called CPU kernels and all delegate calls targeting QnnBackend. Move/Free/Jump are VM plumbing; these probes have no approved KernelCall exemptions.

The runtime independently checks the PTE identity/16 MiB tiny-artifact bound and logical ABI (two FP32 inputs, one FP32 history output) before forwarding. Complete returned tensor bytes precede shape/dtype/comparison validation. Wrong ABI, fallback, mutation, interruption and errors retain evidence and stop; none causes an automatic retry.

The output-only graph may fail HTP delegation because concat/slice remain floating before output quantization. The adapter does not silently insert quantization, switch precision or allow fallback to make that control work.

## Native interface inspection — not native tensor evidence

The installed binding was imported and inspected without constructing native manager or tensor-wrapper objects:

```text
PyQnnManagerAdaptor.cpython-311-x86_64-linux-gnu.so
903,784 bytes
SHA-256 5a6c2eefd72a97d28869b4f219ee93d623c126fecf47214ffbad005083f8562f
```

The actual enum table includes UFIXED_POINT_16 = **1046** and FLOAT_32 = **562**. The new decoder handles integer values, native enum/value objects and canonical enum names. Unknown, fractional and UNDEFINED values remain unresolved rather than being treated as unquantized tensors.

These are QNN datatype codes—not PyTorch serialized scalar tags or quantization bit widths. The CPU reference uses INT32 containers for codes 0–65535. The wrapper getter API exposes **scale, QNN offset and axis**, not complete encoding-kind/bitwidth; missing fields remain null. QNN offset is not mislabeled as a PyTorch zero point.

The real Python compile API bundle was also imported under a manager-construction denial guard. Hooks installed/restored on the real pass/backend classes without any pass, wrapper builder or tensor getter invocation. Signatures, class names, counters, commands and logs are retained. This establishes interface availability, not operational compatibility or successful delegation.

## Capture provenance and missing metadata

The future released adapter captures:

- pre/post/failed pass graphs and per-consumer encoding selection;
- the actual returned operator/tensor wrappers **before Compile**;
- binding identity, dtype resolution and scale bytes for each getter record;
- native Compile entry/context bytes and optional manager-reported IO afterward.

Every tap carries native or mock provenance. Missing getters, unknown dtypes or missing optional manager IO do not fabricate encoding proof or erase outputs. Pre-Compile wrappers and manager IO still do **not** establish the SDK's internal finalized/fused graph.

Mock APIs exercise the real adapter control flow, including success, early fallback, late emitted kernels, missing taps, wrong ABI, mutation, compile/forward failure, release binding, STOP, deadline and no-follow-on behavior. Mock contexts/PTEs remain explicitly labelled mock. All **177 regression tests** passed, including **24 adapter tests** and actual tiny CPU export/JSON roundtrips. All 12 supervised attempt groups were reaped and absent afterward. Scratch contained no files; only empty owned TorchInductor directories needed removal.

## Tiny CPU exports and retained preparation failure

All variants retain the accepted geometry and scalar-reference source: history `[1,6144,1,4]`, projection `[1,6144,1,1]`, concatenate and retain the last four history slots. There are **three encoding domains across four full-chain Q/DQ pairs** (history, projection, concat, output); output-only has one pair and aligned has four.

The first CPU export itself traced successfully, but metadata JSON serialization failed: the old generic snapshotter treated an OpOverload's callable `.name` as an FXNode's string name. Its failure, source-at-failure, logs and result are retained. The fix is confined to the new native-aware serializer, with an actual tiny-CPU-export/JSON roundtrip regression in addition to mocks. It is not a QNN numerical failure.

Subsequent CPU exports passed with 4/1/4 quantize and dequantize nodes and no parameters/buffers. Each exported graph contains exactly one last-axis Slice; full-chain/aligned have 13 graph nodes and output-only has 7. No backend pass has been run on these exports.

Earlier successful preparation records remain unchanged. Final requests were refreshed after the UNDEFINED-dtype guard so their source hashes bind the final adapter. All tiny PT2 files remain LOCAL-ONLY, inventoried separately; graph JSON/text and requests are in Git. The prior complete CPU inputs, three outputs and three scalar-oracle tensors remain in the accepted `conv-history-probe-readiness-20260910` result.

See `final-request-identities.json` for exact request hashes. No request or template in this result authorizes execution. Pi must review this adapter before a separate first-case release. No model-fidelity, backend-defect, FP32-accuracy, physical HTP, Android performance or campaign claim follows from readiness.
