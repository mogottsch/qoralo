# Experiment 0021 — Supertonic canonical-v2 Android CPU benchmark

New matched Android route for the exact canonical-v2 benchmark transcript. This does not rewrite legacy-v1 experiment 0008 or its exact 0020 refresh.

## Frozen route

- Model: `sherpa-onnx-supertonic-3-tts-int8-2026-05-11`, archive SHA-256 `82fa96f9…c427`.
- Runtime: sherpa-onnx 1.13.5 Android AAR, SHA-256 `6419cd8b…a82b`, CPU provider.
- Device: authorized Samsung Galaxy S23 Ultra `R5CW81PR8SY` / `SM-S918B` / `SM8550` / `arm64-v8a`.
- Voice: official M1 / SID5; English; one inference thread.
- Input: exact 226-byte canonical-v2 transcript, SHA-256 `424b3807…db67`, no trailing newline.
- Timing: setup separately, one first generation, five same-session warm generations, actual-duration RTF, warm median over the five warm RTFs.
- Listening: every new WAV starts `not_reviewed`.

The copied 0021 Android project changes only verified input storage from app-external storage to app-internal `getFilesDir()`, using the bounded 0020 adapter required by Android 16 scoped storage. Model/runtime/frontend/timing/memory/output logic remains the frozen 0008 implementation. Inputs are shell-stage hash checked, copied by app UID, and app-UID hash checked. Frozen 0008 remains unchanged.

## Evidence

- [`protocol/benchmark-policy.json`](protocol/benchmark-policy.json) — prospective route and measurement policy.
- [`protocol/transcript.txt`](protocol/transcript.txt) — exact canonical-v2 bytes.
- `results/` — source/build/frontend/device/run/cleanup evidence after completion.
- `samples/` — only independently verified listening WAVs.

Phone work uses the exact Windows ADB shim, repository `phone.lock`, fresh identity/boot/unlock checks at every mutation, unique staging, binary-safe evidence pull, and verified package/internal/external cleanup.
