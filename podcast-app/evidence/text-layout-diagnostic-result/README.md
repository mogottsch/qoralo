# Observed polish-05 text-layout false positives

The two approved diagnostic invocations completed, each running the same two failing methods against the unchanged polish-05 app and diagnostic test APK. The original assertions failed in all four cases. Shell exit status 0 is **not** a test pass: the retained instrumentation stdout reports two failures per invocation.

Janek independently checked all four observation/PNG hashes and installed APK identities, exact returned texts, line coverage and logical character extents, and inspected all four same-scene PNGs after Nik's independent review.

| Condition | Requested/returned text | Intrinsic size | Reconstructed paragraph | Line right |
|---|---|---:|---:|---:|
| Default OS; test's 320dp/font2 override | CONTINUE LISTENING | 619 × 84 | 650 × 84 | 617.2368 |
| Default OS; test's 320dp/font2 override | −15 | 119 × 98 | 330 × 98 | 117.04616 |
| Actual 320dp / OS font2 | CONTINUE LISTENING | 719 × 96 | 744 × 96 | 717.0664 |
| Actual 320dp / OS font2 | −15 | 135 × 112 | 378 × 112 | 133.2 |

Every observation returned exactly one layout for the requested text, with one complete non-ellipsized line, no height or max-line overflow, and line/logical-character boxes fitting the intrinsic dimensions. The same failing-test-scene PNGs visibly contain the full requested labels. Thus these four width flags are false positives for content clipping, not wrong-target selection. The paragraph's reconstructed maximum width exceeds intrinsic size; the actual content does not. Cached Compose 1.7.6 bytecode inspected independently by Janek and Nik matches this reconstruction/comparison.

## Correction to the diagnostic hypothesis

The earlier description of `Density(density.density, 2f)` as *strictly linear* was unverified and is withdrawn. In these OS-font2 observations, platform `DensityWithConverter`, wrapper `DensityImpl`, and the layout coordinator all map 11/14/16/22/28sp to **66/78/84/105/112px**. The sampled conversions are identical and are not the cause. At default OS font scale 1, the test intentionally overrides its content to font scale 2; those conversions differ, as expected. No broader converter-equivalence claim is made beyond the observed samples.

Frozen diagnostic sources/docs/readiness remain unchanged as historical artifacts. This separate result corrects the hypothesis; it does not rewrite old failures as passes. `+15` and the later player assertions did not execute after the failing `−15` assertion. The separate policy revision must execute them before claiming a complete ScreenSemantics pass.

`retained-manifest.json` binds all 16 original collected files under `raw/`, including stdout, installed identities, raw archives, four observations and four same-scene PNGs. No physical-device/model inference, retry, full-matrix rerun, or form switch occurred during the diagnostic collection. Nik's final overall polish report/cleanup is a separate artifact.
