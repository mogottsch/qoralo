# Scoped correction: new paired-run APK postflight was not observed

The new paired controller defined `_cleanup_root`, but the preserved lifecycle invokes `_finish_remote`. The proposed postflight APK check therefore never ran. **Genuine preflight hash verification must not be reported as before-and-after verification.**

## Claims superseded

- The postflight promise in `matched-prefill-reference-readiness-01` was not wired into the actual lifecycle.
- The derived `paired-prefill-checkpoint-02` claim that APK hashes matched “before and after” is withdrawn. The verified hashes are **preflight only**.
- The allocation-observer preparation inherited the same unused override. For `allocation-20260912T144721Z-01`, no postflight APK command or postflight identity observation exists either.

The affected new readmes carry explicit correction banners. Original derived readmes and checksum manifests are retained verbatim under `original-derived/`, with bindings. Original native errors, captures, command receipts, profiles, run-result JSON and private originals are not changed. These are additive corrections, not an inference replay or history rewrite.

## What remains valid

The fresh preflight hashes, read-only job/playback observations, actual command records, complete/partial raw-pull facts, verified owned-process/root absence and phone-lock release remain distinct evidence. A controller that performed no app-modifying action is not by itself proof of postflight APK byte identity.

This correction is confined to the **new paired controller introduced in `41662f52`, its `38ab443e` correction and the `b2a2ed57` allocation adapter**. It does not invalidate independent Janek post-install evidence or earlier source/runtime runs, which are not being relabeled or re-audited here. Run 01 stopped before native launch and did not claim a postflight observation.

## Future lifecycle fix

The controller now overrides the actual `_finish_remote` hook. Base raw preservation and cleanup run first; the postflight check is then attempted under the same held lease. Its result explicitly distinguishes verified, failed/unavailable and not-launched states. A postflight error cannot replace an independent successful cleanup result or suppress preservation of an incomplete capture.

Fake-transport tests execute the actual `Controller.run` dispatch, including:

1. Successful native completion, raw pull, cleanup and then postflight.
2. Native failure with raw retention, cleanup and postflight.
3. Capture-transfer failure: keep the partial raw/root, still record postflight, release the lease.
4. Postflight failure: keep the already verified cleanup and record identity verification as unavailable/failed.

All device traffic in these tests is fake. No additional phone verification, app access, model run, AS-limit change or replay was performed for this correction. Future device work still requires its own scoped slot and current identities.
