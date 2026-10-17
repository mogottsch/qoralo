# Qoralo podcast app

Android podcast app: sources → on-device script → review/edit → narrated audio,
with a persistent player, local WAV export, episode diagnostics and deletion.
The [UX](../docs/app-ux-mvp.html) and
[architecture](../docs/podcast-generation-app-architecture-proposal.md) describe
the design; the [current closeout/runbook](docs/current-closeout.md) is the entry
point for build identities, delivery steps, evidence and remaining gaps.

## Current state

- Launcher **Qoralo**; app `dev.qoralo.podcast.internal`, instrumentation
  `dev.qoralo.podcast.internal.test`, Kotlin namespace `dev.qoralo.podcast`.
  The old `dev.vibevoice` app was removed; **do not use the legacy-ID build
  selector** for current delivery. Renaming an application ID does not migrate
  Android app data. [Rename history](docs/rebrand-qoralo.md).
- Last recorded phone app SHA-256 begins **`677f8d6f…`**, not the old
  `bf53c566…` episode-management build. The renamed GPU script and HTP voice
  routes have device evidence; owned export-byte checks are separate from the
  unproven system-picker hop. Later prompt round3/3b records and the final
  offline candidate have distinct provenance — see the runbook, not an old
  handoff's “current” heading.
- Frozen offline source **`1a089581`**, bundle
  `.local/closeout/20261017T075644Z-1a089581a3a0/`: app **`cc1f6436…`**, test
  **`9c40d918…`**. Active Gradle build/**lint pass**, JVM **301 discovered /
  288 executed / 13 skipped**, no failures/errors; APK assembly and native-byte
  verification pass. The earlier lint failure was fixed with explicit debug
  cursor cleanup, reviewed by Thomas and covered by eight passing host tests.
  Native bytes are unchanged; app bytes differ from the last phone-tested app.
  The prior `33fbfb4d` freeze is preserved, not overwritten.
- The weekend closeout is **host-only**: Moritz has the phone. No install,
  instrumentation, model inference or new listening verdict is authorized in
  this window. The frozen pair is not a new device pass.
- The Python historical scope suite is **not green**: eight retained source/hash
  drift failures after two obsolete behavioral checks were repaired.
  [Exact audit and reproducer](docs/host-scope-test-baseline.md).

## Build on an authorized, provisioned host

Start with the [fresh-clone setup guide](docs/getting-started.md) for what is
included, separately authorized inputs and the current provisioning/helper gaps.
[Own-code licensing remains a proposal](docs/licensing-recommendation.md), not a
blanket license for model/vendor payloads or third-party assets.

The final host build used **OpenJDK 21.0.12.1+1 / Gradle 8.9**; Java/Kotlin
bytecode target **17** is separate. Requires Android compile/target SDK 35
(min 29), build-tools **35.0.0**, NDK **28.1.13356709**, CMake **3.22.1**,
Python 3 and the Gradle dependency cache for offline builds. Native deployment
target: Galaxy S23 Ultra, SM8550 / V73, arm64-v8a. Gradle's wrapper pins the build tool; do not run parallel builds in
this shared checkout.

```bash
cd podcast-app
./gradlew --offline --no-daemon --max-workers=2 \
  -Ppodcast.legacyApplicationId=false -Ppodcast.shortProductE2e=false \
  :app:testDebugUnitTest --rerun :app:assembleDebug :app:assembleDebugAndroidTest \
  :app:compileReleaseKotlin :app:lintDebug :app:testNativePolicies
python3 -m unittest discover -s tools/tests -v  # eight documented failures, not green
python3 -m unittest discover -s tools/provider_pipeline -p test_pipeline.py -v
```

Model/vendor assets are **not in Git**. A checkout alone is not a runnable neural
build: acquire the licensed local inputs separately, prepare/verify them, and
retain the effective configuration. Missing runtime/model assets are a genuine
provisioning blocker, not permission for fallback. Full steps and the frozen
candidate manifest are in the [runbook](docs/current-closeout.md).

## Two accelerator routes, not interchangeable

| Work | Model/runtime | Execution |
| --- | --- | --- |
| Script, outline, edits | Gemma 4 E2B, LiteRT-LM **0.16.1** | **GPU**, `GEMMA_4_E2B_LITERT_GPU` |
| Narration | Supertonic 3 provider recipe, ORT **1.27.1** + QAIRT **2.49.0.260730** | **QNN/HTP**, `SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP` |

There is no CPU neural fallback, alternate model or silent repair route.
Non-neural normalization and file work on CPU do not make Gemma an HTP route.
The normal voice pack is **`supertonic-3-provider`**, manifest `423429c6…`, not
legacy `supertonic-3` or experimental T2048/L2048. Provider-prescribed sentence
segments use four reusable T320/L512 contexts, eight steps, speed 1.05 and their
own predicted native duration, without stretching or forced word splitting.
Immutable chunks permit progressive listening; the completed canonical WAV is
the later export unit. [Provider details and numerical caveats](docs/provider-htp-integration.md).

## Pack and install rules

Data-only packs live in the app's `no_backup/model-packs/<id>/current/`, with
manifest/file sizes and SHA-256 verified against the APK's pins. Executable code
belongs in the APK, never writable pack storage. Licensed native inputs live in
ignored `app/runtime-libs/arm64-v8a/`; local packs, runtime provenance and APKs
remain under ignored `.local/`. Never push model/vendor payloads or credentials.

When phone work is authorized, delivery includes installation and launch
verification; do not ask for a separate install approval. Take
`artifacts/locks/phone.lock`, pin every command to `R5CW81PR8SY`, avoid active
user generation, and **install both APKs with `adb install -r -t --user 0`**.
Never default/all-user install: the work profile must stay clean. Use the
[frozen-pair procedure](docs/current-closeout.md#install-on-personal-user-0-when-the-phone-returns),
not arbitrary shared `app/build/outputs` files. The existing
`tools/install_local_debug.sh` has the user-0 flag, but still stages the legacy
voice pack and installs only the app; it is **not** a complete normal-provider
pair/provisioning path.

Historical feature reports remain valid for their own APKs, not as current
installation nominations: [UI copy](docs/ui-minimal-handoff-2026-09-20.md),
[episode management](docs/episode-management-handoff-2026-09-14.md),
[progressive player](docs/progressive-player-handoff-2026-09-13.md), and
[provider publication/recovery](docs/provider-app-handoff-2026-09-12.md).
