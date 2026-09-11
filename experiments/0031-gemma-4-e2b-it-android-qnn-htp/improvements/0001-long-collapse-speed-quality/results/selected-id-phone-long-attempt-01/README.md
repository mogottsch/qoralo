# One genuine selected-ID trace: repetition without a selected stop token

**Completed and released.** One exploratory source-runtime long request captured2048 genuine, accepted-generation token IDs. **None was1,106 or50.** The visible output is byte-identical to the completed `f11df93` precision-path negative and still repeats the same paragraph. No second request, calibration, EOS/BOS sweep or precision build followed.

This is strong evidence against a missed configured/50 stop explaining **this instrumented run**. It is not retrospective evidence about the commercial runtime's unavailable selected-ID stream. Equal visible bytes do not establish runtime or hidden-state equivalence, and the internal stop-decision field remains null.

## Bound request and runtime

- Run `trace-long-20260911T150027Z-01`; actual Pi-granted, consumed slot `pi-gemma-selected-id-long-20260911-a`, after Ben's0037 HTP release.
- Readiness `c7abf0cd`; accepted-generation correlator `0e47bc18`.
- Same frozen context `27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd`, ordinary/per-layer embedding path and one text query.
- Stage manifest `07e5b1b5f1e75c20022e6f9356262fe969eadbead6f91b8017f01429c20fc2f2`.
- Source-built Genie `43b9bf47d82aaf375582c0b5631f8b032f65aeeebc5a7758cb8ea7cae5af022a`, with its matching NDK libc++. Build recipe completion and252 added transitive dependency versions are disclosed in the readiness package. **Not assumed equivalent to the supplied commercial library.**
- Fixed1929-token input, single BOS/config−1, greedy, EOS `[1,106]`, max2048. No policy changes.
- Fresh installed app/test hashes matched `e1b33f276aa7f267c778a1c3fe6c113700aa401d61472956a4769a098fcc89ba` / `060edd5f0679b79ec928319a5b1e93c1bbcbd42d775b2df05c78307ad849d0f9`. Read-only target-process quiescence checks passed before staging and immediately before launch. No app/APK/data modification or force-stop.

## Actual accepted-generation evidence

`raw/controller/raw/device/runner.stderr` contains the original observer lines, written immediately after the real sampler returns and before filtering. `trace-observations.json` preserves all records; `accepted-generation-correlation.json` binds them to the actual single BasicDialog generation.

-2048 contiguous ordinals0–2047, no malformed records, no excluded/ambiguous records; matches the actual profile generation counter.
- Actual script/config confirms no grammar, proposal/draft, batch, resume or extra query operation.
- Ordinal0 is the **first generated token after complete prefill**, not an intermediate prefill logit. Ordinal1 is the first primary decode selection. Both observe n_past1929 because the follow-on hook precedes the counter increment. Every subsequent position matches the source-defined relation.
- Actual provider completion order is16AR128 followed by2047AR1. Producing execution indices15–2062 match the2048 selected IDs.
- Actual selected-ID int32le SHA256: `8a78560be15953ec6e41bb3f20606c4572d18cc30ebe233309d344cee6d150bc`.
- No selected1,106 or50. There is consequently no ID50 continuation event to classify. Membership/later sampling remain separate from unavailable internal stop decisions.
- Normal query return and reached2048 ceiling are observed. No independent internal terminal-branch enum is asserted.

After the unchanged query/profile, the same-runtime dialog tokenizer encoded the original input into `input-token-ids.txt`. **All1929 IDs match** the frozen int32le hash `3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64`. The actual profile also reports1929, and rendered bytes/single-BOS prefixes match. This post-query tokenizer observation is not direct prefill-tensor capture.

## Visible outcome and execution

- Output9933bytes, SHA256 `5e3c8bff8006912eabc16b86783d59f387d9239042d55a3f3f312914610cc5c0`: **byte-identical to f11df93**.
- The direct selected-ID trajectory itself has a44-token periodic suffix from index560:1488tokens,33complete cycles plus36tokens,72.66% of the output. It repeats the speed-versus-thoroughness paragraph.
- The actual selected IDs also equal the pinned text tokenizer's re-encoding of this output; that equality is checked, not used to invent the IDs.
- Frozen128-token repetition detector remains null; the longer exact suffix proves repetition regardless. No detector retuning. Sanity remains false, not quality acceptance.
- One context/dialog/query, SMART_MASK, **2063 QnnDsp status0 executions**. No current CPU/fallback/cache/nonzero-execute or connection-reset/SSR-dead marker; known cross-attention warning retained. This is not a universal CPU-free or kernel-arithmetic proof.

Raw runtime observations: init1,821,857µs; query102,575,704µs; TTFT2,448,268µs; prefill788.0221tokens/s; generation20.5901tokens/s over99,417,572µs. These are one instrumented-run observation, not a speed gain. Genie first-token accounting remains unspecified; normalized decode stays null. Process/HTP memory was not measured.

Battery85→84%,28.2→31.4°C, USB powered; thermal status0→0; AP32.0→56.9°C, skin30.4→38.0°C. Full vendor battery histories remain private/hash-bound; public battery values are labeled core-field extracts.

## Retention and release

-277 ADB calls, all under the full lock with noninheritable FD; actual native identity observed, native/controller exits0.
- Full raw pull before remote-root deletion; all scoped processes/root verified absent; lock released.
- **One guarded watchdog-TERM operation returned `ABSENT` before signaling. No delivered signal was observed.** The command name alone is not evidence that TERM was sent. The sequential identity-check-to-signal boundary remains non-atomic.
-54,111,156-byte provider log SHA256 `04706bff87c532f9122667da8bb445f44101322a72db07b0866631d92a129414`, retained as verified lossless deterministic gzip. All1133 original private controller hashes verified unchanged before analysis.
-229 host/source/saved-evidence tests passed, including the actual trace, phase correlation, input parity, repetition, privacy and absent-versus-delivered signal checks.
- Local evidence only: no registry/canonical rewrite, push or external publication. Restricted model/context/runtime/SDK binaries stay private.

The remaining reliability cause is unresolved. Pi's next scope is **host-only readiness for an input-aligned known-good CPU/GPU comparison**, using effective1929 single-BOS IDs rather than adding another BOS to QNN. No additional inference is authorized by this package.
