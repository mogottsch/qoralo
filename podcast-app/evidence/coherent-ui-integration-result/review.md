# Nik coherent UI integration review — fb16b90 attempt02

**APPROVED for the exact matched candidate's host/source and synthetic-emulator UI integration gate.** The combined56-method gate and new-app38-pair gallery audit pass. This is not physical Galaxy runtime, provider/model quality, production generation lifecycle, or product-E2E approval.

## Exact candidate

- Readiness commit: `2fc2657`.
- Source: `fb16b90e493c24e2d0b5f289c393b4cd5b5abd4f`.
- Effective app/src tree: `314010f949ba5e33fe7845230c3c3b2b875d7c97`.
- Frozen directory: `podcast-app/.local/integration-ready/fb16b90-02/`.
- App APK SHA-256: `1cfe1419d974ac4e88d3039806a1a6bc849b602ec3036a474cd877f068ed8e7d`.
- Test APK SHA-256: `b03d8fe7f87325d3db3bf1d6a349b87fad8955b7e41da905655167aae80af76d`.
- Candidate SHA-256: `2b3c1ed1c8fe8683f3a87dc1f6491efbd989775218cc8786f4fd4f33457379e7`.

These frozen hashes and both installed emulator APK identities were independently checked. Candidate hashes were checked again after execution. The app matches the separately approved form APK byte-for-byte, as expected; the test APK is the new coherent test combination. Prior separate passes were not substituted for the combined execution below.

## Independent source/input/build audit

The review used isolated worktree `/home/moritz/.cache/nik-podcast-reviews/fb16b90` without implementation edits.

- Reconstructed polish05 base1aa5acdb plus exactly ten approved form replacements from31ab0b7 and six readability test/asset replacements fromc2ce81b.
- All16 paths, committed blob identities and all92 effective source files match the source anchor and the nominated tree314010f…. No extra or excluded source was found.
- Verified13 declared unchanged05 source subtrees/blobs, including gallery, native bridge source, resources, generation/runtime/model boundaries, three layout files and common UI/theme.
- Verified114 tracked build/test/tool/authority inputs and21 enumerated local properties/native-library/ORT-header inputs by size/hash.
- Verified849 recorded external dependency configuration entries against281 unique actual files (433,869,542 bytes). Repeated file records agree. This verifies the enumerated dependency/input inventory, not a universal hermetic JDK/SDK/toolchain or reproducible-build claim.
- Verified35 candidate evidence bindings,30 prior frozen files and restored c893 Gradle output hashes.
- Independently extracted all nine native APK entries and compared their exact sizes/hashes with05; all match, including bridge and AndroidX payload. The unchanged trusted eight-runtime ELF/pin verifier also passed against the nominated APK.
- Binary manifests confirm app/test package targeting and the non-exported :ui_gallery activity's private task affinity. The runtime guard remains before CLEAR_TASK. DEX contains the required form implementations and combined test classes; the measured fixture asset equals the pinned source.

`independent-preflight.json`, `trusted-runtime-verification.json`, and binary manifest dumps retain this audit.

## Host attempt boundaries

- Attempt01: metadata collector failed on self-project artifact variant/configuration-cache handling before an app test/assembly task ran. Original failure logs/restoration remain retained; this is not an app/model failure.
- Attempt02: retained JUnit XML independently sums to113 tests, zero failures/errors/skips. The log shows testDebugUnitTest executed, not UP-TO-DATE, and successful lint/release Kotlin/app/test assembly. Retained Python output confirms15 executed tests/OK.
- The external-module artifact view and no-configuration-cache collector change are host tooling only; source/test policy did not change between attempts.

These are independently corroborated recorded host executions, not a claim that Nik redundantly rebuilt/re-executed the full host suite in this integration pass. Prior independent component host tests remain separate supporting evidence.

## Actual combined emulator gate

Sole existing fg-test AVD, explicit emulator-5556, API35 Google APIs x86_64 with declared ARM translation,2048MiB guest RAM/2cores/software graphics/read-only/no snapshots,owned disk-backed scratch. No model packs or real inference. Canonical phone.lock covered the ADB/test/cleanup lifecycle; server/children did not inherit it.

Exactly two combined invocations,180s bounds, no retries:

| Condition | Screen | Interaction | PasteIME | Readability policy | Real clipping | Forms | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
|1080×2400/420dpi/~411dp/OSfont1 |8 |3 |1 |7 |2 |7 |28/28 PASS |
|960×2058/480dpi/320dp/OSfont2 |8 |3 |1 |7 |2 |7 |28/28 PASS |

**56/56 methods passed on this matched app/test pair.** The tests retain their calibrated content geometry and real-clipping negatives; form callbacks are synthetic. No native/job model execution is inferred from these tests.

Raw outcomes/commands: `combined-{default,narrow}.stdout/.stderr`, `combined-test-summary.json`, `boot-install.json`. Additional audit verified ten normal-label observation/PNG hashes against this app/test pair and both passed real PasteIME geometry records (`independent-test-observation-audit.json`).

## Conditional new-app gallery

The source/hash checks and combined tests passed before capture started.

1. Within-run Library→Sources smoke,80s bound: IDs218→220, previous-ID rejection, actual new content and final pairs verified.
2. Default Paste/actual-IME smoke,100s bound: dialog ID232 with real keyboard and correct pair/ownership.
3. Only after both smokes: two15-frame matrices,600s each, and seven remaining distinct IME invocations,100s each. The default PasteIME smoke was reused, not repeated.

**38/38 final matrix pairs independently pass** `independent-final-pair-audit.json`:

- Existing production landmarks and Sources Continue enabled/disabled state match each actual frame.
- Fresh/nonreused per-run window IDs; matching window/root/tree IDs, package, frame/run token and initially acknowledged PID.
- Ownership freshness on both sides of final capture and expected temporal ordering.
- Actual observed source APK hash is the new `1cfe1419…ed8e7d`, not05's4bbf… hash.
- Tree/final PNG/candidate PNG hashes and preserved initial PNG hashes match actual files; intermediate tree names match SHA-256.
- All eight requested IME cells contain an actual keyboard and successful editor focus.

Every final PNG/contact sheet was inspected. No stale previous-frame relationship or new blocker was found in this scoped integrated matrix. The default/narrow controls, updated labels/topbars/hero, forms and chapter-only transcript retain the accepted behavior. Long body content still uses scrolling; this is not a promise that every paragraph is simultaneously above the fold or a physical TalkBack audit.

The result is new integrated-app evidence, not transferred05 gallery acceptance. Initial images, candidate images, distinct intermediate trees, metadata, raw archives and final images remain available under `ui-nik-coherent-*`. Contact sheets are `{default,narrow}-contact-{1,2,3}.png` and `{default,narrow}-ime-contact.png`.

## Preservation and cleanup

All frozen candidate/source bytes remained unchanged. Historical inventory failure, false-complete trees and old overflow assertion failures remain separate and immutable. No broad Git/index/history mutation or implementation edit was made by Nik.

At completion, app/test were force-stopped on emulator-5556, display/font overrides reset and the read-only emulator stopped without snapshots. No owned emulator/review process remained, tracked worktree diff was empty and canonical phone.lock was free. `cleanup.txt` and supervisor logs record the local cleanup. No physical/default ADB occurred.

## Acceptance limits / remaining project gates

This closes the assigned coherent host/synthetic-UI integration gate for this exact pair. It does not authorize an unreviewed rebuilt pair or establish:

- physical Galaxy UI/TalkBack, playback/export or platform lifecycle behavior;
- QNN duration device creation succeeding, four ready HTP sessions, speech rendering or physical capacity rejection;
- feasibility of1–2 minute complete chapters under T239/L238;
- model quality/listening acceptance, canonical inference benchmark results or product E2E.

The separate physical QNN startup/capacity and product-generation gates remain unresolved and require explicit Pi authorization. No further build, model preparation or device attempt is implied by this report.
