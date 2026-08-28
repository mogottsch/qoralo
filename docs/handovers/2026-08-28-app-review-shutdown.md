# Nik app-review shutdown handover — 2026-08-28

## State at shutdown

- Reviewer identity/scope: **Nik**, independent review of `podcast-app/`; no ownership of Janek's implementation files.
- Last commit accepted by Nik: `e867348` (**pre-native contract/UI gate only**).
- Native integration reviewed: `3a80e30`; result was **CHANGES REQUESTED before phone install**.
- Repository HEAD at shutdown: `e5c7942` (unrelated later experiment commits).
- Janek subsequently reported shutdown-safe host correction commit `4fb012d` with his handover at `docs/handovers/2026-08-28-podcast-app-shutdown.md`. Nik did **not** inspect or independently verify that commit before shutdown.
- Binding references remain `docs/app-ux-mvp.html` at `42ed50a` and `docs/podcast-generation-app-architecture-proposal.md` at `85f5d67`.

## Shared-tree changes and processes

Nik has no uncommitted implementation change and did not commit anything. The shared tree contains Janek-owned uncommitted `podcast-app/` corrections in:

- `app/build.gradle.kts`
- `app/src/main/cpp/podcast_runtime.cpp`
- `app/src/main/java/dev/vibevoice/podcast/model/ModelPackVerifier.kt`
- `app/src/main/java/dev/vibevoice/podcast/runtime/NativeEngines.kt`
- `app/src/test/java/dev/vibevoice/podcast/generation/GenerationCoordinatorTest.kt`
- `app/src/test/java/dev/vibevoice/podcast/model/ModelPackVerifierTest.kt`
- `tools/install_local_debug.sh`
- `tools/prepare_local_runtime.py`
- New: `app/src/main/cpp/tensor_validation.h`, `app/src/main/java/dev/vibevoice/podcast/runtime/SupertonicTextNormalizer.kt`, `app/src/test/cpp/`, `app/src/test/java/dev/vibevoice/podcast/runtime/SupertonicContractTest.kt`, `SupertonicTextNormalizerTest.kt`, `config/`, `tools/test_native_policies.sh`, and `tools/verify_apk_runtime.py`.

These files were not reviewed or tested by Nik before shutdown and must not be treated as accepted. Other agents also have unrelated dirty files/processes; do not clean, reset, kill, or commit them from this scope.

No Nik-owned compile/test/ADB process is running. Long Qwen/LFM processes and normal Gradle/Kotlin daemons observed at shutdown belong to other scopes. A pre-existing ADB server is running as PID 122115; Nik did not start or use it.

## Completed evidence

For exact commit `3a80e30`:

- Native-injected isolated review: `/tmp/podcast-3a80e30-native-review.rnpNkU`
- No-native isolated review: `/tmp/podcast-3a80e30-shell-review.mq5Pef`
- Both passed `clean`, `lintDebug`, `testDebugUnitTest` (**54/54**), `assembleDebug`, and `compileDebugAndroidTestKotlin`.
- Native CMake/JNI compiled; this is host build evidence, not runtime proof.
- Native APK contained the expected nine arm64 entries; shell APK contained only LiteRT JNI and AndroidX path JNI.
- Git tracking/ignore boundaries and the installer's priority plus `phone.lock` guards were checked.
- No ADB, install, instrumentation, native inference, playback, thermal test, or phone evidence was produced.

Review findings sent to Pi and Janek:

1. `prepare_local_runtime.py` was TOFU/self-authorizing: it hashed supplied files, generated manifests, then replaced BuildConfig pins without a separate accepted-hash authority.
2. AGP stripping changed authorized packaged bytes. Source → extracted APK at `3a80e30`:
   - `libonnxruntime.so`: `643c6f6fd3d2b375ca8f2407a1695acaf55320b8e947adc4284665640fdc3ae9` → `8b626b…46f1`
   - `libQnnHtpV73Skel.so`: `bd54463547f0234d06045699b1f747b7d9d3e3b581874840af50c295b3124f25` → `d82f94…bb86`
3. Supertonic preprocessing did not mirror accepted normalization and would reject ordinary newlines, curly punctuation, and precomposed accents.
4. Manifest capacities/runtime identity were not compared with native-introspected shapes/build identity.
5. Non-finite text/vector/vocoder outputs were not rejected before reuse/PCM quantization.

## External ignored artifacts

Current ignored local preparation occupies approximately `2.7G` under `podcast-app/.local` and `117M` under `podcast-app/app/runtime-libs`.

- Gemma pack: `podcast-app/.local/model-packs/gemma-4-e2b/current`
  - Manifest SHA-256: `9fb627ef9a4eb0ed49056c32bc16f2846e6edf68dc8d854b02af90e24e4e96cd`
  - Model declared SHA-256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`
  - Tokenizer declared SHA-256: `e594c8a90eb08d8bda498ff4747977dc827ae0c3c56b5c0d41a605a22d02ef03`
- Supertonic pack: `podcast-app/.local/model-packs/supertonic-3/current`
  - Manifest SHA-256: `dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d`
- Runtime provenance: `podcast-app/.local/runtime-provenance.json`
  - SHA-256: `ef0bd35c8af150cfd3a8080a97fea7d9db4fa04a950c2b0abd6b4067f4ebac35`
- Injected input libraries under `podcast-app/app/runtime-libs/arm64-v8a/`:
  - ORT `643c6f6f…c3ae9`
  - QnnHtpPrepare `db0a4c48…03c9e`
  - QnnHtp `a09b3af2…ee604`
  - QnnHtpV73Skel `bd544635…24f25`
  - QnnHtpV73Stub `2912cc4f…9036f`
  - QnnSystem `536201ed…05baa`

The accepted Supertonic context descriptors embed `v2.49.0.260730134355`; experiment 0023 used the matching QAIRT 2.49.0.260730 route. QAIRT 2.49.40 belongs to newer, separate LLM-QNN work and must not simply be relabeled or substituted for these contexts.

## Remaining blockers, risks, and claim boundary

- Janek's current corrections require exact diff review and clean isolated tests; none were accepted before shutdown.
- The correction must independently verify all supplied model, tokenizer, Supertonic stage, ORT, and QAIRT bytes before manifest creation/pinning.
- Extracted APK runtime bytes must exactly match accepted input hashes; especially preserve the DSP skeleton.
- Canonical text normalization, contract/native shape equality, exact runtime identity, and all-output finite checks need direct tests.
- T239 leaves only 230 chapter codepoints after `<en>` tags; L238 permits at most `238*3072/44100 = 16.58 s`. This cannot produce normal 1–2 minute complete chapters.
- If host corrections pass, approval is only for a **bounded physical wiring gate**: exact packaged libraries, four persistent sessions, canonical short render, QNN HTP/no-fallback proof, and explicit realistic-chapter capacity rejection. It is not product E2E approval or proof of a working podcast app.

## Exact restart step

1. Use Janek's correction commit `4fb012d`; do not test the dirty shared tree. His claimed native/no-native clean suites, 61/61 JVM tests, native policy, untrusted-input rejection, and eight-library APK byte/ELF preflight remain unverified by Nik.
2. Inspect only the app delta:

```bash
git diff --stat 3a80e30..4fb012d -- podcast-app
git diff 3a80e30..4fb012d -- podcast-app
git worktree add --detach /tmp/podcast-4fb012d-nik-review 4fb012d
```

3. In the isolated worktree, first inspect the final tool CLIs and trusted config, then prepare from the ignored accepted inputs without changing the shared tree:

```bash
cd /tmp/podcast-4fb012d-nik-review/podcast-app
python3 tools/prepare_local_runtime.py --help
python3 tools/verify_apk_runtime.py --help
```

4. Review the trust boundary and tests before starting one clean bounded suite. Then run the final documented preparation command followed by:

```bash
./gradlew --no-daemon clean lintDebug testDebugUnitTest assembleDebug compileDebugAndroidTestKotlin
bash tools/test_native_policies.sh
# Run tools/verify_apk_runtime.py with its documented final arguments against app/build/outputs/apk/debug/app-debug.apk.
```

Also repeat the suite in an isolated no-native shell. Do not request a phone gate until both paths pass and the extracted APK hashes are exact.

## Phone and lock cleanup

- No phone action was performed by Nik.
- `artifacts/locks/phone.lock` exists but `fuser` reported **no holder** at shutdown.
- No Nik-owned lock descriptor or child process remains.
- Phone priority was not assigned to Nik; do not install or invoke ADB for this app until Pi explicitly reassigns priority and the installer acquires the lock.
