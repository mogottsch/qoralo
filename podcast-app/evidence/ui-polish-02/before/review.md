# Nik independent polish-01 review — a2dc5cb

**Disposition: functional corrections accepted within the tested host/synthetic scope; CHANGES REQUESTED for completion of the gallery/visual gate.** Gallery driver readiness, remaining Paste/IME occlusion, and two test-navigation gaps prevent broad after-visual approval. No physical/native/provider/product-E2E claim is made.

## Exact identities and environment

- Reviewed source: `a2dc5cb` in isolated `/home/moritz/.cache/nik-podcast-reviews/a2dc5cb`.
- Frozen app APK: `ebdc55f903b6c0440269354610f1d7631556ad7ea6e671b1873a444cdf9fe5b0`.
- Frozen test APK: `4f32a7b423a0cfd402241f9fc98ff857e3dd4cd6ec86407266db5ff717a663e6`.
- Installed unchanged on sole `emulator-5556`, existing fg-test/API35 Google APIs x86_64 with declared ARM translation. Guest2048MiB/2cores,read-only,no snapshots,software graphics,disk-backed scratch.
- Default captures:1080×2400/420dpi/~411dp/font1.0. Narrow captures:960×2058/480dpi/320dp/font2.0. ScreenSemantics supplies its own320dp/font2 wrapper in both environments; UiInteraction uses current system conditions.
- No model packs were present; no real model/GPU/QNN/duration/wiring tests were invoked. Gallery tone and interaction WAVs are synthetic test media only.
- Prior frozen c893963 APK/test and3fd75c0 candidate/APK/test hashes were independently rechecked unchanged; see `host-and-identity-summary.json`.

## Critical functional review

1. **Draft saves / queue / lock:** SavedStateHandle keys are episode-specific; serialized Room writes use an atomic phase guard. Queued/claimed/locked input cannot be overwritten by a late draft save. Host regressions pass. Actual main-app manual Back-to-sources→Continue now preserves both typed text and review=false, with no generation action.
2. **Playback/export ownership:** callbacks/use cases receive immutable episode IDs; old player's disposal retains its owner callback. Host A→Library/B tests pass; actual synthetic Android A→B disposal test passes in both tested sizes. Export ownership is source-verified, not an actual export acceptance test.
3. **Hint cap:** chip insertion shares the2000-character policy and disables an insertion that would exceed it. Host policy plus default Android near-limit/edit/reinsert regression pass. Narrow test fails before interaction because its lazy target is not composed, not because the cap check fails.
4. **Scrub preview:** drag preview is independent of polled playback position and committed explicitly. Paused synthetic drag/hold regression passes in both sizes.

Gallery isolation is source-verified: debug-only/non-exported :ui_gallery activity; no repository/engine/job calls in gallery; fixture actions modify local state. Captured successful metadata reports the gallery process. The main-process instrumentation driver may initialize normal application infrastructure, but no jobs/models were staged and the gallery itself does not dispatch them. Release compilation passes and gallery is absent from the main manifest.

## Independent host checks

**78/78 JVM,15/15 Python**, zero failures/errors/skips. Lint and release Kotlin compilation pass, at≤2workers. No unchanged native/model preparation or full native rebuild was performed. Logs: isolated app `.local/review-evidence/{host-suite.log,python-suite.log}`. No tracked source changes were made by Nik.

## Actual Android test results

| Suite | Default-size environment |320dp/font2 environment |
|---|---|---|
| ScreenSemanticsTest |6/7 |6/7 |
| UiInteractionRegressionTest |3/3 |2/3 |

- ScreenSemantics remaining failure: Instructions line70 assumes Review script first is already displayed after clicking a hint. Manual scrolling makes the correctly labelled switch fully reachable. Keep assertIsDisplayed after intentional lazy-list navigation rather than forcing all large-font content above the fold.
- Narrow UiInteraction failure: line31 fetches Length before its LazyColumn item is composed beneath a long1990-character field. Scroll the lazy container to the matching item before fetching/asserting it. Default same test passes; no policy regression is inferred.
- Held scrub and A→B owner tests pass in both environments.

Raw stdout/stderr files and `android-test-summary.json` preserve exact commands and conditions. ADB's exit0 was never treated as instrumentation success when the JUnit output reported failures.

## Gallery collection blocker (P1)

All ten distinct requested runs are retained under `ui-nik-polish01-*`:

- Both all-frame runs stop at their first frame because `rootInActiveWindow` is null at SyntheticGalleryCaptureTest.kt:64.
- Six of eight requested IME captures fail for the same nullable root at line58.
- Only default Instructions IME and default Agent-error IME produced PNG/tree/metadata.

This is a collection-driver readiness failure, **not a demonstrated app rendering failure**. A frame-file acknowledgement plus fixed750ms does not establish accessibility-window readiness. Required correction: bounded correct-package/window/root polling, record actual window identity, revalidate after IME changes, and retain PNG plus partial metadata/error even when accessibility is unavailable. Do not inject fake semantic content or use unmerged lookups to conceal accessibility problems. Do not rerun the unchanged failing gallery.

The two successful captures were inspected:

- `ui-nik-polish01-default-instructions-ime/instructions.png`: actual keyboard visible; header/input/Create remain usable above it. Lower body content is scrollable, not all initially visible.
- `ui-nik-polish01-default-agent-error-ime/agent-error.png`: error statement and composer remain visible above the keyboard; no misleading current Changes ready card. Historical synthetic message remains ordinary conversation history.

They are valid partial synthetic evidence, not15-frame coverage.

## Confirmed manual after findings

### Fixed in tested main-app flow

- `main-library-320dp-font2.png`: Library/New episode/Settings labels are now present and the primary action is understandable; XML includes full labels.
- `main-instructions-ime-320dp-font2.png`: header/back/input/Create stay above the keyboard.
- `main-instructions-after-back-320dp-font2.{png,xml}`: typed `QA preserve my draft instructions` survives Back→Continue.
- `main-review-toggle-after-back-320dp-font2.xml`: labelled Review script first switch remains checked=false after Back→Continue.
- `main-instructions-review-toggle-scrolled-320dp-font2.*`: ordinary scrolling reaches the switch, distinguishing the test-navigation failure from inaccessible production content.

### Still broken (P1): Paste action partly behind IME

`main-paste-body-ime-settled-320dp-font2.png` and its XML show the Source text field focused after entering a short synthetic source. The dialog title is no longer under the status bar, but the lower Add source label/button remains obscured by Gboard. Label bounds end at1248px while the keyboard begins about1209px. A repeated settled observation confirms this is not merely the opening animation.

Source area: `CreationScreens.kt:153–174`, dialog max-height/inset ownership and action-row sizing. Fix without shrinking text; retain scrollable fields plus fully usable action row above IME. The no-IME comparison is `main-paste-body-no-ime-320dp-font2.png`.

## Source-only later error-preservation follow-up

AgentEditorSheet clears request immediately after a Unit-returning async onRequest; SourcesScreen dismisses Paste immediately after async onPaste. A repository queue/save rejection can lose unsent form text before it is persisted. Agent queue rejection for another active job occurs before inserting its user message. Consider success-acknowledged clear/dismiss and visible error with retained input. This is ordinary form-error preservation, not adding native retry/recovery. It was not emulator-reproduced in this pass and is separate from the two confirmed visual/capture blockers.

## Cleanup and next step

The emulator was explicitly stopped after this bounded pass; app/test were force-stopped, display overrides reset, known original font restored, owned XML scratch removed. The read-only AVD instance was discarded without a snapshot. Supervisor/review processes were absent and the shared phone.lock was free. No physical/default ADB occurred.

Review Janek's next exact driver/Paste/test-navigation correction APKs before repeating missing captures. Preserve this pass, both successful images, all eight failed capture records, and the earlier c893963 baseline. Broad eight-state visual approval, physical TalkBack/playback/export, generation lifecycle, model/audio quality, and provider execution remain unproven.
