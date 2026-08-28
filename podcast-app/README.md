# VibeVoice podcast app

Greenfield Android implementation of the binding UX in `../docs/app-ux-mvp.html` and architecture in `../docs/podcast-generation-app-architecture-proposal.md`.

## Identity

The reversible internal application ID is `dev.vibevoice.podcast.internal`; the launcher name is **VibeVoice**. This is deliberately not a production Play identity.

## Build

```bash
cd podcast-app
./gradlew :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
```

Compile/target SDK 35 and Java 17 are required. The physical target is a Galaxy S23 Ultra.

## Runtime model packs

Licensed and large models never enter Git. Verified packs are installed into the app's no-backup private storage under `model-packs/<route>/<version>/`. Each pack contains a `manifest.json`, all files listed by size and SHA-256, and a route-specific JNI entrypoint library. Accepted routes are exclusively:

- `GEMMA_4_E2B_LITERT_GPU`
- `SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP`

A route that is absent, invalid, incompatible, or fails to initialize stops generation. There is no CPU route, alternate model, hidden text splitting, or synthetic-audio fallback.
