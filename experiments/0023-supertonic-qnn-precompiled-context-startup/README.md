# Experiment 0023 — Supertonic QNN precompiled-context startup

**Status: complete. On the Galaxy S23 Ultra, median four-session QNN setup was 21.6129 s from source ONNX versus 0.497816 s from external EPContext, a 21.115084 s / 97.6967% reduction. Both arms produced the same structurally valid, previously accepted WAV, and a separate source-unavailable context run physically proved all neural calls on HTP.**

## Question

Can the accepted experiment-0011 Supertonic route run all neural components through QNN, and can loading precompiled external QNN/EPContext artifacts reduce cold setup versus compiling source ONNX in each fresh process?

This is an independent pragmatic experiment. It intentionally uses the already accepted 0011 legacy transcript, T239/L238 graph shapes, stable-Softplus vector graph, M1/SID5 voice, and fixed deterministic route. It does not inherit experiment 0022's canonical-T235/exact-T239 constraint.

## Functional host checkpoint

ORT 1.27.1 with QAIRT 2.49.0.260730 generated non-embedded external descriptors and QNN binaries for all four exact graph identities. Each descriptor/binary pair then loaded in a fresh isolated Docker process where source ONNX was not mounted. `session.disable_cpu_ep_fallback=1` remained set. Every recorded ORT node event used `QNNExecutionProvider`; all outputs were finite and generation/reload output hashes matched per component.

| Component | Source graph SHA-256 | Descriptor | External context binary |
|---|---|---:|---:|
| Duration | `8a1875ef…75016` | 815 B, `868610ca…a6ab` | 2,141,048 B, `2cba4208…fda6` |
| Text | `769fd1d2…a8c3` | 824 B, `fcfa9956…389b` | 19,437,184 B, `13534557…c718` |
| Stable-Softplus vector | `f2318c54…c7b` | 1,023 B, `3c49d45a…172a` | 136,894,512 B, `37eaa80b…8a24` |
| Vocoder | `35b90eea…c7c7` | 729 B, `5a60243f…034` | 55,355,808 B, `dc17865e…15f2` |

Total descriptor plus binary size is 213,831,943 bytes. See [`results/host-context-smoke/host-context-functional-smoke.json`](results/host-context-smoke/host-context-functional-smoke.json), its normalized raw records, and the committed ORT/QNN profiles.

## Clean host setup campaign

After experiment 0017 released the shared host, Pi explicitly cleared a clean rerun. The full ten-process campaign held `artifacts/locks/heavy-ram.lock` nonblocking for its complete `2026-08-22T14:50:23Z`–`14:52:37Z` interval. No other QNN campaign or phone work overlapped. A fixed balanced `S-C-C-S-C-S-S-C-S-C` schedule supplied five fresh Docker containers per arm.

The primary boundary is immediately before construction of the duration session through immediately after the vocoder constructor returns, with all four sessions alive. It excludes Python startup/imports, inference, WAV generation, teardown and post-ready artifact hashing. OS filesystem caches were not dropped and are not called cold.

| Arm | All five four-session setup values (s) | Median | Min–max | Population σ |
|---|---|---:|---:|---:|
| Source ONNX | 24.7769, 24.0141, 24.5459, 24.7316, 25.0928 | 24.7316 | 24.0141–25.0928 | 0.3557 |
| External context | 0.20134, 0.20715, 0.19223, 0.18711, 0.20087 | 0.20087 | 0.18711–0.20715 | 0.00714 |

Observed median delta: **24.53069 seconds**. Source/context median ratio: **123.123×**. Context setup reduction: **99.1878%**. There was no minimum-speedup gate.

Per-component source/context medians were duration 0.27375/0.03609 s, text 0.86624/0.01690 s, vector 19.04043/0.10602 s, and vocoder 4.29952/0.04114 s. These are setup/readiness measurements only, not inference latency or E2E RTF. See [`results/clean-host-setup/clean-setup-result.json`](results/clean-host-setup/clean-setup-result.json) and its ten committed raw records.

## Timing exclusion and coordination incident

The host wave overlapped experiment 0017's serialized QNN run before its owner replied to the coordination request. The overlap was disclosed to Jens, Pi and Ben. Exact windows are committed in the functional result.

Therefore **none of the preliminary functional-smoke setup, execution, ratio or resource observations are benchmark evidence**. They establish mechanism and functional reload only. The later clean ten-process campaign above supersedes those excluded preliminary setup observations for the host setup comparison.

## Prepared phone campaign

The matched Android ARM64 runner and 703 MiB hash-bound stage are prepared without phone access. Both arms use the current retained ORT 1.27.1 + QAIRT 2.49 Android build (`libonnxruntime.so` SHA-256 `643c6f6f…ae9`); the historical 0011 binary is no longer retained, so 0023 documents this same-runtime-both-arms adaptation rather than claiming binary identity.

This native Manjaro host uses installed `/usr/bin/adb` 37.0.0 (SHA-256 `506163fd…40f9`). The historical Windows/WSL adb path is absent; `ADB_LIBUSB` is deliberately not carried over. The frozen transport contract still requires nonblocking `phone.lock`, exactly one authorized Galaxy S23 Ultra, full identity/boot/verified-lock gates, unique `/data/local/tmp` staging, remote hash verification, evidence pull and trap cleanup verification.

The bounded campaign contains exactly:

- three fresh four-session setup-only processes per arm;
- one separate E2E process per arm with one first and five warm generations;
- one separate profiled context-arm physical-proof generation;
- source-model deletion and absence verification before every context-arm process;
- sampled PSS/VmHWM, thermal/battery context, WAV structural validation and descriptive numerical comparison.

See [`results/phone-preparation.json`](results/phone-preparation.json) and [`protocol/phone-transport-contract.json`](protocol/phone-transport-contract.json). No ADB/device command was run during preparation.

The first approved invocation failed closed locally before ADB because stage assembly had copied the correct runner bytes without its executable mode. The phone lock was acquired and released, no remote stage existed, and cleanup reported `not_created`. [`results/phone-preflight-blocker.json`](results/phone-preflight-blocker.json) preserves the attempt. Stage assembly now preserves metadata explicitly, and the exact campaign preflight is a shared checker that rejects symlinks, non-regular files, a wrong hash, or missing executable bits before any ADB command.

## Physical-phone result

The corrected bounded campaign ran on the authorized Samsung SM-S918B / SM8550 with Android 16/API 36, verified boot green and flash locked. It used the committed native Linux adb transport, verified the full remote stage, deleted source ONNX before the context arm, pulled the evidence, removed the unique remote root, verified its absence and released `phone.lock`.

| Arm | Three fresh setup values (s) | Median | Min–max | Population σ | Peak sampled PSS range |
|---|---|---:|---:|---:|---:|
| Source ONNX | 22.1599, 21.6129, 20.9571 | 21.6129 | 20.9571–22.1599 | 0.49171 | 1,341,123–1,354,631 KiB |
| External context | 0.785324, 0.496524, 0.497816 | 0.497816 | 0.496524–0.785324 | 0.135838 | 162,301–162,649 KiB |

Observed median setup delta: **21.115084 seconds**. Source/context ratio: **43.4154×**. Context setup reduction: **97.6967%**. This is session readiness only; it excludes inference.

A separate E2E process per arm performed one first generation plus five same-session warm generations:

| Arm | First latency / RTF | Warm median latency / RTF |
|---|---:|---:|
| Source ONNX | 2.17811 s / 0.131628 | 2.16397 s / 0.130773 |
| External context | 2.15767 s / 0.130393 | 2.15371 s / 0.130153 |

Both arms emitted 729,746 mono PCM16 samples at 44.1 kHz (16.547528 s) and were byte-identical in float output and WAV. WAV SHA-256 is `47c30043ccc053fe11b908a383c2bc9996c003b85ec293bae122c5794294783c`, exactly the Moritz-accepted experiment-0011 all-HTP WAV, so the existing exact-hash listening verdict applies. The listening copy is [`samples/supertonic-stable-softplus-qnn-context.wav`](samples/supertonic-stable-softplus-qnn-context.wav).

One separate profiled context process, with source ONNX unavailable and fallback disabled, recorded QNN-only ORT node events for duration, text, five vector calls and vocoder. Every QNN profile contained RPC time, accelerator time, accelerator cycles and four-HVX-thread evidence. It is excluded from setup and E2E timing.

The device processes all passed, but the first local validation invocation rejected a native `LIBNATIVE` prefix before source-arm JSON. No phone rerun occurred. The offline parser now requires exactly one final line-start JSON object, rejects zero/multiple/malformed candidates, preserves the raw stdout byte-for-byte, and hashes the exact diagnostic prefix. Cleanup had already completed successfully. Full evidence is in [`results/phone-campaign/phone-result.json`](results/phone-campaign/phone-result.json).

## Handoff

The experiment evidence is complete. Alex owns dashboard ingestion; no dashboard paths are edited here.

See [`protocol/experiment-contract.json`](protocol/experiment-contract.json) and [`PLAN.md`](PLAN.md).
