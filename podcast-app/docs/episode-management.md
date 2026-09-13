# Episode details and deletion

This feature is developed on `nik/episode-management`, in the isolated
`.local/episode-management/source` worktree. It is not part of the separate
progressive-player validation APK until explicitly integrated and tested.

## Private diagnostics

Library episode overflow opens **Episode details**. The Player has no additional
diagnostic controls. Each attempt retains its own local JSON under
`episodes/<episode-id>/diagnostics/<job-id>.json`; no prompts, responses, source
text, titles, exception messages or secrets are written to these records. There
is no upload, export, analytics endpoint, inference replay or new model call.

- LLM requests record coordinator/job wall time, per-request total wall time,
  conversation creation and synchronous send wall time. Total request time also
  includes conversation close, response validation and observational callbacks.
- The LiteRT-LM 0.16.1 `Conversation.getBenchmarkInfo()` adapter stores exactly
  `lastPrefillTokenCount`, `lastDecodeTokenCount`, their runtime-reported rates,
  runtime initialization and TTFT, when available. A fresh Conversation is used
  for each request. It never uses `getTokenCount()` (KV state), words, characters,
  retokenized output, estimated prefill or callback chunk counts as tokens.
- Unsupported, invalid or missing counters are JSON null and labelled
  **Runtime doesn't report**. Job aggregates use total reported tokens divided
  by the sum of count/reported-rate, and require all recorded requests' counters.
  This is an aggregate of the runtime's phase measurements, not end-to-end speed.
- TTS setup covers `engine.load`; render covers chapter rendering, including
  validated chunk publication callbacks; teardown covers `engine.close` while
  preserving the owned resource guard; finalization covers master assembly and
  commit. Total wall runs from coordinator entry through teardown/publication,
  excluding queue wait. Available PCM frames determine actual audio duration at
  44,100 Hz, including prescribed segment/chapter gaps. Wall/render RTF means
  elapsed time divided by that duration, **lower is faster**.
- Failed and cancelled jobs retain a partial measured prefix. Process death can
  leave an incomplete record with no invented wall-time endpoint. The durable
  job's status is shown separately. Non-neural publication recovery is explicitly
  labelled, records publication wall time, and never claims synthesis RTF.
- Historical attempts without records stay unavailable. Records are bounded to
  512 requests / 1 MiB reads; an omitted request disables job aggregate rates.

## Irreversible deletion request, deferred safe cleanup

Every Library episode (draft, failed, generating or finished) has **Delete
episode** in its overflow. Confirmation captures the immutable episode ID and
title. Cancel changes nothing. Confirm does not use whichever episode navigation
happens to select later.

The deletion request first fsyncs an irreversible marker under
`episodes-lifecycle/<episode-id>/deleted`, outside the deletable episode tree,
then marks the episode `DELETING`. No schema migration or destructive database
fallback is introduced. The marker contains one version byte, not user content.

The coordinator, player, exports and atomic artifact writes acquire per-episode
shared OS file leases. An in-process reference counter shares one Java FileLock,
while the operating system coordinates generation/main processes. Tombstones
reject new leases and repository writes. A separate cancellation watcher cancels
only the matching coroutine; cancellation cannot interrupt in-flight JNI. The
worker's lease remains held until native teardown actually returns. A blocked
worker therefore leaves an honest pending deletion, rather than freeing files or
claiming cancellation completed. Process death releases its OS lease naturally.
No package/process kill, fallback model, new generation or model retry is used.

Queued jobs are made terminal without dispatch. Running jobs retain the global
admission slot until their worker is safe to clean up. An already authenticated
owned resource guard can still persist that exact attempt's failure while keeping
the episode tombstoned; deletion cannot disable the guard during blocked teardown.
Its independent PID/start/plan/current-lease checks remain unchanged.

`PlaybackHost.closeIfEpisode(id)` releases/checkpoints only that matching single
session; deletion of another episode leaves the current player and its lease
alone. The observer also closes a matching tombstoned session. Export holds a
lease until copying completes; already exported files are never removed.

The main application retries pending cleanup on launch and once per second:

1. Reconcile any marker left by a crash before the database phase update.
2. Try an exclusive per-episode OS lease without waiting or guessing a PID.
3. Remove only that ID's episode tree, without following symlinks. Preserve any
   source paths still referenced by another episode.
4. Cascade-delete only that episode's rows, then release the lease. Retain the
   tiny tombstone/lock inode so stale callbacks can never recreate the episode.

Any failure leaves the request pending for retry. Shared source bytes, model
packs, other episodes and private benchmark/diagnostic evidence outside the
owned episode tree remain untouched. Old controllers treating `DELETING` as an
unknown phase fail closed, rather than killing a pending native worker.

## Validation boundary

Host tests use temporary episode roots, in-memory databases, fake engines and a
bounded Python child holding an OS lock. Tests cover wrong/captured identity,
queued/running/finished deletion, blocked render and native teardown, multiple
leases, process-death lock release, restart after marker persistence, symlinks,
shared-source preservation, late callback rejection, genuine runtime-counter
mapping, missing data, gap-inclusive RTF and no synthesis rate for recovery.

`EpisodeManagementRegressionTest` is a three-case Android fixture-only suite:
confirmation/Cancel and captured ID; another-episode deletion preserving the
same muted real ExoPlayer plus matching deletion releasing it; empty historical
diagnostics without model entry. It uses new cache roots and a separate
in-memory database, never deletes a real user episode, and makes zero model calls.

Device execution, default/narrow-font2 visual inspection, final APK hashes and
tested deployment must be scheduled by Pi after the current progressive
candidate's independent validation boundary, under the full phone lock and fresh
preservation/identity checks. Host compilation is not a physical UI/deployment
verdict. No duplicate model run is needed to validate the deletion fixtures.
