# Test-only readable-content policy after observed width false positives

Status: implementation/host preparation; corrected Android checks have not executed yet.

## Evidence and correction

The [diagnostic result](../evidence/text-layout-diagnostic-result/README.md) retains all four original failed checks and same-scene screenshots. Runtime observations prove that the reconstructed paragraph-width flag can exceed the intrinsic text width even when the requested text's complete line/character geometry fits. This is not wrong-target selection. The earlier strictly-linear-density hypothesis is withdrawn: at OSfont2, all sampled platform/wrapper/layout conversions agree.

No production layout, font, semantics or runtime changes are needed for these false flags. This is a test-only revision against the exact frozen polish-05 app. The separate form changes remain excluded. Frozen polish-05 and diagnostic candidates, including their original failed assertions, remain unchanged.

## What the revised helper checks

- Preserve `assertIsDisplayed`, the real merged `GetTextLayoutResult` action, and the previous clipped-node-height assertion.
- Require exactly one returned layout and an exact requested-text match. Do not filter unexpected layouts or use unmerged/synthetic marker nodes.
- Reject empty/nonfinite/invalid geometry, height/max-line overflow, ellipsis, missing visible non-whitespace text, incomplete line coverage, and missing/duplicated character boxes.
- Compare every line and non-whitespace logical character box with the original intrinsic layout size. A fixed **one physical pixel** tolerance covers coordinate rounding; it cannot waive a missing character, ellipsis or overflow flag for height/max-lines.
- Intersect the real clipped merged-node bounds with its semantic ancestors, requiring enough visible width/height for the intrinsic text size. Keep the existing node-height assertion as well. A finite ancestor-chain bound fails closed rather than silently ignoring further ancestors.
- Do not use reconstructed MultiParagraph width alone as a content-clipping verdict. Continue retaining its dimensions/flags in opt-in diagnostics. Height and actual line/character clipping remain failures.

These are public logical text metrics, not rasterized glyph-ink measurements or proof of every possible overlay/occlusion. Same-scene image inspection remains separate evidence.

## Regression coverage

`TextReadabilityPolicyTest` adds **seven Android methods** (pure geometry with frozen runtime fixtures):

1. All four measured reconstructed-width positives pass the content checks.
2. Narrowing the −15 allocation past its final digit rejects the historical −1-style truncation failure.
3. Height and max-line overflow still reject.
4. Ellipsis and incomplete text/character coverage reject.
5. Wrong, missing or additional returned layouts reject rather than being filtered away.
6. Out-of-bounds line/character and nonfinite geometry reject.
7. Insufficient merged-node or ancestor clipping bounds reject.

`TextReadabilityClippingTest` adds **two real Compose negative controls**: a width-constrained −15 label and a height-constrained Creating episode label. Both must be rejected by the helper; those are deliberately clipped test scenes, not production defects.

The unchanged eight `ScreenSemanticsTest` scenarios use the corrected helper, including full −15/+15 and the later transport/transcript assertions previously blocked by the width false positive. New methods are compilation-only until Nik executes the candidate; host unit results do not count them as Android passes.

## Bounded review and execution plan — Nik only

Recheck exact effective source tree, unchanged polish-05 installed app SHA and the new test APK SHA. Install only the test APK; no production/form candidate switch. Run these three selected classes once at default OS settings and once at actual 320dp/OSfont2:

```
dev.vibevoice.podcast.ui.ScreenSemanticsTest,dev.vibevoice.podcast.ui.TextReadabilityPolicyTest,dev.vibevoice.podcast.ui.TextReadabilityClippingTest
```

That is **17 methods per invocation**, maximum **two invocations**, each under an external **100-second** supervisor budget. Use distinct opt-in `textLayoutDiagnosticsRunId=text-...` values to retain same-scene observations for the normal screen helper. Preserve every new result/failure; no unchanged retry or full gallery matrix. Existing 38-pair gallery and interaction/PasteIME evidence stays separate. No physical-device work, model jobs, native recovery, or form-acknowledgement validation is authorized by this candidate.
