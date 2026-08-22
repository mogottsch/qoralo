# Experiment 0023 — Supertonic QNN precompiled-context startup

**Status: all four accepted Supertonic components passed functional host QNN EPContext generation and source-unavailable reload. Current timing is explicitly excluded because the run overlapped experiment 0017. QNN/compiler/phone work is paused until Pi/Jens clears the serialized host run.**

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

## Timing exclusion and coordination incident

The host wave overlapped experiment 0017's serialized QNN run before its owner replied to the coordination request. The overlap was disclosed to Jens, Pi and Ben. Exact windows are committed in the functional result.

Therefore **none of the current setup, execution, ratio or resource observations are benchmark evidence**. They establish mechanism and functional reload only. After explicit clearance, the source and context arms must be rerun without any concurrent QNN/HtpPrepare work, with at least three fresh processes per arm. No performance or setup-reduction claim is made at this checkpoint.

## Next gates

1. Wait for explicit Pi/Jens clearance.
2. Run a clean serialized host/phone eligibility pass as needed; do not reuse the excluded timing observations.
3. Build the matched E2E runner for source and context arms.
4. On the authorized Galaxy S23 Ultra, prove all four neural sessions with fallback disabled and physical QNN/RPC evidence.
5. Run at least three clean fresh-process cold setup measurements per arm, using identical effective graphs/config/input and exact timing boundaries.
6. Produce and structurally validate an E2E WAV. Numerical and byte differences are descriptive, not execution blockers.
7. Commit only 0023 evidence and hand the commit to Pi; Alex owns dashboard ingestion.

See [`protocol/experiment-contract.json`](protocol/experiment-contract.json) and [`PLAN.md`](PLAN.md).
