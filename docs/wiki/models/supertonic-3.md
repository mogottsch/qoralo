---
title: Supertonic 3
aliases:
  - Supertone/supertonic-3
  - Supertonic
kind: model
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
---

# Supertonic 3

> Supertonic 3 is a four-component text-to-waveform system that became the project's main Android CPU reference and its most developed QNN/HTP route, with both source-ONNX and precompiled-context startup evidence.

## Upstream identity

The registry pins the first-party `Supertone/supertonic-3` assets at revision `724fb5abbf5502583fb520898d45929e62f02c0b`:

- <https://huggingface.co/Supertone/supertonic-3/tree/724fb5abbf5502583fb520898d45929e62f02c0b>

Some CPU work instead used the released archive `sherpa-onnx-supertonic-3-tts-int8-2026-05-11`, SHA-256 `82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427`, with sherpa-onnx `v1.13.5` at revision `3dc7c569f31ca2cd4a20ed6f7db780327e6714c5`. Archive-backed INT8 results and first-party FP32 results are distinct deployment variants.

## Project routes and status

| Experiments | Route | Committed status |
|---|---|---|
| `0008`, `0009`, `0020`, `0021` | Released INT8 Android CPU | **Ran.** The registry retains the legacy baseline/thread sweep, an exact historical refresh, and a distinct canonical-v2 CPU benchmark. |
| `0010` | Fixed-shape mixed QNN/HTP plus CPU fallback | **Ran as a bounded hybrid.** Physical HTP work reduced warm latency, but the vector estimator retained CPU fallback and the frozen numerical gate failed. |
| `0011` | Official FP32 CPU and stable-Softplus fallback-disabled QNN/HTP | **Ran.** All four neural components executed on HTP in the rewritten route, but the prospective end-to-end numerical policy still failed. The unmodified full-HTP vector route stopped fail-closed at an unsupported `Softplus`. |
| `0022` | Canonical-v2 input with exact frozen T239 graph identities | **Stopped at a host compatibility gate.** Masked T235-to-T239 padding changed the calculation, so no QNN context, phone run, WAV, or startup measurement followed. |
| `0023` | Legacy-v1 stable-Softplus source ONNX versus external contexts | **Ran.** External contexts reduced the matched four-session phone setup boundary from a 21.6129-second median to 0.497816 seconds while preserving the exact output bytes. |

Supertonic's four neural components are duration prediction, text encoding, a recursively called vector estimator, and a vocoder. CPU orchestration still prepares text and styles, controls generation, and writes audio even when every neural session is assigned to QNN.

## Key limitations

- Legacy-v1 T239/L238 routes and canonical-v2 T235 routes are not interchangeable.
- The stable-Softplus graph is an audited derivative, not the untouched official vector-estimator graph.
- Full neural QNN assignment does not mean all application work runs on HTP or establish internal FP32 arithmetic.
- Experiment 0011's all-HTP output failed its prospective numerical policy despite completing technically.
- Experiment 0023's startup reduction is bounded to four exact legacy-v1 sessions, the authorized phone, and its readiness boundary; offline context generation is excluded.
- Listening verdicts belong only to exact reviewed WAV hashes. The byte-identical 0023 output can inherit the identical 0011 hash verdict, but no verdict transfers to a different transcript, graph, route, or output.
- No broad-corpus or production-readiness conclusion follows from the committed samples.

See [Evidence boundaries](../methods/evidence-boundaries.md).

## Related experiments

- `experiments/0008-sherpa-onnx-android-tts-benchmark/`
- `experiments/0009-android-tts-optimization/`
- `experiments/0010-supertonic-qnn-htp-feasibility/`
- `experiments/0011-supertonic-official-fp32-phone-comparison/`
- `experiments/0020-historic-android-benchmark-refresh/`
- `experiments/0021-supertonic-canonical-v2-android-cpu/`
- `experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/`
- `experiments/0023-supertonic-qnn-precompiled-context-startup/`

## Evidence sources

- `docs/android-benchmarks/registry.json`
- `experiments/0008-sherpa-onnx-android-tts-benchmark/README.md`
- `experiments/0010-supertonic-qnn-htp-feasibility/results/e2e-hybrid-cpu-checkpoint.json`
- `experiments/0011-supertonic-official-fp32-phone-comparison/README.md`
- `experiments/0011-supertonic-official-fp32-phone-comparison/results/softplus-matched-e2e-checkpoint.json`
- `experiments/0021-supertonic-canonical-v2-android-cpu/results/phone-cpu-result.json`
- `experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/results/t235-t239-masked-padding-compatibility.json`
- `experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/phone-result.json`
