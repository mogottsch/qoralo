# Pocket ONNX → QNN HTP results

## Bottom line

The poor output was not primarily an HTP problem. **Experiment 0012 accidentally tried to clone Bria with a no-voice-cloning checkpoint whose entire Mimi encoder was zero.** Its source/ONNX comparisons faithfully validated that broken contract.

The 2026-08-20 recovery replaced invalid audio cloning with the official pinned fixed Alba state. Moritz then independently accepted the source, controlled ONNX, QNN-compatible host, Android CPU, and physical fallback-disabled QNN/HTP samples as good for the exact frozen prompt.

The accepted physical sample is SHA-256 `2c3901ec39a53596759c1d95381a1d67e4f9ca8886cdf39ac03721863c63eb56`. It emitted 56 frames with EOS at step 53 and had 122 QNN / 0 CPU provider events with exactly 122 matching physical RPC, accelerator, cycle, and HVX records.

This is a **quality-accepted observed fixed-Alba route**, not a general voice-cloning or production claim.

## Canonical-v2 first and warm benchmark

The repository-wide canonical-v2 transcript is 226 bytes with no newline, SHA-256 `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`. Pocket produces 64 tokenizer IDs. This required a new derivative rather than relabeling the accepted text26/cache256 route:

- fixed Alba positions: 126;
- text positions: 64;
- official frame cap: 292;
- required context: 482 positions;
- new capacity: 512, with 30 spare positions;
- BOS absolute position: 190.

The new text64 conditioner, text-prefill64/cache512, BOS/cache512, and latent-AR/cache512 graph hashes are recorded in [`results/canonical-v2-benchmark.json`](results/canonical-v2-benchmark.json). The original text26/cache256 files and verdicts remain unchanged.

### Host gates

Original-dynamic one-shot and cache512 host outputs both had EOS step 160, 163 frames, 312,960 samples, and 13.04 seconds audio. They had correlation `0.999997685`, SNR `53.344 dB`, and were both explicitly accepted by Moritz as “good”:

- original dynamic SHA-256 `916b3cf69dcacb423954526fa342e75770eca8644cdc01a210fca812065e4436`;
- text64/cache512 SHA-256 `29a5c94ada79fd04674544881c38f80188162cf89f3686e0caecd3817df4a295`.

Fallback-disabled host QNN assignment and one host execution passed for every required session as one QNN partition: text 1/1, prefill 306/306, BOS 327/327, latent AR 341/341, flow 167/167, and decoder-12/6/1 264/264 source nodes each.

### Persistent Android performance

Sessions were created once. Each route then ran one unprofiled first complete generation and five additional warm generations. Before every iteration, the runner rebuilt the FlowLM cache from the immutable Alba fixture, recreated all decoder state, replayed the deterministic noise fixture from row zero, reran the text conditioner from the same 64 IDs, and cleared EOS/current-latent/audio buffers.

| Measurement | Android CPU | Fallback-disabled QNN/HTP |
|---|---:|---:|
| Setup | 2.597 s | 62.233 s |
| First generation | 5.37667 s | 2.49081 s |
| First RTF | 0.412321 | 0.191013 |
| Warm latencies | 5.38086, 5.30347, 5.40161, 5.43163, 5.46986 s | 2.37007, 2.32942, 2.33791, 2.37913, 2.36863 s |
| Warm RTFs | 0.412642, 0.406708, 0.414234, 0.416536, 0.419467 | 0.181754, 0.178637, 0.179288, 0.182449, 0.181643 |
| **Warm median latency** | **5.40161 s** | **2.36863 s** |
| **Warm median RTF** | **0.414234** | **0.181643** |
| VmHWM | 1,412,276 kB | 2,405,820 kB |

Every one of the twelve benchmark WAVs had EOS step 160, 163 frames, and 13.04 seconds audio. All six outputs within each route were byte-identical, finite, non-silent, unclipped 24 kHz mono PCM16:

- CPU SHA-256 `2e9021b972d69e05e5cd301973e2dc17cb8143f2a029bc027ef619a3460c34bd` — Moritz: **“good”**;
- QNN/HTP SHA-256 `601cd622dd0598c23dd7275074763aa37ae79b18a9d777ad946b1eaebd2c58e5` — independently accepted: **“good”**.

RTF uses each iteration's actual 13.04-second output. VmHWM is cumulative process-lifecycle high-water, not isolated model memory.

### Separate physical proof

The profiled canonical QNN run produced the byte-identical accepted HTP WAV but is kept separate from unprofiled performance:

- setup `60.1781 s`;
- profiled generation `7.48091 s`, RTF `0.57369`;
- VmHWM `2,520,060 kB`;
- 344 QNN provider events and **0 CPU provider events**;
- 344 RPC events, `4,607,489 µs`;
- 344 accelerator events, `4,543,215 µs`;
- 344 cycle records, `4,652,893,276` cycles;
- 344 HVX records, thread sum 1,376.

Observed calls were text 1, prefill 1, BOS AR 1, latent AR 163, flow 163, decoder-12 13, decoder-6 1, and decoder-1 1. Every QNN event had one matching physical record. Thermal status remained 0. For the unprofiled benchmark AP temperature was 41.2→53.6 °C and skin 37.1→39.3 °C; for the proof AP was 42.1→48.4 °C and skin 38.1→39.1 °C.

## Root cause: the invalid voice contract

Frozen checkpoint:

```text
repository: kyutai/pocket-tts-without-voice-cloning
revision:   d29db7978e464fb90cb3359ee0c69a273b9142cc
SHA-256:   be9c6b4876d3f30740a8225dfcaa2e43dc4aeb753c15272735bee16bbb4abb0a
```

The fail-closed audit found:

- all 42 `mimi.encoder.*` and `mimi.encoder_transformer.*` tensors are exactly zero;
- 9,224,736/9,224,736 encoder elements are zero;
- every tensor name, shape, dtype, byte count, and raw-tensor SHA-256 is recorded;
- exact official source and controlled ONNX both return the same all-zero `[1,125,1024]` voice embedding for Bria, zero audio, one-valued audio, and seeded random audio;
- controlled encoder graph SHA-256 `a01b6a65…2f3e` is therefore input-invariant.

The official runtime normally sets `has_voice_cloning=false` when its gated `weights_path` fails and it falls back to `weights_path_without_voice_cloning` (`tts_model.py:200-209`). It then rejects an audio path at `tts_model.py:874-875`.

Experiment 0012's local YAML assigned the same ungated no-voice-cloning file to both fields. `weights_path` succeeded, the fallback branch never ran, `has_voice_cloning` incorrectly stayed true for that local harness, and Bria reached the zero encoder.

**Correct interpretation:** 0012 exercised an invalid audio-cloning route. Numerical equivalence validated the broken route, not speech quality. Experiment 0012 is preserved unchanged; full evidence is in [`results/zero-voice-encoder-root-cause.json`](results/zero-voice-encoder-root-cause.json).

## Quality-recovery listening ladder

All verdicts below are Moritz's explicit sample-bound judgments from 2026-08-20.

| Stage | Route | Temperature | SHA-256 | Verdict |
|---|---|---:|---|---|
| Official source control | invalid Bria + zero encoder | 0.3 | `89630617…db01` | **Rejected:** “complete bullshit” |
| Official source control | invalid Bria + zero encoder | 0.7 | `6ee4015c…b459` | **Rejected:** “complete bullshit” |
| Official source baseline | pinned fixed Alba state | 0.3 | `cbea7c3d…04c1` | **Accepted:** “good” |
| Official source baseline | pinned fixed Alba state | 0.7 | `3a802d9b…bb6f` | **Accepted:** “good” |
| Controlled FP ONNX host | fixed Alba | 0.3 | `e77dd7d6…ad5d` | **Accepted:** “sounded very good and the same” |
| Controlled FP ONNX host | fixed Alba | 0.7 | `9398db86…30ba` | **Accepted:** same observation |
| QNN-compatible derivative, host CPU | fixed Alba | 0.3 | `1a7f85e4…3eab` | **Accepted:** “good” |
| QNN-compatible derivative, host CPU | fixed Alba | 0.7 | `090c5932…bc9c` | **Accepted:** “good” |
| Original dynamic ONNX, Android CPU | fixed Alba | 0.3 | `cdf77f6e…c4b6` | **Rejected:** perceptually deranged; exact quote retained in JSON |
| Fixed-cache derivative, Android CPU | fixed Alba | 0.3 | `e0638f35…1c9a` | **Accepted:** “sounds good” |
| Fixed-cache derivative, fallback-disabled QNN/HTP | fixed Alba | 0.3 | `2c3901ec…eb56` | **Accepted:** “sounds good” |

The physical QNN result was accepted independently despite only `0.299` waveform correlation with the CPU derivative. This directly demonstrates why correlation is descriptive rather than a quality gate.

Full listening record: [`results/quality-recovery-listening.json`](results/quality-recovery-listening.json).

## Valid fixed-Alba host equivalence

The pinned Alba state bypasses the unavailable audio encoder and directly supplies six official FlowLM cache tensors at offset 126.

Source versus controlled ONNX checks showed:

- exact 26 tokenizer IDs;
- exact text-conditioner output;
- exact initial Alba caches and offsets;
- text-prefill cache maximum absolute difference `3.5644e-5`;
- shared-noise free-running source and ONNX trajectories crossed EOS at the same step 53;
- at temperature zero, both emitted 111,360 samples with correlation `0.999999928`, SNR `68.417 dB`, and maximum absolute float difference `0.000809`.

At positive temperature, free-running numerical differences grew autoregressively, as expected, but human listening accepted both 0.3 and 0.7. Temperature 0.3 is canonical because the official English configuration recommends it and no perceptual advantage was heard at 0.7.

## Secondary Android failure and static recovery

The original dynamic ONNX graph was still not platform-faithful on Android, even with the valid Alba state and the exact precomputed NumPy noise fixture:

- host: EOS 53, 56 frames, 4.48 s;
- Android: no EOS by the 134-frame cap, 10.72 s;
- host first AR EOS logit: `-9.8847`;
- Android first AR EOS logit: `-10.2709`.

That first-logit difference occurs before the first sampled latent, after identical token IDs and Alba cache inputs. It localizes the secondary failure to the original Android dynamic FlowLM prefill/AR execution, not tokenizer, RNG, flow integration, or Mimi decode. Moritz separately rejected the resulting Android sample even though its RTF was `0.526`.

Directly initializing the QNN-compatible fixed cache from Alba removed the dynamic recurrent path. The 256-slot contract retains all `126 voice + 26 text + 100 generated = 252` positions without rolling away voice context.

The recovered Android CPU derivative:

- setup `2.603 s`;
- generation `1.846 s` for 4.48 s audio;
- RTF `0.412`;
- EOS 53 / 56 frames;
- VmHWM `1,294,420 kB`;
- correlation `0.9999904` and SNR `47.15 dB` versus the accepted host derivative;
- WAV SHA-256 `e0638f35…1c9a`;
- independently accepted as “sounds good.”

### Later source-audit correction: borrowed BOS input

The retained original CPU runner has a concrete input-lifetime defect. In
[`pocket_alba_cpu_runner.cc`](tools/pocket_alba_cpu_runner.cc), `TV()` wraps a
vector's data using ORT's non-owning user-buffer tensor API. The first-step
`bos` vector is destroyed at the end of its `if` block, before `Run(main,
inputs)` consumes the tensor outside that block. Its backing pointer is
therefore dangling. Source SHA-256:
`a2c833b2ac8fc85f676b1aff8203cc1ada452be87699a65543033136897c45cd`.

A bounded host reproducer using the real ORT tensor API reports
`heap-use-after-free` under AddressSanitizer; keeping the vector alive through
consumption passes. It creates no session, loads no model and runs no inference.
See the [source audit and reproduction procedure](evidence/source-audit.md).

This qualifies the runtime-localization interpretation above: matching fixture
files do not establish valid, identical inputs when a tensor can point at freed
storage. **The first-logit difference does not establish an Android/ORT runtime
or operator fault.** The historical executable hash `a11685f5…f57257` has not
been bound to the audited source by this later check, and no lifetime-only model
replay was performed. The exact old WAV's cause is therefore still unproved.
The successful fixed-cache runner avoids this borrowed BOS input, but also
changes the graph and cache layout; its recovery is not a controlled test of
this defect alone. The separate invalid-Bria/zero-encoder finding concerns
other recordings. Original outputs, listening verdicts and raw result records
remain unchanged.

**Subsequent bounded host replay strengthens this explanation.** The graph
selects its learned BOS embedding using
`Where(IsNaN(sequence), flow_lm.bos_emb, sequence)`. In the retained 0024
reconstruction of the dynamic graph (`ce8d8701…b3bff2`, not the missing original
`021288bd…d9a95e`), a valid NaN start input reproduces the recorded host first
logit `-9.8847` and EOS step 53. Replacing only that start input with zeros gives
`-10.2709` to the recorded precision and closely tracks all 134 retained Android
EOS logits: maximum absolute difference `0.0736`, mean `0.00577`, and no EOS
before the cap. The NaN control also agrees with 57 retained fixed-cache CPU
logits to maximum absolute difference `0.0021`. Pi independently reran the
host-only script with ORT 1.22.1 and reproduced these results, without a phone,
model change or audio decode.

This is strong support for a wrong start input, consistent with the confirmed
buffer-lifetime defect, rather than a runtime-only explanation. It is **not an
observation of zeros in the phone's freed buffer**, proof of the old executable's
source binding, or a replay of the exact old graph/WAV. The prefix/suffix
partial-zero scan covers only its stated patterns, not every possible corrupt
input. See the [replay script](evidence/bos-zero-replay.py)
and [saved result](evidence/bos-zero-replay.json) for the
controlled inputs, graph identity and full trajectory comparisons. Exact
historical audio causality remains unverified, but the source bug now has a
specific, replay-supported failure mechanism.

**Subsequent phone check directly observes the input and tests a lifetime-only
repair.** One CPU-only window ran four rebuilt variants twice each using the
same reconstructed graph, Alba cache and noise. The diagnostic variant of the
original runner printed all 32 BOS words immediately before `Run()`: all were
zero in both runs. Retaining the vector through consumption instead produced
32 NaN words (`0x7fc00000`) in both diagnostic runs. These observations belong
to the instrumented builds; printing can itself perturb allocation.

The rebuilt, unmodified original reproduced the historical rejected WAV
**byte-for-byte** in its first run (`cdf77f6e…f5c4b6`), as did both diagnostic
runs: first logit `-10.2709`, no EOS and 134 frames / 10.72 s. Its second run
produced a different wrong WAV (`d4297712…ada44`) and first logit `-4.37185`,
still without EOS. Its input contents were not dumped. In contrast, the
lifetime-only repaired runner, with and without diagnostics, produced the same
WAV (`465ac270…d7c72`) in all four runs, with first logit `-9.8847`, EOS step 53
and 56 frames / 4.48 s. Pi independently checked the eight raw results, input
dumps and WAV hashes. There is no new listening verdict for the repaired WAV.

This establishes a reproducible input-lifetime failure and successful
lifetime-only repair in the rebuilt phone test, including reproduction of the
exact old rejected audio. It does not recover the missing historical executable,
make the reconstructed graph identical to the old export, observe the
unmodified second run's buffer, or establish why this allocator yielded zeros.
The earlier runtime-only interpretation must not be used to blame Android/ORT.

The window's controller initially reported **cleanup incomplete** because its
termination scan timed out; that failed cleanup receipt remains. A subsequent
lock-held manual cleanup verified all eight owned PID/start identities absent,
no process with the stage as its working directory, and explicit stage absence
on the reachable phone. The separately recorded preflight/parser corrections
and reduction of the memory gate from 3 to 1.5 GiB are protocol changes, not a
claim that the original 3 GiB admission passed. See the
[phone evidence packet](evidence/phone-bos-check/) for
source/configuration identities, all planned runs and both cleanup receipts.

## Accepted physical QNN/HTP path

The observed fixed-Alba path invoked:

| Neural session | QNN calls |
|---|---:|
| Text conditioner | 1 |
| Text prefill | 1 |
| BOS AR | 1 |
| Latent AR, including the final stop check | 56 |
| Flow step | 56 |
| Decoder-12 | 4 |
| Decoder-6 | 1 |
| Decoder-1 | 2 |
| **Total** | **122** |

CPU fallback was disabled. The ORT and physical profiles recorded:

| Evidence | Events | Aggregate |
|---|---:|---:|
| `QNNExecutionProvider` | 122 | — |
| `CPUExecutionProvider` | **0** | — |
| RPC execute | 122 | 1,481,483 µs |
| QNN accelerator execute | 122 | 1,458,206 µs |
| Accelerator cycles | 122 | 1,230,903,724 cycles |
| HVX | 122 | 488 threads summed, four per call |

Every invoked neural session—including decoder-12, decoder-6, and decoder-1—has physical proof. The old decoder-6 limitation does not apply to this recovered 56-frame path.

### Timing and memory

| Measurement | Profiled physical proof | Separate unprofiled run |
|---|---:|---:|
| Setup/session creation | 58.198 s | 66.695 s |
| Complete generation | 2.352 s | 0.740 s |
| Audio | 4.48 s | 4.48 s |
| RTF | **0.525** | **0.165** |
| VmHWM | 2,447,980 kB | 2,241,184 kB |
| WAV SHA-256 | `2c3901ec…eb56` | same, byte-identical |

The unprofiled value is **one first complete generation after session setup**, not a warm median or warm distribution. The profiled result includes detailed ORT/QNN instrumentation and remains the physical-proof timing. Batch decoding exposes no honest streaming first-audio boundary.

VmHWM is cumulative process high-water including eight sessions, model mappings, QNN contexts, caches, buffers, profiles where enabled, and output. It is not isolated tensor or weight memory.

Thermal status remained `0` before and after the profiled run. AP temperature was 39.7→48.3 °C, skin 37.2→38.9 °C, and battery 35.0→35.4 °C. The USB-powered battery remained at 47%. These are observed system readings, not laboratory thermal control.

### CPU versus neural boundary

CPU handled:

- fixed token IDs;
- loading and packing the official fixed Alba state;
- deterministic NumPy seed-0 noise fixtures;
- recurrent tensor ownership and call orchestration;
- EOS scanning;
- concatenation and PCM16 WAV encoding.

QNN HTP handled every invoked neural call: text conditioning, text prefill, BOS and latent autoregression, flow, and all decoder variants. “FP source” describes graph tensor types; this QNN toolchain executes the unquantized neural graphs as FP16, not FP32.

## Distinct 0008 archive reconciliation

The exact pinned 0008 sherpa INT8 archive is not the broken controlled 0012 encoder route:

- archive SHA-256 `2f3b8882…67cb`;
- encoder SHA-256 `e8f2f6d3…0260`, distinct from controlled zero encoder `a01b6a65…2f3e`;
- all 13,312 tested output values were nonzero;
- outputs differed for Bria, zero, one-valued, and seeded random inputs.

Its encoder is therefore genuinely input-sensitive. It also has an important limitation: the traced output remained `[1,13,1024]` for tested lengths, and the Bria result was byte-identical for 2 seconds versus 10 seconds, so later reference audio is ignored.

Historical 0008 performed structural validation only. New exact-asset host samples at temperatures 0.3 and 0.7 were both explicitly accepted as “good” on 2026-08-20. This establishes those new route/sample results, not a retroactive verdict for missing historical WAVs. The archive's conflicting license statements remain research-only.

## Historical 2026-08-19 blind listening verdict

> The following sections preserve the earlier invalid-Bria continuation exactly as technical history. They do not override the 2026-08-20 root cause or recovered fixed-Alba result above.

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

The historical Bria-conditioned routes remain rejected and must not be deployed. The recovered fixed-Alba route is a credible bounded prototype with independent host, Android CPU, and QNN/HTP acceptance. It is still not a general production recommendation: broader text evaluation, fixed-voice product fit, licensing review, and a real performance distribution remain necessary.

Machine-readable evidence:

- recovered result: [`results/alba-quality-recovery.json`](results/alba-quality-recovery.json)
- root cause: [`results/zero-voice-encoder-root-cause.json`](results/zero-voice-encoder-root-cause.json)
- full listening ladder: [`results/quality-recovery-listening.json`](results/quality-recovery-listening.json)
- historical continuation: [`results/full-qnn-continuation.json`](results/full-qnn-continuation.json)
