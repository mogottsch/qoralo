# Plan — MOSS-TTS-Nano official Android ONNX CPU evaluation

## Scope

Evaluate the official MOSS-TTS-Nano Android ONNX Runtime path on the authorized S23 Ultra. CPUExecutionProvider is the only initial provider claim. Do not treat ORT profiling as HTP evidence. Do not modify experiment 0017 or dashboard files and do not spawn agents.

## Gates

1. Pin the official GitHub source plus the MOSS-TTS-Nano-100M-ONNX and MOSS-Audio-Tokenizer-Nano-ONNX revisions. Record every file hash, provenance, and source/model/weight license. Stop rather than authenticate or accept any gate, click-through, consent, export attestation, or additional terms.
2. Preserve the official Android ONNX architecture: prefill, autoregressive global decode, fixed-frame local decoder, and full audio-tokenizer decode.
3. Replace only the pre-tokenized demo prompt with a direct, reproducible encoding of the frozen benchmark transcript using the pinned official SentencePiece model. Retain exact text, model hash, pieces, and IDs.
4. Freeze timing, RTF, first-audio, thread, and memory semantics before execution. Run one fresh app process with four session creations, one first generation, and three warm generations.
5. Retain and structurally validate the deterministic WAV with exact container, encoding, channel, rate, frame count, duration, amplitude statistics, and SHA-256. Do not infer listening quality without Moritz's review.
6. Run one separate instrumented generation with ORT profiling enabled for all four components. Aggregate every node event by provider and operator. Keep its overhead out of benchmark latency.
7. Use `artifacts/locks/phone.lock`, exact serial/model/SoC gates, Windows ADB with `ADB_LIBUSB=1`, a closed lock FD for every ADB child, unique verified upload and app-internal stages, evidence pullback, cleanup verification, uninstall, and lock release.

## Outcome

All six technical objectives completed. The official path generated a structurally valid 16.72-second WAV entirely on CPUExecutionProvider. First RTF was 1.138 and warm median RTF was 1.125, so this full-decode implementation was slower than real time. Process RSS high-water was about 5.43 GiB. The separate profile assigned all 543,972 node-kernel events to CPUExecutionProvider and isolated the dominant component/operator costs. No HTP claim is made. Moritz accepted the exact retained sample as “Okay to good, but with a bit of a Chinese accent.” This sample-level verdict carries an accent caveat and does not establish broad-corpus quality.
