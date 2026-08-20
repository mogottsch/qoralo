# Experiment 0021 — Supertonic canonical-v2 Android CPU benchmark

**Status: complete; listening not reviewed.** New matched Android route for the exact canonical-v2 benchmark transcript. This does not rewrite legacy-v1 experiment 0008 or its exact 0020 refresh.

## Frozen route

- Model: `sherpa-onnx-supertonic-3-tts-int8-2026-05-11`, archive SHA-256 `82fa96f9…c427`.
- Runtime: sherpa-onnx 1.13.5 Android AAR, SHA-256 `6419cd8b…a82b`, CPU provider.
- Device: authorized Samsung Galaxy S23 Ultra `R5CW81PR8SY` / `SM-S918B` / `SM8550` / `arm64-v8a`.
- Voice: official M1 / SID5; English; one inference thread.
- Input: exact 226-byte canonical-v2 transcript, SHA-256 `424b3807…db67`, no trailing newline.
- Timing: setup separately, one first generation, five same-session warm generations, actual-duration RTF, warm median over the five warm RTFs.
- Listening: every new WAV starts `not_reviewed`.

The copied 0021 Android project changes only verified input storage from app-external storage to app-internal `getFilesDir()`, using the bounded 0020 adapter required by Android 16 scoped storage. Model/runtime/frontend/timing/memory/output logic remains the frozen 0008 implementation. Inputs are shell-stage hash checked, copied by app UID, and app-UID hash checked. Frozen 0008 remains unchanged.

## Result

The exact route completed setup once, one first generation, and five additional same-session warm generations. All six outputs were valid mono PCM16 44.1 kHz, finite, non-silent, unclipped, and exactly 696,523 frames (`15.794172335600907` s).

- Setup: `0.853867031` s.
- First: `6.246926665` s, RTF `0.39552098915111206`.
- Five warm RTFs: `0.39063055789844703`, `0.3913861966078651`, `0.3956153837777073`, `0.39570824828297124`, `0.39715652771882626`.
- Warm median RTF: **`0.3956153837777073`**.
- Peak sampled PSS: `480,366,592` bytes; peak boundary PSS: `479,744,000` bytes; cumulative process VmHWM: `548,986,880` bytes.
- Thermal gate: Android status `NONE`, battery `33.8 °C` before launch; no device tuning.
- Representative warm-median WAV: SHA-256 `201f8e79…87df`, `not_reviewed`.

The six calls reuse one created `OfflineTts` session, while each call independently invokes `generateWithConfigAndCallback`; no cache/state/output object crosses calls. The historical harness does not emit an ORT profile, so provider evidence is the pinned `provider=cpu` descriptor and engine fail-closed check, with the missing profile recorded explicitly.

## Evidence

- [`protocol/benchmark-policy.json`](protocol/benchmark-policy.json) — prospective route and measurement policy.
- [`protocol/transcript.txt`](protocol/transcript.txt) — exact canonical-v2 bytes.
- `results/` — source/build/frontend/device/run/cleanup evidence after completion.
- `samples/` — only independently verified listening WAVs.

Phone work uses the exact Windows ADB shim, repository `phone.lock`, fresh identity/boot/unlock checks at every mutation, unique staging, binary-safe evidence pull, and verified package/internal/external cleanup.
