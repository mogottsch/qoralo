# Supertonic provider-prescribed segmented pipeline

**Status: one complete Android chapter produced on each route. Qualified unprompted ASR strongly supports whole-chapter coverage: CPU 2.42% WER, HTP 3.03% WER. Both exact WAVs await Moritz's listening verdict.** This is a new, noncanonical product-reference experiment. It does not replace or reinterpret experiment 0036: that earlier test prohibited segmentation and both its CPU and HTP WAVs were rejected.

## Question

Does the provider's actual long-text recipe produce intelligible, complete speech for the unchanged persisted chapter, on Android CPU and Android HTP? Moritz explicitly authorized segmentation and audio assembly for **this** test.

The private input remains exactly 3,190 UTF-8 bytes / 487 whitespace words, SHA-256 `cbfd5bbef581f0e793b86a568f8d4aa87fe857f413e5c2ea4780b558fc71600b`. No text regeneration, rephrasing, omission, duration forcing, stretching, repair or model substitution is performed.

## Exact upstream authority

Official [`supertone-inc/supertonic-py` v1.3.1](https://github.com/supertone-inc/supertonic-py/tree/908a56486e821e833a80530ff0cae3ad0b046fce), commit `908a56486e821e833a80530ff0cae3ad0b046fce`, is the authority. Its `config.py` explicitly pins Supertonic-3 weights to Hugging Face revision `724fb5abbf5502583fb520898d45929e62f02c0b`, exactly matching the existing official FP32 assets. Six fetched source files are byte-identical to the installed 1.3.1 package; their hashes and URLs are retained in `protocol/inputs.json`. No current-HEAD behavior is assumed.

The actual order is:

1. Validate the original input and its supported characters; the validation does not rewrite the supplied string.
2. Run `utils.chunk_text` on the **raw text**, before normalization. Split paragraphs, then sentences using the pinned abbreviation-aware regex. Group whole sentences toward a 300-code-point target. An individually overlong sentence remains intact; this pinned Python version does **not** invent a comma/word fallback or enforce a hard 300-character cap.
3. Per chunk, run the actual official `UnicodeProcessor`: global NFKD first, then emoji/symbol/decorative handling, expression expansion, punctuation spacing, duplicate quotes, whitespace cleanup, terminal punctuation and language tags. Explicit known language `en` and official M1 voice are used, as in upstream examples. The generic multilingual API default would otherwise be `na`.
4. Run duration prediction, divide the float32 prediction by the provider-default **speed 1.05**, encode text, sample masked Gaussian latent input, run **eight** vector steps, then the vocoder.
5. Append the **full native vocoder output, `nativeL * 3072` samples**, not a crop to `floor(duration * 44100)`. Insert exactly **13,230 zero samples (0.3 seconds)** between adjacent chunks, with no leading or trailing added gap.
6. Keep the four CPU sessions resident and reuse them for all chunks. Export mono 44.1 kHz PCM16; the port's conversion was checked against pinned soundfile 0.13.1.

These details intentionally differ from 0036's five steps, speed 1.0, app normalization and duration-based final sample selection. They are provider recipe changes, not hidden attempts to improve a failing output.

## Frozen chapter and stochastic contract

Official segmentation produces **15 chunks**, raw lengths:

```text
300,204,234,144,179,289,97,203,88,230,215,227,243,220,271
```

The resulting exact native text extents, including tags, are:

```text
309,213,243,153,188,298,106,212,97,239,224,236,252,229,280
```

Every original non-whitespace source character is accounted for **exactly once and in order** before normalization, with private byte-range maps. The differing whitespace at segmentation boundaries is the provider's own behavior. No overlong sentence occurs in this reference. Chunk text, IDs, masks, source maps and audio remain private.

Upstream uses a continuous `np.random.randn(...).astype(np.float32)` stream and specifies no seed. For reproducibility we explicitly seed **NumPy 2.3.5 legacy RandomState/MT19937 with 20260911** and save a sufficiently long one-dimensional Gaussian stream. Each route consumes exactly `144 * its_own_nativeL` consecutive values per chunk, reshapes them to `[1,144,nativeL]`, and applies its own mask. It does not consume artificial static-bucket padding as random draws. Per-chunk stream offsets and initial-array hashes establish actual correspondence. If backend duration differences change nativeL, channel alignment and subsequent offsets may differ; equal seeds alone are not claimed to imply equal inputs.

`protocol/freeze.json` binds all bundle files and the original CPU models. The private bundle manifest SHA-256 is `ea3b4830da25a5d9a01ae5da343296700ae841a019248f3be8364b39243715df`. A mismatch aborts before staging.

## Android route boundaries

**CPU:** official frontend preparation runs on the host with the pinned package, without creating model sessions or invoking neural inference. The Android C++ port runs all four neural stages on CPU using the original dynamic ONNX graphs, with exact native T/L and the original 1,000-entry positional table unchanged. Four sessions are constructed once and reused. ORT 1.27.1, four intra-op threads, one inter-op thread, sequential execution, graph optimizations enabled, ordinary CPU arenas/memory patterns and profiling enabled. Model bytes are unchanged, including native Softplus. Native latent shapes above the original positional bound fail rather than silently extend or crop.

**HTP (Ben):** fifteen exact native-T duration/text pairs plus shared vector T320/L512 and vocoder L512 contexts. Naive latent padding failed source checks. The explicit candidate instead preserves the native boundary at all 28 symmetric vector EDGE pads using four own-nativeL-derived INT32 Gather-index arrays. Original weights and the 1,000-position table remain unchanged; the audited stable Softplus identity is retained. The original strict numerical source gate **failed and remains failed**: this is a structurally validated, explicitly non-bit-exact lowering, not a retroactive pass. Full source controls, observed numerical error bounds and physical-run evidence are in [`htp/README.md`](htp/README.md).

All neural stages execute through fail-closed QNN contexts with CPU fallback disabled. Each route owns its duration, embeddings, latent inference and vocoder; no CPU predictions/features are injected. Only artificial bucket extension is removed to restore full provider-native `nativeL * 3072` output. Vector/vocoder sessions are reused; the current exact-T duration/text pair is retained only until T changes: 32 constructors, at most four resident sessions. This case-specific prepared pack is not a generic app-ready solution. CPU's dynamic reference was neither changed nor delayed.

**Audio availability:** each completed CPU or HTP chunk is atomically published as a valid WAV, not a partial header/payload. The phone controller pulls new completed chunks during inference at approximately one-second polling intervals. The device's first completed/playable boundary and the separately observed host-availability boundary are both measured. Nothing autoplays; no empty listening page is created.

## Measurement, safety and privacy

One initial complete chapter per route; no automatic warm campaign or warm-median claim. Measure session setup/lifecycle, first completed/playable chunk, full generation wall time, each chunk's predicted and actual emitted duration, prescribed gap duration, emitted final WAV/hash, provider evidence, process memory and thermal context. HTP's interleaved exact-T constructor/teardown costs are separated; no apples-to-apples four-session setup claim is made. RTF uses actual emitted duration and explicitly reports whether provider-prescribed gaps are in the denominator. Prepared host frontend/noise generation is outside device inference timing and identified separately. Per-chunk evidence writes and live transfers are disclosed overhead, not hidden.

Phone `R5CW81PR8SY` is scheduled by Pi **behind Janek's app work**. `artifacts/locks/phone.lock` covers live checks, staging, execution, pulls and cleanup. No app installation/data changes or unrelated process termination. Initial available memory must be at least 3 GiB and battery temperature below 42°C. CPU bounds: 5 GiB address space, 4 GiB sampled RSS ceiling, 600 MiB available-memory emergency floor, 45°C battery ceiling, 1,800-second native alarm. HTP uses a stricter 3.5 GiB initial available-memory floor and 3 GiB own-RSS ceiling, with the same 5 GiB address-space, 600 MiB emergency floor, 45°C ceiling and 1,800-second native alarm. Read-only live APK and double DB/WAL snapshots verify app preservation; idle main/Room presence is not mistaken for generation. Every attempt is retained privately, including failures.

Raw chapter/chunks, tensors, WAVs, profiles, ASR transcripts and content-bearing logs remain in ignored `.local/`. Public files contain source and non-sensitive metadata/hashes only. The existing offline Whisper-small control (0% word error on the canonical CPU sample) supports a single unprompted coverage check on each exact new full WAV. Only Moritz can accept or reject audio; initial status is `not_reviewed`.

## First Android CPU result

The single scheduled run completed all **165 own CPU neural calls**: 15 duration, 15 text, 120 vector (eight per chunk), and 15 vocoder. All four ORT profiles contain only `CPUExecutionProvider` events, and the four sessions were kept resident and reused. No separate duration calibration, host neural substitution or second chapter render was performed.

| Measurement | First CPU provider-pipeline chapter |
| --- | ---: |
| Completed provider segments | 15 |
| Emitted native speech | 205.844898 s |
| Prescribed gaps | 14 × 0.3 s = 4.2 s |
| Final actual audio | **210.044898 s** |
| Four-session setup | 0.813180 s |
| First complete chunk playable on device, from process entry | **10.041025 s** |
| First complete chunk playable, from sessions ready | 9.197313 s |
| First completed chunk observed on host, from command launch | **10.855411 s** |
| Whole generation through final WAV close | **112.709261 s** |
| RTF including prescribed gaps | **0.536596** |
| Peak process RSS | **780,264 KiB** (about 762 MiB) |
| Battery temperature before → after | 27.7 → 30.6°C |

All 15 completed chunk files were pulled while the controller was active, and their hashes match the chunks used in the final output. Each emitted segment is its full native `L * 3072` extent. The final PCM payload was verified byte-for-byte as those exact chunk payloads plus the fourteen prescribed zero gaps. The native vocoder-grid rounding contributes about 0.358 seconds beyond the sum of predicted speech durations; no duration-based crop was applied.

The exact final PCM16 mono 44.1 kHz WAV is private:

```text
.local/cpu/20260911T140048Z-full/phone/output/chapter.wav
SHA-256 6848fcd649f11ca0b5d2ecdeb237fb3337690ead18ceb2939ba54c9e72e9a0be
```

One unprompted offline Whisper-small decode recovered **493 words against 495 normalized reference words**: 10 substitutions, two deletions, no insertions, **2.4242% WER**, and 483 exact aligned matches. Every reference decile has 46–50 exact matches; 29 of the final 30 words matched. This strongly supports full-chapter coverage, but does not prove every word was spoken correctly or grant human listening acceptance. **Moritz's verdict remains `not_reviewed`.** Raw transcripts stay private.

The same chapter's 0036 single-pass CPU output was only 29.57 seconds with 89.09% WER and was rejected by Moritz. The new result follows the complete prescribed recipe: segmentation, normalization order, eight steps, speed 1.05 and native-wave assembly all changed together. This is not a single-factor causal experiment proving segmentation alone fixed the old failure.

Phone lock and host ASR lock were released. The uniquely named phone directory was removed; app/data were untouched. First-run/profile/transport qualifications above remain applicable; no warm median or accepted-quality throughput claim is made.

## Completed HTP result and first-route comparison

The one HTP run completed all 15 provider chunks, with **165 reported neural Run calls** across 32 fail-closed QNN contexts. Owned-PID/time-filtered logs corroborate CDSP loading, the v73 QNN skeleton, domain-3 user PD and DSP queue creation, followed by closed remote handles. Profiling stayed OFF; hardware cycle/HVX counters and independent per-node device profiler counts are unavailable, not invented. Nonfatal driver lookup/control/teardown diagnostics are preserved.

| Measurement | Native CPU | HTP candidate |
| --- | ---: | ---: |
| Completed provider chunks | 15 | 15 |
| Actual final audio, including 4.2 s prescribed gaps | 210.044898 s | 210.184218 s |
| Session constructors / maximum resident | 4 / 4 | 32 / 4 |
| Constructor setup | 0.813180 s upfront | 1.055379 s total: shared + interleaved |
| Interleaved HTP pair teardown | — | 0.096857 s |
| First complete/playable chunk on device, from entry | 10.041025 s | **6.457313 s** |
| First completed chunk on host, from launch | 10.855411 s | **6.949330 s** |
| Generation wall, including any interleaved setup | 112.709261 s | **87.778723 s** |
| Matched process-entry → final WAV-close wall | 113.552973 s | **88.364559 s** |
| RTF with prescribed gaps and interleaved setup | 0.536596 | **0.417628** |
| HTP RTF excluding interleaved constructor/teardown | — | 0.414806 |
| Own-process `ru_maxrss` (not total DSP/device memory) | 780,264 KiB | 173,864 KiB |
| Unprompted ASR WER | **2.4242%** | **3.0303%** |
| Exact aligned reference words / 495 | 483 | 480 |
| Last 30 reference words matched | 29 | 29 |
| Exact-WAV human listening verdict | `not_reviewed` | `not_reviewed` |

The preferred comparison is the matched **process-entry → final WAV-close** boundary: CPU **113.552973394 s** / HTP **88.364558664 s** = **1.285× configuration-level wall ratio**. It includes upfront and interleaved setup through the same output boundary, not post-output teardown. The earlier 1.284× generation ratio is retained only as a historical diagnostic: its CPU interval excludes upfront setup while its HTP interval includes interleaved setup. Neither is a controlled pure-provider speedup: CPU profiling is ON, HTP profiling is OFF; tensor geometry, precision/lowering, session lifecycle and later active noise differ. These are first runs, not warm medians or accepted-quality throughput. HTP's 32-case specialization/export/support checks, build and staging are outside device timing; host QNN constructors alone totaled 40.30 seconds. The reported Linux RSS/PSS does not capture all DSP/DMA/global allocations and cannot establish a total-memory improvement.

HTP's complete native waveform for the first chunk was available at 6.441463 seconds from entry, followed by a closed playable chunk file at 6.457313 seconds. Fourteen chunk files were pulled before the final chapter file existed; all 15 delivered hashes match the final assembly. No playback is implied. The final PCM payload is byte-exactly the 15 full native chunk payloads plus the 14 prescribed zero gaps.

The exact HTP PCM16 mono 44.1 kHz WAV remains private:

```text
htp/.local/phone-provider-full-01/evidence/run/chapter.wav
SHA-256 0ddfc170d5fca1a11018d68fea6a403175d422ca5b454f1cc9a6bbcddc287209
```

One qualified unprompted Whisper-small decode recovered **493 words against 495 normalized reference words**: 13 substitutions, two deletions, no insertions, and **480 exact matches**. Every decile has 46–50 matches; 29 of the final 30 words matched. The same model/runtime/settings and canonical 0-WER control were verified. There was no second decode, source prompt, repair or additional TTS run. Strong automatic coverage is not Moritz's listening acceptance.

Own HTP nativeL differs from CPU at zero-based chunk **006 (96 versus 95)** and **014 (250 versus 249)**. Only chunks **000–005** have equal complete active-noise hashes. The shared stream offset diverges after 006; equal seeds are not a blanket matched-noise claim. Every HTP duration, consumed native-layout noise slice and boundary-index array was independently checked against its own recorded values.

Battery temperature was 28.3°C before staging and 28.8°C at the last native sample. The memory/thermal guard did not fire. The phone directory was removed, phone and ASR locks released, and live installed APK plus all captured DB/WAL/SHM file hashes were unchanged. The one granted phone slot is consumed; no retry or listening-approval wait holds the phone.

Current aggregate evidence is [`htp/results/comparison-01.json`](htp/results/comparison-01.json); the original CPU evidence remains frozen. Neither positive new result reinterprets the rejected 0036 configuration or isolates one recipe change as the cause.

## Source and checks

- `common/prepare_inputs.py`: executes pinned official segmentation/frontend, preserves source-order evidence, prepares shared stochastic stream.
- `protocol/inputs.json`, `protocol/freeze.json`: exact shared recipe, chunk identities and immutable bindings.
- `cpu/runner.cc`: complete dynamic Android CPU pipeline and promptly available chunk WAVs.
- `cpu/build.sh`, `cpu/run_phone.py`: pinned original models, native build, phone safety/transport/controller.
- `cpu/test_protocol.py`: synthetic/protocol and retained-result checks, including chunk ordering, overlong sentences, continuous Gaussian correspondence, latent arithmetic and PCM16 conversion. No neural inference in these tests.
- `cpu/summarize.py`, `cpu/results/first-chapter-01.json`: phase/timing/provider/memory/thermal/stochastic/WAV evidence, exact assembly checks and all 15 chunk results.
- `cpu/results/asr-first-chapter-01.json`: unprompted automatic coverage evidence; no transcript text.
- `protocol/assets.json`: verified official config/indexer/voice source identities and runtime constants; frozen inputs are unchanged.
- `htp/README.md`: boundary lowering, preserved strict-gate failure, numerical qualification, case-specific setup and physical execution details.
- `htp/results/first-chapter-01.json`, `asr-first-chapter-01.json`, `physical-evidence-01.json`, `comparison-01.json`: exact HTP run and additive coverage/provider/comparison metadata; no content-bearing transcripts or WAVs.

Build: `bash experiments/0037-supertonic-provider-pipeline/cpu/build.sh`. Tests use the already-installed experiment 0007 Supertonic 1.3.1 environment:

```bash
experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/venv/bin/python \
  -m unittest discover -s experiments/0037-supertonic-provider-pipeline/cpu -p 'test*.py' -v
```
