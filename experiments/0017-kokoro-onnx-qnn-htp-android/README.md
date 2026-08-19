# Experiment 0017 — Kokoro exact-source ONNX QNN/HTP Android feasibility

## Status

**Complete with a bounded host-finalization blocker.** A narrow fixed-contract derivative was bit-identical to its source on patched ORT 1.27.1 CPU and reported complete QNN assignment in one partition (`1685/1685`, then `1821/1821`). Assignment did not become execution: the final fallback-disabled host session was kernel-OOM-killed after `28:01.52`, during `Graph Sequencing for Target` at 64%, before session finalization or inference. No output/profile evidence was produced and the phone was not accessed. See [`RESULTS.md`](RESULTS.md) and [`results/host-gate-checkpoint.json`](results/host-gate-checkpoint.json).

## Fixed route

- official source: `hexgrad/Kokoro-82M@f3ff3571791e39611d31c381e3a41a3af07b4987`;
- official model SHA-256: `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4`;
- exact-source-derived FP32 ONNX SHA-256: `d11a0dd7c4eb768e1f0ef03090c69b6761f55e37b9f196749349591c40be232b`;
- transcript SHA-256: `bec8bf482f4d816f0c95471c289a2607a7a169e33389b8b13e525214ec639461`;
- fixed input: tokens `[1,125]`, `af_heart` style row 123 `[1,256]`, speed `1.0`, seed `20260818`;
- fixed output: duration sum `304`, audio `[182400]` at 24 kHz;
- runtime: patched ORT `1.27.1`, QAIRT/QNN `2.49.0.260730`, HTP SoC model 43, one thread, CPU fallback disabled.

The source model, frontend, controlled export, host CPU fidelity, and successful CPU phone route are documented in [`../0013-kokoro-onnx-vs-executorch-android/`](../0013-kokoro-onnx-vs-executorch-android/). This follow-up neither changes nor relabels experiment 0013.

See [`protocol.json`](protocol.json) for frozen acceptance criteria, [`PLAN.md`](PLAN.md) for the gated procedure, and [`results/source-inventory.json`](results/source-inventory.json) for verified hashes.

## Conclusion

Experiment 0013's CPU route remains the proven Android reference. Experiment 0017 demonstrates compatibility/assignment potential but not a finalized session, host inference, physical HTP execution, numerical HTP fidelity, or acceleration. A larger host preparation environment or graph segmentation would require a new decision; neither was attempted here.
