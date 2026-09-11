# Post-projection value precision: fixture and source-island milestone

**Positive preparation result. The full Gemma candidate is still in progress.**

This is a new precision-path candidate, not a rerun or relabeling of the completed FP16-cache-interface investigation. The accepted exact-long negative result remains unchanged.

## What changed

The candidate uses explicit **v1.0.0 FLOAT16 activation encodings**, not just FP16 graph inputs/outputs. The intended island starts **after the unchanged quantized V-projection**, covers value normalization, cache export/import and concatenation, and ends at the selected value MatMul outputs.

The value MatMuls also need a floating probability operand. The tested route retains the quantized probability tensor, then converts it to Float16 at the MatMul boundary. It does not silently promote the upstream probability calculation or pretend that dequantization recovers information already lost.

The full source discovery identifies:

- global value caches in layers 4, 9 and 14;
- 8, 8 and 40 MatMul consumers respectively: 56 total per AR graph;
- 71 explicit activation targets in AR1 and 74 in AR128;
- unchanged original FP16-candidate ONNX bytes, weight data and parameter encodings.

AR1's genuinely changed FP16 export is preserved. This is **not** an assertion that the prior candidate was a no-op, or that the new candidate is a wholly FP16 model.

## Evidence obtained

All cases below are single fresh host conversions/compilations. There was no model inference, generated text, phone operation or app change.

| Case | Evidence | Outcome |
|---|---|---|
| Authored AR128 control | 964-byte ONNX, CL256 / width32 | Reproduces quantized producer/export and value read |
| Authored AR128 FP16 candidate | Identical ONNX; four explicit float overrides | Float16 export/Concat and both MatMul inputs/output |
| Authored AR1 FP16 candidate | Same authored pattern at AR1 | Float16 export/Concat and both MatMul inputs/output |
| Exact-source AR128 control | Original layer4 / first value head, CL4096 / width512 | Reproduces retained quantization |
| Exact-source AR128 FP16 candidate | Same original nodes, constants, shapes and boundary inputs | Required internal DLC edges pass |
| Exact-source AR1 FP16 candidate | Original layer4 / first value head, CL4096 / width512 | Required internal DLC edges pass |
| Exact-source AR128 HTP compile | Saved compiler recipe settings; one fixture graph alias | SM8550/v73 host compilation succeeds |

The exact-source derivatives load ONNX metadata without checkpoint weight arrays. Their inputs are the original projected-V boundary, cache input and quantized probability boundary; they are not a complete attention block or complete model. The small scalar/axis constants and original node lists are retained in the preparation receipts. Source nodes are copied unchanged; no new arithmetic is substituted.

Key artifacts:

- AR128 source-candidate DLC: **13,952 bytes**, SHA-256 `75e8165099c58d5790613c3d241bc0f81ea8eabecde93bbe72ba628655e74a09`.
- AR1 source-candidate DLC: **12,616 bytes**, SHA-256 `a262d084e7b677adba88487b5778e815f800b04cf21f9922e3f40e8e9e2d6e12`.
- AR128 source-island context: **58,728 bytes**, SHA-256 `08f34ae61078363068e9c7404896618ea5132486707a14309d1f7a5b71659a8e`.

Binary artifacts stay private. `result.json` and `raw/` retain hashes, commands, raw stdout/stderr, compressed exact CSVs, encoding changes and the actual graph-edge gate observations.

## Supported dtype boundary

The installed QAIRT 2.49.40 HTP supplement and backend-aware configuration list an all-Float16 MatMul configuration. A separate FP16/quantized-weight configuration has static-weight restrictions and is not an excuse to leave a dynamic value-cache operand quantized. The coupled operand/output constraint is therefore checked explicitly.

The v1 encoding route is deliberate: the inspected v1-to-v2 conversion source discards FLOAT encodings. These fixtures use `use_quantize_v2=False`; the resulting DLC, not the requested encoding file alone, establishes the observed precision.

The source/SDK identities and document locations are recorded in `result.json`; restricted SDK files are not copied into this result.

## Bounds and validation

Each small conversion/compile ran sequentially with:

- 2 GiB `MemoryMax`, 1 GiB existing-swap cap;
- one CPU and one requested numerical-library thread, nice 15;
- 240-second systemd deadline, owned disk-backed scratch;
- complete owned cgroup cleanup; all seven units ended successfully with PID 0.

Exact-source conversions took about 4.5–6.8 seconds, with roughly 540 MiB parent peak RSS. The source-island compile took 2.93 seconds with 549,088 KiB peak RSS. These are **host preparation observations**, not inference performance. The initial authored-fixture runner did not instrument RSS; that value is null rather than reconstructed from an unavailable post-exit transient-unit peak.

Twelve focused pure-Python tests cover scoped encoding changes, unchanged parameters, coupled dtypes, graph/interface boundaries and actual-capacity guard decisions. A separate saved-CSV counterexample check confirms that the previous FP16-interface DLCs do **not** pass the new full precision-path gate. That is not another Gate B run or a replacement outcome.

The helper snapshot used by the exact-source conversions was reconstructed byte-for-byte from the later helper's unchanged prefix and checked against the SHA-256 recorded by all three runs. Both the original authored-fixture helper and the matching exact-source helper are retained separately from the later full-model gate implementation.

## What is not established

- No complete new Gemma DLC has passed the full precision gate in this milestone.
- A small compiled context does not expose or prove the precision of every finalized internal kernel.
- No numerical state, rounding, clipping, repetition behavior, speed or generated-text benefit was measured.
- The inference campaign and prior exact-long negative result are untouched.
- This is QNN research, not evidence about the app's LiteRT GPU failure.
- No Nik review, new agent, model-output repair, registry update or push is part of this result.

## Continuing work

The full candidate keeps the prior FP16-candidate ONNX graphs and changes only the declared activation encodings. Full AR conversion is sequential and subject to fresh RAM/swap/disk headroom checks, with app work taking priority. Internal DLC edges and unchanged interfaces must pass before larger compilation or physical comparison. Failures and partial output are retained; unsupported or ineffective precision changes will not be silently accepted.
