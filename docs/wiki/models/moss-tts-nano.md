---
title: MOSS-TTS-Nano
aliases:
  - OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX
  - MOSS TTS Nano
kind: model
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
---

# MOSS-TTS-Nano

> MOSS-TTS-Nano is a multi-stage text-to-speech system with official ONNX assets; it matters here because its complete Android CPU route worked, while its reusable QNN design and final physical-phone HTP path both encountered explicit blockers.

## Upstream identity

The benchmark registry pins `OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX` at revision `f52645cb467506d8e18e746ddd59482685b74e58`:

- <https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX/tree/f52645cb467506d8e18e746ddd59482685b74e58>

Experiment 0018 additionally pins:

- source repository `OpenMOSS/MOSS-TTS-Nano` at `cc7bdf19c7639c0870dab22045a33b442760f6be`;
- audio-tokenizer ONNX assets `OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX` at `ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae`.

## Project routes and status

| Experiment | Route | Committed status |
|---|---|---|
| `0018` | Official ONNX Runtime Android CPU | **Ran end to end.** Four official sessions produced a structurally valid 16.72-second WAV through `CPUExecutionProvider` only. The uninstrumented warm median RTF was 1.125 and process VmHWM reached approximately 5.83 GB. |
| `0019` | Reusable dynamic-decode QNN/HTP host feasibility | **Blocked before Android.** The reusable decode graph left most optimized nodes unsupported; a 209-session fixed-shape workaround was host-feasible but not a reusable deployment. |
| `0019` | Canonical-v2 fixed-capacity derivative and phone carrier | **Passed CPU equivalence and host QNN/context gates, then blocked on the phone.** QNN `CreateDevice` returned `QNN_DEVICE_ERROR_INVALID_CONFIG` before session assignment or inference. |

The CPU path performs prefill, autoregressive decoding, a fixed-frame local decoder, and full audio-tokenizer decoding. Its reported “first decoded PCM” is when the full non-streaming audio-tokenizer decode returned audio, not time to a streaming chunk.

## Key limitations

- The experiment-0018 CPU route was slower than real time on its exact benchmark and had a large process-wide memory high-water mark.
- Its provider profile is CPU-only; it is not HTP evidence.
- The accepted experiment-0018 listening verdict applies only to WAV SHA-256 `173850781b055e70a606fb561d93b70e6d8c6318db1b29b2324f83506c21ad6b`. It does not establish broad-corpus quality, every voice, or every configuration.
- Host QNN assignment, generated contexts, and context reload are feasibility evidence, not physical accelerator execution.
- The phone blocker occurred before any neural session, inference, audio, timing, memory benchmark, provider-event proof, or physical RPC/HVX proof. Missing values are unavailable, not zero.
- The final `CreateDevice` result is bounded to the recorded carrier, app UID, Android build, runtime versions, and phone; it is not a general claim that MOSS or QNN cannot run on Android.
- No MOSS QNN/HTP phone WAV or listening verdict exists.

See [Evidence boundaries](../methods/evidence-boundaries.md).

## Related experiments

- `experiments/0018-moss-tts-nano-onnx-android/`
- `experiments/0019-moss-tts-nano-qnn-htp-android/`

## Evidence sources

- `docs/android-benchmarks/registry.json`
- `experiments/0018-moss-tts-nano-onnx-android/README.md`
- `experiments/0018-moss-tts-nano-onnx-android/results/source-inventory.json`
- `experiments/0018-moss-tts-nano-onnx-android/results/phone-cpu-checkpoint.json`
- `experiments/0019-moss-tts-nano-qnn-htp-android/README.md`
- `experiments/0019-moss-tts-nano-qnn-htp-android/results/host-checkpoint.json`
- `experiments/0019-moss-tts-nano-qnn-htp-android/results/fixed-capacity-cpu-equivalence.json`
- `experiments/0019-moss-tts-nano-qnn-htp-android/results/fixed-capacity-context-provenance.json`
- `experiments/0019-moss-tts-nano-qnn-htp-android/results/fixed-capacity-phone-blocker.json`
