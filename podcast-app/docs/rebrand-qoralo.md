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
- The app's own JNI library is rebuilt because the registered class paths changed, so its hash differs from `01d2ba53…`. The six vendored ONNX Runtime/QNN libraries are untouched.

### Migration path for the existing episodes

Both builds are debuggable, so app-private data can be moved without root and without uninstalling anything:

1. Install the Qoralo build alongside the existing app and start it once so its data directory exists.
2. With the old app stopped and no generation job running, copy `files/` and `databases/` out of `dev.vibevoice.podcast.internal` using `adb exec-out run-as`, recording sizes and hashes.
3. Copy the tree into `dev.qoralo.podcast.internal` through `run-as`, preserving the WAL and SHM files together with their database.
4. Verify row counts, file hashes and playback state in the new app before relying on it. Keep the old app installed until that check passes.

This has not been performed. It needs a coordinated phone slot, and it must not interrupt an active job or playback.

## Deliberately unchanged

- **Historical evidence, receipts, handoffs and listening records.** They describe builds that really were named VibeVoice and really did run under the old application ID. Rewriting them would falsify the record.
- **References to Microsoft's VibeVoice model** in `experiments/` and the benchmark registries. Those are factual records of models that were actually evaluated.
- The published dashboard URL, the Git remote and the repository directory name, which are external and need an explicit decision.

## Remaining steps

1. Build and install a Qoralo candidate, then verify the new installed hashes.
2. Migrate the existing episode data as described above, or accept a fresh library.
3. Rename the repository and its working directory, then update absolute paths in local tooling. Do this while no agent sessions are running, because their working directory would disappear.
4. Decide what happens to the published dashboard path.

