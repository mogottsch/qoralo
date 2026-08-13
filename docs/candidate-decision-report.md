# Candidate decision report

**Status: experiment 0008 complete.** The Galaxy S23 Ultra measurements select the pinned Supertonic 3 INT8 deployment as the strongest default. Pocket and exact Kokoro v1.0 work with limitations. The canonical tables, exact values, retained hashes, failure disclosure, and validation are in the [measured Android decision](../experiments/0008-sherpa-onnx-android-tts-benchmark/results/measured-decision.md).

## Android decision

| Candidate | Pinned Android deployment | Outcome | Canonical one-thread result |
|---|---|---|---|
| Pocket TTS 100M | `sherpa-onnx-pocket-tts-int8-2026-01-26` | **works_with_limitations** | Load 0.659 s; cold RTF 0.436; warm median RTF 0.389; sampled peak PSS 683.6 MB; 4/4 WAVs valid |
| Kokoro 82M | exact `kokoro-multi-lang-v1_0`, SID 3/`af_heart` | **works_with_limitations** | Load 1.303 s; cold RTF 1.188; warm median RTF 1.195; sampled peak PSS 929.7 MB; 4/4 WAVs valid |
| Supertonic 3 | `sherpa-onnx-supertonic-3-tts-int8-2026-05-11`, SID 5/M1, English | **works** | Load 0.765 s; cold RTF 0.385; warm median RTF 0.370; sampled peak PSS 463.0 MB; 4/4 WAVs valid |

The baseline was sherpa-onnx `v1.13.5`, arm64, CPU, one canonical inference thread, filesystem-backed models, and the frozen experiment 0007 transcript. Kokoro alone triggered the separate two-thread comparison: cold RTF 0.917 and warm median RTF 0.963. It remains separate from the canonical table.

### Prominent Pocket limits

Pocket requested Alba but used the pinned package's official `test_wavs/bria.wav`; `voice_match=false`. Bria is not Alba and must not be labeled as such. The package workflow describes non-commercial use while the bundled model license says CC BY 4.0. Experiment 0008 does not resolve that conflict, so Pocket remains research-only pending a production license determination.

No manual listening check was performed for any Android WAV. `works` means the pinned deployment passed this technical generation benchmark, not that product quality or licensing has been approved.

## Thermal, order, and failures

The fixed order was Pocket, Kokoro, then Supertonic. All canonical runs began at thermal status `NONE`, at 34.8 °C, 34.5 °C, and 34.3 °C against the 34.3 °C baseline. None waited. Kokoro's optional two-thread run waited 120 seconds to become eligible at 35.0 °C. Fixed order was not randomized, so the protocol bounds but cannot eliminate order, charging, or residual thermal bias.

Earlier Pocket and Kokoro runs aborted in cold synthesis because the Kotlin callback bridge exposed the wrong JNI signature. Their failure manifests remain retained. The successful results followed the concrete Java callback correction; the earlier attempts are disclosed harness failures, not model failures.

## Evidence boundary

These are measurements of the pinned Android INT8/ONNX deployment archives, not the different host PyTorch/model workflows used for experiment 0007 listening evidence. Host timings below must not be compared as Android deployment timings.

Experiment 0007 remains immutable historical context. Its recorded three-way listening order was Kokoro first, Pocket second, and VibeVoice Realtime third; Supertonic, Inflect, and Kitten were not reviewed before that experiment stopped.

| Candidate | Historical host duration | Historical host RTF | Current role |
|---|---:|---:|---|
| VibeVoice Realtime 0.5B | 20.133 s | 0.441 | Historical-only |
| Pocket TTS 100M | 13.840 s | 0.296 | Android `works_with_limitations` |
| Kokoro 82M | 17.475 s | 0.383 | Android `works_with_limitations` |
| Supertonic 3 | 16.161 s | 0.341 | Android `works` |
| Inflect Nano v1 | 14.933 s | 0.232 | Historical-only |
| Kitten TTS Mini 80M v0.8 | 15.417 s | 0.714 | Historical-only |

VibeVoice Realtime 0.5B, Inflect Nano v1, and Kitten TTS Mini 80M v0.8 are **historical-only**. They are not pending review or Android follow-up.

## Evidence index

- [canonical measured comparison](../experiments/0008-sherpa-onnx-android-tts-benchmark/results/measured-decision.md)
- [machine-readable measured comparison](../experiments/0008-sherpa-onnx-android-tts-benchmark/results/measured-decision.json)
- [machine-readable project report](candidate-decision-report.json)
- [experiment 0008 protocol](../experiments/0008-sherpa-onnx-android-tts-benchmark/protocol/benchmark-protocol.json)
- [historical experiment 0007 listening manifest](../experiments/0007-mobile-podcast-preview-bakeoff/publication/bakeoff-manifest.json)
