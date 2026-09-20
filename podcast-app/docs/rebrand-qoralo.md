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
- Repository and app documentation describing the current product.

## Deliberately unchanged

- **Application ID `dev.vibevoice.podcast.internal` and Kotlin package `dev.vibevoice.podcast`.** Android treats a different application ID as a different app: the installed episodes, sources, revisions, jobs, playback positions and exported audio live under the current ID, and every evidence receipt binds installed APK hashes to it. Renaming without a migration would hide real user data and break those bindings.
- **Historical evidence, receipts, handoffs and listening records.** They describe builds that really were labelled VibeVoice. Rewriting them would falsify the record; the older handoffs remain accurate for the builds they describe.
- **References to Microsoft's VibeVoice model** in `experiments/` and the benchmark registries. Those are factual records of models that were actually evaluated.
- The published dashboard URL and the Git remote, which are external and need an explicit decision.

## Staged plan for the identity change

1. Land the brand layer (this step) and install a build whose launcher reads Qoralo while the application ID is unchanged. Existing episodes stay visible.
2. Decide whether the stored data must survive the identity change. If it must, add an explicit export/import path, or migrate files and the database into the new ID before switching.
3. Change the application ID and package in one commit, with a fresh candidate build, new installed hashes, and re-verified preservation counts.
4. Rename the repository and its directory, then update absolute paths in local tooling.

Until step3, anything that pins `dev.vibevoice.podcast.internal` — controller tooling, receipts, installed hashes — remains correct as written.
