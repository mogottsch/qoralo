# Experiment 0018 — MOSS-TTS-Nano ONNX on Android CPU

## Result

Official MOSS-TTS-Nano completed end to end on the authorized Galaxy S23 Ultra through Android ONNX Runtime **CPUExecutionProvider only**. It generated a valid retained sample for the frozen benchmark text, but this implementation was slower than real time and had a large process memory footprint.

This is an initial CPU candidate result. It is not HTP evidence, and the separate ORT profile run must not be compared directly with uninstrumented latency.

## Reproducibility contract

- Official source: `OpenMOSS/MOSS-TTS-Nano` revision `cc7bdf19c7639c0870dab22045a33b442760f6be`
- TTS ONNX assets: `OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX` revision `f52645cb467506d8e18e746ddd59482685b74e58`
- Audio tokenizer ONNX assets: `OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX` revision `ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae`
- Source, model, and weight license: Apache-2.0
- Access: anonymous and ungated; no login, click-through, consent, export attestation, or additional terms appeared
- Device: `R5CW81PR8SY` / `SM-S918B` / `SM8550`, Android 15 / API 35
- Runtime: `com.microsoft.onnxruntime:onnxruntime-android:1.20.0`
- ORT threads: four intra-op and one inter-op
- Voice: official built-in `Junhao`; fixed-frame sampling seed `20260818`

Every downloaded file hash and byte size is in [`results/source-inventory.json`](results/source-inventory.json).

## Frozen benchmark text and tokenizer

The benchmark uses [`protocol/transcript.txt`](protocol/transcript.txt), SHA-256 `350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f`.

[`tools/tokenize_transcript.py`](tools/tokenize_transcript.py) removes one final text-file LF if present—the frozen file has none—and otherwise performs direct SentencePiece encoding with the pinned official `tokenizer.model` (SHA-256 `c353ee1479b536bf414c1b247f5542b6607fb8ae91320e5af1781fee200fddff`). SentencePiece 0.2.1 produced 51 IDs, round-tripped exactly, and wrote the full text, pieces, and IDs to [`protocol/tokenization.json`](protocol/tokenization.json). The generated `BenchmarkPrompt.kt` replaces the official pre-tokenized demo prompt.

## Uninstrumented phone benchmark

The app created the four sessions once, then generated the same deterministic 16.72-second output four times in one process.

| Measurement | Result |
|---|---:|
| Four-session setup | 1.713 s |
| First end-to-end latency | 19.033 s |
| First RTF | 1.138 |
| Warm end-to-end latency | 18.324–18.816 s |
| Warm RTF median | 1.125 |
| First decoded PCM, first run | 18.953 s |
| First decoded PCM, warm median | 18.780 s |
| Configured ORT intra/inter-op threads | 4 / 1 |
| Sampled total process threads | 17–38 |
| Process RSS high-water (`VmHWM`) | 5,691,920 KiB |
| Peak sampled process PSS | 5,853,862 KiB |

RTF is end-to-end latency divided by decoded audio duration, so values above 1 are slower than real time. “First decoded PCM” runs from request start until full audio-tokenizer decode returns PCM. The official Android example uses full decoding, not streaming; this is therefore not time-to-first-streaming-chunk. Memory values are process-wide, not component-isolated allocations.

## Retained listening sample

Ignored artifact:

```text
work/vibevoice-0018-20260819T144325Z-172685/benchmark/listening-sample.wav
```

- SHA-256: `173850781b055e70a606fb561d93b70e6d8c6318db1b29b2324f83506c21ad6b`
- RIFF/WAVE, PCM signed 16-bit little-endian
- mono, 48,000 Hz
- 802,560 frames / 16.72 seconds
- 1,605,164 total bytes
- RMS `0.133849`; peak `0.999969`; finite

The native codec output is stereo; the official Android example averages the two channels to mono before writing the WAV.

## Separate ORT profile run

All `543,972` profiled node-kernel events were assigned to `CPUExecutionProvider`; no other provider appeared. The instrumented component wall times were 0.612 seconds for prefill, 10.209 seconds for autoregressive decode, 15.775 seconds for the fixed-frame local decoder, and 7.060 seconds for full audio-tokenizer decode. Profiling overhead raised total latency to 33.872 seconds, so these numbers describe the profile run only.

| Component | Node events | Summed kernel time | Largest operator totals |
|---|---:|---:|---|
| Prefill | 1,189 | 0.587 s | MatMul 0.439 s; Slice 0.054 s; Where 0.017 s |
| Autoregressive decode | 207,955 | 7.640 s | MatMul 3.161 s; Transpose 0.881 s; Cast 0.518 s |
| Local decoder | 333,227 | 7.888 s | MatMul 3.606 s; Unsqueeze 0.402 s; Reshape 0.386 s |
| Audio tokenizer | 1,601 | 6.833 s | MatMul 4.196 s; Softmax 0.911 s; Add 0.831 s |

[`results/ort-profile-summary.json`](results/ort-profile-summary.json) retains every operator aggregate, provider, event count, profile size, and profile hash. The ignored raw profiles occupy about 548 MiB under the run root.

## Evidence and caveats

- [`protocol/benchmark-policy.json`](protocol/benchmark-policy.json) — frozen measurement semantics and device procedure
- [`results/phone-cpu-checkpoint.json`](results/phone-cpu-checkpoint.json) — canonical phone result, metrics, hashes, provider counts, and caveats
- [`android/`](android/) — instrumented adaptation of the official Android example
- [`device/run_phone_cpu.sh`](device/run_phone_cpu.sh) — identity gates, phone lock, staging, run, pullback, and cleanup

An initial Windows-ADB `exec-out` stdin staging attempt hung and was discarded. The completed evidence run instead used fast unique `/data/local/tmp` uploads, verified each upload and app-internal mode-0600 copy by SHA-256, pulled the evidence, and removed the stage. A wrapper quoting error occurred only while verifying final cleanup; a fresh locked identity-gated check then confirmed the package and all experiment-0018 remote stages were absent.
