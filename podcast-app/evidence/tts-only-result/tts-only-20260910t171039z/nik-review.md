# Nik — saved TTS-only request review

## Verdict

PASS for one complete canonical engineering request through the four unchanged Supertonic QNN/HTP contexts on the Galaxy S23 Ultra. Actual neural execution is independently established by per-component ORT Node execution and matching typed QNN RPC/accelerator-execute records, not merely session construction or configured provider strings.

No listening verdict, warm median, normal full-chapter feasibility, benchmark campaign, or product E2E approval. No device commands or replay were performed by Nik.

## Exact binding and scope

- Run: `tts-only-20260910t171039z`; saved root: `podcast-app/.local/tts-only-phone/tts-only-20260910t171039z/`.
- Archive SHA256: `aac3e3ae19cd7e3121381ffe53e5ad40c27620da744b24d0c9a615042b110a6a`.
- Candidate: `3cf46e271a515ed30125c09ac6f9891c808218e6871ef39adee7767b0e4c6fed`.
- Observed app APK: `024f5cd58761f5816163b907293e51867a5c0f3962b37c7aa6416c18ad47228d`; observed test APK: `7066cbee3abdeff69dbaa5bd0f1ff6031614061f444237488b407aa44bc3263d`.
- Guard: `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`; TTS controller: `a62d204c380a5b2d0c8f7c5bd94729b6f823e18200feed2ebe24fa73962bec3c`.
- Contract: `5844320c0ce2442e16d2d837fc1239bf8e9da05ede672d1249f125d91fdf57ca`; verified Supertonic manifest: `dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d`.
- Driver PID3410 and generation PID3525. Saved identity is SM-S918B/SM8550, ARM64, Android16/API36. App target SDK remains35.
- Effective source remains frozen3fd plus the reviewed nine-path debug/manifest overlay; unchanged main render and native code. All nine APK native payloads are still byte-identical to the proven manifest-only baseline. This binding uses the observed APK hash and independently compared APK payloads, not a claim of nine freshly captured extracted-device-library hashes.

Actual request and normalized request are identical to the canonical 226-byte/no-newline transcript, SHA256 `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`. Independently reconstructed IDs match the saved pinned-indexer reconstruction: 235 wrapped codepoints, four zero pads, INT64 IDs [1,239], FLOAT32 mask [1,1,239], seed `9402311491680997705`. These are explicitly reconstructed values, not captured native input buffers. ORT execution records independently corroborate the actual tensor types and shapes. M1/SID5, five diffusion steps, speed1.0 and unchanged chapter-seeded xorshift/Box–Muller recipe remain app-specific engineering parameters.

## Actual execution

Each profile has one Session initialization plus the following real Node `_kernel_time`, phase-X events, all attributed to `QNNExecutionProvider`. Every listed QNN execute row is BACKEND/ROOT with positive finite values and the appropriate US or CYCLES unit.

| Component | ORT Node executions | RPC execute microseconds | Accelerator execute cycles |
|---|---:|---|---|
| Duration | 1 | 6,647 | 6,712,518 |
| Text | 1 | 24,003 | 26,119,549 |
| Vector | 5 | 739,367; 539,087; 539,198; 538,285; 522,897 | 770,548,669; 770,266,679; 768,417,416; 768,296,022; 768,931,246 |
| Vocoder | 1 | 241,972 | 222,412,600 |

All observed neural Node events use QNN; no CPU neural Node is present. CPU preprocessing, buffer handling and WAV work remain distinct from neural fallback. The approved source has one logical render and no Gemma, splitting, retry or capacity probe. One instrumentation dispatch and two installs are recorded.

Generation maps show app-owned `libQnnHtp.so`, V73 stub, QNN System, ORT and bridge plus vendor `libcdsprpc.so`. Generation logcat line4825 imports `libOpenCL.so:libcdsprpc.so` into clns-9; line5020 reports FastRPC loaded. Runtime identity remains ORT1.27.1/QAIRT2.49.0.260730. Native stdout/stderr files are empty; the actual ORT/QNN profiles and app-relevant saved logcat supply the execution evidence. Four profile sets are complete, the close stage returns, and saved cleanup confirms process absence.

## WAV and timings

- WAV: `canonical-short.wav`, SHA256 `bcc277bce02cdb3042a853c91172abc6c99c325657cdce4829b2eabfc79c163a`.
- Independently read archive and extracted copies: identical, 1,379,546 bytes, 689,751 frames, 44,100 Hz, mono, PCM16.
- Exact derived audio duration: **15.640612244897959 seconds**.
- Four-context adapter load: **669.641354 ms**. This excludes prior verification/library setup and is not total app startup.
- First profiled render: **6441.159529 ms**, including normalization, native work, WAV validation/publication; excluding verify/load/close.
- Independently recomputed first profiled RTF: **0.4118227233145004**. Not a neural-only timing or warm median.
- Driver elapsed: 12,277 ms. Exactly one ordered verify/load/render/close sequence finishes within its declared deadlines.
- Structural PCM check: peak absolute integer sample12,360; normalized RMS0.0494997; zero full-scale samples. This establishes non-silent/non-full-scale PCM, not intelligibility, correct spoken content, voice quality or listening acceptance.
- Process VmHWM after load/render/close: 345,848 kernel-reported kB (about337.74 MiB). This is cumulative process resident high-water, not PSS, isolated model memory, or total remote DSP memory.

Service status is `tts_complete`, optional warnings are empty. WAV publication precedes optional diagnostics. Thirty-eight inventory records were independently size/hash verified. Warm median remains null with the explicit one-request reason; listening remains `not_reviewed` and is reserved for Moritz.

## Guard, cleanup and privacy

Recorded unchanged guard/controller identities and non-inheritable lock flag match approval. Three pre-install/pre-instrument guards each report stable identical two-copy snapshots, unchanged file hashes, zero episodes and zero generation history. Before/after settings records match. Raw PID probes return exit1 with empty stdout/stderr; saved cleanup records all three actual package names absent and no errors/settings errors. Generation termination is corroborated by app-relevant logcat lines7304/7364. These are end-of-run observations, not a statement about the phone's later/current state.

Private DB and conditions directories are mode0700 and contained raw files mode0600. Labelled whitelisted conditions extracts bind the full originals by SHA256 and contain only allowed battery fields and anonymous numeric thermal samples. Private DB contents and full conditions text were not inspected; global logcat was queried only for app-specific library/lifecycle evidence. Full originals/global logcat remain private. Git pushes and external publication remain held.
