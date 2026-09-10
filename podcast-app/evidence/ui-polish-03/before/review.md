# Nik independent polish-02 review

**Disposition: Paste IME and test-navigation fixes accepted in the tested synthetic emulator scope. CHANGES REQUESTED for gallery capture readiness; full visual matrix remains blocked.**

## Exact target / ownership

- Source commit: `a603f5259292bb8b33afa33253b87a0306861d0f`.
- Readiness/evidence commit: `f698b95`.
- Verified app/src tree: `cef7dfaf91ce38acab925d6af5a39c5bb4ff7cba`.
- Frozen candidate SHA-256: `2558ea1543403172c011c96a616ac58314ee9762ab851fae1c7c0a6928ab1561`.
- Frozen app APK: `a732878a5c9f19721651f92a6c9bbdc62678ac57b2af4031f3d81d43e87565b7`.
- Frozen test APK: `4a98ea74f831b6f49427ed52a3914052daf4fbc4ea466ad3c6e64ca7b6d682c6`.
- The retained mixed commit f637a74 contains Janek-owned gallery changes; its unrelated Gemma evidence supplies no app test approval.

Isolated source worktree: `/home/moritz/.cache/nik-podcast-reviews/a603f525`. Frozen APK hashes matched before emulator installation. No implementation or historical evidence files were edited by Nik.

## Independent host result

**88/88 JVM tests and15/15 Python tests pass**, with zero JVM failures/errors/skips. Lint and release Kotlin compilation pass at≤2workers. The deprecated ADJUST_RESIZE warning is retained; it did not fail compilation/lint. No model/native payload preparation or native inference was performed.

Source review confirms gallery remains debug-only/non-exported in :ui_gallery, uses production composables and synthetic media, and contains no repository/job/model calls. Window observations are real platform/accessibility observations, not injected semantic nodes. Screenshot-first retention now works on the observed failure.

## Actual synthetic Android regressions

Single existing fg-test emulator, explicit emulator-5556, API35 Google APIs x86_64/declared ARM translation,2048MiB guest RAM/2cores/software graphics,read-only/no snapshots,disk-backed scratch. No model packs. All ADB commands explicitly addressed that emulator under the canonical shared lock; children did not inherit it.

| Suite | Default1080×2400/420dpi/font1 | Narrow960×2058/480dpi/320dp/font2 |
|---|---:|---:|
| ScreenSemanticsTest |7/7 PASS |7/7 PASS |
| UiInteractionRegressionTest |3/3 PASS |3/3 PASS |
| PasteImeRegressionTest |1/1 PASS |1/1 PASS |

**22/22 executed tests pass.** ScreenSemantics uses its own320dp/font2 wrapper in both environments; the other interaction tests honor the system conditions. Raw outputs and exact commands are in `android-test-summary.json` and each suite/condition stdout file.

The tests now navigate the real LazyColumn before fetching virtualized chips/fields/toggle, retaining visibility/enabled/click assertions. This is not a merged-semantics bypass or font shrinking.

### Paste body/IME proof

The new test focuses and types into the Source text body, observes actual IME bounds, checks the entire enabled/clickable Add button and text label, saves a pre-submit screenshot, and verifies the exact submitted body.

- Default: button bottom1237px and label bottom1195px, IME top1517px.
- Narrow/font2: button bottom1161px and label bottom1119px, IME top1209px. Entire action has48px clearance.

Both retained PNGs were independently inspected and agree with geometry. The focused large-text body has a bounded/scrolling viewport; this pass validates the action/label/submit regression, not every long-form editing interaction.

Artifacts:
- `ui-regressions/paste-ime-1789038104041/{focused-body.png,geometry.json,result.json}` (font1).
- `ui-regressions/paste-ime-1789038122373/{focused-body.png,geometry.json,result.json}` (font2).
- Original pulled archive: `ui-regressions.tar`.

## Remaining P1: gallery window-identity mismatch

Only the requested **base Library smoke** was attempted. It failed; Paste gallery smoke and the full15-frame/IME matrix were deliberately NOT started. No unchanged gallery retry occurred.

Run: `ui-nik-polish02-smoke-library`.

- Private frame acknowledgement succeeds, with :ui_gallery PID3372 and intended token/title.
- All50 window polls over the10s budget observe an active/focused application window ID10, package `dev.vibevoice.podcast.internal`, nonempty visible accessibility root.
- Actual `AccessibilityWindowInfo.title` is **VibeVoice**.
- Policy instead requires **Synthetic UI gallery · ui-nik-polish02-smoke-library-library**.
- Setting WindowManager.LayoutParams.title in `SyntheticGalleryActivity.kt` did not establish that accessibility title. The acknowledgement records the requested value, not the observed platform identity.
- Result is correctly partial: PNG retained, tree unavailable, run failed. The PNG shows the real Library UI; this is **not an app-render failure**.

Required correction: correlate the private frame token to the actual public platform/accessibility window ID or a verified public title operation, with package/ownership and dialog/IME checks preserved. Do not simply accept the requested title, accept any package window, or insert fake semantic content. Re-smoke a new exact candidate before the full matrix.

Evidence: `ui-nik-polish02-smoke-library/{library.png,library-metadata.json,library-error.txt,run-summary.json,capture-error.txt,raw-capture.tar}`. The metadata retains actual platform window observations and the failed selection boundary.

Minor visual follow-up, not the capture blocker: the one-episode Library frame displays an empty Recent episodes heading below the sole hero; consider hiding that heading when there are no remaining rows.

## Boundaries and cleanup

- Prior c893963/a2dc5cb failed evidence remains unchanged; fixes are not retroactively credited to those runs.
- Async form-error acknowledgement remains a separate uncommitted/future implementation scope; not claimed fixed here.
- No model/provider performance, real generated audio, physical TalkBack/playback/export, or production generation lifecycle success is inferred from translated synthetic UI.
- Emulator/app/test were explicitly stopped after this bounded pass; display/font overrides restored, read-only instance discarded without snapshots. No owned review/emulator process remained and phone.lock was free at cleanup.
- Next step is the exact corrected window-correlation candidate. No physical-phone action is authorized by this review.
