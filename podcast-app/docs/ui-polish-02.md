# Corrected gallery driver and Paste IME follow-up

Status: host-validated implementation; awaiting Nik's next exact synthetic-emulator run. No physical-phone or model work. This does not complete the visual, native-runtime or product-E2E gates.

## Scope and provenance

- The six gallery-driver files in mixed commit `f637a74` are Janek's work, ready to commit at the time of a shared-index collision. Jere's unrelated Gemma evidence in that commit has a separate owner and validation scope. Pi and Janek agreed to retain the commit unchanged; no test result transfers between scopes.
- The driver repair connects UiAutomation before launch, uses token-labelled **debug platform windows** and genuine merged roots, waits with deadlines, records identities/observations, retains PNG/partial metadata before optional tree extraction, and continues later distinct frames while failing incomplete runs overall. See [capture contract](ui-polish-gallery.md). Ten deterministic host tests cover readiness/identity/IME and failure retention.
- This follow-up changes production Paste layout and UI test navigation, not native code, model inputs or inference routes. Earlier frozen APK directories are immutable.

## Confirmed baseline and targeted changes

Nik's `a2dc5cb` report and all ten gallery attempts are retained byte-for-byte in `evidence/ui-polish-02/before/`, alongside the settled Paste failure and successful main-app persistence evidence. The retained manifest hashes every copied file.

Baseline classification remains explicit:

- Main-app instructions **and review-off** survive Sources back-navigation at 320dp/font2; header/Create stay above the IME.
- Scrub hold and A→B disposal ownership pass at both sizes. Hint recovery passes at default size; its narrow failure occurs before interaction because the lazy item is not yet composed.
- The review toggle is reachable by ordinary scrolling. Its old test's above-fold assertion was not evidence of an unreachable control.
- Two default gallery IME captures are valid partial coverage. Eight missing-root failures are capture-driver failures, not app-rendering verdicts.
- Paste's settled large-font Add source label genuinely extended below Gboard (label bottom1248, IME top about1209px).

The pinned Compose UI1.7.6 `DialogLayout.internalOnMeasure` substitutes configuration display height when `usePlatformDefaultWidth=false` rather than respecting the incoming height constraint (inspected from the locally cached AAR). Paste now uses the platform-constrained dialog with explicit resize as the **sole IME owner**, without a second layer of content IME/system padding. Header and full-width primary action are measured before the bounded scrolling field area. Cancel remains available as the labelled header close action. This avoids the narrow two-line primary action sharing a row with Cancel. Pixel success still requires the new emulator capture.

Large-font instructions show at most four lines at once with internal scrolling; all text, editing, font size and the2,000-character limit remain unchanged. Tests scroll the actual LazyColumn to matching content **before** fetching virtualized chips/fields/review controls, then retain real visibility/enabled/click assertions.

## Next exact emulator checks (Nik only)

Use the newly frozen app/test APKs and unique run IDs; never overwrite or retry old run directories. Keep every ADB command explicitly on `emulator-5556` under the canonical shared lock. No model packs or inference.

1. Smoke the new gallery at one base frame and one dialog/IME frame. Inspect selected package/window title/token, actual PNG, and merged tree. Do not repeatedly rerun an unchanged failing driver.
2. If the new driver is functioning, capture the requested15 frames and IME variants at default and actual320dp/font2. Its supervisor budgets are now480s all-frame /90s single-frame; those bounds allow partial evidence retention after window timeouts.
3. Run `ScreenSemanticsTest` (7 methods) and `UiInteractionRegressionTest` (3 methods) at both sizes. The navigation changes are not policy-test weakening.
4. Run `dev.vibevoice.podcast.ui.PasteImeRegressionTest` separately at both sizes. It focuses and types into the **body**, waits for actual IME bounds and a stable entire primary button/label above them, asserts visible/enabled/clickable controls, and checks the submit callback. It retains pre-click/failure PNG and geometry under `files/ui-regressions/paste-ime-<timestamp>/`. The ordinary gallery Paste IME request focuses the first visible field, so it does not replace this body-focused check.
5. Retain before/after screenshots, raw test results and exact tested APK/commit identities. Window readiness is not a pixel-layout verdict, and synthetic media is not model evidence.

## Separate later input-error preservation

Nik also identified a source-level issue: Agent and Paste currently clear/dismiss after Unit callbacks while queue/save is asynchronous. Success-acknowledged submission identity, preserved text and visible local errors on rejection remain a **separate follow-up**, with no automatic native retries or generation recovery. This is not claimed fixed by the current layout/driver candidate.
