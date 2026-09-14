# Episode diagnostics and deletion — installed handoff

**Implemented, integrated and left installed after scoped non-neural validation.**
This is a feature/fixture and preservation pass, not a new neural benchmark or
proof that the SDK reports every metric on this device.

## Installed identity and navigation

- App: `bf53c566a160c018e56d19e0aac5e7f9578a6d3f168326fa82163bdcf1c7721c`.
- Test APK: `f1543993c2ff77441b3fd1e4c4fa131975a6a30bee2d347619a0adc646f3b0a4`.
- Frozen candidate07: `6d3c0f3af6dc6fb7f94c188c9f0bd33e381fc213b6485199ed5ad50bb5167f11`.
- Tested source: `012c965fa02e861d37df9130be255cb1317a310a`.
- Source integration into then-current main: `51993598`. The app source/config
  matched the tested source exactly; thirteen unrelated modified tracked files
  were hash-checked before/after and left unchanged. No push or history rewrite.

Open **VibeVoice → Library → the episode's ⋮ menu**:

- **Episode details** opens the local attempt/request diagnostics. Nothing was
  added to the main Player. Old attempts without measurements explicitly say so;
  opening details does not generate anything or fill missing statistics.
- **Delete episode** opens a confirmation naming the selected episode. **Keep
  episode** changes nothing. Confirmed deletion is irreversible and captures that
  immutable ID, not a later navigation selection. Both drafts and completed
  episodes use this action.

For active work, cancellation is cooperative at managed boundaries. Files remain
protected by cross-process leases until the worker/native teardown and matching
player release are safe. A pending deletion may therefore remain visible while a
native call is blocked. No blanket process kill or automatic model retry is used.
Deleting another episode leaves the current single player alone. Shared source
references, model packs and previously exported copies are retained.

At narrow/font2, the confirmation's long explanatory body is scrollable while
both Keep/Delete actions stay visible. The unavailable-history diagnostic is
reached by scrolling its lazy list, not by guessing that an offscreen node exists.

## What diagnostics mean

See [the implementation contract](episode-management.md) for exact boundaries.
The LiteRT-LM adapter records the SDK's last-prefill/last-decode token counts and
rates, initialization and TTFT when reported. It does not substitute words,
characters, callback counts or total KV size. Missing/invalid data is null.
Per-request wall time and setup/send boundaries are separate from SDK phase
rates; job aggregates require complete runtime-counter coverage.

TTS records setup/render/finalization/teardown and total wall boundaries. Actual
validated PCM frames, including prescribed gaps, define available audio duration.
RTF is **elapsed time / audio duration**, lower is faster. Failed/partial attempts
are labelled; non-neural publication recovery has no new-synthesis RTF. Records
are local and content-free: no raw prompts/responses/secrets or upload endpoint.

**Actual on-device SDK metric availability and new neural timing values remain
unverified.** No model was run merely to populate diagnostics. Host fixtures test
mapping/calculation/null behavior, not real throughput or DSP timing.

## Validation and preservation

Final run: `provider-app-feature-stable-20260914t140718z`.

- **9/9 Android cases passed**: exact-pair blocked-teardown guard, four owned
  feature cases at default, and the same four at 320dp/font2.
- Feature cases cover confirmation/Cancel and captured ID; another episode's
  playback remaining intact; awaited Default→Main matching closure; wrong-thread
  rejection and failed-release lease retention/retry; and unavailable historical
  diagnostics without inference. They use new cache roots and in-memory
  databases, never actual user-podcast deletion.
- **Six actual compositor images inspected: PASS** for menu, settled confirmation
  and unavailable-history details in both profiles. Focused target-app window,
  visible fixture marker, root identity and geometry are paired before/after.
  Window geometry must be stable for400ms within a bounded wait before one image;
  there is no screenshot retry loop. Raw images remain private.
- The exact APK pair's non-neural guard committed owned failure before self-only
  termination; observed stop→PID absence **60.120833ms**. This is a synthetic
  blocked-teardown observation, not in-flight QNN cancellation or a DSP bound.
- **263 JVM tests passed**, with two disclosed fixture-dependent skips (optional
  long-pack reconstruction and private15-chunk accepted-reference fixture).
  Fifteen Python pipeline checks and seven typed ProfileVerifier-cache checks
  passed. App/test APKs and release Kotlin compiled. No lint-pass claim.
- Earlier same-app `bf53…` windows also passed the eight existing player/profile
  cases and retained real-IO collector replay. Those are separately retained
  results, not claimed rerun in this final nine-case window.
- All **14 current episodes,20 jobs,183 episode files** and all other user rows
  were unchanged. All **1058 pre-existing persistent files**, including model
  packs and private benchmark evidence, retained their hashes.
- `files/profileInstalled` was captured before/after as actual24-byte data and
  bound to the APK's AndroidX ProfileInstaller1.4.0 `ProfileVerifier$Cache` format,
  schema/result values and actual app `PackageInfo.lastUpdateTime`. It was
  unchanged in the successful window. No blanket exclusion, restoration or
  invented earlier bytes were used.
- Zero model constructions/calls, new user jobs or actual user deletions.
  Captured settings were restored exactly, owned fixture caches were absent,
  app/generation/probe/test processes were absent, cleanup errors0, and the full
  phone lock was released. Post-cleanup installed hashes were verified.

## Original failures and inherited boundaries

Original attempts remain private and are not retroactively passed:

1. The initial narrow test tried to find an uncomposed lazy item. The repair
   scrolls the container to the node and retains the exact visible-text assertion.
2. Opportunistic progress-based capture produced no feature images. Explicit
   fixture captures replaced it.
3. Compose PixelCopy captured the underlying Activity for popup/dialog bounds;
   those images were rejected after inspection, despite paired semantics.
4. Compose1.7.6's accessibility node provider does not implement find-by-text.
   Bounded child traversal replaced that unsupported ownership query.
5. One confirmation retained the same owner but moved69px during native-window
   settling. The strict geometry check rejected it; the bounded stability wait
   fixes capture timing without changing production UI or relaxing assertions.
6. One later invocation stopped at its first ADB visibility check while the phone
   was disconnected; zero installs/tests/data operations occurred and no blind
   reconnect loop ran.

The first install's strict full-file check flagged only the framework profile
cache; its earlier raw bytes were not captured, so that original numeric
transition is not reconstructed. Subsequent windows retain both bytes and hashes.

The [prior progressive Player handoff](progressive-player-handoff-2026-09-13.md)
remains mixed genuine-concurrency and retained zero-neural replay evidence, not a
single clean original all-controls script. Its Main/applicationLooper fixes,
3072/2648MiB owned phase policy and guarded teardown are preserved. All nine native
libraries and shared model files are unchanged. This feature validation adds no
new neural, listening, export, dark/tablet or universal cancellation claim.

See [the bounded final evidence](../evidence/episode-management/feature-stable-20260914t140718z/README.md).
