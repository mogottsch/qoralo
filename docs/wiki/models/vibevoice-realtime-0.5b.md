---
title: VibeVoice Realtime 0.5B
aliases:
  - microsoft/VibeVoice-Realtime-0.5B
  - VibeVoice Realtime
kind: model
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
---

# VibeVoice Realtime 0.5B

> VibeVoice Realtime 0.5B is the smaller, streaming-oriented VibeVoice checkpoint considered as a possible mobile alternative after the 1.5B work; in this project it remains a feasibility study, not an Android deployment.

## Upstream identity

The registry pins `microsoft/VibeVoice-Realtime-0.5B` at revision `6bce5f06044837fe6d2c5d7a71a84f0416bd57e4`:

- <https://huggingface.co/microsoft/VibeVoice-Realtime-0.5B/tree/6bce5f06044837fe6d2c5d7a71a84f0416bd57e4>

Experiment 0006 also pins the upstream implementation at VibeVoice source revision `94da20d98b2fa7688e9cbfaf7692ddb4954f7600`.

## Project route and status

| Experiment | Route | Committed status |
|---|---|---|
| `0006` | Component-level Android feasibility inventory | **Recommendations only; not run.** The project inspected checkpoint structure, streaming state, package arithmetic, and candidate runtime order without converting a model or accessing the phone. |

The checkpoint contains 1,017,626,724 learned parameters. Experiment 0006 classifies 881,492,068 as active on the inspected source path after excluding a stored duplicate embedding. That static classification explains why the “0.5B” name does not describe the entire speech checkpoint; it is not a traced mobile-graph measurement.

The proposed runtime order was narrow QNN/HTP microprobes first, then LiteRT/LiteRT-LM, then ONNX Runtime Mobile. It was a recommendation contingent on explicit listening approval and did not authorize conversion.

## Key limitations

- No model conversion, Android package, phone execution, timing, memory measurement, provider proof, or Android WAV exists.
- FP16, INT8, and INT4 storage figures in experiment 0006 are arithmetic estimates, not supported package sizes or quality-preserving quantization results.
- The official implementation uses dynamic Qwen KV-cache orchestration, acoustic-decoder convolution caches, diffusion state, and RNG/noise that had not yet been frozen into a mobile ABI.
- A host preview informed the feasibility review, but host execution is not Android evidence.
- A later preference ranking did not explicitly accept or reject the preview's usability, so no listening approval is inferred.

See [VibeVoice 1.5B](vibevoice-1.5b.md) for the separate large-model deployment work and [Evidence boundaries](../methods/evidence-boundaries.md) for the project's claim rules.

## Related experiments

- `experiments/0006-vibevoice-realtime-0.5b-android/`
- `experiments/0007-mobile-podcast-preview-bakeoff/`

## Evidence sources

- `docs/android-benchmarks/registry.json`
- `experiments/0006-vibevoice-realtime-0.5b-android/README.md`
- `experiments/0006-vibevoice-realtime-0.5b-android/feasibility-inventory.json`
- `experiments/0007-mobile-podcast-preview-bakeoff/results/realtime-preview.json`
