# 0014 — Pocket ONNX through QNN HTP

This experiment began as a fail-closed compatibility screen for the exact Pocket FP ONNX graphs from experiment 0012 and was later reopened for deeper QNN-oriented conversion.

## Final result

Two complete observed text-to-WAV neural paths ran with:

- CPU fallback disabled
- zero CPU provider events
- one-for-one QNN provider and physical RPC/accelerator/cycle/HVX events
- valid, non-silent, unclipped WAV output

That is **technical QNN-only execution evidence for the observed paths**. It is not a deployment success.

Moritz blind-listened to the FP-QNN sample, calibrated-INT16 QNN sample, and 0012 CPU comparator on 2026-08-19 and rejected all three as unusable. The CPU sample repeated “takakakakakakakaka”; both QNN samples were unintelligible mumbling.

See [`RESULTS.md`](RESULTS.md) for the host transformations, physical assignment proof, timing, memory semantics, temperature-protocol correction, samples, and claim boundaries.

Machine-readable evidence:

- [`results/full-qnn-continuation.json`](results/full-qnn-continuation.json)
- [`results/blind-listening.json`](results/blind-listening.json)
- [`results/temperature-drift.json`](results/temperature-drift.json)
- [`results/host-gate.json`](results/host-gate.json) — preserved original unchanged-graph screen

## Claim boundary

CPU preprocessing/orchestration and WAV encoding are stated separately. Decoder-6 passed the fallback-disabled host gate but was not required or physically invoked by the final 91- and 100-frame samples. The QNN-only observed-path claim is bounded to the neural calls actually used by those samples, never generalized to every possible shape or input.

Android stage assembly is captured in [`tools/prepare_android_stage.sh`](tools/prepare_android_stage.sh); the locked phone protocol is [`device/run_full_qnn_proof.sh`](device/run_full_qnn_proof.sh).

**Deployment recommendation: no.**
