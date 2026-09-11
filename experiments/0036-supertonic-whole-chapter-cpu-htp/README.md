# Whole-chapter Supertonic: Android CPU vs Android HTP

Status: **Real full Android CPU and HTP WAVs produced; both automatic whole-chapter coverage checks failed. Moritz rejected the exact CPU WAV as unusable audio. The HTP WAV has not been human-reviewed.** This is a **noncanonical product-reference comparison**, not the canonical 226-byte TTS campaign. No warm-median or registry claim is intended. This experiment preserves earlier Supertonic experiments and does not change the installed podcast app or its limits.

## Question and fixed input

Can each complete Android route speak the entire longest persisted reference chapter, without splitting text or audio, stitching, stretching, forced duration, repair, or hidden neural fallback?

The unchanged private reference is 3,190 UTF-8 bytes, SHA-256 `cbfd5bbef581f0e793b86a568f8d4aa87fe857f413e5c2ea4780b558fc71600b`. The pinned app frontend produces 3,158 normalized code points plus nine language-tag positions: **3,167 active positions**. Both routes use text extent **T3200**, with zero IDs and zero mask at the remaining 33 positions. The input is not regenerated or shortened. Normalization is the existing product frontend, not content rewriting.

Shared settings: official Supertonic-3 FP32 weights, M1 voice (product identity `M1/SID5`), speed 1.0, five vector steps, 44,100 Hz mono output. `common/prepare_inputs.py` reproduces the pinned Kotlin normalization and creates private token/style/mask tensors. The saved timestep schedule is five float32 values `[0,1,2,3,4]`, with total step `[5]`.

## Route and extent contract

CPU owns duration prediction, text encoding, five vector-estimator calls, and one whole vocoder call. HTP independently executed the same four logical stages, with CPU fallback disabled. Its text stage required three **network-depth** subgraphs, each retaining the whole T3200 sequence and full attention context. CPU duration/embeddings/latents were not inputs to the HTP route.

The separately labelled Android CPU duration calibration returned **29.56986237 seconds**, 1,304,030 natural frames and 425 active latent positions. Both owners agreed on **L512**, with 87 positions (20.5%) of latent-capacity margin. The full CPU render repeats its own duration prediction. This unexpectedly short duration for a 487-word chapter is a substantial coverage concern, not something to correct by forcing a longer output. Each route computes natural frames as `floor(FP32(duration * 44100))`, active latent positions as `ceil(frames / 3072)`, and writes precisely that natural number of frames. This is the model's ordinary final sample selection, not a target-duration crop. A route exceeding the common latent capacity fails rather than silently truncating.

The original vector graph has a nonlearned INT64 arange position table with only 1,000 entries. Its derivative extends this table to at least `max(T,L)`, preserving the exact original prefix, theta, all learned tensors, and position normalization. The stable Softplus identity already audited in earlier experiments is shared. CPU uses source-graph shape derivatives; HTP may require documented exact operator lowering. Structural checks do not establish long-sequence speech quality.

Once L is set, both routes read identical saved **unmasked float32 noise bytes on `[1,144,L]`**. Each applies its own duration-derived latent mask. The saved bytes, not a nominal matching seed, define stochastic matching. This comparison uses seed 20260813 to prepare those bytes; it does not claim to reproduce the app's chapter-ID-dependent random stream.

## Execution and evidence boundaries

One full render per route first. Same phone `R5CW81PR8SY` (SM-S918B / SM8550), sequentially scheduled by Pi and guarded for the complete stage/run/pull/cleanup interval by `artifacts/locks/phone.lock`.

The CPU runner uses ORT 1.27.1, CPU EP only, four intra-op threads, one inter-op thread, sequential execution, and profiling. No non-CPU EP is appended. Sessions are created and destroyed **one stage at a time** to reduce memory; setup is reported separately per stage and summed. Render time is reported as stage-run sum, with pipeline wall time also retained. This is not an all-sessions-resident startup measurement. CPU arenas and memory patterns are disabled to reduce retained temporary allocations.

Enforced CPU limits: 5 GiB process address-space bound; 180-second duration-calibration or 1,800-second full-render alarm; host monitoring aborts on RSS above 4 GiB, available phone memory below 600 MiB, or battery temperature at/above 45°C. Initial headroom checks require at least 2 GiB available for calibration or 3 GiB for the full render, temperature below 42°C, and no known live benchmark command. The initial calibration ran before these explicit headroom assertions were added, but its retained preflight records 3,647,100 KiB available and 27.9°C, comfortably within them. These are safety bounds, not predicted performance. Only the uniquely named standalone runner is terminated on a bound failure. Installed app/data are preserved.

All reference text, normalized text, tensor bundles, waveforms, ASR transcripts, profiles, and potentially content-bearing logs remain under ignored `.local/`. Public artifacts contain source and non-sensitive metadata/hashes only. Exact WAV validity and local ASR can support coverage evaluation; **only Moritz grants listening acceptance**, initially `not_reviewed`. No autoplay or empty listening page is created.

## CPU first full result

The complete Android CPU route ran once, with its own duration predictor, text encoder, five vector calls, and one whole vocoder call. All four ORT profiles contain only CPU execution events: 186 duration, 311 text, 3,970 vector (five × 794), and 115 vocoder.

| Measurement | First full CPU run |
| --- | ---: |
| Natural predicted duration | 29.56986237 s |
| Emitted WAV | 1,304,030 frames / 29.56984127 s |
| Setup, summed sequential stage constructors | 0.796162 s |
| Duration / text / five vector / vocoder execution | 0.7581 / 2.6585 / 13.7956 / 1.3101 s |
| Generation wall time excluding session setup | 18.597834 s |
| RTF, that wall time / emitted audio duration | 0.628946 |
| Peak process RSS, Android `getrusage` | 2,102,392 KiB (about 2.01 GiB) |
| Battery temperature before → after | 27.8 → 28.3°C |

This is a **single profiled run**, not a warm median. Sequential constructors, profile finalization, and private evidence writes are disclosed in the timing metadata. The phone lock was held throughout staging/execution/pull/cleanup and released afterwards; the unique remote directory was removed, with no app/data change.

The real PCM16 mono 44.1 kHz WAV is retained privately at:

```text
.local/cpu/20260911T123235Z-full/phone/output/cpu.wav
SHA-256 9b1c8587308fb2a98ef1d600549e8f06beec86c3419684789279a143b17c46d2
```

It is finite, nonempty and unclipped, but that does not establish intelligibility or coverage. The qualified unprompted local ASR produced **103 words against 495 regex-normalized reference words**, with **89.09% word error**, 392 deletions and 49 substitutions. Only three of the final 30 reference words matched. The original raw chapter's 487 whitespace-word count uses a different tokenizer; nothing was removed from the model input.

**Full chapter coverage is not demonstrated and the automatic check fails strongly.** No output repair, duration forcing, second render or ASR retry was performed. Moritz subsequently listened to the exact CPU WAV and **rejected it as unusable audio**. The additive review in `cpu/results/listening-review-20260911.json` records his exact words and WAV hash; original execution/ASR snapshots remain unchanged as historical pre-review evidence. Raw transcripts stay private.

## HTP completed result and matched comparison

The original single text context failed before text execution. Two fresh text-only constructor controls, with no DP context or model inputs and **zero Run calls**, failed at both 5 GiB and 8 GiB Linux address-space limits. Owned-PID native logs exposed RPC allocator `size >= 0` failures for 2,666,528,768-byte and 2,245,001,216-byte requests, both above `INT32_MAX`. These failures and the initial incomplete pipeline are retained; they are not successful full renders.

The successful route splits text encoding by **network depth, not text positions**: prefix + encoder block 0 → blocks 1–2 → block 3 + style conditioning. Every part still processes the whole sequence. All 1,934 original nodes and 146 initializers are preserved byte-for-byte; only nonlearned mask/control work is repeated. An offline CPU source-equivalence check was bitwise exact. Complete hidden-state and residual-skip tensors produced by HTP are copied before closing their contexts; **no CPU validation activation is staged or substituted**. The conservative allocation plan leaves at least 268,435,455 bytes of signed-size margin after extra allowance and rounding.

This lowered route completed **once**, with **10 own QNN calls: duration 1, text parts 3, vector 5, vocoder 1**. ORT 1.27.1/QNN uses the same official FP32 source weights, M1 style, frozen inputs and noise. Source-weight identity and CPU partition equivalence do not claim bitwise equality of CPU and HTP backend arithmetic. Profiling is off, CPU fallback is disabled, and owned-PID logs show the v73 HTP skeleton and cDSP transport. No profiler cycle/HVX/RPC-time values are invented.

| Measurement | Android CPU | Android HTP, depth-partitioned text |
| --- | ---: | ---: |
| Own natural duration prediction | 29.56986237 s | 29.57812691 s |
| Emitted frames | 1,304,030 | 1,304,395 |
| Emitted audio duration | 29.56984127 s | 29.57811791 s |
| Summed interleaved session setup | 0.796162 s | 2.454394 s |
| Generation wall excluding session setup | 18.597834 s | 8.702102 s |
| RTF, generation wall excluding setup | 0.628946 | 0.294207 |
| Complete pipeline wall including setup | 19.393996 s | 11.156496 s |
| Linux process peak RSS | 2,102,392 KiB | 181,740 KiB |
| ASR hypothesis / normalized reference words | 103 / 495 | 122 / 495 |
| ASR word error rate | 89.09% | 88.69% |
| Exact aligned word matches | 54 | 56 |
| Matches in the final 30 reference words | 3 | 2 |

**Timing qualifications:** these are individual first completed runs, not warmed medians. CPU profiling was on and HTP profiling was off. Both interleave session setup, execution and release; HTP has six physical contexts for four logical stages. Its stage-only duration/text/vector/vocoder times are 0.7930 / 2.4219 / 5.0868 / 0.0934 seconds. The reported setup-excluded wall time also includes the remaining host copies, cleanup and evidence writes. **Memory qualifications:** HTP's Linux RSS excludes substantial DSP/shared allocations; this table does not demonstrate device-wide memory savings.

The real HTP PCM16 mono 44.1 kHz WAV is private:

```text
htp/.local/phone-depth-full-attempt-01/evidence/run/htp.wav
SHA-256 3ae276f2d61eae37b05df23c334704e69434700dbd9360f74768c075ad40a69c
```

Both routes independently selected 425 active latent positions. Their saved masked initial noise and latent masks are **byte-identical**, not merely seeded alike. HTP emitted its own naturally predicted frame count; no speed/duration override, external text/audio chunks, stitching, stretch or repair occurred. Its live memory guards did not fire, the unique remote directory was removed, and the phone lock was released. Installed app/data were untouched.

The same qualified offline unprompted Whisper-small protocol was run **once** on the exact HTP WAV. It produced 122 words, with 373 deletions, 66 substitutions and no insertions against the same 495-word normalized reference used for CPU. The first post-decoding alignment used raw punctuation and counted 506 reference words; that private result is retained. The **unchanged saved hypothesis** was then aligned to CPU's frozen normalized reference. This was alignment-only arithmetic, not an ASR retry, decoding prompt, transcript repair or input change.

**Conclusion:** both complete execution paths produced valid WAV files, but neither demonstrates speaking the entire unchanged chapter intelligibly. Qualified ASR strongly argues against whole-chapter coverage on both routes. The roughly 29.57-second natural predictions are retained rather than forced to fit the chapter. Moritz's exact-WAV listening verdict is **`rejected` for CPU**, with **HTP still `not_reviewed`**. Valid PCM is not successful speech generation. No accepted-quality throughput or registry claim follows.

## Files

- `common/prepare_inputs.py`: private frontend, voice, schedule, and shared noise bundle.
- `common/prepare_graphs.py`: pinned source-shape and position-extent derivatives with weight checks.
- `cpu/runner.cc`: bounded standalone complete Android CPU runner and duration calibration mode.
- `cpu/build.sh`, `cpu/run_phone.py`: build and phone-lock-aware execution.
- `cpu/test_common.py`: public synthetic frontend/stochastic-layout/runner-contract tests.
- `htp/`: standalone HTP runner, retained failed allocation diagnostics, full-sequence depth partition and evidence.
- `htp/results/full-depth-render-01.json`: exact completed HTP WAV, 10-call/provider/stochastic/timing/memory/cleanup evidence and failed automatic coverage status.
- `htp/results/asr-depth-full-01.json`: one unprompted HTP decode, matched normalized-reference alignment; no transcript text.
- `htp/results/comparison-01.json`: matched CPU/HTP numeric summary and claim boundaries.
- `htp/results/text-load-controls.json`: preserved 5/8 GiB controls and evidenced RPC signed-size failure path.
- `protocol/contract.json`: frozen T3200/L512 model, input, schedule and noise metadata/hashes.
- `cpu/results/duration-calibration-01.json`: separate Android CPU calibration evidence; 186 CPU-only profile kernel events.
- `common/asr_coverage.py`: offline unprompted Whisper-small analysis, CPU-only and bounded. The existing canonical CPU control WAV produced 0% word error over 36 normalized words; this qualifies the local analysis setup, not chapter coverage or listening acceptance.
- `cpu/results/asr-control-01.json`: control metadata; raw ASR output stays private.
- `cpu/results/full-render-01.json`: complete first CPU execution, WAV identity, phase/provider/memory/thermal evidence and failed automatic coverage status.
- `cpu/results/asr-full-render-01.json`: qualified automatic coverage metrics for that exact WAV; no transcript text.
- `cpu/results/listening-review-20260911.json`: later exact-hash human rejection of the CPU WAV; original pre-review evidence preserved.
