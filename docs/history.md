# Project history

## Goal and direction

The project started by asking whether Microsoft's VibeVoice could generate a local two-speaker podcast on a modern Android phone. The goal later widened to finding any practical local TTS model that sounds pleasant and natural enough for a future NotebookLM-like listening experience.

Two-speaker generation remains desirable, but it is no longer mandatory. A strong narrator or persistent voices generated turn by turn can also meet the goal. Model quality, sustained listening, and practical Android deployment matter more than preserving the original VibeVoice architecture.

## Experiment record

Each summary links to the experiment that holds the detailed commands, measurements, artifacts, and limitations.

| Experiment | Question at the time | Result and consequence |
|---|---|---|
| [`0001: VibeVoice 1.5B host reference`](../experiments/0001-vibevoice-1.5b-local-reference/) | Can we create a fixed reference before attempting Android conversion? | Produced the reproducible host reference and the evidence protocol used by the first Android campaign. This established the rule that conversion results must be compared with locked inputs and outputs. |
| [`0002: VibeVoice 1.5B ExecuTorch`](../experiments/0002-vibevoice-1.5b-executorch-android/) | Can the model run component by component and then end to end through ExecuTorch on Android? | Individual components ran, but the complete fixed-shape path stopped after two near-silent chunks, covered only 2.04% of the reference, ran very slowly, and required about 9.1 GB. Later analysis showed that the quiet prefix closely matched the expected reference prefix, but it did not fix the capacity limit. The deployment was rejected. |
| [`0003: VibeVoice LiteRT`](../experiments/0003-vibevoice-1.5b-litert-android/) | Should the failed VibeVoice deployment be repeated with LiteRT? | Deferred. A second full conversion was not justified while the model itself had not passed the practical deployment gate. |
| [`0004: VibeVoice ONNX Runtime`](../experiments/0004-vibevoice-1.5b-onnx-android/) | Should the same VibeVoice path be attempted with ONNX Runtime Mobile? | Deferred for the same reason. |
| [`0005: VibeVoice direct QNN`](../experiments/0005-vibevoice-1.5b-qnn-android/) | Should direct Qualcomm acceleration be attempted for VibeVoice 1.5B? | Deferred. Hardware-specific optimization was not justified before selecting a model that already produced acceptable output through a general runtime. |
| [`0006: VibeVoice Realtime 0.5B`](../experiments/0006-vibevoice-realtime-0.5b-android/) | Is the smaller VibeVoice model a more practical comparison? | Recorded feasibility notes and storage estimates, but produced no Android deployment result. This helped motivate a wider candidate search instead of remaining VibeVoice-only. |
| [`0007: Host listening bake-off`](../experiments/0007-mobile-podcast-preview-bakeoff/) | Which smaller models sound promising enough to justify phone work? | Created a six-model, natural-duration host listening comparison. The campaign moved model choice ahead of more conversion work and narrowed the candidates for physical Android measurement. Host listening remained separate from Android feasibility. |
| [`0008: Android TTS benchmark`](../experiments/0008-sherpa-onnx-android-tts-benchmark/) | How do Pocket, Kokoro, and Supertonic perform as pinned Android CPU deployments? | All three generated valid audio on the Galaxy S23 Ultra. Supertonic 3 became the measured technical default with a one-thread warm median RTF of `0.370`. Pocket and Kokoro worked with documented limitations. This replaced VibeVoice as the active deployment direction. |
| [`0009: Android TTS optimization`](../experiments/0009-android-tts-optimization/) | Can model size or CPU threading materially improve the selected candidates? | The exact Kokoro mixed-INT8 candidate was 46.0% smaller and passed the user listening gate. All nine thread configurations ran successfully. Kokoro's four-thread improvement was materially directional; Pocket and Supertonic changes below 10% remained inconclusive. Supertonic stayed the technical default. |
| [`0010: Supertonic QNN/HTP feasibility`](../experiments/0010-supertonic-qnn-htp-feasibility/) | Can the dominant Supertonic components run on the SM8550 HTP without hidden CPU fallback, and is acceleration worth its cost? | Work completed so far proved the physical HTP toolchain with a six-node QDQ add control and CPU fallback disabled. It also localized an ONNX Runtime 1.27.1 QNN crash and retained the upstream fix as a narrow patch. The Supertonic vocoder itself has not executed on HTP: after the crash fix, eight `Erf` nodes in decomposed GELU patterns still prevent a no-fallback session. The experiment remains active. |

## Decisions carried forward

- The repository covers the TTS layer only. Source ingestion, retrieval, script generation, application UI, and episode management belong to the later product.
- Pleasant, natural long-form speech is the primary goal. Joint multi-speaker generation is useful but optional.
- Full-context generation is preferred. Naive sentence or clause splitting was rejected because it can damage prosody and naturalness.
- Supertonic 3 is the current measured Android CPU default. This is a technical selection, not a claim that every listening or product-quality question is closed.
- Accelerator work must fail closed. A graph counts as HTP execution only when CPU fallback is disabled and physical-device profiling proves delegation.
- A control graph, component result, or emulator result is not an end-to-end Supertonic acceleration claim.
- Qualcomm software and generated restricted artifacts stay local. New terms, logins, consent, or export gates require explicit human approval.

The next work is defined in [`plan.md`](plan.md) and its [HTML mirror](plan.html).
