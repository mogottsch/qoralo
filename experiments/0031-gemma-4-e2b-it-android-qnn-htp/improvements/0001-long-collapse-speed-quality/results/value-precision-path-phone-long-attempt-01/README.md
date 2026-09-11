# True precision-path candidate: output changes, repetition remains

**Bounded candidate validation is complete. It did not fix the exact-long
repetition failure.** This is a new result, not a revision of the accepted
canonical campaign or the previous FP16-interface candidate's byte-identical
negative. No further phone run is queued.

Run `value-long-20260911T130755Z-01`, one-use slot
`pi-gemma-value-long-20260911-a`, followed Pi's confirmed release of Ben's TTS
TEXT-load control. The frozen1929-token input, greedy sampler, max2048 ceiling,
tokenizer/BOS/config and new precision-path context were unchanged. There was one
fresh context/dialog/query, no warmup or baseline replay, no app/data change,
no hidden fallback, truncation, text repair or retry.

## Physical result and RPC boundary

Context SHA-256:
`27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd`.
Stage manifest:
`373ca1b67b3ce65920127eede27df84b2832a783aee14d934d328835bc9f0996`.

Fresh Genie initialization succeeded on SM8550 with SMART_MASK and the expected
paired graphs. The profile records1929 input/2048 generated tokens. The provider
log records16AR128+2047AR1=2063 status0 completions and one query entry/return.
No nonzero-execute, CPU-backend, runtime-fallback or cache-quantization marker was
observed. The known usesCrossAttention warning remains in the raw log.

Pi warned that Ben's earlier failed allocator/teardown had connection-reset and
SSR-dead messages. A new read-only service/CDSP sysfs snapshot was taken under
the full lock immediately before launch. Those fields were unexposed here;
**that snapshot did not prove RPC health**. Functional evidence is the subsequent
successful initialization and2063 completed executions in this run. A separate
hash-bound review found no connection-reset/SSR-dead marker in this run's provider,
stdout or stderr. No historical Ben log was used to attribute a Gemma failure,
and no backend reset or reboot was performed.

## Output and frozen repetition comparison

The9,933-byte output has SHA-256
`5e3c8bff8006912eabc16b86783d59f387d9239042d55a3f3f312914610cc5c0`.
It differs from all five accepted baseline outputs and the earlier FP16-interface
negative (`f0e9d284…7b2d`). It still repeats this paragraph through the ceiling:

> The most important trade-off is between **speed and thoroughness**. A quick answer is fast, but potentially incomplete; a deep analysis takes time, but the system must decide if the trade is worth the effort.

The exact output was reviewed: sanity is false, with severe repetition collapse.
No semantic-quality or broad model-family claim is made.

| Frozen descriptive metric | Saved baseline / previous interface candidate | New precision-path candidate |
|---|---:|---:|
| Retokenized output length |2048|2048|
| Unique4-gram ratio |0.059169|0.192176|
| Exact periodic suffix start, zero-based |478|560|
| Period length in tokens |9|44|
| Periodic suffix length |1570|1488|
| Complete cycles plus partial tokens |174+4|33+36|
| First128-token window with4-gram unique ratio≤0.25 |start83|none|

**The null128-token-window result is not “no collapse.”** A44-token repeated
paragraph does not cross this particular narrow window/diversity threshold.
The exact periodic suffix still covers1488/2048=72.66% of the output. Greater
n-gram diversity partly reflects a longer repeating unit; it is not a quality
pass. The metric was not retuned after seeing the output.

The same frozen metric source (`6084bb73…fb70`) and tokenizer (`cc8d3a0c…e0f`)
were used for saved-text retokenization, not model inference. These are not
independently logged emitted token IDs. Locations are descriptive, not causal
onset or logit/state-divergence measurements. Changed decoded text does not
establish which part of the coupled precision change mattered or prove finalized
kernel arithmetic.

## Timing and operating context

Raw Genie observations: init2,050,841us; query100,899,526us; TTFT2,366,228us;
prefill815.6607tok/s; generation20.9139tok/s. These are one engineering request,
not a warm distribution or a normalized speed comparison. First-token rate
semantics remain unspecified; normalized decode is null. The output and thermal
conditions differ from previous runs. No speed win is accepted.

The query returned normally and the2048 ceiling was reached. An independent
EOS-versus-limit enum remains unexposed/null. Battery81→80%,28.0→31.0°C, USB
powered; thermal status0→0, AP33.1→54.5°C, skin30.2→37.7°C. PSS/VmHWM and
HTP-private memory were not measured; allocation logs are not substitutes.

## Raw retention, cleanup and conclusion

All269 ADB calls were guarded by the full noninherited phone.lock lease. A live
native PID was validated. Raw pull completed before root deletion. Model,
wrapper, watchdog and remote root were verified absent; no signals were issued,
and the lock was released. The launcher saved actual exit0. Pi received the
outcome and release; Janek's later app diagnosis does not overlap this run.
All207 host/saved-evidence tests passed, and all1100 entries in the original
private controller checksum manifest were verified unchanged.

The54,110,245-byte provider log has SHA-256
`45e73f2c596153e801bccd386bc7a1f89a266d636713f46b735c6b9caca6ec91`.
Its deterministic gzip was decompressed and checked against the original bytes
and size. Full Samsung battery originals remain private/hash-bound; public data
contains explicitly labeled core-field extracts only. Originals, old result
packages and model/context/SDK binaries were not rewritten or published.

This intervention changed the long trajectory, unlike the previous
FP16-cache-interface candidate, but remains insufficient for usable long output
on this request. The earlier AR1 export was already a genuine change; its
unchanged text was not proof of a numerical no-op. This result does not disprove
every precision-related cause. Another change should be
motivated by new bounded evidence, not an automatic retry or blanket FP16
expansion. No new optimization/phone work is initiated by this conclusion.
Canonical execution acceptance/registry entries and the separate app/LiteRT GPU
work remain untouched; push/history-rewrite hold remains in force.
