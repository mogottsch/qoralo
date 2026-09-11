# Whole-chapter Supertonic: Android CPU vs Android HTP

Status: **Android CPU duration calibration complete; full CPU and HTP renders pending.** This is a **noncanonical product-reference comparison**, not the canonical 226-byte TTS campaign. No warm-median or registry claim is intended. This experiment preserves earlier Supertonic experiments and does not change the installed podcast app or its limits.

## Question and fixed input

Can each complete Android route speak the entire longest persisted reference chapter, without splitting text or audio, stitching, stretching, forced duration, repair, or hidden neural fallback?

The unchanged private reference is 3,190 UTF-8 bytes, SHA-256 `cbfd5bbef581f0e793b86a568f8d4aa87fe857f413e5c2ea4780b558fc71600b`. The pinned app frontend produces 3,158 normalized code points plus nine language-tag positions: **3,167 active positions**. Both routes use text extent **T3200**, with zero IDs and zero mask at the remaining 33 positions. The input is not regenerated or shortened. Normalization is the existing product frontend, not content rewriting.

Shared settings: official Supertonic-3 FP32 weights, M1 voice (product identity `M1/SID5`), speed 1.0, five vector steps, 44,100 Hz mono output. `common/prepare_inputs.py` reproduces the pinned Kotlin normalization and creates private token/style/mask tensors. The saved timestep schedule is five float32 values `[0,1,2,3,4]`, with total step `[5]`.

## Route and extent contract

CPU owns duration prediction, text encoding, five vector-estimator calls, and one whole vocoder call. HTP must likewise execute its own four neural stages, fail closed against CPU fallback. CPU duration/embeddings/latents are not inputs to the HTP route.

The separately labelled Android CPU duration calibration returned **29.56986237 seconds**, 1,304,030 natural frames and 425 active latent positions. Both owners agreed on **L512**, with 87 positions (20.5%) of latent-capacity margin. The full CPU render repeats its own duration prediction. This unexpectedly short duration for a 487-word chapter is a substantial coverage concern, not something to correct by forcing a longer output. Each route computes natural frames as `floor(FP32(duration * 44100))`, active latent positions as `ceil(frames / 3072)`, and writes precisely that natural number of frames. This is the model's ordinary final sample selection, not a target-duration crop. A route exceeding the common latent capacity fails rather than silently truncating.

The original vector graph has a nonlearned INT64 arange position table with only 1,000 entries. Its derivative extends this table to at least `max(T,L)`, preserving the exact original prefix, theta, all learned tensors, and position normalization. The stable Softplus identity already audited in earlier experiments is shared. CPU uses source-graph shape derivatives; HTP may require documented exact operator lowering. Structural checks do not establish long-sequence speech quality.

Once L is set, both routes read identical saved **unmasked float32 noise bytes on `[1,144,L]`**. Each applies its own duration-derived latent mask. The saved bytes, not a nominal matching seed, define stochastic matching. This comparison uses seed 20260813 to prepare those bytes; it does not claim to reproduce the app's chapter-ID-dependent random stream.

## Execution and evidence boundaries

One full render per route first. Same phone `R5CW81PR8SY` (SM-S918B / SM8550), sequentially scheduled by Pi and guarded for the complete stage/run/pull/cleanup interval by `artifacts/locks/phone.lock`.

The CPU runner uses ORT 1.27.1, CPU EP only, four intra-op threads, one inter-op thread, sequential execution, and profiling. No non-CPU EP is appended. Sessions are created and destroyed **one stage at a time** to reduce memory; setup is reported separately per stage and summed. Render time is reported as stage-run sum, with pipeline wall time also retained. This is not an all-sessions-resident startup measurement. CPU arenas and memory patterns are disabled to reduce retained temporary allocations.

Enforced CPU limits: 5 GiB process address-space bound; 180-second duration-calibration or 1,800-second full-render alarm; host monitoring aborts on RSS above 4 GiB, available phone memory below 600 MiB, or battery temperature at/above 45°C. Initial headroom checks require at least 2 GiB available for calibration or 3 GiB for the full render, temperature below 42°C, and no known live benchmark command. The initial calibration ran before these explicit headroom assertions were added, but its retained preflight records 3,647,100 KiB available and 27.9°C, comfortably within them. These are safety bounds, not predicted performance. Only the uniquely named standalone runner is terminated on a bound failure. Installed app/data are preserved.

All reference text, normalized text, tensor bundles, waveforms, ASR transcripts, profiles, and potentially content-bearing logs remain under ignored `.local/`. Public artifacts contain source and non-sensitive metadata/hashes only. Exact WAV validity and local ASR can support coverage evaluation; **only Moritz grants listening acceptance**, initially `not_reviewed`. No autoplay or empty listening page is created.

## Files

- `common/prepare_inputs.py`: private frontend, voice, schedule, and shared noise bundle.
- `common/prepare_graphs.py`: pinned source-shape and position-extent derivatives with weight checks.
- `cpu/runner.cc`: bounded standalone complete Android CPU runner and duration calibration mode.
- `cpu/build.sh`, `cpu/run_phone.py`: build and phone-lock-aware execution.
- `cpu/test_common.py`: public synthetic frontend/stochastic-layout/runner-contract tests.
- `htp/`: Ben's separately owned implementation and evidence.
- `protocol/contract.json`: frozen T3200/L512 model, input, schedule and noise metadata/hashes.
- `cpu/results/duration-calibration-01.json`: separate Android CPU calibration evidence; 186 CPU-only profile kernel events.
- `common/asr_coverage.py`: offline unprompted Whisper-small analysis, CPU-only and bounded. The existing canonical CPU control WAV produced 0% word error over 36 normalized words; this qualifies the local analysis setup, not chapter coverage or listening acceptance.
- `cpu/results/asr-control-01.json`: control metadata; raw ASR output stays private.
