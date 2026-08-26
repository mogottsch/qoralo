# Experiment 0029 — LFM2.5-2.6B on Android

## Status

**Pinned official GGUF route and bounded host viability smoke passed. Android build was interrupted before producing a binary; no phone run or Android result exists.**

This experiment evaluates `LiquidAI/LFM2.5-2.6B` through a pinned CPU-only llama.cpp route. It preserves the model-native reasoning continuation and does not treat it as equivalent to the non-thinking Qwen route. Host work is feasibility evidence only and must never enter the Android registry.

## Pinned route

- Artifact repository: `LiquidAI/LFM2.5-2.6B-GGUF`
- Repository revision: `84022ce711b28455e8c4fc364ce68c00cf995875`
- Artifact: `LFM2.5-2.6B-Q4_K_M.gguf`
- Artifact bytes: `1,674,455,040`
- Artifact SHA-256: `02a8b7e17487d326e46d68ce0ba24211e1b80a14c4cd0597fa73c1cd697f52ed`
- Download URL: `https://huggingface.co/LiquidAI/LFM2.5-2.6B-GGUF/resolve/84022ce711b28455e8c4fc364ce68c00cf995875/LFM2.5-2.6B-Q4_K_M.gguf`
- License: LFM Open License v1.0, exact pinned text under [`protocol/upstream-LICENSE`](protocol/upstream-LICENSE)
- Runtime: llama.cpp build 7446, commit `5c0d18881e0e9794c96b2602736b758bac9d9388`
- Initial backend: ARM CPU, four inference and four batch threads

The route contract is not yet complete: before phone execution, add the full tokenizer/chat-template and quantization provenance required by the shared Android LLM protocol and bind the final Android binary hash.

## Host viability

The bounded noninteractive host smoke used `llama-completion`, a 180-second external timeout, a 1 MiB output guard, `-no-cnv`, greedy `--temp 0`, and `--override-kv tokenizer.ggml.add_bos_token=bool:false`. The override is required because the pinned native renderer already emits BOS.

Observed on the host:

- canonical short rendered prompt: 171 tokens, no truncation;
- prompt evaluation: 4.10562 s, 41.65 tokens/s;
- decode: 63 timed runs in 2.69382 s, 23.39 tokens/s;
- raw 64-token continuation: 323 bytes;
- output SHA-256: `3f703023ba052195c3f074178b1979bed040bfff867fbc917e5de77994490f52`.

See [`results/host-smoke/`](results/host-smoke/). These numbers are not Android evidence.

## Interrupted Android preparation

The NDK build was configured for `arm64-v8a`, API 31, Release, static libraries, and no OpenMP. The session ended during compilation and no `llama-completion` Android binary exists. Ignored local state on the originating workstation contained the 1.6 GB model, a 175 MB llama.cpp checkout, a 57 MB host build, and the incomplete Android build; none is transferred through Git.

Continue from [`PLAN.md`](PLAN.md). Do not access the phone until the bounded host route, full contract, Android binary hash, lock, identity, storage, and scoped cleanup gates are all restored.
