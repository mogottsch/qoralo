# Coherent UI integration candidate — fb16b90, build attempt02

**Host validated and frozen; independent combined emulator gate pending.** This is not final UI polish, physical-runtime or product-E2E approval.

## Exact composition and artifacts

Source anchor: `fb16b90e493c24e2d0b5f289c393b4cd5b5abd4f`.

The isolated-index proof reconstructs polish-05 `1aa5acdb` plus exactly ten approved form paths from `31ab0b7` and six approved readability-test/asset paths from `c2ce81b`. All **92 source files** match both the nominated committed tree and actual build worktree, with no excluded, extra, untracked or stale source files.

Effective `app/src` tree: **`314010f949ba5e33fe7845230c3c3b2b875d7c97`**. The accepted gallery, three layout fixes, common UI/theme/resources and runtime/JNI trees remain pinned to05. The form and readability changes are both present, not temporarily isolated out.

Frozen directory: `podcast-app/.local/integration-ready/fb16b90-02/`.

| Artifact | SHA-256 |
|---|---|
| `app.apk` | `1cfe1419d974ac4e88d3039806a1a6bc849b602ec3036a474cd877f068ed8e7d` |
| `test.apk` | `b03d8fe7f87325d3db3bf1d6a349b87fad8955b7e41da905655167aae80af76d` |
| `candidate.json` | `2b3c1ed1c8fe8683f3a87dc1f6491efbd989775218cc8786f4fd4f33457379e7` |

Both APKs came from the same combined build. The app is byte-identical to the approved form app because its production/debug inputs already contained05 plus the form changes; the later readability overlay changes only the test APK. This is expected, not a substitution of an older app. Existing separate test passes do not automatically validate the newly matched pair.

## Executed host validation

- **113 JVM tests executed**, zero failures/errors/skips; the JVM task was not UP-TO-DATE.
- **15 Python tests executed**, all passed.
- Debug lint, release Kotlin, debug app assembly and Android-test assembly passed.
- The normal host assembly invoked CMake for the existing bridge; no model/context/native-pack preparation was run.
- All **nine packaged native-library entries**, including the app bridge and AndroidX library, exactly match05 in entry set, byte length and SHA-256. The independent trusted-runtime verifier also passes its eight runtime ELF/pin checks.
- Form implementations and all selected interaction/readability classes are present in the appropriate DEX. The packaged measured-label fixture matches its pinned source hash.
- Tracked source/build/test/tool/authority inputs and existing local native libraries/headers/pins are hash-bound. Resolved external application/test/release and buildscript dependencies are recorded in **849 configuration records / 281 unique files**. Internal project code is covered by the complete source and matched-APK proofs, not ambiguous external-artifact resolution.
- Prior frozen APK/candidate hashes checked unchanged; the nominated old c893 Gradle-output APKs restored. **Do not install normal Gradle output paths as this candidate.**

`attempt-02/` retains the immutable build script, commands, all proofs and logs, JUnit XML, dependency inventory, runtime comparison and candidate manifest. APKs/dependencies/licensed runtime binaries remain outside Git.

## Retained host inventory failure

`host-inventory-attempt-01/` retains the first attempt unchanged. Its new metadata collector tried to resolve Android's self-project artifacts without an artifact-type selector and captured Project state under configuration caching. Gradle rejected that inventory task **before any app test or assembly ran**. The finally block restored old APK outputs and checked all frozen hashes.

Attempt02 changed only the host collector: an external-module artifact view avoids internal-project variant ambiguity, and `--no-configuration-cache` is used for that temporary metadata task. It ran offline with `--max-workers=2`. Neither attempt changed app implementation or test policy. This is a retained host-tooling failure, not an app/runtime failure and not an unchanged emulator retry.

## Proposed separate gate

Pi must assign the exact candidate to Nik before any execution. Proposed scope remains the reviewed integration plan:

- **28 methods at each of two conditions**, maximum two invocations, **180s each**: ScreenSemantics8, UiInteraction3, PasteIME1, readability-policy7, real-clipping2, form-interaction7.
- Default OS and actual320dp/OSfont2, explicit `emulator-5556`, sole Nik operator/canonical lock, synthetic UI/media only, no packs.
- After successful combined tests: genuine `library,sources` smoke (**80s**), default Paste/actual-IME smoke (**100s**); only after both validate, two complete15-frame matrices (**600s each**) and seven remaining distinct IME cells (**100s each**), reusing the successful default Paste/IME cell.
- Fresh observed installed APK/image/tree hashes, actual content and ownership checks, retained initial/failed candidates, no unchanged retry. Preserve every failure and stop/report rather than weakening assertions or silently switching candidates.

No emulator/physical/model activity was performed for this readiness. Physical TalkBack/playback/export, QNN startup, whole-chapter capacity and product generation E2E remain separate unresolved gates. Earlier raw failed assertions and the accepted05 matrix are unchanged.
