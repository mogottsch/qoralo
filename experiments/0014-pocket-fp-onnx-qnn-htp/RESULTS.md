# Pocket ONNX → QNN HTP results

## Bottom line

The continuation achieved **technically QNN-only neural execution for complete observed text-to-WAV paths** on the S23:

- CPU fallback was disabled.
- Every neural call used to produce the listed WAVs was assigned to `QNNExecutionProvider`.
- There were zero CPU provider events.
- Every QNN provider event had matching RPC, accelerator, cycle, and HVX evidence.

However, **Moritz rejected every sample as unusable in a blind listen**, including the experiment-0012 CPU comparator. The QNN samples were unintelligible mumbling; the CPU sample was repetitive “takakakakakakakaka.” This is therefore a technical execution result, not a speech-quality success or deployment recommendation.

## Blind listening verdict

On 2026-08-19, Moritz listened before route labels were revealed:

| Blind sample | Revealed route | SHA-256 | Moritz's verdict |
|---|---|---|---|
| A | QNN-only FP-source route; HTP FP16 | `467e7778…7f3` | Unintelligible mumbling; perhaps only “Android” recognizable |
| B | 0012 ONNX Runtime CPU oracle | `40634981…d22` | Repetitive “takakakakakakakaka” |
| C | QNN-only calibrated-INT16 FlowLM route | `dcdb36df…820` | Unintelligible mumbling; perhaps only “Android” recognizable |

All three were explicitly rejected as unusable. Full record: [`results/blind-listening.json`](results/blind-listening.json).

The ignored listening page and WAVs remain at:

```text
/home/moritz/vibevoice-android-spike/experiments/0014-pocket-fp-onnx-qnn-htp/work/listening/index.html
```

## What changed after the original screen

The first phase of 0014 correctly showed that the unchanged 0012 graphs could not run fail-closed on QNN. The continuation preserved that evidence and introduced reproducible derivatives from the exact pinned weights.

### Fixed-cache FlowLM ABI

The dynamic cache/scatter graph was replaced with:

- twelve right-aligned K/V tensors (`6 layers × K/V`) of shape `[1,16,256,64]`
- one additive validity mask
- explicit absolute RoPE positions
- separate static graphs for 126-frame voice prefill, 26-token text prefill, BOS AR, and latent AR

All four graphs formed one QNN partition each with fallback disabled:

| FlowLM graph | QNN nodes | Partitions |
|---|---:|---:|
| Voice prefill | 306/306 | 1 |
| Text prefill | 306/306 | 1 |
| BOS AR | 327/327 | 1 |
| Latent AR | 341/341 | 1 |

CPU component checks were close: prefill-cache max error `3.64e-5`, maximum conditioning error across 100 steps `3.25e-4`, and maximum latent error `1.96e-4`. Those small differences nevertheless accumulated autoregressively. An Android CPU run of the derivative also changed long-run EOS behavior, proving that the issue was not HTP alone.

### Mimi rewrites

The Mimi derivatives narrowly:

1. removed one encoder `Pad` whose six extents were all exactly zero;
2. replaced two verified erf-GELU chains with `com.microsoft.Gelu`;
3. bypassed NaN cleanup around finite Softmax fixtures;
4. exposed unchanged decoder states directly instead of unsupported output `Identity` nodes.

Results:

| Graph | Host assignment | CPU check |
|---|---:|---:|
| Encoder | 152/152 source nodes, one QNN partition | exact |
| Decoder, 12 frames | 264/264 source nodes, one QNN partition | exact on 78-frame audio |
| Decoder, 6 frames | 264/264 source nodes, one QNN partition | exact on 78-frame audio |
| Decoder, 1 frame | 264/264 source nodes, one QNN partition | max `1.36e-6` vs a six-frame call |

### Calibrated INT16 experiment

Because HTP maps unquantized FP source graphs to FP16 kernels, a second FlowLM family used real-prompt QDQ calibration with asymmetric UINT16 activations and symmetric INT16 weights for eligible MatMul, Gemm, and LayerNormalization nodes. Every graph still formed one QNN partition, but CPU error was materially larger, reaching `0.2365` for conditioning and `0.2208` for latents across 100 steps.

## Explicit-temperature-0.7 physical candidates

A protocol drift was discovered: the committed 0012 runner did not pass temperature through `extra`, the C API conversion omitted the zeroed C struct temperature field, and Pocket therefore used its default `0.7`. The device WAV called the 0012 oracle was not generated at the prose-declared `0.3`. Exact evidence is in [`results/temperature-drift.json`](results/temperature-drift.json). Experiment 0012 was not edited.

Both corrected 0.7 runs used the unchanged text, Bria WAV, seed 0, one flow step, one thread, and exact pinned weights.

| Measurement | FP-source QNN | INT16-FlowLM QNN | 0012 CPU |
|---|---:|---:|---:|
| Setup/session creation | 236.175 s | 220.405 s | 1.079 s |
| One complete generation | 6.248 s | 7.283 s | warm median 3.933 s |
| Emitted audio | 8.00 s | 7.28 s | 6.24 s |
| **RTF, normalized by emitted duration** | **0.781** | **1.000** | **0.630 warm median** |
| Frames | 100 | 91 | 78 |
| EOS step | none before cap | 88 | inferred 75 |
| Process VmHWM | 4,039,684 kB | 4,050,344 kB | 1,586,080 kB |

Lower RTF is better. The setup numbers include ten profiled ORT/QNN sessions and graph compilation. VmHWM is cumulative process high-water, not isolated model memory.

Only one profiled generation was collected per QNN candidate before Moritz stopped further work. There is no honest cold-plus-five-warm distribution or first-audio latency for these routes.

## Provider assignment and physical HTP evidence

### FP-source route

The complete 100-frame observed path recorded:

- 216 QNN provider events
- 0 CPU provider events
- 216 RPC execute events, 5,061,149 µs total
- 216 accelerator execute events, 5,020,487 µs total
- 216 accelerator-cycle events, 4,204,175,420 cycles total
- 216 HVX records, four threads each

Calls were: text 1, encoder 1, voice prefill 1, text prefill 1, BOS AR 1, latent AR 99, flow 100, decoder-12 8, and decoder-1 4.

### INT16 FlowLM route

The complete 91-frame observed path recorded:

- 201 QNN provider events
- 0 CPU provider events
- 201 RPC execute events, 5,489,103 µs total
- 201 accelerator execute events, 5,450,016 µs total
- 201 accelerator-cycle events, 4,264,781,696 cycles total
- 201 HVX records, four threads each

Calls were: text 1, encoder 1, voice prefill 1, text prefill 1, BOS AR 1, latent AR 91, flow 91, decoder-12 7, and decoder-1 7.

In both runs, QNN provider-event count exactly matched physical execute-event count. Decoder-6 was not required by either emitted path; it passed the fallback-disabled host gate but was not physically invoked. The technical claim is therefore bounded to the observed 91- and 100-frame paths, not every possible tail shape.

## CPU versus neural boundaries

On the proven paths, CPU handled:

- fixed token IDs and input/WAV parsing
- deterministic noise generation
- tensor and recurrent-state ownership
- EOS scanning and orchestration
- concatenation and PCM16 WAV encoding

The text embedding, reference encoder, both prefills, every AR call, every flow call, and every decoder call that contributed to the WAV ran through QNN HTP.

## Audio validity versus quality

Both QNN WAVs were structurally valid:

| Route | Samples | Duration | Peak PCM16 | RMS PCM16 | SHA-256 |
|---|---:|---:|---:|---:|---|
| FP-source QNN | 192,000 | 8.00 s | 19,599 | 1,326.84 | `467e777879691237472b51f5ccf9a8d43dae337cf63c2344ed3cfb645948c7f3` |
| INT16 FlowLM QNN | 174,720 | 7.28 s | 18,367 | 1,989.90 | `dcdb36df3d8cb8fc8754257fe060d5a4b2deb7c49983d579b8f90c3aa5035820` |

They were 24 kHz mono PCM16, finite, non-silent, and unclipped. Those mechanical checks did not predict intelligibility; Moritz's blind listening rejection is the ultimate quality result.

## Stopped integrated-graph attempt

A final host-only design began to integrate voice/text prefill and 100 exact-length AR/flow steps into one static graph to remove host cache round-trips. The legacy exporter emitted invalid Identity aliasing that ORT rejected; canonicalizing those aliases made a 10-step prototype load. Work stopped before equivalence, QNN gate, or phone use when Moritz rejected the underlying CPU and QNN audio. No claim is based on this unfinished design.

## Safety and recommendation

Every phone run used the actual nonblocking shared lock, exact serial/model/SoC/ABI checks, Windows ADB with `ADB_LIBUSB=1`, lock-FD closure in ADB children, a unique remote root, evidence pull, and verified cleanup. No personal data was accessed.

**Recommendation: do not deploy any Pocket artifact tested here.** The continuation proves an observed neural path can run entirely through QNN HTP, but neither the QNN derivatives nor the 0012 CPU-derived comparator passed human listening.

Machine-readable continuation evidence: [`results/full-qnn-continuation.json`](results/full-qnn-continuation.json).
