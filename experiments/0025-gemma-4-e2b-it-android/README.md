# Experiment 0025 — Gemma 4 E2B IT on Android

## Status

**Fresh-Session isolation is approved and contract-locked. The complete canonical Android CPU campaign passed and is retained with raw evidence. The earlier rewind run remains only a reset diagnostic; GPU work has not started.**

This experiment compares only the official instruction-tuned Gemma 4 E2B LiteRT-LM CPU and GPU Android routes on the authorized Galaxy S23 Ultra. It measures execution, setup, TTFT, prefill/decode throughput, total latency, process memory, and operating conditions under the repository's fixed short/medium/long prompt contract. It does not evaluate transcript quality and makes no NPU/HTP claim.

## Locked route

- Base model: `google/gemma-4-E2B-it@3e22461f65e89153144f8adb70e3b8c2cc9845a7`.
- Deployment: `litert-community/gemma-4-E2B-it-litert-lm@6b78abd019e61a1ca4cbe3b212d2c9ce8ff38a94`.
- CPU artifact: `gemma-4-E2B-it.litertlm`, SHA-256 `18193810…a63c`, 2,588,147,712 bytes.
- GPU artifact: `gemma-4-E2B-it-gpu.litertlm`, SHA-256 `a53a5900…5cf5`, 2,008,432,640 bytes.
- Runtime: LiteRT-LM v0.16.1 at `924e79c91542761242244e4f1651851f822e4cbb`.
- Device: SM-S918B / SM8550 / `arm64-v8a`, serial `R5CW81PR8SY`.
- Context/KV capacity: 8,192 tokens; every canonical prompt plus the 2,048-token output ceiling must fit without truncation.
- Thinking and speculative decoding: disabled.
- Sampling: LiteRT-LM's supported CPU `TOP_P` sampler with `k=1`, `p=1`, temperature 1.0. Its pinned implementation directly returns the single top-k token when `k==1`, which is exact greedy argmax. Both neural arms use that CPU sampler.

The complete machine contract is [`protocol/experiment-contract.json`](protocol/experiment-contract.json).

## Host viability gate

The exact CPU deployment artifact loaded on the host through LiteRT-LM/XNNPACK and completed a bounded 64-token canonical-short smoke. The rendered prompts contain 171, 595, and 1,930 effective tokens, so each fits the locked 8,192-token capacity with the 2,048-token ceiling. The retained output looks sensible; that is only a corruption/gibberish smoke check.

Host metrics and output remain experiment-local in [`results/host-smoke/result.json`](results/host-smoke/result.json). They are not Android evidence and will never enter the Android registry.

Pre-contract runner development exposed two non-model issues: a Bazel daemon inherited the heavy-RAM lock, fixed by mandatory `--batch` builds, and early runner assertions treated optional LiteRT-LM BenchmarkInfo turn counters as required. The runner now drains callbacks, persists raw output first, and represents unavailable internal telemetry as null with a reason. The required logical 1+5+5+5 request contract remains strict.

## First Android smoke

The exact CPU route completed a bounded 64-token canonical-short smoke on the authorized phone. Setup was `3.7395 s`; TTFT `6.0621 s`; isolated prefill `4.2478 s` / `40.256 tok/s`; callback-boundary decode `4.5993 s` / `13.698 tok/s`; and total request time `10.6614 s`. Peak sampled process PSS was `3,132,081,152 B` and VmHWM `3,262,898,176 B`. Exact output SHA-256 `0f588698…4686` looks sensible under the narrow smoke check.

See [`results/android-cpu-smoke/result.json`](results/android-cpu-smoke/result.json). This is viability evidence with a 64-token cap, not a full canonical campaign distribution.

## Reset-semantics diagnostic

The first 16-request CPU run completed, but it is **not canonical evidence**. `RewindToStep(0)` reset LiteRT-LM's logical step while retaining reusable prefix/KV state. The first request for each tier performed real prefill; repeated identical prompts then reported microsecond prefill and impossible multi-million-token/s rates. The complete run is retained under [`results/android-cpu-reset-diagnostic/`](results/android-cpu-reset-diagnostic/) rather than published.

Two bounded host probes isolated the behavior. Rewinding one Session reproduced prefix reuse on request two. Keeping one loaded Engine but creating a fresh Session before each request forced genuine 171-token prefill on both requests, with measured Session recreation of about 41 microseconds. Those probes are retained under [`results/host-reset-probes/`](results/host-reset-probes/).

Moritz approved the smallest honest adaptation on 2026-08-26: **one loaded Engine, fresh Session per logical request**. The shared protocol now treats loaded-route reuse plus actual conversation/KV isolation as the invariant rather than Session object identity. Every fresh-Session creation is measured separately and excluded from the runner's request timing; the Engine and mapped model remain loaded, accelerator compilation is not repeated, and no prompt-prefix/KV state carries across requests.

## Canonical Android CPU campaign

The fresh from-scratch CPU campaign completed all 16 requests: one first short request followed by five loaded-route requests for each of short, medium, and long. Every request performed full prompt prefill, completed at EOS, retained exact output bytes, and used the approved isolation strategy. Median loaded-route observations were:

- short (171 input / 421 output tokens): TTFT `3.044 s`, prefill `58.33 tok/s`, decode `10.57 tok/s`, total `42.82 s`;
- medium (595 / 700): TTFT `7.560 s`, prefill `80.08 tok/s`, decode `10.28 tok/s`, total `75.57 s`;
- long (1,930 / 756): TTFT `28.663 s`, prefill `67.65 tok/s`, decode `8.65 tok/s`, total `115.81 s`.

Setup was `6.474 s`. Peak sampled PSS was `5,726,960,640 B`; VmHWM/ru_maxrss was `5,887,778,816 B`. Median fresh-Session recreation was below `0.35 ms` for every tier and is excluded from request timing. The phone began warm (AP `45.4 C`, skin `39.7 C`) and ended at Android thermal status 3 (AP `51.7 C`, skin `45.0 C`), so sustained thermal throttling is an explicit limitation rather than hidden or treated as a failed request.

See [`results/android-cpu-campaign/result.json`](results/android-cpu-campaign/result.json) and its hash-bound raw evidence.

## Claim boundaries

- A successful host smoke is not Android execution or performance.
- CPU and GPU use distinct official `.litertlm` files and remain distinct deployment routes.
- Process PSS/VmHWM does not directly measure private GPU memory.
- `looks_sensible` is not quality, correctness, grounding, transcript usefulness, or acceptance.
- Missing runtime-internal timing splits remain null with reasons; they do not invalidate a completed logical request.
- Published rows require exact Android device, workload, artifact, runner, runtime-library, output-hash, and campaign-count evidence.
