# Strict binding for the single declared-policy host reference

The corrected phone run `legacy-prefill-20260913T125558Z-01` completed and released the phone before this validation. It supplies exactly **128 actual non-cache inputs across 16 AR128 executions**, plus **one complete raw UINT16 row-8 logit vector** captured before unchanged dequantization and sampling. All 129 payloads total **66,060,288 bytes** and remain private.

- Corrected observer stage: `7b61cf0a…0486c`; library `e2b554ca…a1e1ed`.
- Actual soft/hard AS: **12,884,901,888 bytes**, all 28 readbacks valid.
- Full 1,929 post-query IDs match the frozen history; exactly 16 AR128 status-0 completions / zero AR1.
- Genuine independent pre/post APK checks match `119e0f92…613c34` / `7ae210bf…7d4d8`; raw pull, owned cleanup and phone release completed.
- Complete QNN raw logit vector: **524,288 bytes**, SHA-256 **`7b6c6e2d755a024e59d8ac05fbe4a27e992bfa4774c2286fff85144da26bafe9`**.

## Binding, not a numerical-policy change

The new host adapter preserves the original guard and both mathematical helpers. Its three count-checked source replacements change only the owned output root, the explicit observer-stage binding and the implementation-binding manifest path. Added validation pins the exact collection, every payload and relevant raw receipt, the corrected controller/scripts, independent postflight, actual AS12 readback and row-8/before-dequantization provenance. It accepts only this run's single granted host authorization.

The original mathematical source bindings remain enforced. The actual final-DLC policy (`7fffebe9…18b59`) and original own-cache/input ledger (`db3e696f…fd3cf`) are explicitly pinned too; the reference verifies all static-array hashes before executing operators. No model arithmetic, quantization, cache update, dtype, runtime budget or dependency is changed.

The real `bind_captured_noncache` accepted the complete capture. All **128 captured input arrays / 32,768,000 UINT16 values** also matched the prepared host formulas, with zero differing elements. This is a measured comparison of actual captures, not an inference of equality from token IDs or formulas. The execution still consumes the captured bytes and evolves its **own 30 caches**; HTP-produced caches are never imported.

Saved validation used 2 GiB / 1 CPU / no swap / 90 seconds and completed in 3.324 seconds / 716.2 MiB. It executed no model and consumed no host grant. **326 regression tests passed**, including wrong grant, changed policy/source, missing postflight/release, wrong AS/stage, incomplete output and double-offset provenance rejection. The earlier passing test receipts before adding explicit policy/ledger pins are retained; `tests-02/` validates the final source.

## Execution boundary

This packet freezes readiness, not a host-run outcome. Pi already authorized the still-unused **one** conditional reference once these checks pass and the phone is released. Execution remains bounded by:

- 12 GiB RAM / 10 GiB high / 2 GiB swap / 2 CPU;
- 1,800 seconds total, 1,770 seconds work with cleanup reserved;
- 1 GiB new output disk / 64 MiB trace;
- unchanged admission and live headroom floors, no memory-lock admission.

Raw complete vectors must be retained before comparison. The reference implements the declared DLC numerical policy, **not proprietary DSP bit-exact behavior**. No success here retrodiagnoses earlier failures, proves AS was the sole cause, or establishes long-generation quality. There is no automatic retry or second host-reference grant.
