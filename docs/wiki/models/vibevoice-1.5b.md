---
title: VibeVoice 1.5B
aliases:
  - microsoft/VibeVoice-1.5B
kind: model
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
---

# VibeVoice 1.5B

> VibeVoice 1.5B is the original large speech-generation checkpoint behind this repository's first Android deployment work; it matters here because it exposed the practical limits of exporting a multi-component streaming model to a phone.

## Upstream identity

The registry pins `microsoft/VibeVoice-1.5B` at revision `c00898d257e6b46004e3e2866a47534085fb685a`:

- <https://huggingface.co/microsoft/VibeVoice-1.5B/tree/c00898d257e6b46004e3e2866a47534085fb685a>

This identity is the model source. The ExecuTorch files produced by the project are deployment derivatives, not the original checkpoint.

## Project routes and status

| Experiment | Route | Committed status |
|---|---|---|
| `0002` | ExecuTorch 1.2 / XNNPACK component exports and bounded integrated generation | **Partial, terminal negative feasibility result.** Fixed-shape components executed on the Galaxy S23 Ultra, but the integrated route covered only 2.04% of the locked reference, was effectively silent, used an approximately 9.1 GB package, and was not useful end-to-end speech. |
| `0003` | LiteRT / LiteRT-LM | **Deferred before conversion or Android execution.** |
| `0004` | ONNX Runtime Mobile | **Deferred before conversion or Android execution.** |
| `0005` | Direct Qualcomm QNN | **Planned and blocked** on first establishing a correct portable implementation. |

Experiment 0002 also proved narrower facts: an acoustic-decoder component and other fixed-shape probes could run reproducibly through ExecuTorch/XNNPACK on Android. Those component results do not turn the rejected bounded generation into a complete deployment.

## Key limitations

- No practical, complete VibeVoice 1.5B Android route is established.
- The experiment-0002 integrated output stopped at a two-chunk static-cache capacity and covered only 0.266667 seconds of a 13.066667-second reference.
- Prefix agreement with the equally short reference prefix is numerical diagnostic evidence, not evidence of useful speech or a listening verdict.
- No Moritz listening acceptance is recorded for the Android output.
- LiteRT, ONNX Runtime Mobile, and direct-QNN rows are plans or deferrals, not failed phone benchmarks and not zero-valued measurements.
- Package size, fixed-cache capacity, and approximately 107× prefix RTF apply to the exact experiment-0002 derivative, not every possible VibeVoice deployment.

See [Evidence boundaries](../methods/evidence-boundaries.md) for the distinction between component execution, structural audio, numerical comparison, and listening review.

## Related experiments

- `experiments/0001-vibevoice-1.5b-local-reference/`
- `experiments/0002-vibevoice-1.5b-executorch-android/`
- `experiments/0003-vibevoice-1.5b-litert-android/`
- `experiments/0004-vibevoice-1.5b-onnx-android/`
- `experiments/0005-vibevoice-1.5b-qnn-android/`

## Evidence sources

- `docs/android-benchmarks/registry.json`
- `experiments/0002-vibevoice-1.5b-executorch-android/README.md`
- `experiments/0002-vibevoice-1.5b-executorch-android/results/complete-build-final.json`
- `experiments/0002-vibevoice-1.5b-executorch-android/results/acoustic-decoder-android.json`
- `experiments/0003-vibevoice-1.5b-litert-android/README.md`
- `experiments/0004-vibevoice-1.5b-onnx-android/README.md`
- `experiments/0005-vibevoice-1.5b-qnn-android/README.md`
