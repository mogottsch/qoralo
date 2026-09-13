# Final raw logits: corrected PLE legacy-dispatch observer

**Host-only build/freeze; no new phone or model execution.** The AS12 attempt completed 16 successful AR128 graphs and 128 input payloads, but its final-logit hook was attached to `getLogits(Tensor&)`. The saved runtime instead invoked **`getDequantLogits`** through the PLE legacy path. That incomplete capture is preserved separately and the host reference remains unstarted.

## Narrow source change

The existing read-only hook is relocated into the actual `getDequantLogits` method, after the original buffer-pointer adjustment and before the original `deQuantizeOutputs` call.

**The pointer already selects row 8. No second row offset is applied.** The hook writes that pointer directly, for `262144 × 2 = 524288` bytes, and records the original UINT16 grid, final `n_past=1920` / `n_process=9`, row 8, and before-dequantization/sampler provenance. All original dequantization arithmetic and calls remain unchanged.

Exactly one SDK C++ file differs. The input, mapping and allocation observers and capture header are unchanged. There is no model/LUT/dtype/sampler/null-mapping fix or AS/cap change.

## Regression through the real legacy route

The bounded C++ regression compiles the actual PLE `NspEngine::process` and `processAll`, the original legacy `runInference` entry/output sizing/final dispatch, the actual `getDequantLogits` body, and the **unchanged original dequantization template**.

Only the QNN execution loop is replaced by a synthetic backend. It supplies 128 row-distinct rows of 262,144 UINT16 values and the final 1,929-token schedule (`n_past=1920`, `n_process=9`). Both frozen config and script cap 1 are checked. The downstream sampler is an explicit fixture stand-in, not a real sampler-fidelity test or full-model run.

The test verifies:

- The old observer misses the real path; the relocated observer records exactly one BEGIN/COMPLETE pair.
- All **262,144 raw values** equal source row 8, not row 16 or another row. The row-distinct pattern detects a double offset.
- Exact UINT16 shape/grid/provenance metadata and 524,288 bytes are recorded.
- Capture is complete **before** the original dequantization, which executes unchanged **once**; the downstream sampler marker follows once.
- Raw source rows are unchanged, and original/relocated F32 outputs are byte-identical (`8ff35c3f…0f5bb`).
- With the prior input-budget counters explicitly seeded to 128 / 65,536,000 bytes (not fake input files), the final payload reaches exactly 129 / 66,060,288 bytes within the unchanged caps.

The first fixture attempt stopped before C++ compilation because its source anchor did not distinguish overloaded legacy methods. The failure and tool snapshot are retained. A full `std::vector<float>` signature resolved the anchor; the corrected fixture passed in 4.770 seconds / 355 MiB / no swap under 1 GiB / 1 CPU / 150-second limits. The full regression suite also executes this real-dispatch synthetic integration test, not just the logger helper.

## Frozen runtime and controller

- New `libGenie.so`: **11,674,360 bytes**, SHA-256 **`e2b554ca4e216f1df77c3c331b3f1295584cf030c7120cccc3b15bbce3a1e1ed`**.
- Native build exit 0 in **20.625 seconds**; service 22.558 seconds / 1.6 GiB / no swap under 4 GiB RAM / 1 GiB swap / 2 CPU / 1,800-second limits.
- AArch64 ELF, legacy-path marker and all **103** unchanged runner Genie imports verified.
- Frozen `paired-legacy-logits-stage-01`: **19 files / 4,013,564,596 bytes**, manifest **`7b61cf0a03ad93292127a7ad59e1b74ae9b61ac4e660691a0cff5a947b40486c`**. Only the observer library payload differs from stage 807.
- Same **12 GiB AS**, model/LUT/input, cap 1, 300 seconds and capture limits. All materialized control scripts are identical to the AS12 controller at the same placeholder root.

`phone_legacy_prefill_capture.py` remains plan-only without a fresh Pi-scheduled slot around Janek's priority work. It retains current APK/job/playback checks, actual AS readback, corrected postflight dispatch, full phone lease and raw-first cleanup/release. No second attempt or automatic replay is implied.

A new physical capture is still required to establish all 129 payloads. The still-unused host reference may start only after complete validated capture, strict new-observer/input binding and phone release. Earlier inputs and future logits must not be stitched together.
