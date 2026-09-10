# Nik polish-03 review — actual window ownership and full matrix

**Disposition: actual window-ID ownership correction accepted; CHANGES REQUESTED for frame-content freshness and the newly observed narrow-layout defects.** Instrumentation completion is not full semantic/visual acceptance.

## Exact target / isolation

- Source: `17a41c5874cb56929d3aee9200e87f44f3bd6f68`; readiness: `786183b`.
- App/src tree verified: `eb93a7788bd38d6e2855212a19c84cab21d5e27d`.
- Production main tree: `f025e231d85f1f96062254b51d051e01ac5efa01`, exactly equal to accepted `a603f525`.
- App APK: `2c188e747d8a13b62e93340aa50bcccbcbf8107e48514ff3b9920a82280ae7b3`.
- Test APK: `4e8d52c33a8f794e071ccb5abcc67a55526fe9cc20616eaac8574d37b3b44f60`.
- Candidate: `814575ea561324249321708505b71c65d748fa93d3b22ceaa0f785cb470d6aba`.

Hashes matched before installation. WIP isolation records were inspected and neither FormSubmissionState nor FormSubmissionFeedback helper name occurs in APK DEX. No form WIP is accepted as part of this candidate. The prior22/22 production UI regression results at a603f525 are reused; unchanged main code was not rebuilt/retested unnecessarily.

Independent relevant host checks: **12/12 gallery-policy JVM tests and15/15 Python tests passed**. The owner-reported full90-test suite is not relabelled as my independent execution.

## Device/test boundary

Sole existing fg-test emulator, explicit emulator-5556, API35 Google APIs x86_64 with declared ARM translation,2048MiB/2cores/software graphics/read-only/no snapshots,owned disk-backed scratch. No model packs, model inference, native diagnostic, physical/default ADB, or production generation jobs were requested. UI media is the synthetic test tone.

Default:1080×2400/420dpi/~411dp/font1. Narrow:960×2058/480dpi/320dp/font2. Animations disabled. Shared phone.lock remained with the supervisor, not its children.

## Smoke and matrix execution

1. New Library smoke passed: owner/window/root/tree ID10, correct package/PID/token, observed title VibeVoice retained as observation only.
2. New Paste/IME smoke passed: owned dialog/window/root/tree ID22, underlying gallery ID21, actual Gboard visible, observed dialog title null. PNG and merged tree agree with the requested dialog.
3. Only after those smokes, ran both15-frame matrices and all eight requested IME cells. Default Paste/IME reused the successful smoke instead of repeating it.

Captured **38 matrix PNGs plus one extra Library smoke PNG**. All matrix invocations reported complete. Window IDs, owner snapshots, package/PID/token, fonts and IME-presence checks matched. **Subsequent content audit invalidates12 of the30 base accessibility trees**, despite those reported-complete statuses.

## P1 — stale merged trees across same-window frame changes

Correct PNGs are paired with accessibility JSON from previous frames:

| Wrong target tree | Byte-identical earlier tree | Applies to |
|---|---|---|
| sources, sources-empty | library-empty | default and narrow |
| review | instructions | default and narrow |
| script-loading, failure, player | generating | default and narrow |

Examples, default SHA prefixes: sources/library-empty `3537af948606…`; review/instructions `bda4d2cb4c8c…`; player/failure/generating `cbc963583065…`.

The player PNG shows Now playing/transport, but its tree contains Creating episode/Creating What flooding remembers/Script locked. These are not harmless optional fields: the tree is from the wrong requested state. Source/window ownership can remain correct while accessibility content is stale.

Do not rewrite raw metadata.complete flags; retain the contradictory evidence and apply the independent audit. Required next correction: fresh per-frame gallery window or verified public cache refresh, plus current-frame checks against real existing production content. Preserve package/PID/window identity and bounded deadlines; do not inject marker nodes or bypass merged semantics. Add a false-completion regression where window identity is valid but content belongs to a prior frame.

Evidence:
- `semantic-frame-audit.json` (all30 tree hashes, expected existing landmarks and observed prefixes;12 wrong-frame results).
- Paired originals under `ui-nik-polish03-{default,narrow}-all/`.
- `matrix-identity-checks.json` proves ownership checks only, **not content validity**.

The remaining18 base trees match the inspected frame landmarks; all8 single-frame IME trees also match their respective inputs/actions and keyboard geometry. That is a limited consistency check, not complete accessibility/TalkBack approval. No unchanged matrix rerun was performed.

## Newly observed production UI issues at320dp/font2

These were exposed by the now-available PNG matrix. They are in the unchanged production tree, not introduced by the driver-only commit. Earlier22/22 regression results remain valid for the behaviors those tests actually cover.

### P1 — skip labels show the wrong number

`ui-nik-polish03-narrow-all/player.png` visibly renders **−1 / +1** instead of **−15 / +15**. Source action still seeks15seconds, so the visible label misrepresents the action.

Source: `PlayerScreen.kt:142,154`, full-size text inside constrained IconButtons. Use an appropriate adaptive control/icon arrangement; do not simply reduce accessibility font settings. Verify complete numeric labels with actual text-layout/overflow or image checks, not only assertIsDisplayed. The player tree in this particular matrix is stale, so it cannot establish the platform-accessible label even though source declares15-second descriptions.

### P2 — generation/failure topbar hard-clips its second line

`ui-nik-polish03-narrow-all/{generating,script-loading,failure}.png` shows Creating episode or Episode stopped wrapping into a second line that is cut off by the topbar/content boundary. This is the fixed header, not ordinary scrolling of long body text.

Source: `GeneratingScreen.kt:52`, unbounded wrapping Text in the fixed TopAppBar. Fit a meaningful header without hard clipping; retain correct semantics. Add large-font overflow/visual checks for these titles.

### P2 — ready-episode hero still wastes text space at large font

`ui-nik-polish03-narrow-all/library.png` shows CONTINUE LISTENING broken into fragments and the episode name abbreviated after very little text, while fixed-width artwork consumes much of the card. Source: `LibraryScreen.kt:133–136` (116dp art beside a weighted text column). Consider stacking/reducing decorative art for large text so title/resume metadata has useful width. Default Library also shows an empty Recent episodes heading when only the hero exists (`LibraryScreen.kt:114`).

Other long body content below a scroll viewport is not automatically a defect. In particular the narrow failure text, chapter copy and agent error history need normal scrolling; the stale trees mean this pass cannot prove every offscreen control is accessible. No blanket claim of inaccessible controls is made from those crops.

## Inspected positive visual evidence

- Default15-frame sheet preserves the eight-state structure and readable creation/review/lock/player controls.
- Narrow primary Create/New episode/Lock actions and Paste remain readable in the captured states; the previously confirmed Paste action/IME fix remains applicable from its dedicated regression evidence.
- All eight IME captures contain an actual keyboard; input/composer and primary actions stay above it in the inspected images. Error history is cramped at large font but remains a scroll-body question, not a fabricated complete-view claim.
- Lock consequence text/count and cancel/confirm actions are visible in both sizes. Transcript is chapter-only/read-only; no sentence-timing claim is introduced.

Contact sheets: `default-contact-{1,2,3}.png`, `narrow-contact-{1,2,3}.png`, and `{default,narrow}-ime-contact.png`. Originals, metadata, trees and SHA manifests remain alongside them.

## Cleanup / next gate

No new captures followed the stale-tree discovery; only retained artifacts were inspected. Emulator/app/test were stopped, display/font overrides reset and read-only state discarded. No owned review/emulator process remained; shared phone.lock was free. No implementation/history/evidence mutation, physical phone, or model work occurred.

Next review target should separately fix current-frame semantic freshness and the confirmed large-font layout issues. Existing PNGs remain useful visual evidence; the12 wrong-frame trees and their false-complete reports must remain preserved. Native/provider/model-quality, physical TalkBack/playback/export, and product E2E remain outside this UI-only review.
