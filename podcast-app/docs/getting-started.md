# Getting started with the Android prototype

**A fresh clone is not a ready-to-run neural app.** It contains app/JNI source,
Gradle configuration, tests, small fixtures and artifact hashes. Model weights,
licensed native runtime libraries, prepared QNN contexts, local configuration,
dependency caches and frozen APKs are supplied separately. The measured target
is a Galaxy S23 Ultra (SM-S918B, SM8550/V73, arm64-v8a); other phones are not
qualified by these results. Our original app code, tests and tools are
[Apache-2.0 licensed](licensing-recommendation.md); third-party material retains
its own terms.

The [current closeout](current-closeout.md) is the authority for candidate hashes,
exact test coverage and delivery. Its final APK is **host-tested, not a new phone
pass**. This guide documents that existing route; it is not a newly tested
clean-machine installation.

## 1. Host tools

The final closeout used Linux x86-64, **OpenJDK 21.0.12.1+1** as both Gradle
launcher and daemon, and the checked-in **Gradle 8.9** wrapper. Java/Kotlin
**bytecode target 17** is a compiler setting, not the JDK used in that build.
Android Studio is optional; command-line tools are sufficient.

Install/authorize these separately:

- Android SDK platform **35**, build-tools **35.0.0**, NDK **28.1.13356709**
  (r28b), CMake **3.22.1**, and platform-tools for eventual device work.
  App compile/target API is 35, minimum API 29; that minimum is not a hardware
  compatibility claim.
- Git, Python 3, Bash, a host C++17 compiler (`c++` or `CXX`) and binutils
  `readelf`; `flock` is required for coordinated phone access.
- The wrapper distribution and Maven/Gradle dependencies. AGP **8.7.3**,
  Kotlin **2.3.0** and LiteRT-LM Android **0.16.1** are pinned in the build.
  `--offline` assumes these downloads are already cached. An authorized host
  can resolve ordinary build dependencies online; Gradle does not fetch the
  model/context/vendor inputs below. No hermetic Python environment is supplied.

## 2. Authorized local inputs

From repository root, work in `podcast-app/`. Obtain rights to use each input
before acquiring it; stop for human approval if acquisition introduces an account,
new terms or an export attestation. Do not publish the resulting packs or APKs
merely because a preparation/build command succeeds.

| Input, outside Git | Existing authority / preparation |
| --- | --- |
| Gemma `.litertlm` and its matching tokenizer | [Trusted hashes](../config/trusted-local-runtime.json), originating from [experiment 0025](../../experiments/0025-gemma-4-e2b-it-android/README.md). The pinned GPU route uses `gemma-4-E2B-it.litertlm`, **not** the incompatible dedicated `-gpu` artifact. |
| ONNX Runtime **1.27.1** headers and the six reviewed ORT/QAIRT **2.49.0.260730** Android/V73 runtime libraries | Same hash authority. Generic desktop ORT or a different SDK build is not a substitute. Libraries are injected into ignored `app/runtime-libs/arm64-v8a/`; CMake builds the app bridge. |
| Legacy accepted Supertonic stage, then the four accepted provider context exports | [Provider authority](../config/trusted-supertonic-provider.json), [normal pack selector](../config/normal-supertonic-pack.properties), and the provisioning section of [current closeout](current-closeout.md#provisioning-prerequisites-not-repository-payloads). These are compiled, device/backend-specific inputs, not included model downloads. |

Existing preparation commands, **only after those inputs are available**:

```bash
cd podcast-app
python3 tools/prepare_local_runtime.py --help  # paths/defaults; no provisioning
python3 tools/prepare_local_runtime.py         # verifies inputs, injects libs, writes local.properties
python3 tools/provider_pipeline/prepare_pack.py
```

The first helper expects accepted inputs under the historical experiment paths
(or its explicit CLI overrides). It **recreates** the local Gemma and legacy
`supertonic-3` pack directories. Do not rerun it over a prepared host gratuitously.
The provider helper separately requires the accepted duration/text exports under
`.local/provider-integration/` and vector/vocoder exports under experiment 0037.
It refuses an existing provider destination and **writes the tracked provider
authority JSON**: inspect the diff and require agreement with the reviewed pins,
not an automatic trust update. Neither helper is an end-to-end download/compiler
installer; missing accepted context exports remain a provisioning gap.

Set `sdk.dir` in ignored `local.properties`. Preparation supplies
`native.runtime.enabled=true`, `onnxruntime.include.dir` and
`gemma.manifest.sha256`. The **normal** voice selector comes from
`config/normal-supertonic-pack.properties`, not the legacy
`supertonic.manifest.sha256` local property. Required deployment packs are
`.local/model-packs/{gemma-4-e2b,supertonic-3-provider}/current/`.
Keep both model packs data-only; verify every manifest-listed file, not only the
manifest hash. Do not disable native injection or silently switch to CPU to make
an incomplete neural setup appear successful.

## 3. Build and check the provisioned host

Use the wrapper; serialize Gradle/native builds if sharing a checkout. This is the
existing tested closeout command, not proof that a new clone has its prerequisites:

```bash
./gradlew --offline --no-daemon --max-workers=2 \
  -Ppodcast.legacyApplicationId=false -Ppodcast.shortProductE2e=false \
  :app:testDebugUnitTest --rerun :app:assembleDebug :app:assembleDebugAndroidTest \
  :app:compileReleaseKotlin :app:lintDebug :app:testNativePolicies
python3 -m unittest discover -s tools/provider_pipeline -p test_pipeline.py -v
python3 -m unittest discover -s tools/tests -v
```

Outputs: `app/build/outputs/apk/debug/app-debug.apk` and
`app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk`.
The closeout records Gradle/lint success, **288 JVM cases executed, 13 skipped**,
15 provider tests passed, and **eight retained historical failures** in the
106-case general Python suite. Preserve/report that nonzero result; do not call
all host checks green or skipped pack-gated tests passed. See the
[scope-test audit](host-scope-test-baseline.md).

## 4. Deployment is still a separate developer step

For authorized phone work, follow the
[personal-user frozen-pair and provider-pack procedure](current-closeout.md#install-on-personal-user-0-when-the-phone-returns).
Use a nominated matching app/test pair, acquire `artifacts/locks/phone.lock`,
select the serial explicitly, and do not interrupt an active user job.
**Both app and test installs require `adb install -r -t --user 0`.** Never install
into a work profile or use the legacy application-ID selector for current delivery.

`tools/install_local_debug.sh` is **not provider-complete**: it installs only the
app and stages legacy `supertonic-3`, while the normal build selects
`supertonic-3-provider`. It is not a one-command deployment path for this app.
The runbook explains staging verified Gemma/provider data through `run-as` into
`no_backup/model-packs/<id>/current/`, avoiding nested/replaced active packs, and
checking installed APK and pack identities. No turnkey clean-clone provisioning,
automatic vendor redistribution or new device/listening acceptance is promised.
