# Experiment 0008 — sherpa-onnx Android TTS benchmark

**Status: selected variants; real-device measurement pending.** No Android timing or memory result exists yet. The target is the Samsung Galaxy S23 Ultra (`SM-S918B`); it was enumerated previously, but current connection, authorization, unlock, and readiness are unverified.

This experiment compares three pinned local Android CPU deployments in a fixed order:

1. Pocket TTS 100M — `sherpa-onnx-pocket-tts-int8-2026-01-26`;
2. Kokoro 82M — exact `kokoro-multi-lang-v1_0`;
3. Supertonic 3 — `sherpa-onnx-supertonic-3-tts-int8-2026-05-11`.

The canonical baseline is sherpa-onnx `v1.13.5` at commit `3dc7c569f31ca2cd4a20ed6f7db780327e6714c5`, its pinned arm64 Android AAR, `provider="cpu"`, one inference thread, and models loaded directly from app-specific external storage. Host smoke tests validate configuration only; host timing never enters the Android comparison.

## Frozen input and voice contract

[`protocol/transcript.txt`](protocol/transcript.txt) is a byte-for-byte copy of experiment 0007's transcript: 230 UTF-8 bytes, no trailing newline, SHA-256 `350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f`.

Pocket requests Alba, but the result must separately record `requested_voice`, `actual_reference`, `actual_reference_sha256`, and `voice_match`. A provenance-verifiable packaged Alba may be used. Otherwise the predeclared fallback is the package's official `test_wavs/bria.wav`; it must have `voice_match=false` and must never be labeled Alba. Kokoro SID 3 must be proven as `af_heart` from pinned v1.0 metadata. Supertonic's M1-equivalent index must be proven from archive metadata or deterministic pinned conversion ordering; otherwise that candidate is blocked rather than run with a guess.

## Measurement contract

The complete machine-readable contract is [`protocol/benchmark-protocol.json`](protocol/benchmark-protocol.json). Each model starts in a fresh process. The first generation on its newly constructed `OfflineTts` is cold (without claiming page-cache clearing), followed by at least three warm generations. A monotonic synthesis-only timer excludes WAV writing, hashing, validation, playback, and listening. Every valid run reports its own RTF; the canonical comparison uses the median of valid warm RTFs.

The callback metric is time from synthesis start to the first non-empty audio callback, without playback. A missing callback is an observed unavailability with a reason, not a zero or estimate. Memory records boundary PSS/RSS/`VmHWM` and sampled phase peak PSS/RSS; `VmHWM` is explicitly cumulative for the process lifetime, not a per-phase peak.

A successful one-thread candidate receives one separate two-thread cold-plus-three-warm campaign only when its valid one-thread warm median RTF is greater than `1.0`. Two-thread data never replaces the canonical table.

## Thermal and failure rules

Before the campaign baseline and before every model, poll battery temperature and Android thermal status every 60 seconds. Eligibility requires status `NONE`, battery temperature at most `35.0°C`, and, after baseline establishment, no more than `1.0°C` above baseline. Wait at most 20 minutes and do not change device settings. A timeout is a recorded thermal block. Retain waits and disclose fixed-order thermal bias.

Outcomes include success, partial success, blocked, timeout, native crash, OOM, invalid audio, and general failure. A failed model is finalized as evidence before continuing in fixed order. Result schemas require measured observations or explicit unavailable reasons; estimated metrics have no representation.

## Files

- [`protocol/candidates.json`](protocol/candidates.json) — order, exact variants, voice conditions, and historical-only candidates.
- [`protocol/evidence-retention.json`](protocol/evidence-retention.json) — committed versus ignored evidence.
- [`schemas/result.schema.json`](schemas/result.schema.json) — normalized success/partial/failure outcomes.
- [`schemas/failure-manifest.schema.json`](schemas/failure-manifest.schema.json) — host-generated negative outcomes when native serialization is impossible.
- [`pins/assets.json`](pins/assets.json) — immutable release metadata, checksums, licenses, conversion/build provenance, and the exact Ubuntu 22.04 CPython 3.11.9 host wheels.
- [`tools/pinning.py`](tools/pinning.py) — fail-closed download, verification, extraction, host-runtime verification, and deterministic inventory utility.

## Pinned asset workflow

The utility uses only the Python standard library. Downloads are written atomically only after their byte size and SHA-256 match. Extraction first verifies the archive and rejects absolute or ambiguous paths, traversal, links, special files, duplicate members, decompression limits, and top-level layout drift. Existing non-empty destinations are never merged. Inventories contain sorted relative paths, byte sizes, and SHA-256 values and reject symlinks.

```sh
PIN=experiments/0008-sherpa-onnx-android-tts-benchmark/pins/assets.json
TOOL=experiments/0008-sherpa-onnx-android-tts-benchmark/tools/pinning.py
python "$TOOL" --manifest "$PIN" download pocket experiments/0008-sherpa-onnx-android-tts-benchmark/downloads
python "$TOOL" --manifest "$PIN" extract pocket experiments/0008-sherpa-onnx-android-tts-benchmark/downloads/sherpa-onnx-pocket-tts-int8-2026-01-26.tar.bz2 experiments/0008-sherpa-onnx-android-tts-benchmark/extracted/pocket
python "$TOOL" --manifest "$PIN" inventory experiments/0008-sherpa-onnx-android-tts-benchmark/extracted/pocket --output pocket-inventory.json
python "$TOOL" --manifest "$PIN" verify-host-runtime experiments/0008-sherpa-onnx-android-tts-benchmark/host-wheels
```

Host smoke testing is permitted only with the two exact wheels in the manifest, on its pinned platform. An extra, missing, locally built, differently hashed, or wrong-platform wheel fails validation. Host smoke output validates configuration only: its timing must never be copied into Android results.

Large archives, extracted models, host wheels, APKs, WAVs, full logcat, and raw high-frequency telemetry remain ignored. Git retains normalized manifests, inventories, independent validation reports, failure manifests, and hash-addressed relative references to raw evidence.

Experiment 0007 remains immutable historical listening evidence. VibeVoice Realtime, Inflect Nano v1, and Kitten TTS are historical-only and are not pending Android follow-up.
