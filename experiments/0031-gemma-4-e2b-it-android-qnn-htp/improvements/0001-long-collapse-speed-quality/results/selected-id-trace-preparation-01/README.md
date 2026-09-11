# Selected-ID tracing: host preparation ready

**No Android request or model inference has run.** The prepared diagnostic observes real sampler returns; it does not add token50, alter BOS history, change the sampler, or make another precision candidate. Both completed precision-path results and the termination/template audit remain unchanged.

## What will be observed

Three observation-only calls in a private copy of `BasicDialog` write:

```text
GEMMA_SELECTED_ID_V1 ordinal=… token=… configured_eos=… n_past=…
```

Each call follows the existing `sampler.process(logits)` return, before EOS/text filtering. The tiny helper only writes and flushes stderr. It neither selects tokens nor changes stopping behavior. The fixed max2048 request bounds the record count; the existing1800s watchdog remains.

- An observed50 is genuine selected-ID evidence for **this new instrumented runtime/request**.
- A later actual record establishes subsequent sampling. No later record does **not** identify whether a limit, EOS, interruption, or incomplete capture ended it.
- Configured EOS membership is observed, but an internal stop-decision enum is **not exposed**. That field stays null.
- Absence of50 is only reported when the trace is contiguous from ordinal0 and matches the bound runtime-generated count. Decoded or re-tokenized output is never used to invent selected IDs.

The existing `tokenQuery` API was rejected as a shortcut: its available LUT path supplies an empty per-layer vector/null callback, unlike the Gemma text-query path in use. The diagnostic keeps that text query and both ordinary/per-layer LUT paths.

After the unchanged query and its saved profile, two existing runner commands encode the original input using the dialog tokenizer and save the complete IDs. This checks same-runtime tokenization against the frozen1929-ID input. It is **not direct prefill-tensor capture**, and it does not affect the preceding request. No host neural smoke or separate tokenizer dependency build was needed.

## Build and provenance

The Android runtime built successfully from the hash-bound available SDK example source. All372 existing source files are bound in `source-bindings.json`; final differences are `basic.cpp`, the Android build recipe, and the resolved Rust lockfile. Restricted source and binaries remain private.

| Attempt | Actual outcome | Evidence-led next step |
|---|---|---|
|01 | Rust101 after5.05s: incomplete SDK lock rejected by `--locked`; no NDK compile | Resolve metadata in a fresh private source tree |
|02 | Rust0 at232.09s; C++2 at361.55s total: missing `inference-types.hpp` search path | Add its existing `engines` include directory |
|03 | C++/link2 after265.80s: missing ModalityEncoder, AudioEncoder and ImageDecoder implementations | Audit the entire Android source inventory, not another guessed flag |
|04 | C++/link0 after266.68s | Complete132-file non-Windows source inventory, all required runner Genie imports exported |

The fourth recipe adds only the existing include directory and three supplied CPP files. It does not edit those implementations. Successful Rust archive/lock bytes were reused with hash checks, not rebuilt after each C++ failure. All first failures and original trees/logs remain private and hash-bound.

**Runtime equivalence is not assumed.** Rust dependency resolution retained every existing package version/source/checksum but added252 registry-required transitive/feature versions missing from the shipped lock. The source-built Genie and NDK C++ runtime are new artifacts; they are not proven equivalent to the supplied commercial library. A future trace cannot retroactively supply selected IDs or stop decisions for older runs, even if decoded output matches.

- `libGenie.so`:11,622,384bytes; SHA256 `43b9bf47d82aaf375582c0b5631f8b032f65aeeebc5a7758cb8ea7cae5af022a`.
- Added `libc++_shared.so`:9,236,352bytes; SHA256 `77a34d3f03b17709f3f6473f37cb7795314e51fa3e5e652b5c37d53cfd05c754`.
- Static ELF checks: AArch64; observer marker present; no missing Genie imports required by the unchanged runner. Needed libraries are Android libc/libm/libdl/liblog and the explicitly staged libc++.
- Existing NDK28.1.13356709 and Rust1.98.1; Android Rust standard library downloaded/manifest-verified into private storage, not globally installed. Private Cargo/cache/temp paths; no SDK-original/global toolchain modification.
- Sequential host builds:4GiB RAM/1GiB existing swap/2CPU/nice15/1800s. No global resource changes. Actual child receipts, not watcher exits or post-GC systemd defaults, determine outcomes.

## Frozen diagnostic and lifecycle

Stage: `.local/frozen-stages/selected-id-long-20260911T143756Z-01`.

- Manifest SHA256 `07e5b1b5f1e75c20022e6f9356262fe969eadbead6f91b8017f01429c20fc2f2`.
-19 independent read-only payloads;4,013,512,626bytes; runner0555.
- Same context SHA256 `27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd`, embeddings, tokenizer, config, rendered input and runner.
- Exact expected1929 input IDs, single BOS/config−1, greedy, EOS `[1,106]`, max2048. No50/BOS correction, truncation, splitting or output repair.
- Only changed old payloads: Genie library and the script's **post-query** tokenizer observation. Only added payload: matching libc++ library.
- Stage preparation: actual child0,40.963s,1GiB/no-swap/1CPU bound; no runtime/model/ADB execution.

`tools/phone_selected_id_long.py` defaults to plan-only. It uses inverse-checked frozen substitutions over the completed full-lock controller, a fresh result/remote namespace, and the same read-only RPC preflight. Actual execution still requires a real Pi-granted one-use slot, reviewed stage digest, fresh run ID and full phone lock. Raw pull precedes scoped cleanup. Unknown identity is not permission to signal; check-to-signal remains non-atomic. No APK or app-data changes.

**219 host/source/saved-evidence tests passed**, including9 tracer-specific tests: observer-only C++ fixture, exact source/recipe scope, complete Android source inventory, script ordering, unchanged guarded lifecycle, incomplete/malformed trace handling, membership, continuation and full input-ID comparison. Fixture tokens are synthetic, not model observations.

No phone slot has been consumed for this diagnostic. Janek/TTS scheduling remains with Pi. The stop-policy gap and LiteRT extra-BOS difference remain parity limitations, not demonstrated collapse causes. No benchmark/registry update, speed claim, quality acceptance, push or external publication is made.
