# Frozen-PTE range sweep readiness — no native execution

**Source, one retained tiny CPU reference forward, and CPU/mock regression tests only.** This does not extend the firstcase's native execution permission. No QNN SDK/native API was imported, no QNN backend/context was initialized, no compiler or native load/forward ran, and no model or phone was accessed. Existing firstcase/physical evidence is unchanged.

## Immutable value pack

`pack/` contains complete new history/projection inputs, per-value scalar stages, three full analytical oracle arrays and one actual CPU fullchain output. Four Q/DQ pairs and the same three encoding domains/topology remain unchanged. No export or recompilation is needed for inputs-only variation.

- **39 labelled sweep values**, duplicated in channels `0..38` and `3072..3110` at history slot3 / output slot2.
- Original channel6053 outlier retained: **40 rows / 35 distinct FP32 bit patterns**, counting negative zero separately. Boundary triplets intentionally overlap; labels are not independent unique values.
- All other history slots/channels and all projection bytes are unchanged from firstcase.
- One CPU forward, four math threads, **24,576 finite output values**, byte-equal to the independent fullchain scalar oracle. Its hash is `e3828c763bd4a3006a71991193bd7b0062cb4ec36e2bc8e42f1ba2628226d09f`.
- Output-only/aligned arrays are scalar predictions on the new inputs, **not additional CPU/native executions** and not explanations of an observed SDK path.

The table retains each stage's scaled FP32 value, unclamped integer code, clamped code, clipping flag and decoded output. Three stages lie on the history branch; projection supplies the graph's fourth Q/DQ pair.

| Boundary | Exact FP32 value | History code before clamp |
|---|---:|---:|
| Upper decoded endpoint | 22.131834030151367 | 65535 |
| Last value before upper code clipping | 22.13222885131836 | 65535 |
| First value with upper code clipping | 22.132230758666992 | 65536 |
| First lower-side value with code clipping | -29.8638973236084 | -1 |
| Its inward FP32 neighbor | -29.863895416259766 | 0 |

Decoded range endpoints and actual code-clipping onset are different. The sweep includes both their FP32 neighbors, nominal half-step estimates, in-range anchors/ordinary rounding boundaries, upper-gap values inside the final output range, and lower-side controls. Lower controls are confounded by the final range: being below its decoded minimum does not automatically mean the integer code is clipped. In the saved fullchain lower-onset trace, history clips but concat/output reach code0 without another clipping event. The direct-output prediction is recorded separately; do not merge those paths.

## Runtime-only adapter and proposed release

`tools/conv_history_sweep_runtime.py` has source-only `prepare-request`/`verify-request` modes and a separately gated one-case executor. **There is no Compile/export branch.** Preparation imports neither Torch nor native ExecuTorch APIs; tests check this in a separate process.

The future request binds:

- Pack manifest `422726849aabe269ee6c18c06f16eee7ca5dca2815600ca2f3bc0a44314e4225` and every input/oracle file, independently reconstructed before any load.
- The **same 232,144-byte PTE**, SHA `0170b6a2ae96759b36722f05daf8d0925f14b4da57968806b6602008c05d69c3`.
- Its **same 230,736-byte context**, SHA `33ba1075e4b4a31db22d47f6cf9b7d7d645975d8bab11907e0ada01244a2cf1f`.
- Reviewed early delegation, final emitted zero-KernelCall/QnnBackend receipts, original source/binding stack, and new adapter source hashes.
- Additional prospective portable-runtime/SDK file pins. These were not all recorded by firstcase and **do not retroactively prove historical binary identity or enumerate every dynamic dependency**.

The context and PTE remain LOCAL-ONLY at their original paths in `pack/frozen-route.json`; they were read/hashed, never loaded or copied into Git. Migrate their bytes and the protected old CPU exports; hashes alone are not replacements.

Proposed limits are **zero compiles, at most one load and one forward**, runtime guard60s, overall active ceiling90s, termination grace20s, four threads, nice15/ionice2:7 and owned disk scratch. The executor propagates external STOP and uses the existing independent PSI/memory/deadline/TERM/KILL/reap guard. No retry, resume or automatic follow-on. A fresh runtime load of the same PTE is not proof of loaded-route reuse or conversation-state isolation.

The worker gates the logical FP32 ABI before forward, saves all returned raw tensor bytes before interpretation, retains inputs before/after, and preserves errors/partial data. Nonfinite output is retained and classified as nonfinite; collection completion does not mean numerical equivalence. Injected transports/runtimes are explicitly mock, not native provenance. Internal SDK callback counts remain unknown until actual logs exist.

Request SHA-256 is `dd7e107a6ee22c8793fc43bb76eed6430bd9b5d0b1fdae39b6b0218ce2df1cc1`.

`request/release-template.json` is **NOT_APPROVED**. A new explicit approval must bind the exact request digest and a fresh output directory. The consumed firstcase request/release cannot authorize this pack. Do not invoke execution or the internal worker during readiness review.

## Validation

All **206 tests passed** in default unittest discovery without `PYTHONDONTWRITEBYTECODE`, under the external120s guard (42.845s observed). This includes11 new source/scalar tests,15 new fake-runtime/transport tests and the extended38-test evidence contract. Coverage includes actual FP32 onset bracketing, unchanged non-sweep bytes, same PTE/context receipts, unauthorized/old/mismatched releases, raw-first nonfinite/mismatch/mutation/error retention, one load/forward, no retries, STOP propagation and active deadlines. Source-only import/metadata-validation paths are checked in fresh processes for absence of Torch/native imports; CPU-reference mode intentionally imports Torch. No cache appeared under immutable evidence.

All five supervised preparation/test workers were reaped; owned scratch is empty. Complete commands/logs/guard reports are retained under `validation/`; `cleanup.json` records the final checks. CPU/mock regression operations are separate from the single retained CPU reference forward.

## Interpretation boundary

The firstcase's substantial mismatch was localized to its single out-of-range history input; all nonselected outputs followed fullchain within1ULP. This sweep is designed to test where behavior changes while holding the compiled artifact fixed. There are **no new native outputs yet**. No global output-only behavior, frontend omission, internal finalized path, SDK defect, FP32 accuracy, full-model causality or physical-performance claim follows from preparation.
