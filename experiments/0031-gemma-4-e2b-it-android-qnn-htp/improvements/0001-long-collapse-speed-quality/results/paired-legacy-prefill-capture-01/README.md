# Complete corrected PLE prefill capture

The single granted `legacy-prefill-20260913T125558Z-01` run used corrected stage `7b61cf0a…0486c`, library `e2b554ca…a1e1ed`, **12 GiB RLIMIT_AS / cap 1 / 300 seconds**, with unchanged model, DLC/context, LUTs and input.

Native/controller exits were **0**. Exactly **16 AR128 graphs completed with status 0; zero AR1**. The complete post-query 1,929-token history matches `3b5c04fe…52b64`.

## Complete, same-run inputs and output

- **128 actual non-cache inputs**, covering all 16 chunks: 65,536,000 bytes.
- **One full final-row UINT16 logit payload**: 524,288 bytes / 262,144 values, SHA-256 **`7b6c6e2d755a024e59d8ac05fbe4a27e992bfa4774c2286fff85144da26bafe9`**.
- Total: **129 payloads / 66,060,288 bytes**.
- The actual PLE `getDequantLogits` path captured the already-offset **row 8**, once, before unchanged dequantization and sampling. Final-step metadata records `n_past=1920`, `n_process=9`.
- Genuine selected-ID trace: ordinal 0 / token **818**. The retained profile's generated-token counter is 0; it is not relabeled to match that trace.

All 28 native AS observations read soft/hard **12,884,901,888 bytes**. Maximum recorded kernel VmPeak was **8,694,972,416 bytes**; maximum sampled RSS **205,795,328 bytes**. Neither is HTP-private memory. No sole-AS-cause or long-generation quality conclusion follows.

## Lease, identity and privacy

All **67 ADB operations** were under the full phone lease. Actual preflight and corrected postflight verified `119e0f92…613c34` / `7ae210bf…7d4d8`. Raw pull completed before owned-process/root cleanup; all owned roles/root were verified absent; no signal operation occurred. The phone was released before analysis or host execution. No replay was performed.

All input tensors, full logits and tokenizer IDs remain private and hash-bound. The public provider log is a **labeled execution/dispatch metadata extract**, excluding neural debug values. Battery files are labeled current-state extracts. The outer manifest describes the public extracts; the copied controller manifest describes the full private originals.

The strict host binding is recorded in [paired-legacy-host-binding-01](../paired-legacy-host-binding-01/README.md). The subsequent host computation completed but disagreed badly with QNN; see [paired-declared-policy-prefill-01](../paired-declared-policy-prefill-01/README.md). That disagreement is under reference-contract audit, not accepted as evidence of a QNN defect.
