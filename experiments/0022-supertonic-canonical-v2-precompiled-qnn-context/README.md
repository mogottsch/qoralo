# Experiment 0022 — Supertonic canonical-v2 precompiled QNN context

**Status: authorized and frozen at a safe pre-implementation boundary; no context has been generated and no benchmark has run.**

This experiment will measure whether production-style precompiled ONNX Runtime QNN EPContext/context binaries reduce cold startup for the previously accepted stable-Softplus all-HTP Supertonic route. It is a new canonical-v2 route. It does not modify or relabel historical experiment 0011 or the canonical-v2 CPU route in experiment 0021.

The matched arms are:

- **A — source ONNX:** create four QNN sessions from the frozen source/transformed ONNX graphs with CPU fallback disabled. QNN compilation is inside the measured readiness/setup boundary.
- **B — precompiled context:** create the same four QNN sessions from independently reload-validated, non-embedded EPContext ONNX descriptors plus external QNN context binaries. Context generation is an offline cost and is reported separately, not charged to arm-B startup.

Both arms must preserve the same graph identity, source precision claim, provider options, runtime binaries, voice, frontend, random seed, fixed shapes, phone, thermal eligibility, and benchmark runner. The only intended variable is source-graph compilation versus context reload.

## Canonical contract

- Transcript: `protocols/android-tts-benchmark/transcript.txt`, canonical v2, 226 bytes, no trailing newline.
- SHA-256: `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`.
- Voice: official public M1, semantic SID5.
- Provider: QNN HTP, CPU fallback disabled.
- Runtime baseline: the experiment-0011 Android `libonnxruntime.so`, ORT 1.27.1, SHA-256 `40bc591798287525f365e8ded4bbc40e0c4e9440737e876026ec09ba359ac041`.
- QAIRT baseline: 2.49.0.260730 and the exact QNN library hashes in `protocol/experiment-contract.json`.
- Target phone: Samsung SM-S918B / SM8550 / arm64-v8a, serial `R5CW81PR8SY`; identity and boot-state gates remain mandatory.

## Required gates before a benchmark claim

1. Resolve and freeze canonical-v2 frontend/fixed-shape compatibility without changing the accepted transformed graph hashes. The historical runner requires processed text length 239, while canonical v2 plus `<en>…</en>` is 235. Padding is only permissible after proving that it is mask-neutral and that the semantic input bytes remain exactly canonical v2. No silent transcript substitution or graph re-specialization is allowed.
2. Prove complete QNN source assignment for duration, text, stable-Softplus vector, and vocoder with fallback disabled.
3. Generate each context while recording generation time, tool/runtime/device identity, source hash, output hash, and byte size.
4. Reload every EPContext in an independent fresh process after making source ONNX unavailable. Require successful output and zero CPU-provider node events.
5. Run at least three independent cold processes for each arm and report each per-session and total readiness/setup value plus median/distribution.
6. In each measured process, perform one first complete generation plus at least five same-session warm generations with full generation-state reset. RTF is latency divided by actual emitted duration.
7. Record peak sampled PSS, cumulative VmHWM, thermal/power context, source/context/package sizes, and context-generation time.
8. Collect physical provider/RPC/accelerator/cycle/HVX evidence. Host QNN evidence is not phone HTP proof.
9. Compare arm-A and arm-B output hashes and prospective numerical metrics. Any different WAV bytes start `not_reviewed` and require Moritz’s exact route/hash verdict.

See `protocol/experiment-contract.json` for the machine-readable frozen scope and [`PLAN.md`](PLAN.md) for the gates, commands, known compatibility question, and next action.
