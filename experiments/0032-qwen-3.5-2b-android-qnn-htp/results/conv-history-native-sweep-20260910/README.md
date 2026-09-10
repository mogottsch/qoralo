# Frozen-PTE convolution-history sweep — first runtime outcome

**Collection complete; finite numerical mismatch.** Exactly one separately released host-QNN load/forward used the existing fullchain PTE. No compilation, retry, other pack, full model or phone access. The release is consumed; no follow-on is authorized.

## Execution and retained evidence

- Request: `dd7e107a6ee22c8793fc43bb76eed6430bd9b5d0b1fdae39b6b0218ce2df1cc1`.
- Pack manifest: `422726849aabe269ee6c18c06f16eee7ca5dca2815600ca2f3bc0a44314e4225`.
- Same **232,144-byte PTE**: `0170b6a2ae96759b36722f05daf8d0925f14b4da57968806b6602008c05d69c3`.
- Same **230,736-byte context**: `33ba1075e4b4a31db22d47f6cf9b7d7d645975d8bab11907e0ada01244a2cf1f`.
- Output: **98,304 bytes / 24,576 finite FP32 values**, SHA `3b895987f287a73f430a6ee672ccb791360fb3f631ae6e897ad06355f589b432`.
- Inputs before/after are byte-identical to the released pack. Three domains/four Q/DQ pairs, geometry and compiled artifact are unchanged.

The runtime worker1820681 exited0 after5.206708s under60s; controller1820679 exited0 after5.808014s under90s. Four math threads, nice15/ionice2:7, fresh EXT4 scratch, external STOP/PSI/memory/deadline guard and bounded20s TERM grace were used. Both processes/groups were absent and scratch empty before saved analysis. These durations include verification/import/evidence work, **not isolated inference-performance measurements**.

Logical counts are **0 compile / 1 load / 1 forward**. Separately, the retained native log reports one backend-create success, one context-create-from-binary start, one graph-execute start/done with status`0x0`, and no graph-finalize messages. No compiler stage/directory was created. Log counts are observations, not substituted for logical calls or complete internal SDK instrumentation.

`raw/` retains the exact request, bound approval, preflight/source/library/PTE identities, complete runtime/controller logs and guards, all inputs before/after, output descriptors and bytes, pack/oracles/stages, and original firstcase input/output bytes. The PTE/context remain LOCAL-ONLY at their original paths in `raw/pack/frozen-route.json`; **migrate their bytes**, not just hashes. Zero ExecuTorch tensor-fallback comes from the accepted early/final receipts bound to this same PTE; it is not a claim that host simulation performs no CPU work. Prospective runtime-library pins do not retroactively establish historical binary identity or enumerate every dynamic dependency.

## What the saved outputs show

**The earlier single-outlier finding applies only to the first fixture. It is not a general “saturation-only” explanation.** This broader sweep also shows in-range and ordinary half-step discrepancies of about one final quantization step, as well as upper-range behavior that does not follow the fullchain saturation plateau.

All **39 paired channel rows are bit-identical**. All repeated samples among the35 distinct input FP32 bit patterns also agree across positions. Input positive zero (`00000000`) and negative zero (`00000080`) remain separately retained; both produce positive-zero output in both channel ranges. These are position-consistency observations within one synthetic call, not repeated-run reproducibility or loaded-route isolation.

| Sample/region | Actual QNN output | Fullchain scalar output | Direct-output scalar prediction |
|---|---:|---:|---:|
| In-range0.5 | 0.49958908557891846 | 0.49958905577659607 | 0.5004067420959473 |
| In-range20.0 | 20.000734329223633 | 19.999916076660156 | 19.999916076660156 |
| Negative ordinary half-step “at” | -0.07931282371282578 | -0.07849517464637756 | -0.07931283116340637 |
| Positive ordinary half-step “at” | 0.08013049513101578 | 0.07931283116340637 | 0.08013048768043518 |
| Upper decoded-endpoint triplet | 22.132368087768555 | 22.131549835205078 | 22.131549835205078 |
| Upper code-clipping-onset triplet | 22.132368087768555 | 22.131549835205078 | 22.132368087768555 |
| Upper endpoint + one history step | 22.133188247680664 | 22.131549835205078 | 22.132368087768555 |
| Upper gap midpoint | 22.927133560180664 | 22.131549835205078 | 22.92713165283203 |
| Original outlier / final upper endpoint | 23.72189712524414 | 22.131549835205078 | 23.721895217895508 |
| All13 lower-side labelled rows | -29.863319396972656 | -29.863325119018555 | -29.863325119018555 |

The exact upper decoded endpoint is22.131834030151367. Actual scalar history code-clipping begins at22.132230758666992, with inward neighbor22.13222885131836 still mapping to unclamped code65535. **There is no native-output transition across that sampled scalar onset**, although its scalar clipping flag changes. Endpoint-triplet inputs, onset-triplet inputs and larger upper samples must not be conflated. Higher inputs rise rather than stay at the fullchain scalar plateau. This does not identify how the SDK computes the result.

There is **no universal output-only match**:20.0, the decoded-endpoint triplet and endpoint-plus-one/two-step samples disagree with that prediction; unchanged slot0 values also discriminate it. Output-only/aligned predictions are saved scalar arrays, not alternate native executions or native intermediate observations.

Lower-side controls remain confounded by the final output range. At the actual lower history-clipping onset−29.8638973236084, the history unclamped code is−1, but subsequent fullchain concat/output reach code0 **without another code-clipping event**. Direct quantization of this original input to the final domain clips separately. Being below a decoded endpoint does not itself imply integer-code clipping. All13 sampled lower rows share the observed endpoint approximately3ULP above the scalar final endpoint; no internal lower-path attribution follows.

### Complete-array agreement

- **24,498 unchanged output positions** (all except the78 new sweep cells, including the old anchor) are **bit-identical to the original firstcase native output**.
- Excluding all79 labelled cells, **24,497 outputs** match the fullchain scalar reference within1ULP; maximum absolute difference is5.960464477539063e−8.
- Across the complete array, fullchain has18,425 bit mismatches and65 values more than1ULP away; maximum absolute difference remains1.5903472900390625.
- Output-only/aligned each have6,184 values more than1ULP away; all6,144 slot0 values discriminate them from the native result. Numerical grouping by1ULP is descriptive, **not a fidelity acceptance tolerance**.

See [`LABELLED_RESULTS.md`](LABELLED_RESULTS.md) for every label, signed FP32 bits, exact outputs and clipping flags. `analysis.json` retains all per-channel comparisons to three final reference arrays and arithmetic differences to each scalar intermediate stage. **No native intermediate tensors were tapped in this runtime-only call.**

## Independent analysis and boundary

`analyze_saved.py` uses only the Python standard library. It checks the released pack/hash/file set, reconstructs all three full-array scalar oracles and every saved stage, verifies inputs before/after, paired/signed-zero/repeated samples, original-anchor/untouched outputs and raw/log bindings. Analysis ran only after runtime cleanup, with no backend calls. Tests use a bytecode-free source loader so immutable evidence manifests remain exact.

**41 default saved-data contract tests passed** in2.263s (2.404s guard elapsed), including complete independent recomputation, empirical-region assertions and signed-zero/bytecode-hygiene checks. The standalone analyzer completed in0.602s under its30s guard. All four supervised execution/analysis/test groups were reaped and scratch empty. The original118 firstcase hashes and48 readiness hashes/exact file sets are unchanged. The earlier206-test CPU/mock suite was not rerun: no execution/preparation helper changed, and this milestone is saved evidence plus independent analysis.

This is empirical host-synthetic evidence, not frontend omission, a finalized/fused SDK path, an SDK defect, FP32 accuracy, a full-model/logit cause, a physical run or a campaign. Persistent-state input/output encoding alignment remains an untested future hypothesis; no model/encoding change or further execution is authorized here.
