# Rebrand to Qoralo

The app is named **Qoralo** (“ko-RAH-lo”). The previous name borrowed Microsoft's VibeVoice model, which this app no longer uses: narration is rendered by the Supertonic provider pipeline on the device's own NPU.

## What the name means

It is a coined name, not an acronym.

- **Q** — Qualcomm, from *quality communications*; every model stage runs on the phone's own accelerator.
- **-oral-** — Latin *os/oris*, mouth: material meant to be spoken aloud.
- **-o** — an open spoken ending. Somali *qoraal* (“writing”) is a pleasant coincidence noticed while screening the name, not its origin.

Read as: **your writing, spoken, on your own device.**

Shorter names screened first were already used by software companies or apps: Qoral, Akou, Eidon, Loqi, Qoda, Qorus, Loquora, Phonoid and Qorali. A web screen is not a trademark-register or store clearance, and none has been performed.

## Changed in this step

- Launcher and accessibility name `VibeVoice` → **Qoralo** (`app_name`).
- Platform theme `Theme.VibeVoice` → `Theme.Qoralo`; Compose `VibeVoiceTheme`/`VibeVoiceColors` → `QoraloTheme`/`QoraloColors`. Colours, typography and layout are unchanged.
- Gradle root project `VibeVoicePodcast` → `Qoralo`.
- Kotlin/Java package `dev.vibevoice.podcast` → `dev.qoralo.podcast`, including the JNI class paths resolved by `RegisterNatives` in `podcast_runtime.cpp` and `provider_runtime.cpp`.
- Application ID `dev.vibevoice.podcast.internal` → `dev.qoralo.podcast.internal`; instrumentation `…internal.test`.
- Room schema directory `app/schemas/dev.vibevoice.podcast.data.PodcastDatabase/` → `…dev.qoralo…`. The schema JSON itself is byte-identical; the database version and identity hash are unchanged.
- Controller tooling, gate configuration and the install helper's staging path.
- Repository and app documentation describing the current product.

### Re-pinned integrity hashes

Some gate controllers embed the SHA-256 of sibling controllers, so a package rename inside them changes those pins. They were re-pinned mechanically, and the superseded values are recorded here:

| File | Old SHA-256 | New SHA-256 |
| --- | --- | --- |
| `tools/run_tts_only_gate.py` (privacy source) | `a62d204c…62bec3c` | `0d4a150f…cbf64120` |
| `tools/run_tts_long_gate.py` (long caller) | `a87b3f35…40815a4` | `841fcb89…c519def` |

Historical evidence receipts keep the original values. Nothing in `evidence/` was rewritten.

## Consequences for the installed app

Android identifies an app by its application ID, so the renamed build is a **different app** from the one currently installed:

- The installed `dev.vibevoice.podcast.internal` app and all of its data stay exactly where they are. Nothing is deleted or overwritten by installing Qoralo.
- The new build starts with an empty library. Existing episodes, sources, revisions, jobs, playback positions and audio files will not appear in it until they are migrated.
- Every prior installed-hash binding, receipt and preservation count refers to the old ID and remains accurate for the build it describes.
- The app's own JNI library is rebuilt because the registered class paths changed, so its hash differs from `01d2ba53…`. The eight vendored ONNX Runtime/QNN libraries are untouched.

### Rebuilt native bridge

`RegisterNatives` resolves its classes by name, so `podcast_runtime.cpp` and `provider_runtime.cpp` had to change and the bridge had to be recompiled. Keeping the old prebuilt library would have failed at native initialisation.

- Build directory `.local/provider-integration/native-build-02-qoralo/`, same NDK 28.1.13356709 / CMake 3.22.1 toolchain, `arm64-v8a`, `android-29`, `c++_static`, Debug, as the original bridge.
- Unstripped bridge `059a4c31f91fef681891312db6e67d8a17f16dbce79d0359cd9b64325a8f5cc0`; packaged after AGP stripping `44a41cd41eabd1022c3363b816276c102b0274ab1a49e758e80c7c311cc62c22`.
- The original `native-build-01` output and its logs were left in place.

### Migration path for the existing episodes

**Moritz decided this is not needed.** The old app stays installed with all of its data until he removes it himself, and the Qoralo build may be installed beside it as a second, empty app. No migration is authorized, and none has been performed. The procedure below is kept only in case that decision changes.

Both builds are debuggable, so app-private data could be moved without root and without uninstalling anything:

1. Install the Qoralo build alongside the existing app and start it once so its data directory exists.
2. With the old app stopped and no generation job running, copy `files/` and `databases/` out of `dev.vibevoice.podcast.internal` using `adb exec-out run-as`, recording sizes and hashes.
3. Copy the tree into `dev.qoralo.podcast.internal` through `run-as`, preserving the WAL and SHM files together with their database.
4. Verify row counts, file hashes and playback state in the new app before relying on it. Keep the old app installed until that check passes.

This has not been performed. It would need a coordinated phone slot, and it must not interrupt an active job or playback.

## Deliberately unchanged

- **Historical evidence, receipts, handoffs and listening records.** They describe builds that really were named VibeVoice and really did run under the old application ID. Rewriting them would falsify the record.
- **References to Microsoft's VibeVoice model** in `experiments/` and the benchmark registries. Those are factual records of models that were actually evaluated.
- The published dashboard URL, the Git remote and the repository directory name, which are external and need an explicit decision.

## Remaining steps

1. Install the Qoralo candidate in a coordinated phone slot and verify the new installed hashes. Unverified local build: app `10e698876967619dbebd14d07132e340cd358596bac46903993cef1498e5f111`, test `ede1a9387ff278008b4bc5c1a46f570cd921225e5dcc36db0c92707ecae8c6fd`; 265 host tests pass with 1 pre-existing skip, and the renamed bridge is present in all nine packaged native libraries. No device has run this build, so neither generation nor playback has been re-proven under the new identity.
2. Nothing else is required before the old app can be removed: that is Moritz's own step, at his timing.
3. Rename the repository and its working directory, then update absolute paths in local tooling. Do this while no agent sessions are running, because their working directory would disappear.
4. Decide what happens to the published dashboard path.


## Installed

The Qoralo build is installed on the phone beside the old app.

- App `dev.qoralo.podcast.internal` — `18780c26e4b0e32320d5d79744d0e93790a598a3c6b66068fb062e3ba32d3e6b`
- Instrumentation `dev.qoralo.podcast.internal.test` — `9bbd562fd8e89a7399bb6f0527faf8f40cecbf87688cf1cc19d4ca1ba89d1744`
- Both hashes were read back from the device after installation. 277 host tests pass with 1 pre-existing skip.
- Cold launch succeeded in 676ms with the app's own window focused and no crash-log entries; the app was stopped again afterwards.
- The previous id stays installed and keeps all of its data: app `0062cf41…`, test `abe68ac7…`. Nothing was uninstalled and no data was cleared.
- The Qoralo library is empty, as expected for a new application id.

Generation, playback, export and native QNN/HTP execution have not yet been exercised under the new id. See `evidence/qoralo-rebrand/install-20260920/result.json`.

### Launcher label

The app is labelled **Qoralo**. An earlier build briefly used "Qoralo dev" to distinguish it from the retired app while both were installed; that app has since been uninstalled, so the distinction is gone and the label is plain again.

## Single app, provisioned and bridge-proven

The old id was uninstalled at Moritz's instruction, with data loss explicitly accepted, so the phone now holds exactly one app.

- `dev.qoralo.podcast.internal` — `53abde985c2f288a073603920f231d591eacbb80a9257bacc46cca2b3ce01dfa`, label **Qoralo**, debug variant so `run-as` and the debug-only failure diagnostics stay available.
- Instrumentation `dev.qoralo.podcast.internal.test` — `9bbd562fd8e89a7399bb6f0527faf8f40cecbf87688cf1cc19d4ca1ba89d1744`.
- No `vibevoice` package remains.
- Model packs staged into the new id and matching the APK's pinned hashes: `gemma-4-e2b` `9fb627ef…`, `supertonic-3-provider` `423429c6…`. The build pins the provider pack, not the legacy `supertonic-3` pack.

`RenamedBridgeSmokeTest` proves the rebuilt bridge on the device. `JNI_OnLoad` resolved `SupertonicNative`, the wiring probe and the provider natives under `dev/qoralo`; a stale path would have failed closed with `UnsatisfiedLinkError` at load. One real provider segment then rendered on HTP: 79,872 frames of mono 44.1kHz audio, 1.811156s, WAV `1e176357cbabfe9f373e5c1f1d49730fa2ca365f920f8a6f0d6da6ba438e16d9`, with the native-reported hash matching the file.

The first attempt failed in the render phase with `IllegalArgumentException` because the test called `renderChapter` without `load()`. That was a defect in the new test, not in the app or the bridge, and the receipt records it as such.

Gemma script generation, playback, export and the full UI flow are still unexercised under the new id.

### Bridge re-proof on the shipped pair

The rename build that first proved the bridge was superseded by a rebuild from `ffa7cf3c` carrying the UI copy pass. Running the same smoke test against that installed pair — app `677f8d6f…`, test `21293c4c…` — produced a byte-identical segment: 79,872 frames, WAV `1e176357…e16d9`. Two independent builds of the same source therefore render the same audio through the renamed bridge, so the earlier result was not a one-off.

The Qoralo id now holds real user episodes; six episode directories were present before and after the re-proof, and the run wrote only its own receipt, which it then deleted.
