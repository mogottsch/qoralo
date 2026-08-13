# Candidate decision report

**Status: experiment 0008 selected; real-device measurement pending.** Pocket TTS 100M, exact Kokoro 82M v1.0, and Supertonic 3 are the only active Android follow-up candidates. They will be measured in that fixed order under the [experiment 0008 contract](../experiments/0008-sherpa-onnx-android-tts-benchmark/README.md).

VibeVoice Realtime 0.5B, Inflect Nano v1, and Kitten TTS Mini 80M v0.8 are **historical-only**. They are not pending review or Android follow-up. Their natural-duration host samples and all experiment 0007 evidence remain immutable historical context.

## Selected deployment variants

| Order | Candidate | Pinned deployment | Voice condition | Android status |
|---:|---|---|---|---|
| 1 | Pocket TTS 100M | `sherpa-onnx-pocket-tts-int8-2026-01-26` | Request Alba; record actual reference/hash/match; packaged Bria is the declared honest fallback | Pending real-device measurement |
| 2 | Kokoro 82M | exact `kokoro-multi-lang-v1_0` | SID 3 must be proven as `af_heart` | Pending real-device measurement |
| 3 | Supertonic 3 | `sherpa-onnx-supertonic-3-tts-int8-2026-05-11` | M1-equivalent SID must be proven; otherwise blocked | Pending real-device measurement |

The baseline is sherpa-onnx `v1.13.5`, CPU, one canonical inference thread, arm64, and filesystem-backed models in app-specific external storage. No Android timing or memory value has been measured for these variants. Host listening timing from experiment 0007 and future host configuration smoke tests are not Android performance evidence.

## Historical listening evidence

Experiment 0007 compared six natural-duration host outputs. The recorded historical three-way order was Kokoro first, Pocket second, and VibeVoice Realtime third. Supertonic, Inflect, and Kitten were added later. Selection for experiment 0008 supersedes the old listening gate without rewriting those results.

| Candidate | Natural duration | Host RTF | Current role |
|---|---:|---:|---|
| VibeVoice Realtime 0.5B | 20.133 s | 0.441 | Historical-only |
| Pocket TTS 100M | 13.840 s | 0.296 | Selected; Android measurement pending |
| Kokoro 82M | 17.475 s | 0.383 | Selected; Android measurement pending |
| Supertonic 3 | 16.161 s | 0.341 | Selected; Android measurement pending |
| Inflect Nano v1 | 14.933 s | 0.232 | Historical-only |
| Kitten TTS Mini 80M v0.8 | 15.417 s | 0.714 | Historical-only |

## Next action and boundaries

Complete experiment 0008's pinned host validation and Android harness before touching the phone. The `SM-S918B` was enumerated previously, but current connection, unlock, authorization, and readiness are unverified. Device work must wait for explicit readiness and the experiment's thermal rules.

The normalized schemas represent successes, partial successes, blocks, timeouts, native crashes, OOM, invalid audio, and other failures. Missing metrics require an observed reason and are never estimated. The optional two-thread campaign is allowed only after a successful candidate has a valid one-thread warm median RTF greater than `1.0` and is reported separately.

## Evidence index

- [experiment 0008 candidate manifest](../experiments/0008-sherpa-onnx-android-tts-benchmark/protocol/candidates.json)
- [experiment 0008 benchmark protocol](../experiments/0008-sherpa-onnx-android-tts-benchmark/protocol/benchmark-protocol.json)
- [machine-readable decision report](candidate-decision-report.json)
- [historical experiment 0007 listening manifest](../experiments/0007-mobile-podcast-preview-bakeoff/publication/bakeoff-manifest.json)
- [historical A–C listening review](../experiments/0007-mobile-podcast-preview-bakeoff/results/user-listening-review.json)
