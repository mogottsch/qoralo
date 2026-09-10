# Independent bounded text-layout diagnosis — a552ecb overlay on polish-05

**Finding: the four observed width-overflow failures are test-proxy false positives for the requested labels, confirmed by runtime dimensions, logical extents, same-scene PNGs, and the cached Compose1.7.6 implementation.** The original assertions remain failed and are not rewritten as passes. No replacement assertion policy has been tested by Nik yet.

## Exact source and bytes

- Production base: `1aa5acdb30899b56afacd4a540f3b284502fff04`.
- Diagnostic patch: `a552ecb92412de37e41f7a7dd162a761f38bea3e`; readiness: `21c64c9`.
- Effective app/src is base05 plus ONLY ScreenSemanticsTest.kt and TextLayoutDiagnostics.kt from the patch. Independently reconstructed the Git tree hash: `083cedbbc70b1372f28e52c39f2b0c7f718e3b6e`.
- Production main tree stays `d89b881aee0502deca28287c38baa3c3779c373c`.
- Unchanged installed app SHA: `4bbf162acbd93f6bff38c0aa042f044af9fd289a5f15f0b2e49ba6763daf1fcd`.
- Diagnostic installed test APK SHA: `f7f5b40f141fa9d6fabff846cfb26a92bde57336990f365d7ec4743f0fde1f98`.
- Candidate SHA: `12380969605577af6e3ea85363ae3fe86c25e8cc7ebbd5d675ad76d887ecb1b9`.

Both installed identities were queried/verified on emulator-5556 before execution. Helper presence and form-helper absence were checked in test DEX. This is not the full shared-tree a552ecb production state; it is the explicitly verified two-file overlay on05.

## Execution boundary

Exactly TWO instrument invocations, each selecting only the ready-hero and player methods. One default environment, one actual320dp/font2 environment;100s external bounds, no retry. Both methods still fail their unchanged width assertion in both invocations. Since −15 fails first, the later +15 layout assertion and subsequent player assertions are not credited as executed.

The app stayed05; no production/form APK switch, full-matrix rerun, physical/default ADB, model pack, native inference or generation recovery occurred. The logger saved every observation and same-scene PNG before the original assertion.

## Measured result

Every observation returned **exactly one layout with text equal to its requested target**, eliminating wrong-target selection for these cases.

| Environment | Target | Intrinsic result size px | Reconstructed paragraph px | Line right px |
|---|---|---|---|---:|
| Default OSfont1, test wrapper font2 | CONTINUE LISTENING |619×84 |650×84 |617.2368 |
| Default OSfont1, test wrapper font2 | −15 |119×98 |330×98 |117.04616 |
| Actual320dp/OSfont2 | CONTINUE LISTENING |719×96 |744×96 |717.0664 |
| Actual320dp/OSfont2 | −15 |135×112 |378×112 |133.2 |

In all four:

- `didOverflowWidth=true`, solely because result width is less than the reconstructed paragraph width.
- Height overflow=false, max-lines exceeded=false, one complete line, no ellipsis; visibleEnd reaches all18 or3 UTF-16 positions.
- All recorded logical character boxes fit the intrinsic result width/height.
- Same-scene PNGs visibly show the complete requested label. PNG hashes and observed app/test hashes were independently checked.
- Merged target/ancestor bounds were retained. The narrow hero's merged card extends below the scroll viewport, but its upper CONTINUE LISTENING label is visibly complete; card cropping must not be conflated with label clipping.

These are logical character/layout boxes, **not rasterized glyph-ink bounds**. The image inspection supplies the specific visual corroboration; no universal font/ink guarantee is inferred.

## Why the width flag misleads here

I independently inspected cached Compose1.7.6 AAR bytecode under `../layout-static/`:

- `ParagraphLayoutCache.slowCreateTextLayoutResultOrNull` constructs MultiParagraph using incoming maximum constraints while retaining the original intrinsic `layoutSize` for TextLayoutResult.
- `TextLayoutResult.didOverflowWidth` compares result.size.width against multiParagraph.width, not the actual line right/glyph extent.

The runtime values above match that reconstruction exactly. The helper's message "Text layout clips…" therefore overstates what this width flag means for these compact simple-string labels.

## Density correction

Class names differ (platform DensityWithConverter, wrapper DensityImpl), but at actual OSfont2 both report identical sampled11/14/16/22/28sp conversions: **66/78/84/105/112px** at density3. This is not strictly linear2× scaling, and it does not support a wrapper-versus-platform conversion mismatch as the cause. Earlier descriptions calling the wrapper strictly linear were assumptions, not measured facts. Default OSfont1 and an intentional font2 wrapper naturally differ; the targeted false width flags occur in both environments.

## Raw locations

`text-nik-05-default-01/`:
- `62662f20-b67b-4732-9089-3a07f9c7010a/` — CONTINUE LISTENING.
- `97d0716d-bd25-4ca6-9181-11db15bcbb8d/` — −15.

`text-nik-05-narrow-01/`:
- `bbc9ee02-8e92-44d0-937e-5a2222565c3d/` — CONTINUE LISTENING.
- `97be4190-df4e-4555-90a3-c77ab9f5c4db/` — −15.

Each contains observation.json and test-scene.png. Raw tar archives/stdout remain in the run directories. `independent-analysis.json` binds observations/PNG checks and computed extents; `installed-identities.json` and `run-summary.json` retain exact installation/command boundaries.

## Next action

A TEST-ONLY evidence-backed replacement for this unreliable width predicate is justified. Keep exact target identity, visibility, ancestor checks, height/max-line/ellipsis/completeness checks and actual line/logical-character extents, with positive measured reconstruction cases and genuine clipping negatives. Do not remove all clipping checks, reduce font sizes, or change production layout merely to satisfy this proxy. Review the exact correction and perform a bounded ScreenSemantics rerun; do not rerun the accepted full gallery matrix.

Current05 gallery/layout evidence remains separate from these diagnostic assertion outcomes. No form-candidate acceptance or physical/native/product-E2E claim is made.
