# Experiment 0017 plan — exact-source Kokoro ONNX on QNN HTP

## Outcome

The gated procedure stopped before phone access. The CPU-equivalent compatibility derivative reached complete QNN capability assignment, but the required fallback-disabled host session was kernel-OOM-killed during graph sequencing at 64%, before finalization or inference. See [`RESULTS.md`](RESULTS.md).

## Objective

Start from experiment 0013's exact-source-derived, unquantized FP32 fixed-contract ONNX model and determine whether the complete model can run through ONNX Runtime's QNN EP on the authorized SM8550 HTP with CPU fallback disabled.

The frozen machine-readable contract is [`protocol.json`](protocol.json). Experiment 0013 remains the source/provenance and CPU-oracle record; it is not modified.

## Gates

1. **Inventory** — verify the 0013 commit, ONNX byte count/hash, official source hashes, transcript, tokens, style, speed, deterministic phase/noise representation, duration, and CPU audio oracles.
2. **Exact graph host gate** — use the exact patched ORT 1.27.1/QNN 2.49 runtime proven in experiment 0010. Set `session.disable_cpu_ep_fallback=1`, `offload_graph_io_quantization=0`, and SoC model 43. Retain capability and QNN logs.
3. **Bounded compatibility work, only if needed** — identify exact unsupported nodes. A standard-operator rewrite may target only those nodes or fixed-contract control flow, must retain learned tensors, and must first pass the prospective same-runtime CPU equivalence gate. Quantization, calibration, custom QNN operators, and broad architecture surgery require a new decision from Moritz.
4. **Full host gate** — session creation and fixed-input inference must succeed with all optimized nodes on QNN and no CPU-provider node events. Otherwise stop before phone access.
5. **Phone run, only if host-eligible** — acquire both phone locks; verify serial/model/SoC/ABI; stage to a unique experiment directory; run one first and five warm generations; retain ORT provider and detailed QNN physical RPC/accelerator/cycle/HVX evidence; collect timing, process high-water memory, output tensors, and WAV.
6. **Fidelity and cleanup** — check exact duration/shape, structurally valid audio, the predeclared phase-tolerant acoustic policy against both 0013 references, and descriptive waveform metrics. Remove every staged/app artifact, verify absence, and release both locks.

## Claim discipline

- QNN assignment is not physical HTP proof.
- Source FP32 tensors do not establish HTP arithmetic precision.
- Mixed fallback is never full HTP.
- Experiment 0013's failed preliminary `.999/.01` waveform screen remains immutable.
- Physical execution, fidelity, performance, memory, and listening evidence are separate claims.
