# Opt-in text-layout observation after polish-05

Status: diagnostic preparation; no runtime diagnosis or new visual acceptance yet.

Polish-05's independent current-frame audit passed all 38 final screenshot/tree pairs, including eight actual-IME cells. The previous 12 wrong-frame relationships are absent. UiInteraction (3) and PasteIME (1) passed at both sizes. ScreenSemantics passed 6/8 at both sizes: its new layout helper reported overflow for `CONTINUE LISTENING` and `−15`, although the separate actual-OS-font2 gallery PNGs show the complete labels. These are different scenes/density paths; neither result cancels the other.

## Diagnostic scope

The production app remains the exact frozen polish-05 APK (`1aa5acdb` source). Only two instrumentation sources differ from that source: `ScreenSemanticsTest.kt` and the new `TextLayoutDiagnostics.kt`. The separate form-acknowledgement changes are excluded from this diagnostic build. No production layout, font, semantics, gallery driver, runtime, or acceptance assertion changes.

With `textLayoutDiagnosticsRunId=text-[a-z0-9-]{1,64}`, the existing helper retains observations **before its unchanged assertions**. Without that argument it remains the same assertion path. The 320dp/linear `Density(density.density, 2f)` wrapper is unchanged. Capturing the platform density before the override does not replace it.

Each observation has a fresh UUID directory in `files/ui-text-layout/<run-id>/`, containing:

- Exact requested text, all returned layout texts, incoming constraints, original layout size, MultiParagraph dimensions/intrinsics, width/height/visual overflow and max-line flags.
- Line starts/ends, visible ends, extents, and ellipsis flags. Public logical character boxes are also recorded (bounded at 512 UTF-16 positions); these are **not rasterized glyph-ink bounds**.
- Genuine queried **merged** node/tree and ancestor bounds. No unmerged fallback, synthetic marker, filtered layout list, or replacement result.
- Actual Android configuration, platform/wrapper/layout density classes and 11/14/16/22/28sp-to-px conversions.
- Observed installed app/test APK SHA-256 and a screenshot of the same failing test scene before the assertion. Numeric JSON is retained even if screenshot capture fails; it is observation evidence, not a gallery finalPair.

The cached Compose 1.7.6 AAR provides a hypothesis, not a verdict: the simple-string semantics callback invokes `ParagraphLayoutCache.slowCreateTextLayoutResultOrNull`, constructing a MultiParagraph with incoming maximum constraints while retaining the original intrinsic layout size. `didOverflowWidth` compares that size with MultiParagraph width. Runtime text/dimensions/line boxes and the same-scene PNG must establish whether this explains the failure, whether the merged action returned another label, or whether there is real clipping under the test wrapper.

## Bounded collection plan — Nik only

Keep the exact polish-05 app installed; install only the separately frozen diagnostic test APK. Verify both installed identities. No form candidate or full gallery rerun. No packs, model jobs, physical-device work, or native recovery.

Select exactly these two existing methods in one invocation at each configuration:

```
dev.vibevoice.podcast.ui.ScreenSemanticsTest#readyHeroUsesReadableFullWidthMetadataAndNoEmptyRecentHeading,dev.vibevoice.podcast.ui.ScreenSemanticsTest#playerExposesTransportExportAndLyricsLikeFrozenTranscript
```

Use a unique run ID at default OS settings, then another at actual 320dp/font2. Each invocation has an external **100-second** supervisor deadline (two invocations total, no unchanged retries). Preserve stdout, failure counts, actual settings, screenshots, every observation JSON and hashes. Both existing assertions may still fail; an expected failure is not converted into a test pass. Since `−15` asserts first, `+15` may remain unexecuted; do not claim otherwise.

Classify the evidence before proposing any assertion or production correction. Original polish-05 failures and all frozen candidates remain unchanged. The separately frozen form candidate and its seven compile-only Android methods remain a later, distinct gate.
