# VibeVoice Android Spike

Research repository for testing whether Microsoft's VibeVoice podcast speech models can run locally on a modern Android phone.

## Approach

We start with **VibeVoice TTS 1.5B**, the smallest released VibeVoice model with joint, context-aware multi-speaker podcast generation.

1. Generate a fixed **15-second two-speaker reference clip on the local laptop** with the official PyTorch implementation.
2. Record the exact transcript, voices, seed, model revision, environment, settings, runtime, memory use, and output hash.
3. Try the simplest plausible Android path next: **ExecuTorch**.
4. Compare the Android output and intermediate tensors with the local reference.
5. Then investigate the other selected Android runtimes:
   - LiteRT / LiteRT-LM;
   - ONNX Runtime Mobile;
   - Qualcomm QNN / AI Engine Direct.
6. After the 1.5B investigations, test **VibeVoice Realtime 0.5B** as a smaller single-speaker deployment comparison.

The target phone is a Samsung Galaxy S23 Ultra (`SM-S918B`, Snapdragon 8 Gen 2, 12 GB class RAM).

## Repository layout

- [`docs/plan.md`](docs/plan.md) — spike sequence and evidence requirements.
- [`docs/runtimes.md`](docs/runtimes.md) — the four selected Android inference paths.
- [`docs/decisions.md`](docs/decisions.md) — short chronological decision log.
- [`docs/candidate-decision-report.md`](docs/candidate-decision-report.md) — current listening/Android/estimate synthesis and the five user decision gates ([machine-readable report](docs/candidate-decision-report.json)).
- [`docs/progress.json`](docs/progress.json) — canonical machine-readable status for the historical work lanes and [live dashboard](https://preview.moket-home.de/vibevoice-android/).
- [`docs/devices/`](docs/devices/) — target-device baselines.
- [`experiments/`](experiments/) — one reproducible directory per experiment.
- [`scripts/`](scripts/) — common inventory and benchmark helpers.

## Experiment index

| Experiment | Scope | Current conclusion |
|---|---|---|
| [`0001`](experiments/0001-vibevoice-1.5b-local-reference/) | VibeVoice 1.5B host reference | Reproducible historical reference |
| [`0002`](experiments/0002-vibevoice-1.5b-executorch-android/) | VibeVoice 1.5B ExecuTorch and four-call recovery | Historical deployment rejected; new four-call artifact rejected by host gate and therefore not deployed |
| [`0003`](experiments/0003-vibevoice-1.5b-litert-android/) | LiteRT | Deferred; no duplicate conversion started |
| [`0004`](experiments/0004-vibevoice-1.5b-onnx-android/) | ONNX Runtime Mobile | Deferred; no duplicate conversion started |
| [`0005`](experiments/0005-vibevoice-1.5b-qnn-android/) | Qualcomm QNN | Requires an approved candidate and any proprietary terms |
| [`0006`](experiments/0006-vibevoice-realtime-0.5b-android/) | Realtime 0.5B feasibility inventory | Recommendations and storage estimates only; Android feasibility unknown |
| [`0007`](experiments/0007-mobile-podcast-preview-bakeoff/) | Six-model host listening bake-off | Immutable historical evidence; historical ranking is Kokoro, Pocket, then Realtime |
| [`0008`](experiments/0008-sherpa-onnx-android-tts-benchmark/) | Pinned sherpa-onnx Android CPU benchmark | Pocket, Kokoro, and Supertonic selected; real-device measurement pending |

## Boundaries

This repository deals only with running and measuring VibeVoice. It does not contain the Podleaf product design, source extraction, Gemma 4 integration, application architecture, or production UI.

Large model files, converted models, generated audio, APKs, tensors, traces, and raw benchmark artifacts remain outside Git under ignored local directories.

## Status

The historical ExecuTorch campaign remains complete at **39/39** and rejected as deployed. Its prefix supplement clarifies the near-silent two-chunk waveform without revising that conclusion.

Experiment 0007's six natural-duration host samples remain immutable historical evidence. Pocket TTS 100M, exact Kokoro 82M v1.0, and Supertonic 3 are now selected for the pinned experiment 0008 sherpa-onnx Android CPU benchmark, with real-device measurements still pending. VibeVoice Realtime 0.5B, Inflect Nano v1, and Kitten TTS Mini 80M v0.8 are historical-only and are not pending Android follow-up. See the [candidate decision report](docs/candidate-decision-report.md).
