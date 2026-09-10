# Nik synthetic UI baseline — c893963

## Evidence boundary

Exact source: `c893963cae681bfdada35f9bb695b177055306c2`.
Frozen app: `f61aba1664ece228ea3b0e517e574d715a55cc92d75f11b92269d44e1b0da379`.
Frozen test APK: `4cd7c1ab251e59b452db92e23a6829834c7eb7fed556f158e3979b0f04d95168`.

Single existing `fg-test` AVD, explicit `emulator-5556`, API35 Google APIs x86_64 with its declared arm64 native bridge. KVM,2048MiB guest RAM,2cores,read-only,no snapshot load/save,software graphics. No production ABI/runtime change, new SDK download, model packs, inference, physical phone action, or generated model audio. The player test uses its existing synthetic 1-second WAV. These observations do not prove Galaxy native/provider performance or production generation lifecycle behavior.

Shared phone.lock was held by the supervisor for the entire emulator ADB/test/cleanup lifecycle; emulator/ADB children did not inherit the lock. The first boot was deliberately stopped before installation because /tmp was nearly full. The test boot used owned disk-backed scratch. Both owned emulator processes have exited; the lock was free at cleanup.

## Actual test result

`ScreenSemanticsTest`, selected by exact class (not the real-runtime test), executed **7 tests:3 passed,4 failed**. ADB shell exit0 was not treated as test success; the retained JUnit text reports FAILURES.

| Method | Result |
|---|---|
| generationShowsChapterProgressAndFailClosedBoundary | Pass |
| reviewAgentAndLockKeepTranscriptReadOnlyAndConsequencesExplicit | Fail at line80: merged text lookup for Edit with agent absent; unmerged match exists |
| playerExposesTransportExportAndLyricsLikeFrozenTranscript | Fail at line107: Now playing not displayed |
| instructionsHaveOneEditableFieldHintChipsReviewToggleAndCreate | Fail at line70: Review script first not displayed |
| libraryShowsUnfinishedEpisodeAsResumableStatusRow | Pass |
| libraryExposesFunctionalPrimaryActionAt320dpAnd2xFont | Fail at line45: Create an episode not displayed |
| sourcesExposeFunctionalPrimaryActionsAt320dpAnd2xFont | Pass |

Test conditions: emulator1080×2400 at420dpi, OS font1.0; test wrapper320dp width/LocalDensity font2.0; animations disabled. Full logs/conditions: `screen-semantics.stdout`, `screen-semantics-run.json`.

Timed screenshots mostly captured activity startup/teardown between fast tests. **Blank contact-sheet frames are not an app-render failure.** The real app renders normally when held open. Assertion failures alone do not establish whether an offscreen scrollable component is unreachable; gallery/manual checks are needed. Do not blindly switch to unmerged selectors if the actual accessibility label/action is wrong.

## Confirmed manual findings

Manual narrow conditions:960×2058px at480dpi =320dp width, OS font2.0, Gboard visible where noted. Default comparison:1080×2400 at420dpi,font1.0. PNGs and corresponding XML dumps are unmodified captures.

### P1 — Instructions are lost on normal back navigation

Repro: create an episode, paste a small synthetic source, Continue, enter `QA preserve my draft instructions`, dismiss IME, Back to sources, Continue. The instruction field returns empty. No Create/job/inference call was made.

- Before: `instructions-keyboard-320dp-font2.png` / `.xml` (nonempty field and33-character counter).
- After: `instructions-after-back-320dp-font2.png` / `.xml` (empty field).
- Source: `CreationScreens.kt:156–157` uses local remember for instructions/review; VM persists these only when queueing generation.
- Fix/regression requirement: episode-keyed retained draft state, not only local rememberSaveable removed on screen navigation. Test text/review toggle across back/forward, recreation, and different episodes without starting jobs.

### P1 — IME obscures actions and pushes content under system bars

At320dp/font2:

- `paste-keyboard-320dp-font2.png`: dialog title/source-name area is pushed under the status bar; Add source/Cancel are behind the IME. XML still lists these actions, demonstrating that semantics presence is not visibility.
- `instructions-keyboard-320dp-font2.png`: screen header/back navigation are above the viewport, field intersects the status area, and Create is behind the keyboard.
- Source areas: `CreationScreens.kt:131–146` (unbounded dialog column/min8 lines), `165–190` (instructions Scaffold, fixed action sizing, min7 lines); nested outer Scaffold insets in `PodcastApp.kt:58–61` compound available-space handling.
- Regression requirement: stable IME-open captures with actions/header in usable bounds or reachable by intentional scrolling, no automatic inference to test the controls.

### P1/P2 — Persistent Library action/labels are clipped

- `library-default.png`: at~411dp/font1, persistent New episode label is already clipped to New.
- `library-320dp-font2.png`: center action reads approximately `+ Ne`; Settings is clipped. The large empty-state body CTA is below the initial viewport.
- Source: `LibraryScreen.kt:60–78`, extended action constrained inside weighted NavigationBar cells; maxLines1 does not make the full label fit.
- Regression requirement: adaptive action/nav layout with intact accessible labels and usable hit targets. A scrollable body CTA can be below the fold, but the persistent primary action must remain comprehensible.

## Source-confirmed issues awaiting fixture/runtime regression

- **Playback identity:** `PlayerScreen.kt:104–111` saves on disposal; `PodcastViewModel.kt:65` clears selectedEpisodeId before disposal, and117–118 reads it later with errors suppressed. Pass an immutable episode ID. Verify A's saved position/speed after closing and that delayed A saves never attach to B.
- **Hint overflow:** `CreationScreens.kt:182` caps typing at2000, but194–195 inserts hints without the cap. Create remains enabled; repository rejects overlong input. Single-char deletion can also be refused while the value remains above2000. Test near-limit chip insertion and recovery editing through the real UI policy.
- **Scrub race:** `PlayerScreen.kt:115` polls into the same position state edited by the slider;158 commits whatever value survives the poll. Hold a paused synthetic seek for>300ms, then release; committed target must win.
- **Resume presentation:** `LibraryScreen.kt:121–128` says Continue listening but progress is hardcoded0 and text says Start listening; no actual playback/chapter metadata reaches the component.

These are not yet claimed as emulator playback reproductions. The confirmed instructions navigation loss above is an actual UI reproduction.

## Eight-state follow-up matrix

| State | Current evidence / next check |
|---|---|
| Library | Manual screenshots; fix clipping, then ready/resume metadata fixture |
| Sources | Manual paste/IME captures; add validation-failure retention and long-name checks |
| Instructions | Confirmed back-loss/IME issue; verify toggle, limits and persistence corrections |
| Review | Test fails before agent action; need stable chapter/expanded/FAB-or-replacement captures |
| Agent | Not reached by failed baseline test; need long conversation, IME, validation and accessible send/close |
| Lock | Not reached by failed baseline test; need2x-font consequence/cancel/confirm layout without queuing real jobs |
| Generation | Synthetic semantics test passed; need stable progress plus long-error layout captures |
| Player/transcript | Baseline test fails early; need synthetic transport/seek/persistence/overflow/transcript chapter-change fixtures |

No TalkBack/manual accessibility acceptance or broad visual approval is claimed. Continue with Janek's separately committed debug-only gallery/stable-capture fixtures using production composables and synthetic data only.

## Artifact inventory / cleanup

`boot-and-identity.json`, `install-baseline.json`, `manual-commands.jsonl`, `screen-semantics*`, PNG/XML captures, and emulator logs remain in this directory. A misnamed intermediate `instructions-before-typing-320dp-font2.*` capture still shows Sources and is not used as instructions proof; it was preserved rather than rewritten.

Before stopping: force-stopped only emulator app/test packages, reset display size/density and the known original font1.0, removed only the owned emulator XML scratch file, then terminated the emulator. Animation changes existed only in the read-only disposable AVD instance. No snapshot was saved and no physical-device settings were touched.
