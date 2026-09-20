# Qoralo podcast app

Greenfield Android implementation of the binding UX in `../docs/app-ux-mvp.html` and architecture in `../docs/podcast-generation-app-architecture-proposal.md`.

## Current tested internal build

See [the installed episode diagnostics/deletion handoff](docs/episode-management-handoff-2026-09-14.md) for current app `bf53c566…` / test `f1543993…`, exact identities and scoped validation. **Library → episode ⋮ → Episode details** opens private metrics; **Delete episode** confirms the immutable target and safely waits for worker/player file leases. Default/narrow-font2 owned fixtures, six actual paired captures, the exact-pair non-neural guard and preservation checks passed. No real user podcast was deleted and no model was run to fill old statistics; actual SDK metric availability remains unverified.

The [prior progressive Player handoff](docs/progressive-player-handoff-2026-09-13.md), on app `119e0f92…` / test `7ae210bf…`, retains its separate navigation and coverage table. Genuine muted playback advanced while HTP generated; remaining pause/navigation/transcript/finalization controls passed a zero-neural production-IO replay of the same retained audio. The original all-in-one script remains failed on optional screenshot capture—not relabelled a clean E2E pass. The app has one persistent top mini-player, attempt-bound immutable audio availability and honest passage following. Use the frozen tested APK, not arbitrary build output. The [earlier provider publication/recovery](docs/provider-app-handoff-2026-09-12.md), [chat-edit](docs/chat-edit-repair-handoff-2026-09-11.md) and [capacity](docs/app-repair-handoff-2026-09-11.md) evidence remains preserved; no new listening verdict is inferred.

## Identity

The launcher name is **Qoralo**. The internal application ID and Kotlin package are still `dev.vibevoice.podcast.internal` and `dev.vibevoice.podcast`: changing them creates a different Android app identity, which would hide the existing on-device episodes and invalidate every installed-hash evidence binding. See [the rebrand notes](docs/rebrand-qoralo.md) for the staged plan. This is deliberately not a production Play identity.

## Build

```bash
cd podcast-app
./gradlew :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
```

Compile/target SDK 35 and Java 17 are required. The physical target is a Galaxy S23 Ultra.

## Runtime model packs

Licensed and large models never enter Git. Verified, data-only packs are installed into the app's no-backup private storage under `model-packs/<route>/<version>/`. Each pack contains a `manifest.json` and model/context/assets listed by size and SHA-256. Executable code is rejected from writable packs. The matched JNI, LiteRT, ONNX Runtime, and QNN integration must be supplied by the installed APK or a trusted native split. Accepted routes are exclusively:

- `GEMMA_4_E2B_LITERT_GPU`
- `SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP`

A route that is absent, invalid, incompatible, or fails to initialize stops generation. There is no CPU route, alternate model, hidden text splitting, or synthetic-audio fallback.

Licensed local native artifacts are injected at build time under `app/runtime-libs/arm64-v8a/`; that directory is Git-ignored. The app never loads executable code from model-pack storage.

For the authorized local environment:

```bash
./tools/prepare_local_runtime.py
./gradlew :app:assembleDebug
```

The preparation tool uses the accepted experiment artifacts by default, creates hard-linked data-only packs under `.local/model-packs`, records private runtime hashes in `.local/runtime-provenance.json`, pins both generated manifest hashes in the ignored `local.properties`, and enables the Supertonic JNI build. Gemma uses the official `litertlm-android:0.16.1` API with `Backend.GPU`; Supertonic uses the APK-packaged ORT/QNN libraries and app-owned JNI bridge. Generated model packs, QAIRT libraries, hashes that disclose private local provenance, and model bytes must never be committed or published. The current default provider pack uses T320/L512 with four reusable HTP contexts. The authorized provider1.3.1 recipe groups raw paragraphs/sentences toward300 codepoints without forcibly splitting overlong sentences, then applies the pinned Unicode14 frontend. Each segment uses its own HTP-predicted native duration/full waveform, with exact prescribed gaps and no stretching or hidden fallback. Immutable validated chunks support progressive playback; the completed canonical master supports later playback/export. The earlier T239/L238 short pack remains an explicitly separate legacy route/evidence case, not the current long-text default.

`tools/install_local_debug.sh` is intentionally gated by both explicit Pi priority (`PODCAST_PHONE_PRIORITY=approved`) and `artifacts/locks/phone.lock`; do not invoke it outside an assigned phone gate.
