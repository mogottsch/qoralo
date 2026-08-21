# Experiment 0017 — Kokoro exact-source ONNX QNN/HTP Android feasibility

## Current status

**Canonical-v2 host gate externally interrupted after 15 of 18 completed stages; phone forbidden.**

The current comparable route uses the exact 226-byte canonical-v2 transcript, the pinned official Kokoro 0.9.4 American-English frontend, and a new fixed FP32 ONNX derivative. Its CPU gates are complete:

- transcript SHA `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`;
- tokens `[1,235]`, SHA `9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280`;
- `af_heart` style row 232, SHA `8acaca07623d98a1085f6b182fb997d715dd1d67862e350567e6d9b1bc8ec71b`;
- duration `[235]`, sum `602`, SHA `99494f78e82ad3d8b506d5b0a5c4edde6292c6a52ca54a47b50f109fa534480c`;
- audio `[361200]` at 24 kHz (`15.05 s`);
- controlled FP32 ONNX SHA `26120b192f2ad7567c6c1215ccbcf374d1946460c4589c1098941ab15e43aa73`;
- QNN compatibility graph SHA `0c7ce33eac4c6664819a61e48469a9cf43ad403d852b01af5517a13c7ed2a066`;
- 18 deterministic stage models cover all 1,685 source nodes;
- separate-process CPU stage recomposition is bit-exact to the complete compatibility graph.

In the interrupted fallback-disabled host QNN attempt, stages 1–15 finalized and ran their real upstream tensors. Every completed ORT profile had one `QNNExecutionProvider` event and zero CPU-provider events. A WSL shutdown/restart interrupted stage 16 during `Graph Sequencing for Target` at 12%; stage 16 did not finalize or run, stages 17–18 were not attempted, and no final canonical QNN audio exists. This is an external interruption, not a technical stage-16 failure or OOM.

See:

- [`protocol-canonical-v2-stage-decomposition.json`](protocol-canonical-v2-stage-decomposition.json) — frozen canonical contract and all stage hashes/I/O;
- [`results/canonical-v2-host-qnn-interrupted-checkpoint.json`](results/canonical-v2-host-qnn-interrupted-checkpoint.json) — exact interrupted attempt;
- [`REPRODUCING.md`](REPRODUCING.md) — clean-machine reconstruction and restart instructions;
- [`RESULTS.md`](RESULTS.md) — historical and canonical evidence with claim boundaries.

## Historical fixed-fixture route

The original 116-byte experiment-0013-derived route remains preserved and is **not canonical v2**. Its monolithic QNN session was kernel-OOM-killed during graph sequencing. The later authorized stage decomposition proved that all 18 host stages could finalize and execute with QNN assignment, but its duration changed from 304 to 305 and its final float audio was invalid (`absolute peak 94848`, 182,236 samples with `abs >= 1`). Canonical machine evidence is [`results/staged-host-qnn-feasibility.json`](results/staged-host-qnn-feasibility.json).

That result is bounded host feasibility/debug evidence only. It is not physical phone HTP proof, valid listening material, or a verdict on Kokoro.

## Source and runtime boundary

Both routes retain:

- official source `hexgrad/Kokoro-82M@f3ff3571791e39611d31c381e3a41a3af07b4987`;
- official model SHA `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4`;
- official voice SHA `0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff`;
- seed `20260818`, speed `1.0`, no quantization;
- patched ONNX Runtime `1.27.1`, QAIRT/QNN `2.49.0.260730`, HTP SoC model 43, one thread, CPU fallback disabled.

Large models, fixtures, tensors, profiles, compiler logs, binaries, and audio remain ignored under `work/` and `.local/`; their hashes and regeneration commands are committed.

## Claim discipline

- Host QNN assignment/execution is not physical HTP phone proof.
- Physical execution, provider assignment, numerical/acoustic fidelity, latency, memory, and listening are independent claims.
- CPU preprocessing/orchestration/tensor transport/WAV encoding must be disclosed separately.
- The canonical source ONNX passes the named phase-tolerant acoustic policy but fails the separate strict `.999/.01` waveform screen; neither is a listening verdict.
- Moritz's accepted experiment-0013 CPU sample is scoped to that old route and does not transfer to canonical v2.
- No canonical QNN sample exists; its listening status is `not_reviewed`/not yet applicable.
- No phone access is allowed until a fresh complete 18/18 canonical host record passes, including structurally valid final audio.
