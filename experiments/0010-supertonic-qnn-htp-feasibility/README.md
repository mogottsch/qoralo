# Experiment 0010 — Supertonic 3 QNN/HTP feasibility

## Status

**Paused after a successful physical-HTP control and a fail-closed vocoder investigation.** See the detailed [`PLAN.md`](PLAN.md), [`HANDOFF.md`](HANDOFF.md), and [`results/phone-probe-checkpoint.json`](results/phone-probe-checkpoint.json) for the execution sequence and exact resume point. A tiny QDQ graph has proven real SM8550 HTP execution with CPU fallback disabled; the vocoder has not run, produced output, or established a speedup. [`results/host-checkpoint.json`](results/host-checkpoint.json) is the earlier pre-phone snapshot.

This experiment proceeds component-first with the exact Supertonic 3 deployment measured in experiment 0008 on the Galaxy S23 Ultra's Qualcomm HTP/NPU. Its final gated goal, if the component probes succeed, is to integrate the accepted acceleration into the complete Android TTS path and run the model end to end from the frozen text and voice inputs to final audio. It is not a production integration.

Moritz supplied an already-installed QAIRT/QNN `2.22.6.240515` SDK and explicitly authorized its use for this experiment on 2026-08-13. A local QAIRT `2.49.0.260730` installation was subsequently used for the recorded host probes and Android runtime build because it matches current ONNX Runtime QNN interfaces more closely. No Qualcomm SDK content is committed, and the checkpoint pins the observed local license/runtime hashes without reproducing their contents. Any acquisition that presents new or changed terms, login, export attestation, or other consent must stop for Moritz rather than accepting automatically. Qualcomm materials and generated artifacts remain local-only.

## Question

Can the dominant ONNX components from the pinned Supertonic 3 sherpa-onnx deployment execute wholly on the SM8550 HTP through QNN, without CPU fallback, while preserving acceptable numerical and audio behavior and improving warm inference enough to justify startup and integration costs? If so, can those components accelerate a complete, correct end-to-end Supertonic Android synthesis rather than remain isolated microbenchmarks?

## Exact baseline

The source of truth remains experiment 0008:

- candidate: `sherpa-onnx-supertonic-3-tts-int8-2026-05-11`;
- archive SHA-256: `82fa96f91c4ef8abaae3a14a3f4153facf88bed821d1f7331cec2700f432c427`;
- sherpa-onnx: `v1.13.5`, commit `3dc7c569f31ca2cd4a20ed6f7db780327e6714c5`;
- device: Samsung Galaxy S23 Ultra `SM-S918B`, Snapdragon 8 Gen 2 / `SM8550`;
- voice/language: proven SID 5 / M1, English;
- frozen transcript SHA-256: `350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f`;
- CPU baseline: load `0.765107603` s, cold RTF `0.3854677480612432`, one-thread warm median RTF `0.3703028479158501`, sampled peak PSS `463003648` bytes;
- baseline limitation: all four WAVs were valid, but manual listening was not performed and generation was nondeterministic across runs.

Canonical evidence:

- [`../0008-sherpa-onnx-android-tts-benchmark/results/measured-decision.md`](../0008-sherpa-onnx-android-tts-benchmark/results/measured-decision.md)
- [`../0008-sherpa-onnx-android-tts-benchmark/results/supertonic-3/one-thread-result.json`](../0008-sherpa-onnx-android-tts-benchmark/results/supertonic-3/one-thread-result.json)
- [`../0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/conversion-provenance.json`](../0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/conversion-provenance.json)
- [`../0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/sherpa-config.json`](../0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/sherpa-config.json)

## Runtime choice

The initial target is **QNN's HTP backend**, which addresses the Hexagon tensor accelerator commonly described as the Snapdragon NPU.

The desired application bridge is ONNX Runtime's QNN Execution Provider because the measured assets are already ONNX and the EP exposes explicit fallback controls and QNN profiling. A direct QNN converter plus `qnn-net-run` pass is permitted before that bridge as an isolated toolchain/backend preflight. It can expose conversion and HTP graph-composition failures quickly, but neither HTP emulation nor `qnn-net-run` alone completes the application or end-to-end gates. SNPE, GENIE, and the TFLite delegate remain out of scope. Direct QNN/QAIRT C++ integration may be reconsidered only after a component proves useful on HTP.

The existing experiment 0008 AAR is not a QNN artifact. Its arm64 ONNX Runtime library exports CPU and NNAPI provider entry points, and the pinned sherpa-onnx generic TTS provider path does not recognize `qnn`. It contains ONNX Runtime `1.27.1`; that upstream release's QNN CI pins QAIRT `2.42.0.251225`, while QAIRT `2.22.6.240515` predates it. Experiment 0010 built Android arm64 ONNX Runtime `1.27.1` with QAIRT `2.49.0.260730` QNN static integration and exercised that runtime on the phone. This remains a separate runtime path, not a descriptor-only change to experiment 0008.

## Recorded phone and crash-localization result

A staged six-node QDQ-add control passed on the physical `SM-S918B` with `session.disable_cpu_ep_fallback=1`. Its detailed profile contains RPC and QNN-accelerator finalize/execute timings, accelerator cycles, and four HVX threads. QAIRT 2.49's dynamically loaded `libQnnHtpPrepare.so` is a required deployment file; omitting it caused the first control attempt to fail closed.

The fixed-I/O-shape released-vocoder derivative then crashed during session creation, before inference, with `SIGSEGV`/exit 139. The same fault occurred in x86 HTP emulation. Host GDB localized it to `onnxruntime::QDQ::PadNodeGroupSelector::Check`, where ORT 1.27.1 dereferences an empty `dq_nodes` vector during QNN capability analysis. Microsoft fixed that exact defect upstream in commit `a08e17aab393a922d619736a4150cfe43bc7f8ec` (PR #28733); the minimal backport is tracked at [`patches/onnxruntime-a08e17-pad-empty-dq.patch`](patches/onnxruntime-a08e17-pad-empty-dq.patch).

With that backport, the host runtime no longer crashes. It reports 338 of 354 nodes supported across nine QNN partitions for the fixed released derivative. The sixteen unsupported nodes are eight decomposed-GELU `Erf` nodes and eight weight-only `DequantizeLinear` constants. Folding only those eight constant DQ tails and reconcretizing the measured shapes leaves 338 of 346 nodes supported; only the eight `Erf` nodes remain. Optimization levels 0, 1, 2, and 99 do not produce a complete no-fallback session.

No vocoder inference or audio was produced. The next graph change is consequential and remains pending review: either replace the eight proven standard GELU decompositions with explicit `com.microsoft.Gelu` nodes as a fully provenance-recorded derivative, or create an explicit CPU/HTP split. Enabling implicit ORT CPU fallback is not an accepted route.

## Gated execution order

### 1. Vocoder — toolchain and delegation control

`vocoder.int8.onnx` is the smallest credible HTP entry point:

- bytes: `25991073`;
- SHA-256: `e923d60f53f95eb1ce235f1dc33ec56d9c057823c96fa6f8acf98f32b0da6152`;
- input contract: float tensor `[batch_size, 144, latent_length]`;
- graph contains explicit `QuantizeLinear`/`DequantizeLinear` structure and convolution-heavy work;
- invoked once per Supertonic text chunk.

Its role is to prove the approved toolchain, fixed-shape preparation, actual HTP execution, profiling, and numerical comparison. Passing this control alone does not establish a useful end-to-end speedup.

### 2. Vector estimator — primary value probe

`vector_estimator.int8.onnx` is the priority compute candidate:

- bytes: `78400833`;
- SHA-256: `20cd86fa5c6effedfda0e7cffe5b0569ca401c440a0c3a1d72bf39286c0db3fd`;
- dynamic text and latent dimensions;
- invoked five times by the measured default Supertonic generation loop;
- graph contains convolution/matrix work, but also `DynamicQuantizeLinear` and `MatMulInteger`, which are preliminary compatibility risks for QNN HTP.

The exact graph is tested first. If QNN rejects it, that negative result is retained before any rewrite or re-quantization is considered.

### 3. End-to-end accelerated Android synthesis — final goal

Only after the vocoder and vector-estimator gates succeed will the experiment proceed to its final step: integrating the accepted QNN/HTP component sessions into the complete pinned Supertonic Android generation path. The run must start with the frozen transcript, proven SID 5/M1 voice, and English configuration; execute every required preprocessing, duration, text-encoding, five-step denoising, and vocoder stage without fixture substitution; and produce the complete final audio through the Android harness.

The final path may be explicitly hybrid: text preparation, orchestration, and non-targeted graphs may remain on CPU, while each HTP-targeted component must still run with implicit CPU fallback disabled. Detailed profiles must prove that the accepted components execute on HTP during the end-to-end run. The result must compare cold and warm latency, callback timing, memory, output validity, and numerical/audio behavior with the experiment 0008 CPU baseline.

A component-only success is not the final outcome. Experiment 0010 may claim that Supertonic works with QNN acceleration only after this end-to-end Android step passes. A full rewrite of every sherpa-onnx component is not required if the measured hybrid pipeline is correct and useful.

The duration predictor and text encoder are not initial HTP targets: they run once per chunk, while the repeated vector estimator is more likely to dominate. They are still part of the final end-to-end model execution and may remain explicitly on CPU unless profiling justifies additional HTP work.

## Probe requirements

### Exactness and fixed shapes

QNN HTP requires concrete deployment shapes. Capture the actual experiment-0008 component inputs before preparing fixed-shape graphs; do not guess representative lengths.

Every derived graph must record:

- source path, byte count, and SHA-256;
- transformation tool and exact version/revision;
- complete command/configuration;
- fixed input/output shapes and why they correspond to the frozen transcript;
- output byte count and SHA-256;
- whether the change is shape fixing, graph rewriting, or re-quantization.

A fixed-shape derivative may not be silently described as the original ONNX file. A re-quantized graph is a separately labeled deployment derivative and does not prove that the exact released graph works unchanged.

### Proof of HTP execution

A positive component result requires all of the following:

1. QNN HTP is selected explicitly; QNN CPU and GPU backends do not qualify.
2. ONNX Runtime CPU fallback is disabled for the component session.
3. Session creation fails rather than silently partitioning unsupported nodes to CPU.
4. Detailed QNN profiling is enabled and retained by hash-addressed provenance.
5. The profile demonstrates HTP graph execution for the measured calls.
6. Provider options, runtime versions, loaded library hashes, device/SoC identity, and logs are recorded.

Provider presence, successful audio, process names, or wall-time improvement alone do not prove HTP delegation.

### Numerical and audio equivalence

Before HTP measurement, freeze deterministic CPU fixtures from the same graph and exact component inputs. Compare CPU and HTP outputs with predeclared tensor metrics and thresholds, including finite-value checks, shape/dtype equality, maximum and mean absolute error, relative error where meaningful, and a scale-insensitive metric such as cosine similarity or SNR.

For the final end-to-end accelerated synthesis, set an explicit seed and compare decoded audio length/rate, finiteness, silence/clipping, waveform or spectral error, and listening status. The nondeterministic experiment-0008 WAV hashes are not a direct numerical oracle.

Thresholds must be reviewed and frozen before looking at HTP outputs. A plausible-sounding WAV cannot override a failed numerical gate.

### Latency

Measure these boundaries separately in fresh processes:

- runtime/library initialization;
- ONNX Runtime session creation and QNN graph finalization;
- first component execution;
- at least three warm executions and their median;
- optional QNN context-binary load in a separate campaign, only after uncached execution works;
- host-to-HTP and HTP-to-host tensor-transfer costs where observable.

Do not compare component latency directly with experiment 0008's end-to-end RTF. The final end-to-end accelerated run must preserve the experiment 0008 timing boundary and report cold and warm results separately.

## Decision rule

A component is **HTP-feasible** only if it:

- initializes and runs with CPU fallback disabled;
- has profiling evidence of real HTP execution;
- passes frozen numerical criteria;
- has complete startup and warm-latency measurements;
- uses a fully provenance-recorded graph derived from the exact pinned source.

A technically successful component is **worth continuing** only if its warm benefit is not erased by startup, transfers, remaining CPU work, memory, package size, or integration complexity. No speedup is assumed in advance; the CPU baseline is already faster than real time.

The experiment-level positive outcome requires a complete Android synthesis with the accepted components accelerated on HTP, no fixture substitution, full audio validation, HTP proof from the end-to-end run, and a direct cold/warm comparison with experiment 0008. Component feasibility alone is an intermediate result.

## Boundaries

- End-to-end accelerated Supertonic execution is in scope; production productization and forcing every component onto HTP are not.
- No Pocket or Kokoro QNN work; those require separate decisions.
- Pocket's model-license ambiguity is unrelated to this track.
- No claim about energy or thermal benefit without measurement.
- No privileged device changes, root access, or system-library mutation.
- No publication or bundling of Qualcomm proprietary libraries, headers, tools, generated binaries, agreement text, or restricted documentation.
- Proprietary SDKs, shared libraries, generated QNN contexts, profiles, APKs, tensors, and audio remain ignored local artifacts. Git may retain only permitted scripts, manifests, hashes, measurements, public-source citations, and conclusions.

## Approval gates

1. **Technical direction — agreed:** Supertonic first; QNN HTP; vocoder control followed by vector estimator.
2. **Existing Qualcomm SDK use — authorized:** Moritz supplied and authorized QAIRT `2.22.6.240515`; any new or changed terms still require a stop and human review.
3. **Fixture/protocol review:** freeze shapes, inputs, equivalence thresholds, and measurement contract.
4. **Vocoder result review:** decide whether the HTP toolchain is credible.
5. **Vector-estimator result review:** decide whether end-to-end integration is justified.
6. **End-to-end accelerated Android result:** run the complete pinned model path, prove HTP use in context, validate final audio, and compare it with the experiment 0008 CPU baseline.

## Public documentation consulted during planning

These links are context only and do not replace review of the actual agreement or the exact approved SDK release:

- Qualcomm QAIRT overview: <https://docs.qualcomm.com/doc/80-63442-10/topic/general_overview.html>
- ONNX Runtime QNN Execution Provider: <https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html>
- sherpa-onnx Qualcomm NPU overview: <https://k2-fsa.github.io/sherpa/onnx/qnn/index.html>

Operator support, provider behavior, and licensing must be pinned again against the exact versions approved for execution.
