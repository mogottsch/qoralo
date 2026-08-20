# Experiment 0010 — Supertonic 3 QNN/HTP feasibility

## Status

**Complete with a bounded hybrid result.** See the detailed [`PLAN.md`](PLAN.md) ([HTML mirror](PLAN.html)), final [`HANDOFF.md`](HANDOFF.md), and canonical [`results/e2e-hybrid-cpu-checkpoint.json`](results/e2e-hybrid-cpu-checkpoint.json). The fixed-transcript Android path ran all four Supertonic components and produced complete CPU and hybrid WAVs. Hybrid warm generation was 37.215% lower latency. Moritz first reported no audible CPU/hybrid difference, which remains comparison-only evidence; he later explicitly accepted each exact end-to-end sample as “Good.” The sample-level acceptance is bound to CPU SHA `7e83537630b3e354f7586b9887f7a8359d62e438c9addeea61d87d878b2a84ff` and hybrid SHA `9b0d488776b144c972e8be4e9434fac14ce3ceddfcfa5a10d137fca41b772668`. It does not erase the failed prospective waveform gate or establish broad-corpus quality.

The result is explicitly limited: duration and text encoding remained on CPU; each vector-estimator call used 21 QNN/HTP partitions plus 136 CPU nodes; only the explicit-GELU vocoder was fully delegated with fallback disabled. The route is fixed to T239/L238, has very high startup and memory costs, and is neither full HTP nor numerically accepted. CPU remains the supported technical reference; hybrid is retained as a bounded research baseline rather than a production integration. Earlier checkpoints remain historical evidence.

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
- baseline limitation: all four WAVs were structurally valid, but manual listening was not performed and generation was nondeterministic across runs; subjective quality was unknown.

Canonical evidence:

- [`../0008-sherpa-onnx-android-tts-benchmark/results/measured-decision.md`](../0008-sherpa-onnx-android-tts-benchmark/results/measured-decision.md)
- [`../0008-sherpa-onnx-android-tts-benchmark/results/supertonic-3/one-thread-result.json`](../0008-sherpa-onnx-android-tts-benchmark/results/supertonic-3/one-thread-result.json)
- [`../0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/conversion-provenance.json`](../0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/conversion-provenance.json)
- [`../0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/sherpa-config.json`](../0008-sherpa-onnx-android-tts-benchmark/models/supertonic-3/sherpa-config.json)

## Inference architecture

Supertonic processes one text chunk through four ONNX components. The surrounding runtime performs text preparation, selects the requested voice, sizes the latent sequence, and writes the resulting audio.

```text
text
  → normalize + add language tags + Unicode indexing
  → text IDs and text mask
      ├─ + duration style → duration predictor → predicted audio duration
      └─ + text-to-latent style → text encoder → text embedding
  → duration-based latent length and mask + seeded noise
  → vector estimator × 5 (each output becomes the next step's latent)
  → vocoder → float waveform
  → trim to predicted sample count → mono PCM16 WAV
```

The packaged `voice.bin` contains two style tensors for each speaker. The selected speaker supplies `style_dp` to duration prediction and `style_ttl` to text encoding and every vector-estimator step. These are model conditioning inputs, not recorded reference audio.

The four ONNX components run in this order:

1. **Duration predictor (`duration_predictor.int8.onnx`)** — consumes the indexed text, text mask, and `style_dp`; returns the chunk's predicted duration. The configured speed scales this value, which then determines the target waveform length and latent length.
2. **Text encoder (`text_encoder.int8.onnx`)** — consumes the same text IDs and mask with `style_ttl`; returns the text embedding that conditions latent generation.
3. **Vector estimator (`vector_estimator.int8.onnx`)** — consumes the current noisy latent, text embedding, `style_ttl`, text and latent masks, and current/total step values. The default inference loop calls it five times, feeding each output latent into the next call.
4. **Vocoder (`vocoder.int8.onnx`)** — converts the final latent tensor into waveform samples. The runtime trims that waveform to the duration-derived sample count and encodes it as a mono PCM16 WAV.

Before the ONNX calls, the runtime normalizes punctuation and spacing, adds language tags, applies Unicode NFKD decomposition, and maps supported BMP code points through the packaged `unicode_indexer.bin`. Latent initialization is Gaussian noise masked to the duration-derived sequence length; a fixed seed is used only when deterministic reproduction is required.

## Runtime choice

The initial target is **QNN's HTP backend**, which addresses the Hexagon tensor accelerator commonly described as the Snapdragon NPU.

The desired application bridge is ONNX Runtime's QNN Execution Provider because the measured assets are already ONNX and the EP exposes explicit fallback controls and QNN profiling. A direct QNN converter plus `qnn-net-run` pass is permitted before that bridge as an isolated toolchain/backend preflight. It can expose conversion and HTP graph-composition failures quickly, but neither HTP emulation nor `qnn-net-run` alone completes the application or end-to-end gates. SNPE, GENIE, and the TFLite delegate remain out of scope. Direct QNN/QAIRT C++ integration may be reconsidered only after a component proves useful on HTP.

The existing experiment 0008 AAR is not a QNN artifact. Its arm64 ONNX Runtime library exports CPU and NNAPI provider entry points, and the pinned sherpa-onnx generic TTS provider path does not recognize `qnn`. It contains ONNX Runtime `1.27.1`; that upstream release's QNN CI pins QAIRT `2.42.0.251225`, while QAIRT `2.22.6.240515` predates it. Experiment 0010 built Android arm64 ONNX Runtime `1.27.1` with QAIRT `2.49.0.260730` QNN static integration and exercised that runtime on the phone. This remains a separate runtime path, not a descriptor-only change to experiment 0008.

## Recorded execution and outcome

### Toolchain and crash fix

A six-node QDQ-add control first proved physical SM8550 HTP execution with fallback disabled. The fixed released vocoder then exposed an ONNX Runtime 1.27.1 null dereference in `PadNodeGroupSelector::Check`; Microsoft fixed the same defect upstream in commit `a08e17aab393a922d619736a4150cfe43bc7f8ec`. The experiment retains the minimal backport at [`patches/onnxruntime-a08e17-pad-empty-dq.patch`](patches/onnxruntime-a08e17-pad-empty-dq.patch).

The exact fixed vocoder still had eight `Erf` and eight weight-only `DequantizeLinear` blockers. Folding only the constant DQ tails and replacing eight verified standard GELU decompositions with explicit `com.microsoft.Gelu` produced a provenance-locked derivative that was bit-identical on CPU and fully assigned to one QNN partition. Physical HTP execution then succeeded, but the frozen vocoder numerical policy failed. In a later informal A/B, Moritz reported no audible difference between the isolated CPU and HTP vocoder samples; no separate standalone-quality acceptance was recorded, and the numerical rejection was not changed.

### Vector estimator

The official vector estimator is SHA-256 `20cd86fa5c6effedfda0e7cffe5b0569ca401c440a0c3a1d72bf39286c0db3fd`. A deterministic shape-only T239/L238 derivative preserves every node and initializer, but full QNN assignment remains blocked: 921 of 1,057 optimized nodes are supported across 21 partitions, leaving 80 `DequantizeLinear`, 34 `MatMulInteger`, 21 `DynamicQuantizeLinear`, and one `Softplus` on CPU.

A separately authorized fallback diagnostic proved mixed physical execution. In a matched single step, mixed execution was 9.23% faster than CPU. This did not establish full HTP, so the final hybrid continued to label the estimator explicitly as QNN+CPU.

### Complete fixed-transcript synthesis

The final Android runner started from the frozen experiment-0008 transcript, Unicode indexer, M1/SID5 styles, and seed `20260813`; executed duration prediction, text encoding, five recursive estimator calls, vocoding, trimming, and WAV writing; and substituted no intermediate fixture tensors. QNN's concrete-shape requirement kept the predeclared T239/L238 and `729746`-sample deployment contract. Duration prediction still ran and reported `16.9202` seconds, but did not dynamically rebuild the graph.

Provider evidence across four complete generations:

- CPU route: all four sessions report CPU events only;
- hybrid duration and text encoder: CPU;
- hybrid vector estimator: `420` QNN partition events plus `2720` CPU node events across 20 calls;
- hybrid vocoder: four QNN events and zero CPU events;
- all `424` QNN events include physical RPC, accelerator-time/cycle, and four-HVX-thread evidence.

Never interpret this as full HTP.

| Measurement | CPU | Hybrid | Difference |
|---|---:|---:|---:|
| Session creation | `0.611356 s` | `26.965 s` | hybrid `44.107×` longer |
| First generation after sessions | `5.84446 s` | `4.33056 s` | hybrid `25.903%` lower |
| Warm generation median | `6.06733 s` | `3.80935 s` | hybrid `2.25798 s` / `37.215%` lower (`1.593×`) |
| `ru_maxrss` after sessions | `217420 KiB` | `1028044 KiB` | high-water only |
| `ru_maxrss` after runs | `459432 KiB` | `1154172 KiB` | hybrid `2.512×` higher |

Hybrid startup is dominated by vector QNN session creation (`21.9854 s`) and vocoder creation (`4.74756 s`): QNN partitions, optimizes, compiles, and finalizes graphs; prepares weights/layouts; and establishes RPC/shared buffers. It is generally a one-time cost only if sessions remain resident. Setup plus first generation was `6.456 s` CPU versus `31.296 s` hybrid; setup plus four was `24.649 s` versus `42.590 s`. The observed setup delta divided by warm savings suggests roughly 12 retained-process generations to amortize, but this is illustrative arithmetic, not a controlled claim.

`ru_maxrss` is a process-lifetime high-water mark, not steady live PSS or complete DSP-private memory. The hybrid retains CPU graph/fallback state while adding QNN prepared/compiled representations, metadata, shared buffers, profiling state, and transient setup allocations.

Both WAVs are structurally valid, finite, non-silent, unclipped mono PCM16. The prospectively frozen waveform gate nevertheless failed: cosine `0.405431`, SNR `-0.592623 dB`, normalized RMSE `1.07061`, RMSE `0.0593432`, mean absolute error `0.0302192`, and max error `0.641157`. Moritz's initial report of no audible CPU/hybrid difference remains comparison-only evidence. His later explicit “Good” verdict separately accepts both exact samples for listening; it does not override numerical rejection, identify an operator defect, or generalize beyond this utterance and configuration.

The canonical machine-readable result is [`results/e2e-hybrid-cpu-checkpoint.json`](results/e2e-hybrid-cpu-checkpoint.json). WAVs, profiles, latency arrays, and the convenience listening report remain ignored local evidence under `work/e2e/`.

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

## Final decision

Experiment 0010 is complete. It demonstrated a technically complete fixed-transcript hybrid with 37.215% lower warm generation latency. Moritz accepted both exact end-to-end samples as “Good,” but the route is still not full HTP, arbitrary-shape, numerically accepted, broad-corpus quality-proven, or production-ready in startup/memory.

**Retained deployment decision:** keep Supertonic CPU as the supported technical reference, now with a positive sample-level listening verdict for the exact reviewed artifact. Preserve the hybrid only as a bounded research baseline despite its positive exact-sample verdict; do not claim production adoption, broad quality generalization, numerical acceptance, or full-HTP success. A source-model-first or full-HTP follow-up is only under discussion with Moritz. No export route or subsequent experiment is approved by this document.

## Public documentation consulted during planning

These links are context only and do not replace review of the actual agreement or the exact approved SDK release:

- Qualcomm QAIRT overview: <https://docs.qualcomm.com/doc/80-63442-10/topic/general_overview.html>
- ONNX Runtime QNN Execution Provider: <https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html>
- sherpa-onnx Qualcomm NPU overview: <https://k2-fsa.github.io/sherpa/onnx/qnn/index.html>

Operator support, provider behavior, and licensing must be pinned again against the exact versions approved for execution.
