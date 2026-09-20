# Chapter JSON failure: evidence notes (2026-09-20)

Two observed SCRIPT failures, both on installed build `70394e79…` (app) / `abe68ac7…` (test), which does
**not** contain the constrained-decoding or retry change. Recurrence is established; **cause is not**.

## The two occurrences

| | 09-14 `e7f43cf8` | 09-20 `ea688d38` |
| --- | --- | --- |
| Episode | `7eb30e01…` | `d56f0d17…` |
| Failed at | chapter 2 of 7 | chapter 3 of 4 |
| Error | `JSON_PARSE; 0:JSONException(cause=null,suppressed=[],sdk=null)` | identical string |
| Job wall | 122.4 s | 98.6 s |
| Prior chapters | 1 complete | 2 complete |
| Saved revision | none | none |

Per-request timing (from each job's private diagnostics; fields only, no content):

| Request | 09-14 | 09-20 |
| --- | --- | --- |
| source_notes | 13.66 s | 10.19 s |
| outline | 27.35 s | 12.90 s |
| chapter (complete) | 21.98 s | 21.31 s, 18.64 s |
| **chapter (failed)** | **43.16 s** | **23.40 s** |

## What this changes

**The truncation hypothesis is weaker, not stronger.** On 09-14 the failing request took ~1.96x the
successful chapter, which fit a run to the 4,096-token ceiling. On 09-20 it took ~1.17x the mean of its
two successful siblings. A response that exhausted the output ceiling would be expected to take
markedly longer than a normal complete chapter, and on 09-20 it did not. This is indirect: decode rate
is not constant across prompts and no token counts exist, so timing bounds nothing exactly.

**A better-fitting hypothesis for 09-20** is a normal-length response that simply was not valid JSON —
for example an unescaped control character inside the `text` string, or stray prose captured by the
first-`{`/last-`}` extraction. Both produce `JSONException` at ordinary length.

**Constrained decoding still addresses both.** A grammar prevents malformed escapes and stray prose
regardless of which cause is real, so the primary fix is unaffected by this update. The escalating
brevity retry, however, targets truncation specifically, and on this evidence it may fire rarely or
never. It is bounded and harmless, but it should not be described as the thing that fixes these cases.

## Caveat on the added instrumentation

`reachedOutputLimit` derives from `BenchmarkInfo.lastDecodeTokenCount`. In **both** jobs every runtime
counter was null — `prefillTokens`, `decodeTokens`, both rates, `runtimeInitMs`, `runtimeTtftMs`:

```text
09-20 ea688d38: 5/5 requests, all runtime counters null
09-14 e7f43cf8: 4/4 requests, all runtime counters null
```

So on this build and runtime the new flag will also be null, and **the change does not yet evidence
truncation as claimed**. Treat that claim as withdrawn until counters are seen to be non-null on device.

## Cheapest decisive next evidence

The raw response is never retained in normal operation, which is why cause is still open. The existing
opt-in `UserFailureDiagnostics` receipt path already captures `request-00N/response.txt` under an
explicit private scope, and is the sanctioned way to see what the model actually returned. That needs
its own authorized slot and owner; it is not covered by the read-only pulls done so far.
