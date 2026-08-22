# Experiment 0023 — Supertonic QNN precompiled-context startup

**Status: clean isolated host setup campaign passed with five fresh processes per arm. Median exact four-session setup was 24.7316 s from source ONNX versus 0.2009 s from external EPContext, an observed 24.5307 s / 99.1878% reduction. Phone work remains paused pending review.**

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

## Next gates

1. Obtain review of the committed clean host setup campaign.
2. Build the matched E2E runner for source and context arms.
3. On the authorized Galaxy S23 Ultra, prove all four neural sessions with fallback disabled and physical QNN/RPC evidence.
4. Run at least three clean fresh-process phone setup measurements per arm, using identical effective graphs/config/input and exact timing boundaries.
5. Produce and structurally validate an E2E WAV. Numerical and byte differences are descriptive, not execution blockers.
6. Commit only 0023 evidence and hand the commit to Pi; Alex owns dashboard ingestion.

See [`protocol/experiment-contract.json`](protocol/experiment-contract.json) and [`PLAN.md`](PLAN.md).
