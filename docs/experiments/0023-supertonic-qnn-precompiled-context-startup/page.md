---
experiment: 0023-supertonic-qnn-precompiled-context-startup
status: completed
summary: External QNN contexts cut median four-session phone setup from 21.6129 seconds to 0.497816 seconds; both arms emitted the same accepted exact-hash WAV, and a separate context proof established physical HTP execution.
registry: 0023-supertonic-source-onnx-htp, 0023-supertonic-external-context-htp
---

# Experiment 0023 — Supertonic QNN precompiled-context startup

## Experiment description

Experiment 0023 asked whether external ONNX Runtime QNN EPContext artifacts could remove most of the session-compilation delay from the accepted Supertonic all-HTP route. It compared two otherwise matched arms: constructing duration, text, stable-Softplus vector, and vocoder sessions from source ONNX, or loading four non-embedded EPContext descriptors and their external QNN binaries. Offline context generation was not charged to context startup.

The experiment deliberately reused experiment 0011's fixed legacy route: the 230-byte legacy-v1 transcript, T239/L238 shapes, deterministic seed, M1/SID5 voice, and 729,746-sample output. It is independent of experiment 0022's failed canonical-T235 versus exact-T239 constraint. Both phone arms used the same current ORT 1.27.1 and QAIRT 2.49 Android build because the historical 0011 runtime binary was no longer retained; no binary-identity claim is made.

Host work first generated and reloaded all four external contexts in fresh source-absent containers with CPU fallback disabled. A clean ten-process setup campaign then compared five fresh containers per arm under one exclusive heavy-RAM lock. The phone campaign repeated the comparison on the authorized Galaxy S23 Ultra with three fresh setup-only processes per arm, separate six-generation E2E processes, and a separate instrumented context proof. The [experiment contract](../../../experiments/0023-supertonic-qnn-precompiled-context-startup/protocol/experiment-contract.json) and [phone transport contract](../../../experiments/0023-supertonic-qnn-precompiled-context-startup/protocol/phone-transport-contract.json) define those boundaries.

## Progress

1. **August 22, 2026: all four contexts reloaded on the host.** Duration, text, vector, and vocoder descriptors loaded in isolated containers without source ONNX. Every recorded node event used `QNNExecutionProvider`, fallback was disabled, and generation/reload output hashes matched. The functional run overlapped another serialized QNN campaign, so all of its timing and resource observations were excluded.
2. **August 22, 2026: clean host setup comparison completed.** A balanced five-process-per-arm campaign measured the four-session constructor boundary at 24.7316 seconds median from source and 0.200869 seconds from context. This established a host setup result, not phone HTP execution or E2E latency.
3. **August 22–23, 2026: the phone campaign was prepared and failed closed once.** The first approved invocation found that the staged runner had correct bytes but mode 0644. Preflight stopped before ADB, released the phone lock, and created no remote stage. Preparation switched to metadata-preserving copy and added an executable-mode check.
4. **August 23, 2026: the corrected phone campaign passed.** It verified the authorized phone and remote hashes, deleted source ONNX before every context process, completed all setup and E2E runs, collected a separate profiled context generation, removed the remote root, and released the lock.
5. **August 23, 2026: noisy stdout was repaired offline.** The first validator rejected a native-library diagnostic before otherwise valid source JSON. Raw bytes were preserved; the parser was tightened to accept exactly one final line-start JSON object and reject ambiguous candidates. Device execution was not rerun.

The excluded host timing incident is retained in the [functional smoke result](../../../experiments/0023-supertonic-qnn-precompiled-context-startup/results/host-context-smoke/host-context-functional-smoke.json). The valid host distribution is in the [clean setup result](../../../experiments/0023-supertonic-qnn-precompiled-context-startup/results/clean-host-setup/clean-setup-result.json). The [preflight blocker](../../../experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-preflight-blocker.json), [corrected preparation](../../../experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-preparation.json), and [final phone result](../../../experiments/0023-supertonic-qnn-precompiled-context-startup/results/phone-campaign/phone-result.json) preserve the complete path.

## Results

On the phone, external contexts reduced the median four-session setup boundary by **21.115084 seconds**, from **21.6129 seconds** to **0.497816 seconds**. That is a **97.6967%** reduction and a **43.4154×** source/context ratio for this exact route. It measures readiness only and excludes inference, offline context generation, and teardown.

| Phone measurement | Source ONNX | External context |
|---|---:|---:|
| Three setup runs | 22.1599, 21.6129, 20.9571 s | 0.785324, 0.496524, 0.497816 s |
| Median setup | 21.6129 s | 0.497816 s |
| First generation | 2.17811 s / RTF 0.131628 | 2.15767 s / RTF 0.130393 |
| Five-warm median | 2.16397 s / RTF 0.130773 | 2.15371 s / RTF 0.130153 |
| Setup-only sampled PSS range | 1,341,123–1,354,631 KiB | 162,301–162,649 KiB |

Both E2E arms emitted 729,746 samples of finite, non-silent, unclipped mono PCM16 at 44.1 kHz. Their float output and WAV bytes were identical. The WAV SHA-256, `47c30043…4783c`, is also exactly the previously accepted experiment-0011 all-HTP hash. The committed inherited listening verdict therefore applies to this identical file only; it does not transfer to any byte-different Supertonic output.

| Evidence class | What 0023 established |
|---|---|
| Technical execution | Both matched Android arms completed setup and E2E generation with fallback disabled. Source ONNX was unavailable for context runs. |
| Physical provider proof | A separate context-arm process recorded only QNN ORT nodes plus RPC time, accelerator time, accelerator cycles, and four-HVX-thread evidence for every neural call. It was excluded from setup and E2E timing. That proof is not transferred to the source arm. |
| Structural audio | Both arms produced the same valid 16.547528-second WAV. |
| Numerical/acoustic comparison | Source and context output were byte-identical (`max_abs=0`, RMSE `0`, cosine `1.0`). This is an exact-output result for the measured route. |
| Exact-sample listening | Accepted by inheritance of the committed experiment-0011 verdict because the SHA-256 is identical. The boundary is the exact `47c30043…4783c` sample. |

The normalized cards above use each separate E2E process's high-water memory fields, not the setup-only PSS ranges shown in the table. The context proof's RTF `0.197667` includes profiling overhead and is not a performance headline. Finally, this remains a legacy-v1, fixed-shape result for four exact graph identities on one authorized device; it is not a canonical-v2 result or a general claim about Supertonic startup.
