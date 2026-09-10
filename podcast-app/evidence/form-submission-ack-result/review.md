# Nik independent form-acknowledgement review — 31ab0b7

**APPROVED for the scoped Paste/Agent acknowledgement behavior.** Host and synthetic Android evidence establish the tested rejection-retention, success-only clearing, stale acknowledgement and episode-ownership guards. This is not acceptance of a combined application build, physical/native runtime, or general ingestion/export behavior.

## Exact candidate

- Source: `31ab0b7046732b70d0929963b1ce17646db5256e`; readiness: `6ee8d38`.
- App/src tree: `310e50772adc9d51f843c1e95df16fe5d7500712`.
- App APK SHA-256: `1cfe1419d974ac4e88d3039806a1a6bc849b602ec3036a474cd877f068ed8e7d`.
- Test APK SHA-256: `32d89391dcad7e455bbbd6c15359131bc1a872cfe9d3511b507449ee205a2f4b`.
- Candidate SHA-256: `386f1c5ce7dfc458c55f648763b9aa289e28c861bfe765bac28548c554d7672c`.

Frozen and installed emulator APK identities were independently checked. Review/build worktree: `/home/moritz/.cache/nik-podcast-reviews/31ab0b7`.

Provenance correction: PlayerScreen, GeneratingScreen and LibraryScreen are byte-identical to05 source1aa5acdb, independently verified by blob hashes. This is05's same three layout files plus form changes, not an older version of those layouts. It is nevertheless a different app/test pair without the later readability overlay, so no integrated visual/test acceptance is inferred.

## Source review accepted

- Paste awaits actual source persistence; Agent awaits transactionally accepted queueing/user-message insertion. Agent acknowledgement does NOT mean the model edit completed.
- VM APIs return Deferred completion and propagate failure to the originating form. Paste/Agent callbacks capture immutable episode IDs; source deletion uses the source's episode owner. No mutable current-selection lookup is used for these submission acknowledgements.
- Each form has a lifetime ID, submission sequence and input revision. Duplicate pending submit is suppressed before dispatch. Any edit, including edit-undo, makes an older success unable to clear/dismiss current input.
- Disposed/replacement forms ignore old acknowledgements. Cancellation is rethrown rather than labelled rejection. A VM-owned operation already dispatched can finish for its original owner after the form closes; closing does not falsely promise to undo persistence.
- Current-input errors retain exact text and show a local error; keyboard/focus handling makes the current failure visible. Older-input feedback distinguishes the previous submission and keeps newer text.
- Sources/Review composition lifetimes and displayed rows are episode/revision filtered. Selecting an episode resets modal state.
- Source insertion rechecks the captured episode phase inside a Room transaction AFTER stream/file IO. If queueing froze the input in the meantime, insertion is rejected and the new source file is removed. The queue and source commit cannot silently interleave a late source into a frozen generation request.
- No automatic resubmission, native fallback/recovery, direct script editor, or model call was introduced by these forms.

This gate covers Paste and Agent submission forms. It does not automatically validate all document-picker, export, background-process or physical failure paths.

## Independent host validation

```sh
python3 -m unittest discover -s tools/tests -v
./gradlew --no-daemon --max-workers=2 :app:testDebugUnitTest :app:lintDebug :app:compileReleaseKotlin
```

**113/113 JVM tests and15/15 Python tests passed**, zero JVM failures/errors/skips. Lint/release Kotlin compilation passed. No native/model preparation was repeated.

The new host tests include nine form-state cases and five actual in-memory repository/VM cases: pending/duplicate rejection; exact rejection/no retry; newer edits; disposed/replaced/out-of-order acknowledgements; cancellation; queue rejection before message insertion; storage/empty-source validation errors; captured A owner after selecting B; post-IO source completion after queue freeze with file/row invariants.

Host tests are not physical service/lifecycle evidence.

## Actual Android execution

Only `FormSubmissionInteractionTest` was selected, once per condition:

| Environment | Result |
|---|---:|
|1080×2400/420dpi/~411dp/OSfont1 |7/7 PASS |
|960×2058/480dpi/320dp/OSfont2 |7/7 PASS |

**14/14 executed UI tests passed.** Each invocation had a120s external bound and45s per-test instrumentation ceiling, finishing in about10s. No retry/full matrix was run.

The class uses production forms with synthetic suspend callbacks/completable gates, not repositories/services/models. It executes:

1. Paste save rejection retains exact title/body and visible local error.
2. Agent queue rejection retains exact request/error and no misleading Changes ready state.
3. Paste remains pending until success, then dismisses once.
4. Older Paste success cannot dismiss/clear newer edits.
5. A dismissed form's non-cancellable late completion cannot affect its replacement.
6. Unchanged Agent text clears only after queue acknowledgement.
7. Older Agent acknowledgement cannot clear newer input.

UI local-error visibility is tested; physical TalkBack speech is not. The actual repository/IO guard evidence comes from the separate host tests above, not these synthetic callbacks.

## Artifacts and cleanup

- `boot-install.json`: exact APK hashes/commands and emulator identity.
- `android-test-summary.json`, `form-{default,narrow}.stdout/.stderr`: raw executed results and conditions.
- `host-and-scope-summary.json`: independent113/15 counts and matching05 layout blob identities.
- Isolated app `.local/review-evidence/host-suite.log` and `python-suite.log`.
- `cleanup.txt`, emulator supervisor/cleanup logs.

Sole existing fg-test/emulator-5556, API35 Google APIs x86_64 with declared ARM translation,2048MiB/2cores/software graphics/read-only/no snapshots,disk-backed scratch. No packs were present. Every ADB command explicitly addressed emulator-5556 under canonical phone.lock; children did not inherit the lock.

After execution, app/test were force-stopped, display/font settings reset and the read-only emulator stopped. No owned emulator/review command remained, tracked app diff was empty, and phone.lock was free. No physical/default ADB, model inference, implementation edit, or modification of frozen05/readability/form candidates occurred.

## Next gate

A coherent matched app/test pair may now be prepared from the separately accepted production/UI/form/test slices under Pi's coordination. It still needs exact source/native-byte invariants and the explicitly assigned combined regression/capture gate. Do not transfer this14/14 result to an unreviewed integrated APK. Native QNN device initialization, whole-chapter capacity, physical playback/export/accessibility and product E2E remain separate blockers/gates.
