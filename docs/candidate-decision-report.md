# Candidate decision report

**Status: awaiting expanded blind listening review.** The user ranked the historical three samples **Kokoro 82M first, Pocket TTS 100M second, and VibeVoice Realtime 0.5B third**. Supertonic 3, Inflect Nano v1, and Kitten TTS Mini 80M v0.8 were added afterward and have not been rated. No Android conversion or follow-up is authorized yet.

## Active listening policy

The active bake-off compares each model's **natural-duration output**. There is no 15-second requirement and no normalization step. Actual duration and native sample rate are shown for every candidate. Historical protocol-v2 normalized files may remain in local evidence, but they are noncanonical and are not published in the active listening UI.

| Candidate | Natural duration | Host generation | First audible | Host RTF | Peak process-tree RSS | Listening state |
|---|---:|---:|---:|---:|---:|---|
| VibeVoice Realtime 0.5B | 20.133 s | 8.889 s | 0.484 s | 0.441 | 3.532 GB | Historical rank 3 |
| Pocket TTS 100M | 13.840 s | 4.094 s | 0.184 s | 0.296 | 1.145 GB | Historical rank 2 |
| Kokoro 82M | 17.475 s | 6.692 s | 7.042 s | 0.383 | 1.713 GB | **Historical rank 1** |
| Supertonic 3 | 16.161 s | 5.506 s | 5.956 s | 0.341 | 0.609 GB | Pending blind review |
| Inflect Nano v1 | 14.933 s | 3.458 s | 3.917 s | 0.232 | 1.094 GB | Pending blind review |
| Kitten TTS Mini 80M v0.8 | 15.417 s | 11.007 s | 11.445 s | 0.714 | 0.792 GB | Pending blind review |

The listening page starts with neutral Candidate A–F labels. Each card has its own identity-reveal button, and a separate control reveals all identities. Identity data is requested only after an explicit reveal action.

The browser players use WAV carriers where a model's native library output is headerless float PCM. The exact native bytes, formats, rates, durations, and hashes remain preserved in the evidence manifest.

## Android measurements

The VibeVoice 1.5B four-call PTE was **not run on Android** because its deterministic host validation failed the frozen numerical gate. Realtime, Pocket, Kokoro, Supertonic, Inflect, and Kitten have no Android measurements in this campaign. Android work remains deferred until the expanded listening review is complete.

## Historical 39/39 result

The prior 39/39 ExecuTorch/XNNPACK result remains immutable: the tested VibeVoice 1.5B deployment is rejected for capacity, speed, size, and its historical fixed-rubric audio result. The locked-prefix supplement is clarification only and does not revise that conclusion.

## Next decision

1. Listen to all six candidates without revealing identities first.
2. Reveal individual identities only when ready.
3. Record the updated subjective ordering.
4. Select a candidate for Android feasibility work only after that review.

## Evidence index

The machine-readable [decision report](candidate-decision-report.json) pins all six result files and keeps host listening, unavailable Android measurements, estimates, and historical evidence separate. Primary sources:

- [six-candidate listening manifest](../experiments/0007-mobile-podcast-preview-bakeoff/publication/bakeoff-manifest.json)
- [historical A–C listening review](../experiments/0007-mobile-podcast-preview-bakeoff/results/user-listening-review.json)
- [Supertonic 3 result](../experiments/0007-mobile-podcast-preview-bakeoff/results/supertonic-3-preview.json)
- [Inflect Nano v1 result](../experiments/0007-mobile-podcast-preview-bakeoff/results/inflect-nano-v1-preview.json)
- [Kitten TTS Mini 0.8 result](../experiments/0007-mobile-podcast-preview-bakeoff/results/kitten-mini-0.8-preview.json)
- [four-call Android gate result](../experiments/0002-vibevoice-1.5b-executorch-android/results/four-call-android.json)

**Stop here for the expanded listening review.**
