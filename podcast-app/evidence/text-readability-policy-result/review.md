# Nik readable-content policy gate — c2ce81b

**APPROVED: test-only calibrated readability policy and the bounded ScreenSemantics gate.** Both authorized invocations passed17/17 tests (34/34 total), including measured reconstruction positives and two real Compose clipping controls per condition. This does not retroactively turn earlier failed assertions into passes and does not approve the separate form candidate or physical/native behavior.

## Exact source/identity boundary

- Policy patch: `c2ce81bf6d97b3838808104190a651b0fba62b9a`; readiness: `1b3f7c7`.
- Effective source: exact polish-05 base `1aa5acdb30899b56afacd4a540f3b284502fff04` plus six committed Android-test files/assets.
- Independently reconstructed effective app/src tree: `2de06d9902657d43fbd668fbd6718e72d7c6f6ae`.
- Production main remains `d89b881aee0502deca28287c38baa3c3779c373c`.
- Unchanged05 app SHA-256: `4bbf162acbd93f6bff38c0aa042f044af9fd289a5f15f0b2e49ba6763daf1fcd`.
- New test APK SHA-256: `d85b57a07b921928982f842998c0e5408249960d0b02ccd5fe8f9c6a3656bb22`.
- Candidate SHA-256: `4d0321807711c4ea0929c50ce98862bf0c9e25fabae3f53ac86a1b110196b97f`.

Host files and installed emulator APKs were independently hashed. Test DEX has the readability helper and excludes form state/interaction code. Packaged measured-labels asset exactly matches the reviewed source; all four fixture JSON objects exactly equal my independently retained diagnostic observations. No production source/font/semantics/route change was included.

## Policy review

The replacement is justified by the prior runtime diagnosis, not by deleting inconvenient assertions:

- Exactly one returned layout, matching the requested text; unexpected layouts are rejected, not filtered.
- Visible merged target and the original clipped-height check retained.
- Finite positive intrinsic/paragraph geometry; full line/character coverage; height/max-line/ellipsis checks retained.
- Actual line extents and non-whitespace logical character boxes must fit intrinsic size.
- Real merged-node bounds intersected with semantic ancestors; bounded ancestor traversal fails if incomplete.
- Only one physical pixel of rounding tolerance; no font-scale-relative relaxation.
- Reconstructed paragraph width alone is not used as a clipping verdict.

The seven geometry-policy methods exercise the four frozen measured positives, truncating the historical −15 allocation, height/max-line/ellipsis/incomplete text/character cases, wrong/missing/additional targets, nonfinite/out-of-bounds geometry, and insufficient ancestor bounds. Two real Compose controls deliberately constrain width and height and must be rejected.

These logical boxes are not rasterized ink bounds or a universal overlay-occlusion proof. Existing same-scene and gallery image evidence remains a separate check.

## Actual execution

Sole existing fg-test emulator, explicit emulator-5556, API35 Google APIs x86_64 with declared ARM translation,2048MiB/2cores/software graphics/read-only/no snapshots,owned disk-backed scratch. Shared canonical phone.lock held by supervisor; children did not inherit it.

Exactly two invocations,100s bound each, no retries:

| Environment | ScreenSemantics | Policy | Real Compose clipping | Total |
|---|---:|---:|---:|---:|
| Default1080×2400/420dpi/OSfont1 |8/8 |7/7 |2/2 |17/17 |
| Actual960×2058/480dpi/320dp/OSfont2 |8/8 |7/7 |2/2 |17/17 |

Actual durations were about10.4s and10.0s. Raw stdout confirms `OK (17 tests)` for each, not merely ADB exit0. Both genuine clipping controls were rejected as intended. The previous false-width cases pass with complete content geometry, and the later +15/transport/transcript checks now execute successfully.

No full gallery rerun occurred. Previous05 current-frame/final-pair audit and interaction/PasteIME evidence remain separately accepted and immutable. Existing host99JVM inputs were unchanged; this review does not claim a new independent99-test host rerun for this test-only overlay.

## Evidence

- `boot-install.json`: exact commands, ABI and installed identity checks.
- `run-summary.json`: two authorized invocations/conditions/results.
- `text-readable-nik-default-01/` and `text-readable-nik-narrow-01/`: stdout/stderr, original pulled archives and UUID observations.
- `independent-observation-audit.json`:10/10 observations verified for exact source/test APK hashes, single requested target and same-scene PNG hash. All five normal labels were reached per condition: Creating episode, Episode stopped, CONTINUE LISTENING, −15, +15.
- Original20/24 and the four still-failed diagnostic checks remain in the earlier05 evidence, with their measured false-positive interpretation. Nothing was rewritten in place.

## Cleanup / claim limits

App/test were force-stopped on the emulator, display/font overrides reset and the read-only emulator stopped without snapshots. No owned emulator process remained and canonical phone.lock was free at cleanup. No physical/default ADB, model packs, inference, production/form APK change, or source edits occurred.

This closes the specific synthetic readability-test gate. Physical TalkBack/playback/export, native/provider/model quality, production generation lifecycle and product E2E remain separate. The independently frozen form-acknowledgement candidate is the next queued review, not covered by this approval.
