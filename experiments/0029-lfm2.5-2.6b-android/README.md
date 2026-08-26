# Experiment 0029 — LFM2.5-2.6B on Android

## Status

**Pinned official GGUF route, complete tokenizer/template/quantization contract, bounded host reconstruction, and one-request Android CPU viability smoke passed. No canonical Android campaign exists.**

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

[`protocol/experiment-contract.json`](protocol/experiment-contract.json) pins shared Android LLM protocol v2, the exact source revision embedded by the GGUF, tokenizer files, native template, every rendered prompt and token-ID hash, context proof, quantization inventory and provenance limitations, runtime options, and Android artifact. The official GGUF exposes source revision `ab00687315bc1298e9d54e9c4b611dde9867ccc2`; its embedded 5,443-byte template is byte-identical to that revision's `chat_template.jinja`. The official repository does not publish the exact converter/quantizer commit or calibration/importance-matrix provenance, so those values remain null with explicit reasons rather than being inferred.

## Host viability

The bounded noninteractive host smoke used `llama-completion`, a 180-second external timeout, a 1 MiB output guard, `-no-cnv`, greedy `--temp 0`, and `--override-kv tokenizer.ggml.add_bos_token=bool:false`. The override is required because the pinned native renderer already emits BOS.

Observed on the host:

- canonical short rendered prompt: 171 tokens, no truncation;
- prompt evaluation: 4.10562 s, 41.65 tokens/s;
- decode: 63 timed runs in 2.69382 s, 23.39 tokens/s;
- raw 64-token continuation: 323 bytes;
- output SHA-256: `3f703023ba052195c3f074178b1979bed040bfff867fbc917e5de77994490f52`.

See [`results/host-smoke/`](results/host-smoke/). These numbers are not Android evidence. A clean reconstruction on the current workstation independently reproduced all three tokenizer inventories and the exact 323-byte host output SHA-256.

## Android smoke artifact

[`tools/build_llama_cpp.sh`](tools/build_llama_cpp.sh) verifies the pinned clean llama.cpp checkout, acquires `artifacts/locks/heavy-ram.lock`, and builds with NDK `28.1.13356709` (`r28b`), `arm64-v8a`, API 31, Release, static llama/GGML and `c++_static`, `GGML_NATIVE=OFF`, `GGML_OPENMP=OFF`, `GGML_CCACHE=OFF`, and `LLAMA_CURL=OFF`. Source/build paths are prefix-mapped and the final executable is stripped.

The bound `llama-completion` artifact is:

- 5,074,184 bytes;
- SHA-256 `88a91aba5511a712f45aca21c566275681de30e2161f10bb99f9ac54f45b979e`;
- ELF64 little-endian AArch64 PIE, build ID `cecdefd1782ad6058ec56fffe03a982ba314ba30`;
- dynamically dependent only on Android system `libm.so`, `libdl.so`, and `libc.so`.

See [`results/android-build/`](results/android-build/). This is build evidence, not Android execution or performance evidence.

## Android viability smoke

After a bounded passive cooldown observation, the first staged attempt stopped before inference when Windows-hosted ADB transport disappeared during required remote hash verification. That diagnostic is preserved separately; cleanup later removed and verified absence of only the scoped 0029 root. It is not counted as a smoke.

A fresh approved retry through [`tools/run_phone_smoke.sh`](tools/run_phone_smoke.sh) passed on the authorized Galaxy S23 Ultra:

- exact short prompt: 171 input tokens, no truncation or double BOS;
- bounded greedy continuation: 64 output tokens, `max_tokens` stop;
- output: 324 bytes, SHA-256 `75f52326f67379c63d86b49e4520a074dbbd074329fc0d8d53693340ffc0a0c5`, sensible-text smoke passed;
- runtime prompt evaluation: 13.56415 s, 12.61 tokens/s;
- runtime follow-on evaluation: 63 runs in 7.13287 s, 8.83 runs/s;
- total runtime-reported request work: 20.70975 s;
- peak sampled PSS: 1,870,697 KiB; process VmHWM: 1,873,176 KiB;
- actual starting thermal state retained: status 2, AP 47.6 C, skin 41.4 C; after: status 2, AP 60.5 C, skin 42.5 C;
- exit zero; local and remote artifact hashes matched; scoped cleanup was verified absent; no experiment process remained.

See [`results/android-smoke/result.json`](results/android-smoke/result.json), [`results/android-smoke-cooldown/`](results/android-smoke-cooldown/), and [`results/android-smoke-pre-inference-transport-failure/`](results/android-smoke-pre-inference-transport-failure/). This is Android execution evidence, but not registry-eligible benchmark evidence. `llama-completion` exposes neither the protocol setup boundary nor first-token delivery timestamps, so those fields remain null with reasons.

The completion binary is intentionally scoped to this one-request smoke. It must not be looped for a canonical protocol-v2 campaign because each process reloads the model. Before the 1+5+5+5 campaign, bind a loaded-route runner and prove either full in-session state reset or fresh-Session isolation while retaining the loaded model/runtime route.
