---
title: Kokoro-82M
aliases:
  - Kokoro
  - hexgrad/Kokoro-82M
kind: model
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
---

# Kokoro-82M

> Kokoro-82M is a compact text-to-speech model represented in the project by released sherpa-onnx CPU assets and an exact-source-derived FP32 ONNX route; it matters as a technically complete Android CPU candidate whose QNN work stopped before phone execution.

## Upstream identities

The exact-source work pins `hexgrad/Kokoro-82M` at revision `f3ff3571791e39611d31c381e3a41a3af07b4987`:

- <https://huggingface.co/hexgrad/Kokoro-82M/tree/f3ff3571791e39611d31c381e3a41a3af07b4987>

That route also pins `kokoro==0.9.4`, the official `kokoro-v1_0.pth` checkpoint, and the `af_heart` voice. Earlier archive-backed routes use the separate `kokoro-multi-lang-v1_0` sherpa-onnx release:

- <https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2>

## Project routes and status

| Experiments | Route | Committed status |
|---|---|---|
| `0008`, `0009` | sherpa-onnx Kokoro v1.0 CPU and thread sweep | **Ran.** Exact SID 3 / `af_heart` metadata was pinned; the historical benchmark and sweep did not include listening review. |
| `0009` | Mixed INT8 host candidate | **Not deployed.** It passed a relative paired host degradation ballot, but that did not accept either variant as product-quality speech and produced no Android metrics. |
| `0013` | Exact-source-derived FP32 ONNX CPU versus ExecuTorch | **ONNX ran; ExecuTorch blocked before a full-model PTE.** The Android ONNX route completed six CPU generations. |
| `0017` | Canonical-v2 staged fallback-disabled host QNN | **Terminal host gate failed structural audio.** All 18 stages executed with QNN and zero CPU provider events, but duration changed and the final float audio was invalid, so phone eligibility was false. |

Experiment 0013's ONNX file is a controlled deployment derivative from the exact official weights. It is not the original `.pth` checkpoint and not the earlier sherpa graph. The exact route completed slightly faster than real time on its fixed contract and Moritz accepted its retained WAV; that verdict remains bound to that hash.

## Key limitations

- The archive-backed and exact-source-derived routes use different graph identities and must remain distinct.
- The experiment-0013 ONNX route is fixed to one transcript, `af_heart`, speed, seed, and duration contract; its sample verdict does not establish arbitrary-text or broad-corpus quality.
- ExecuTorch never produced a complete mobile program, so no ONNX-versus-ExecuTorch Android performance comparison exists.
- Experiment 0017 proves fallback-disabled **host** QNN stage execution, not Android execution or physical phone HTP work.
- The invalid experiment-0017 float tensor is not a WAV or listening sample. The accepted experiment-0013 CPU verdict does not transfer to it or to canonical v2.
- No completed Kokoro QNN/HTP phone benchmark, physical RPC/HVX proof, Android accelerator RTF, or accelerator listening verdict exists.

See [Evidence boundaries](../methods/evidence-boundaries.md).

## Related experiments

- `experiments/0008-sherpa-onnx-android-tts-benchmark/`
- `experiments/0009-android-tts-optimization/`
- `experiments/0013-kokoro-onnx-vs-executorch-android/`
- `experiments/0017-kokoro-onnx-qnn-htp-android/`

## Evidence sources

- `docs/android-benchmarks/registry.json`
- `experiments/0008-sherpa-onnx-android-tts-benchmark/README.md`
- `experiments/0009-android-tts-optimization/README.md`
- `experiments/0013-kokoro-onnx-vs-executorch-android/README.md`
- `experiments/0013-kokoro-onnx-vs-executorch-android/results/source-weight-verification.json`
- `experiments/0013-kokoro-onnx-vs-executorch-android/results/phone-onnx-cpu-checkpoint.json`
- `experiments/0017-kokoro-onnx-qnn-htp-android/README.md`
- `experiments/0017-kokoro-onnx-qnn-htp-android/results/canonical-v2-host-qnn-gate.json`
