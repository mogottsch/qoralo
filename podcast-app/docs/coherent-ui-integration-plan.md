# Coherent UI integration gate

**Plan only — not a new candidate or authorization to run it.** Freeze/execution waits for Nik's final readability audit and separate form-candidate approval. Old APKs, readiness records and raw failures stay immutable.

## Inputs and approval gates

| Slice | Exact source | State before integration |
|---|---|---|
| Production layout, accessible gallery and paired capture | `1aa5acdb30899b56afacd4a540f3b284502fff04` | Nik accepted 38 final pairs and observed visual fixes; raw original 20/24 results retained in `evidence/ui-polish-05-result/` |
| Readable-content test policy and regression controls | `c2ce81bf6d97b3838808104190a651b0fba62b9a` | Reported 34/34 bounded Android methods; final identity/result audit and cleanup pending |
| Owned asynchronous Paste/Agent acknowledgements | `31ab0b7046732b70d0929963b1ce17646db5256e` | Separate independent review and seven Android interactions at both sizes pending |

Do not transfer any of these passes to another candidate. If review requires changes to a slice, approve its replacement separately and recompute this plan's source identity/counts before freezing the integration candidate.

## 1. Prove the combined source, not just ancestry

Construct an isolated Git index from polish-05, replacing exactly:

- The **ten form source/test paths** from `31ab0b7` (its `app/src` diff against05).
- The **six Android-test file/asset paths** pinned by `evidence/text-readability-policy/source-isolation.json`, from `c2ce81b`.

These sets are disjoint. A host-only planning check reconstructed that union without editing the shared index or worktree. The expected `app/src` tree is **`314010f949ba5e33fe7845230c3c3b2b875d7c97`**, matching the currently committed app source. This is a source-composition check, not combined runtime validation.

Before packaging, repeat that reconstruction and compare every source blob and the complete source-file set with the nominated commit and worktree. Reject untracked/extra/stale app sources. Record the exact nominated commit, effective tree and all slice paths/blob identities. Also bind relevant app build/config files and test-fixture hashes.

Explicit invariants:

- `PlayerScreen.kt`, `GeneratingScreen.kt`, `LibraryScreen.kt`, `CommonUi.kt`, theme/resources and gallery activity/manifest/driver/policies remain the accepted05 versions. No lost seek/header/hero/IME/freshness/pairing fixes.
- The ten form paths match the approved form revision, including saved/queued acknowledgement, captured episode/form identity, retained local error/input, stale acknowledgement protection and post-IO transactional phase check.
- `ScreenSemanticsTest` and the readable-content helper/positive/negative controls match the approved policy slice; no return to the old raw paragraph-width predicate.
- Runtime/JNI, model routes, job recovery rules and physical diagnostic code are unchanged. Source inclusion is not proof that those runtimes work on hardware.

## 2. Build ONE coherent candidate

Use a new unique integration directory; do not reuse any frozen candidate name. **Do not exclude the form files this time.** Build both app and test APK from the same verified combined source. Do not pair the old05 app with a new test APK, or the form-only app/test pair with later policy code.

Run with `--max-workers=2`:

```sh
./gradlew --max-workers=2 :app:testDebugUnitTest :app:lintDebug \
  :app:compileReleaseKotlin :app:assembleDebug :app:assembleDebugAndroidTest
python3 -m unittest discover -s tools/tests -v
```

For the currently pinned slices, expect **113 JVM** and **15 Python** tests; tally XML and failure/skip counts instead of assuming those counts passed. Nine readability/control methods and seven form methods are Android tests, not additional JVM passes.

Verify the combined APKs include the intended form and test-policy classes/assets, with the same production ABI used to compile the tests. Compare packaged native-library entries with frozen05/trusted runtime identities; unexpected native payload drift blocks the freeze and does not authorize fresh native preparation. Hash the APKs and candidate manifest; record source/config proofs and logs. Check every old frozen candidate hash before/after. Restore the nominated c893 build-output APKs in a finally/trap even on failure; never overwrite old frozen artifacts or another agent's files/locks.

## 3. Proposed emulator acceptance on the new exact pair

Nik only, explicit `emulator-5556`, canonical lock, synthetic UI/media, no packs. Pi/Nik must authorize the final scope/budgets before execution. No physical/default ADB, native preparation, model load, inference or automatic retry.

First independently review the composition/isolation proof and check installed app/test hashes. Then run the **combined suites** at default OS settings and actual320dp/OSfont2:

| Suite | Methods per condition |
|---|---:|
| ScreenSemanticsTest | 8 |
| UiInteractionRegressionTest | 3 |
| PasteImeRegressionTest | 1 |
| TextReadabilityPolicyTest | 7 |
| TextReadabilityClippingTest | 2 |
| FormSubmissionInteractionTest | 7 |
| **Total** | **28** |

Proposed bound: one selected-class invocation per condition, **180 seconds each**, maximum two invocations (**56 methods**). Preserve exact settings, commands, result counts, failures and relevant opt-in text-layout/PasteIME evidence. If the runner/budget needs a different grouping, pin it in readiness before running, not after a timeout. The callbacks in form UI tests must remain synthetic; host repository/VM tests cover persistence/queue rejection without native model jobs.

For a final gallery tied to the **new production app hash**, propose a separate staged capture gate after the combined tests:

1. Genuine within-run `library,sources` smoke, **80 seconds**.
2. Separate Paste/actual-IME smoke, **100 seconds**.
3. Only if both validate, full15-frame matrices at both sizes, **600 seconds each**, plus the remaining seven distinct IME cells at **100 seconds each** (reuse the successful default Paste/IME cell).

This would be fresh coverage of the changed combined production candidate, **not a repeat of the unchanged05 matrix**. It is a proposed future integration gate, not authorization issued by this document. Pi may choose a narrower affected-frame scope, but then readiness must state that no new complete38-pair gallery was collected for the integration hash. Keep initial/failed-candidate images distinct, validate actual content and ownership, and hash-bind final pairs to the observed installed combined APK.

## 4. Completion and claims

Call the integrated UI polish ready only after:

- Both prerequisite slice approvals are final.
- Combined source proof, host validation and exact matched APK identities pass.
- Nik accepts the authorized combined emulator regressions and capture scope, with raw evidence retained and cleanup recorded.
- Any new failure is preserved and resolved in a separately frozen revision; no unchanged retry or retrospective pass rewriting.

This means **synthetic emulator UI/integration readiness only**. Physical TalkBack/playback/export, hardware-provider operation, model quality and production generation E2E remain separate gates. The S23 QNN device-initialization failure and whole-chapter capacity limit are still unresolved; this integration neither diagnoses nor approves a workaround for them.
