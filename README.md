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
| [`0008`](experiments/0008-sherpa-onnx-android-tts-benchmark/) | Pinned sherpa-onnx Android CPU benchmark | Complete: Supertonic works; Pocket and Kokoro work with limitations |
| [`0009`](experiments/0009-android-tts-optimization/) | Exact Kokoro INT8 host gate and Android 1/2/4-thread sweep | Complete: INT8 passed user listening; four threads materially improve Kokoro, while Pocket/Supertonic two-thread gains remain inconclusive |
| [`0010`](experiments/0010-supertonic-qnn-htp-feasibility/) | Supertonic QNN/HTP component-first feasibility | Paused after host preflight and reusable Android ORT+QNN build; no phone HTP execution or speedup claim yet |

## Boundaries

This repository deals only with running and measuring VibeVoice. It does not contain the Podleaf product design, source extraction, Gemma 4 integration, application architecture, or production UI.

Large model files, converted models, generated audio, APKs, tensors, traces, and raw benchmark artifacts remain outside Git under ignored local directories.

## Status

The historical ExecuTorch campaign remains complete at **39/39** and rejected as deployed. Its prefix supplement clarifies the near-silent two-chunk waveform without revising that conclusion.

Experiment 0007's six natural-duration host samples remain immutable historical evidence. Experiment 0008 measured the three selected sherpa-onnx Android CPU deployments on the Galaxy S23 Ultra: Supertonic 3 **works** (one-thread warm median RTF 0.370), while Pocket **works with limitations** (RTF 0.389, packaged Bria rather than requested Alba, unresolved license messaging) and Kokoro **works with limitations**. Experiment 0009 found observed best warm RTFs of Pocket 0.367 at two threads, Kokoro 0.753 at four threads, and Supertonic 0.362 at two threads; only Kokoro's scaling is large enough to treat as materially directional in the single campaign. The exact Kokoro mixed-INT8 candidate is 46.0% smaller and passed Moritz's blind listening gate, but has not yet been benchmarked on Android. Experiment 0010 is paused before its first phone QNN execution, with a reusable ignored Android ORT+QNN build preserved locally. VibeVoice Realtime 0.5B, Inflect Nano v1, and Kitten TTS Mini 80M v0.8 remain historical-only. The current human-facing report is the [live HTML dashboard](https://preview.moket-home.de/vibevoice-android/).
