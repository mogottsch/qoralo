# Combined playback UI-only physical result

**PASS for the eight synthetic UI cases; not a genuine generation E2E or full deployment pass.** Run `provider-app-ui-only-20260912t143635z` used the separately authorized2GiB/<42°C synthetic-only mode. The controller returned before the neural entry point.

## Tested and left installed

- Frozen candidate `6ba6a3d54c8e3e28504903a54fe314c0edc0c51de89da7512ef9f71c5ed01358`, controller-only mode commit `cfa94e4b`.
- App **`da9d015ebc69c5ee535abe6f84ccf9e07b1d16f17443b3795d2aa45086c2ee27`**.
- Test **`173e4744fb30de9d778bbe84bf81e51f38e8df31295e92becd8aa3ce20a718bd`**.
- APKs are byte-identical to the previously frozen candidate04. No production code was added to isolate the synthetic stage. All9 native libraries/provider pack bytes remain unchanged.
- Post-cleanup installed SHA-256 values match. No app data clear, model construction, model call, new AUDIO/SCRIPT/EDIT job or export.

Default384dp/font1: **4/4 passed**. Narrow320dp/font2: **4/4 passed**. These exercise real ExoPlayer with synthetic muted/silent PCM: paused restore/no autoplay, delayed chunks/tail waiting, new audio after pause, explicit resume from an old frontier, auto-resume while intent remains active, simulated sleep/focus/noisy stops, finalization without replacing the player, completed-master end/replay, and one shared session across minimize/navigation/reopen/speed/episode switching. They also exercise transcript manual-follow behavior.

Both strict transcript checks now retain the viewport exactly: default3997→3997, narrow2633→2633. Explicit Follow playback reveals the current passage again. Jens reviewed all8 hash-bound PNGs/metadata; the mini-player inset and active-text geometry issues are resolved for these synthetic profiles. This is a scoped implementation-owner visual review, not an independent Nik review.

## Preservation and boundaries

All11 existing episodes,17 historical jobs,63 episode files and other original user rows remained unchanged, including newer user history and the prior2194synthesis/recovery evidence. Original density/font settings were restored. Cleanup reported zero errors; app/test processes, provider control and owned staging root were absent; phone.lock was released.

Before the synthetic wave, available memory was3,608,392KiB and battery35.6°C: admitted by the explicit2GiB UI-only floor, not by silently changing neural admission. Neural admission remains3.5GiB; the genuine one-job AUDIO/progressive-player/Ready chain has not run.

225 JVM tests and9 controller checks passed for this freeze;1 pre-existing optional long-pack test was skipped. Debug/test APKs and release Kotlin compiled. The pre-existing `ShortProductDiagnostics.kt` Cursor `Recycle` lint diagnostic is still disclosed; no lint-pass claim.

## User navigation in this installed build

Open a completed episode to reach Player (paused until explicit Play). The down-chevron minimizes it into the top mini-player while browsing Library/Settings; tapping the mini-player reopens the same session. Transcript follows chapter/provider-passage timing where verified; manual scrolling stops following until Follow playback is selected. Old completed audio remains intact.

For new generation, Listen appears after a validated complete chunk by design, but **this synthetic wave does not prove real inference/playback concurrency, genuine TTFA or seamless Ready finalization**. Those remain pending the separate neural gate. See [the admission assessment](../../../docs/progressive-neural-admission-assessment.md); it proposes requirements, not an authorized lower-floor run.

Original negative outcomes remain in the [interim record](../README.md). Raw screenshots, inventories, DB/WAL and logs remain private; hash bindings accompany this additive result.
