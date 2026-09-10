# Gate B — exact-long execution, unchanged repetition (negative candidate result)

Run `fp16-long-20260910T171555Z-01` used one-use slot `pi-gemma-fp16-long-20260910-a`, the exact reviewed `b43a57f` adapter, frozen long stage `047dd808…b846e` and unchanged FP16-global-value context `1d80d016…ca9f8`.

One fresh process/dialog/query completed naturally with **1,929 input / 2,048 generated tokens**. Raw provider evidence records **16 AR128 + 2,047 AR1 = 2,063 QnnDsp graph executions, all status0**, one context deserialization and SMART_MASK. No CPU-backend/runtime-fallback or cache-quantization-error marker was observed. This is bounded physical route evidence, not a universal CPU-free or uniform-integer claim.

## Decisive output result

The entire **10,027-byte** UTF-8 output has SHA-256:

`f0e9d284f679e2ae426264573bd2be16e7c1e4b190235a3511c5a92ecc097b2d`

It is **byte-identical to all five retained baseline long outputs**. Severe repetition, including occasional `<unk>` leakage, persists. Narrow sanity is false with the retained issue text. No baseline request was rerun.

The same pinned text tokenizer and frozen metric function reproduce exactly the baseline metrics:

- first qualifying128-token/four-gram diversity window starts at **index83**, ratio0.248;
- exact period9 suffix starts at **index478**, covers1,570 tokens, and contains174 full cycles plus4 trailing tokens;
- dominant word six-gram occurs215 times;
- all4/8/16-gram statistics are unchanged.

**Index83 is a threshold-window start, not an exact causal onset or internal state/logit divergence.** The selected FP16 interfaces may still retain internal quantization. This disproves a text/repetition benefit for this particular candidate/request, not every possible cache-precision cause or improvement.

## Completion, rates and operating context

The explicit2048 setting was applied and reached. The query returned normally without timeout or signal, but no independent EOS-versus-limit stop enum/event was exposed; the stop-cause field remains null with a reason.

Raw Genie profile values: create2,141,938us, query109,901,620us, reported TTFT2,469,576us, prompt rate781.25tok/s and generation rate19.1982803tok/s. First-token inclusion remains unspecified; normalized decode is null. A single observation under different thermal/run conditions does not establish a normalized speed win or distribution.

Battery went76→75%,33.0→35.7°C on USB. Thermal status0→1, AP44.2→50.8°C and skin35.3→40.8°C. Process PSS/VmHWM/HTP-private totals were not measured. Full battery histories remain private and hash-bound; public battery JSONs are clearly labeled core-field extracts.

## Retention and cleanup

The **54,108,333-byte** provider log is retained losslessly as gzip, with original SHA-256 `33ab01bb4a3bbd630533ba0e52e5aac067bbd27f446dadb9929084fdc6a2d440`. All query/output/profile/transport/cleanup evidence remains exact.

The live native PID was validated during polling. All recorded model/wrapper/watchdog PIDs and the remote root were verified absent afterward, with no signal command, raw pull preceding cleanup, and the canonical lock released. There was no retry, warmup, short request, baseline rerun or follow-on.

Use the top-level `SHA256SUMS` for public files. `raw/controller-original-SHA256SUMS.txt` is provenance for the full private original and intentionally references private battery files and the uncompressed provider log.

No further optimization, compilation, runtime/phone call or push is authorized by this result. Preserve the completed campaign and await findings review.
