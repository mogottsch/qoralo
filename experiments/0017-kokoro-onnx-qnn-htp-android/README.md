# Experiment 0017 — Kokoro exact-source ONNX QNN/HTP Android feasibility

## Current status

**Canonical-v2 completed all 18 fallback-disabled host QNN stages with zero CPU provider events, but final audio is structurally invalid. The route is host-executed, audio-invalid, and phone-ineligible. No rerun, fix, or phone work is authorized in this experiment.**

The current comparable route uses the exact 226-byte canonical-v2 transcript, the pinned official Kokoro 0.9.4 American-English frontend, and a new fixed FP32 ONNX derivative. Its CPU gates are complete:

- transcript SHA `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`;
- tokens `[1,235]`, SHA `9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280`;
- `af_heart` style row 232, SHA `8acaca07623d98a1085f6b182fb997d715dd1d67862e350567e6d9b1bc8ec71b`;
- duration `[235]`, sum `602`, SHA `99494f78e82ad3d8b506d5b0a5c4edde6292c6a52ca54a47b50f109fa534480c`;
- audio `[361200]` at 24 kHz (`15.05 s`);
- controlled FP32 ONNX SHA `26120b192f2ad7567c6c1215ccbcf374d1946460c4589c1098941ab15e43aa73`;
- QNN compatibility graph SHA `0c7ce33eac4c6664819a61e48469a9cf43ad403d852b01af5517a13c7ed2a066`;
- 18 deterministic stage models cover all 1,685 source nodes;
- historical WSL separate-process CPU recomposition is bit-exact to the complete compatibility graph at audio SHA `fb8895f6bb9c2ee94dd18f8b9bfdc6f1b36f99e01c40f5806bdd71076acd6d36`;
- two clean native-host/Ubuntu 22 reconstruction runs are stage-for-stage bit-exact to each other and to a fresh complete-graph run at audio SHA `56ce6a24498d8db270c0a34eb1fe0a87b762a0fb8121616790f03391c132aa3c`; duration stays exact and the audio is structurally valid;
- cross-environment bit reproducibility is unproven: divergence is established at stage 1 by hashes, while historical value-based deltas are unavailable because the ignored WSL payload no longer exists.

In the interrupted fallback-disabled host QNN attempt, stages 1–15 finalized and ran their real upstream tensors. Every completed ORT profile had one `QNNExecutionProvider` event and zero CPU-provider events. A WSL shutdown/restart interrupted stage 16 during `Graph Sequencing for Target` at 12%; stage 16 did not finalize or run, stages 17–18 were not attempted, and no final canonical QNN audio exists. This is an external interruption, not a technical stage-16 failure or OOM.

A later crossed-message launch was operator-cancelled before Docker creation: missing host `/usr/bin/time` prevented the Docker command, and no QNN session/compiler/stage began. The host script now treats GNU `time` as optional while retaining the memory monitor. This event is not a QNN failure.

The approved `canonical-v2-native-rerun-1` completed stages 1–12 with exactly one QNN provider event and zero CPU events per stage. Disclosed experiment-0023 QNN work overlapped stages 7–10, contaminating only their timing/resource isolation under the committed eligibility policy. The run was then operator-stopped during stage 13 because that policy was initially interpreted too broadly; stage 13 did not finalize or run. This is an incomplete operator-stopped record, not a QNN correctness/provider/compiler failure. It was not resumed.

The fresh locked `canonical-v2-native-rerun-2` completed all 18 stages: 18 `QNNExecutionProvider` events, zero CPU events, and exit code 0. The duration tensor changed from CPU sum 602 to 605 at five indices. Final float audio has 361,200 finite samples but peak `87296.0078`, RMS `61982.4965`, and 360,921 samples with `abs >= 1`; audio SHA is `2992f71911b8af233841af4058e8218e8705c987a51643d1d709d96545b60a08`. The structural gate fails. Stage 1 is the first non-bit-exact output; stage 4 `duration_alignment` is the first discrete/material contract divergence. The evidence localizes divergence but does not establish a root cause.

See:

- [`protocol-canonical-v2-stage-decomposition.json`](protocol-canonical-v2-stage-decomposition.json) — original frozen canonical contract and all stage hashes/I/O;
- [`protocol-canonical-v2-reconstruction-baseline.json`](protocol-canonical-v2-reconstruction-baseline.json) — prospective same-current-environment comparison policy frozen before new QNN output;
- [`results/canonical-v2-cpu-reconstruction-baseline.json`](results/canonical-v2-cpu-reconstruction-baseline.json) — two-run determinism, complete-graph equality, identities, structural metrics, and historical null-reason boundary;
- [`results/canonical-v2-host-qnn-interrupted-checkpoint.json`](results/canonical-v2-host-qnn-interrupted-checkpoint.json) — exact interrupted WSL attempt;
- [`results/canonical-v2-rerun-operator-cancelled-pre-gate.json`](results/canonical-v2-rerun-operator-cancelled-pre-gate.json) — exact no-Docker/no-QNN operator-cancelled boundary;
- [`results/canonical-v2-native-rerun-1-operator-stopped.json`](results/canonical-v2-native-rerun-1-operator-stopped.json) — 12-stage provider/output evidence, exact stages 7–10 timing contamination, partial stage 13, and corrected policy/stop boundary;
- [`results/canonical-v2-host-qnn-gate.json`](results/canonical-v2-host-qnn-gate.json) — terminal 18/18 execution/provider proof, per-stage CPU comparisons, divergence boundary, resource/lock evidence, invalid structure, and phone-ineligible decision;
- [`REPRODUCING.md`](REPRODUCING.md) — clean-machine reconstruction and terminal-summary instructions;
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
- No valid canonical QNN WAV/listening sample exists; the invalid float output is not listening material.
- The next QNN summary must compare against the frozen current-environment `56ce6a…` CPU stage checkpoint; historical `fb8895…` remains separate WSL evidence.
- Every real host run must hold `artifacts/locks/heavy-ram.lock` for its full lifetime; this is infrastructure serialization, not a model eligibility field.
- The 18/18 execution/provider gate passed, but the structural audio gate failed; phone eligibility is false.
- Do not rerun, change graphs/runtime, attempt fixes, create a WAV, or access the phone in experiment 0017 unless Moritz explicitly opens a new experiment/scope.
