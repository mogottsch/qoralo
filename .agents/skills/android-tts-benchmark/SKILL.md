---
name: android-tts-benchmark
description: Run or publish Android TTS benchmarks in this repository. Use whenever an agent benchmarks a TTS model, measures Android CPU/QNN/HTP performance, creates a listening sample, refreshes an old result, or hands a result to the benchmark dashboard.
---

# Android TTS benchmark

Make new routes directly comparable and fill the existing dashboard fields.

## Use the same text

Read and use the exact bytes in:

```text
protocols/android-tts-benchmark/transcript.txt
```

Canonical v2 is 226 bytes with no trailing newline:

```text
SHA-256: 424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67
```

Do not change its punctuation or substitute another sentence. Record the text hash and effective tokenizer output. If a model cannot use it, label the route noncanonical and explain why.

## Collect the standard benchmark output

Create the model sessions once, then collect:

1. setup time;
2. one first complete generation;
3. at least five more generations in the same sessions;
4. full model/cache/decoder/random-state reset before every generation;
5. each run's latency, actual emitted audio duration and RTF;
6. warm median RTF over the five warm runs;
7. peak memory with the measurement method;
8. device, runtime, provider and thread configuration;
9. a valid WAV with duration, format and SHA-256;
10. thermal context for physical phone runs.

Calculate each RTF as:

```text
RTF = generation seconds / actual emitted audio seconds
```

Do not call a single run, first run or profiled proof run a warm median. If output duration changes, disclose it.

## Keep proof and listening separate

For QNN/HTP, disable CPU fallback and collect provider plus physical RPC/accelerator/cycle/HVX evidence. Host QNN validation is not physical phone proof.

Only Moritz can mark an exact WAV `accepted` or `rejected`. Until then it is `not_reviewed`. Numerical similarity and valid PCM do not decide listening quality.

## Finish the evidence

Do not leave an existing dashboard field empty when it can reasonably be measured. Use null plus an explicit reason only when it is genuinely unavailable or blocked.

Preserve historical records; add a dated refresh instead of overwriting them. Commit the experiment evidence first, then give the dashboard owner the commit, metrics, provenance, WAV path/hash and Moritz's exact verdict.
