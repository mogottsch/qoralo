# Nik polish-05 review and bounded layout diagnosis

**Accepted:** fresh current-frame gallery semantics, final PNG/tree pairing, and the observed fixes for the previously reported narrow labels/topbars/hero. **Outstanding test-only follow-up:** calibrate the demonstrated false width-overflow predicate and rerun the affected ScreenSemantics gate without repeating the full matrix. Raw failed assertions remain failures, not retroactive passes.

## Exact candidate

- Source: `1aa5acdb30899b56afacd4a540f3b284502fff04`; readiness: `32fa1c4`.
- App/src tree verified: `282a82f65bf5184f76f5a899f0e7d745271a6fce`.
- Production main tree: `d89b881aee0502deca28287c38baa3c3779c373c`, identical to held polish-04.
- App APK: `4bbf162acbd93f6bff38c0aa042f044af9fd289a5f15f0b2e49ba6763daf1fcd`.
- Original matrix/test APK: `b207bf14a6c2bcd01018c1cc8e24e6e016477f38c3167d121dd18b90bcd2220c`.
- Candidate SHA: `8a7426abb38cf1234489ef811ff44965080ee70cd2f85118963da65212db3fd1`.

The unexecuted04 layout changes are included, and form WIP is excluded. Both APK DEX sets were checked for the excluded form-helper names. No implementation/history or earlier evidence files were edited by Nik.

## Source/host review

- Private gallery task affinity/nonexported guard is checked before NEW_TASK|CLEAR_TASK. The main product task is not cleared.
- Public cache clear/root refresh, fresh per-frame window IDs, package/PID/frame/run/freshness checks and existing production content/state matching remain in force.
- Subsets are nonempty, unique, known-only and≤15, with no mixed all. IME and hold remain single-frame-only. Bounds:80s for the two-frame smoke,100s single/IME,600s all15.
- Initial PNG stays separate/immutable. Distinct intermediate trees and failed image candidates are retained. Final publication occurs only after content validation and ownership checks around capture; finalPair binds actual installed app hash, tree hash, PNG hash, frame/token and both identity snapshots.
- Independently passed **99/99 JVM,15/15 Python**, lint and release Kotlin compilation at≤2workers. No native/model preparation was repeated.

## Emulator and exact execution

Only existing fg-test, explicit emulator-5556, API35 Google APIs x86_64 with declared ARM translation,2048MiB/2cores/software graphics/read-only/no snapshots,disk-backed scratch. No model packs, inference, native diagnostics or physical/default ADB. Gallery/player media are synthetic.

Default:1080×2400/420dpi/~411dp/font1. Narrow:960×2058/480dpi/320dp/font2. ScreenSemantics additionally uses its own320dp/font2 wrapper; diagnostics below measured its actual conversions rather than assuming linear scaling.

1. Genuine within-run `library,sources` smoke passed: Library ID10→Sources ID12 with previousWindowIds=[10], different correct content, verified final pairs.
2. Paste/actual-IME smoke passed with dialog ID24 and matching owner/root/tree.
3. Only then ran both15-frame matrices plus eight IME cells. Default Paste/IME reused its successful smoke.

**38/38 final matrix pairs independently verified** in `independent-final-pair-audit.json`:

- Correct existing production landmarks and Sources Continue enabled/disabled state.
- Fresh/nonreused within-run IDs and matching owner/window/root/tree IDs.
- Exact source APK, tree, final PNG and candidate PNG hashes; preserved initial PNG hash.
- Same frame/token/initial PID, before/after ownership freshness and temporal ordering.
- Actual IME presence/click for all eight requested IME cells.
- SHA-addressed intermediate tree files match their names.

The previous12 stale-tree relationships are gone. Completion is accepted from the independent content/hash/identity audit, not telemetry.complete alone. Initial images are not substituted for final pairs. The38 final PNGs/contact sheets were inspected.

## Actual UI test outcomes before diagnosis

| Suite | Default environment | Actual320dp/font2 |
|---|---:|---:|
| ScreenSemanticsTest |6/8 |6/8 |
| UiInteractionRegressionTest |3/3 |3/3 |
| PasteImeRegressionTest |1/1 |1/1 |

Thus20/24 original assertions/method outcomes passed; four failures are retained. Both environments failed the new width predicate for CONTINUE LISTENING and −15. The false assertion stops each method before later assertions; those later checks are not credited as executed.

The final gallery images show complete −15/+15 labels, full growing Creating episode/Episode stopped headings, a readable stacked ready hero and no empty Recent heading. Existing interaction/Paste regressions pass. Large-font body content may require scrolling; these captures do not claim every body paragraph fits above the fold.

## Bounded diagnostic resolution of the two width assertions

A separate exact diagnostic test APK was reviewed/installed only AFTER the05 matrix/tests completed. The app remained the exact05 APK. No form APK or production change occurred.

- Patch `a552ecb92412de37e41f7a7dd162a761f38bea3e`, readiness21c64c9.
- Effective source is05 plus ONLY ScreenSemanticsTest.kt/TextLayoutDiagnostics.kt; independently reconstructed app/src tree `083cedbbc70b1372f28e52c39f2b0c7f718e3b6e`.
- Diagnostic test SHA `f7f5b40f141fa9d6fabff846cfb26a92bde57336990f365d7ec4743f0fde1f98`.
- Candidate SHA `12380969605577af6e3ea85363ae3fe86c25e8cc7ebbd5d675ad76d887ecb1b9`.
- Exactly two100s-bounded invocations, each selecting only the two failing methods. No retry or full-matrix rerun. Original assertions remained unchanged and still failed.

Runtime evidence confirms a **reconstructed paragraph-width proxy false positive**, not wrong-target selection or a sampled font-conversion mismatch:

| Condition | Target | Intrinsic width | Reconstructed paragraph width | Actual line right |
|---|---|---:|---:|---:|
| Default | CONTINUE LISTENING |619 |650 |617.2368 |
| Default | −15 |119 |330 |117.04616 |
| Narrow | CONTINUE LISTENING |719 |744 |717.0664 |
| Narrow | −15 |135 |378 |133.2 |

Each returned layout is exactly the requested text, one complete non-ellipsized line, with no height/max-line overflow. All recorded logical character boxes fit intrinsic size. All four same-failing-scene PNGs were inspected and show the full requested labels. These are logical boxes, not rasterized ink bounds. I independently inspected cached Compose1.7.6 bytecode showing MultiParagraph reconstruction at incoming maxima while retaining intrinsic layoutSize, followed by size.width<paragraph.width for didOverflowWidth.

At actual OSfont2, DensityImpl wrapper and DensityWithConverter platform conversions are identical at the sampled11/14/16/22/28sp values:66/78/84/105/112px. Earlier wording that called this wrapper strictly linear was an unverified assumption; it is corrected by these measurements.

Detailed diagnostic report and exact observation/PNG hashes: `text-layout-diagnostic/review.md` and `text-layout-diagnostic/independent-analysis.json`.

**Required test-only follow-up:** replace the unreliable width proxy with evidence-backed checks that retain target identity, visibility/ancestor geometry, height/max-line/ellipsis/completeness and actual line/character extents; include measured-positive and genuine-clipping negatives. Review and rerun the affected ScreenSemantics tests before calling the formal test gate green. No font shrinking or production layout change is justified merely by these false flags.

## Remaining scope boundaries

- Async form-error acknowledgement is a separate queued source31ab0b7 candidate, not included or approved here.
- The narrow player prioritizes persistent controls/decorative artwork, so current chapter details can be below the initial scroll viewport; this is a possible UX refinement, not the diagnosed hard-label clipping.
- No physical TalkBack/playback/export, native/provider/model quality, or production generation lifecycle/E2E approval is inferred from translated synthetic UI.
- The S23 QNN device-initialization/capacity work remains a separate blocked/native track.

## Preservation and cleanup

All originals, finalPair metadata, initial/candidate/final PNGs, distinct tree snapshots, audits, failed tests and diagnostic observations remain in this owned directory. Prior false-complete matrices and05 frozen artifacts were not rewritten.

After both bounded diagnostic invocations, emulator/app/test were stopped, display/font overrides reset and the read-only instance discarded. No owned emulator/review command remained; canonical phone.lock was free. No physical-phone operation, model work or implementation edit occurred.
