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
- [`docs/devices/`](docs/devices/) — target-device baselines.
- [`experiments/`](experiments/) — one reproducible directory per experiment.
- [`scripts/`](scripts/) — common inventory and benchmark helpers.

## Boundaries

This repository deals only with running and measuring VibeVoice. It does not contain the Podleaf product design, source extraction, Gemma 4 integration, application architecture, or production UI.

Large model files, converted models, generated audio, APKs, tensors, traces, and raw benchmark artifacts remain outside Git under ignored local directories.

## Status

- [x] Target Android device identified.
- [x] Candidate inference paths selected.
- [x] Produce the 15-second VibeVoice 1.5B local reference (13.07 seconds generated on CPU).
- [ ] Complete human listening review of the reference clip.
- [ ] Export the first component with ExecuTorch.
- [ ] Run the first component on Android.
- [ ] Produce short end-to-end audio on Android.
- [ ] Evaluate LiteRT, ONNX Runtime Mobile, and Qualcomm QNN.
- [ ] Repeat the relevant deployment tests with Realtime 0.5B.
