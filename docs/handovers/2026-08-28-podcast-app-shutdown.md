# Podcast app shutdown handover — 2026-08-28

## Scope and ownership

- Owner: Janek
- Reserved implementation: `podcast-app/`
- Binding inputs: `docs/app-ux-mvp.html` at `42ed50a` and `docs/podcast-generation-app-architecture-proposal.md` at `85f5d67`
- Last independently accepted pre-native commit before this correction: `e867348`
- No experiment or UX source file was edited.

## Current host-native correction

The working tree closes Nik's review findings against `3a80e30`:

- Adds separately reviewed `podcast-app/config/trusted-local-runtime.json` with exact Gemma model/tokenizer, LiteRT AAR/JNI, accepted experiment-0023 stage-manifest, ORT, QAIRT library, byte-size, hash, ELF, SONAME, and fixed-shape identities.
- `prepare_local_runtime.py` verifies the independent authority, the complete accepted 0023 stage manifest and payload, every injected runtime library, both Gemma artifacts, the LiteRT AAR, and pre-authorized generated pack-manifest hashes before changing local outputs. An altered tokenizer was tested and rejected.
- AGP `keepDebugSymbols` prevents mutation of LiteRT, ORT, QNN host/stub, and DSP skeleton binaries.
- `verify_apk_runtime.py` extracts the APK and requires exact trusted bytes plus ELF class/machine/SONAME. It separately records the app-built bridge.
- `SupertonicTextNormalizer` mirrors accepted punctuation/symbol/whitespace/terminal-punctuation/NFKD preprocessing and removes supplementary code points before the JNI modified-UTF8 boundary.
- `VerifiedModelPack` carries typed Gemma/Supertonic contracts. Supertonic load requires exact native T/L/C/steps/sample/channel/PCM readiness and full `ONNX Runtime 1.27.1 / QAIRT 2.49.0.260730` identity.
- Every native duration/text/vector/vocoder output is rejected if empty or non-finite before reuse or PCM conversion. The shared C++ policy has a host executable test.

## Completed evidence

### Native-injected build

Commands completed successfully before shutdown:

```bash
cd podcast-app
./tools/prepare_local_runtime.py
./gradlew clean :app:testNativePolicies :app:lintDebug :app:testDebugUnitTest \
  :app:assembleDebug :app:compileDebugAndroidTestKotlin
./tools/verify_apk_runtime.py
```

Results:

- Gradle build/lint/Android-test compilation: passed.
- JVM tests: 61/61 passed after correcting the normalizer fixture against the accepted canonical replacement order.
- Native policy executable: passed finite values and rejected positive infinity, negative infinity, NaN, and empty output.
- Final native-enabled APK SHA-256: `2d88460baac18e4325516c1d701b48fcf299355a59aad5b4c4c5146d47a94de7`.
- APK runtime preflight: passed, 8 checked libraries.
- APK retained accepted `libonnxruntime.so` SHA-256 `643c6f6f…c3ae9` and DSP6 `libQnnHtpV73Skel.so` SHA-256 `bd544635…24f25` exactly; all six injected identities, LiteRT JNI, and app bridge passed ELF/SONAME checks.

### Isolated no-native shell

With `local.properties` temporarily reduced to `sdk.dir`, this completed successfully:

```bash
./gradlew clean :app:testNativePolicies :app:lintDebug :app:testDebugUnitTest \
  :app:assembleDebug :app:compileDebugAndroidTestKotlin
```

Result: 61/61 JVM tests passed and the shell remained buildable without private runtime inputs. `local.properties` was restored afterward.

### Fast shutdown checks

- `bash -n` for both shell tools: passed.
- `python3 -m py_compile` for both Python tools: passed.
- `tools/test_native_policies.sh`: passed.
- `git diff --check -- podcast-app`: passed.

## External ignored artifacts

All remain Git-ignored and must not be committed or published:

- Prepared packs: `podcast-app/.local/model-packs/`
  - Gemma manifest: `9fb627ef9a4eb0ed49056c32bc16f2846e6edf68dc8d854b02af90e24e4e96cd`
  - Supertonic manifest: `dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d`
- Injected libraries: `podcast-app/app/runtime-libs/arm64-v8a/`
- Private source provenance: `podcast-app/.local/runtime-provenance.json`
- APK extraction evidence: `podcast-app/.local/apk-runtime-provenance.json`
- Local pins/build switch: `podcast-app/local.properties`
- Native-enabled APK: `podcast-app/app/build/outputs/apk/debug/app-debug.apk`

The complete trusted expected identities are in `podcast-app/config/trusted-local-runtime.json`; private absolute source paths remain only in ignored provenance.

## Blockers, risks, and claim boundary

- No host implementation blocker remains at shutdown.
- Physical execution is entirely unproven. No ADB command, installation, phone test, or Android instrumentation run occurred.
- The accepted Supertonic pack remains T239/L238: at most 230 normalized text code points and about 16.58 seconds. It cannot represent the binding 1–2 minute complete chapters. The first physical gate may prove short-sentence wiring and must prove realistic chapter rejection; it is not product E2E approval.
- LiteRT GPU selection, four QNN/HTP session creation, no CPU fallback, Android process death/timeout, playback/export, internal-storage atomic move, UI clipping/TalkBack, and thermal behavior all remain physical gates.
- Namespace-atomic final directory publication is host-tested. Sudden-power-loss durability is not claimed.

## Exact restart step

1. Independently review the correction commit and rerun both native-enabled and no-native suites above.
2. Rerun:

   ```bash
   cd podcast-app
   ./tools/prepare_local_runtime.py
   ./gradlew :app:assembleDebug :app:testNativePolicies
   ./tools/verify_apk_runtime.py
   ```

3. Only after review, obtain explicit Pi phone priority.
4. Acquire `artifacts/locks/phone.lock` for the complete ADB lifecycle. Use the gated installer only with `PODCAST_PHONE_PRIORITY=approved`.
5. First physical gate: install; run all Compose instrumentation; inspect Galaxy screenshots/TalkBack; load exact LiteRT GPU and four QNN/HTP contexts; render one canonical short sentence; retain provider/no-fallback evidence; submit one realistic full chapter and record its explicit capacity rejection. Do not label this product E2E.
6. The expected capacity rejection triggers the architecture decision about a larger one-call compiled graph. Do not add hidden chunking, stitching, CPU fallback, or another model.

## Process and phone cleanup

- No long compile, conversion, Gradle invocation, CMake/Ninja build, preparation tool, or verifier process is running.
- No ADB command was issued during this scope.
- `artifacts/locks/phone.lock` was checked and is free.
- This session never acquired the phone lock and created no remote phone path or process.
