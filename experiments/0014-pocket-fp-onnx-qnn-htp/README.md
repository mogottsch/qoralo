# 0014 — Pocket FP ONNX on QNN HTP

This experiment asks whether the exact working Pocket FP ONNX deployment from experiment 0012 can execute completely through ONNX Runtime's QNN HTP execution provider on the authorized Galaxy S23 Ultra.

## Result

**Blocked at the mandatory fail-closed host gate.** Static specialization made the text conditioner and flow step fully QNN-assignable, but the essential FlowLM main graph, Mimi encoder, and Mimi decoder retained CPU nodes. No phone run, HTP RTF, or HTP WAV was produced.

See [`RESULTS.md`](RESULTS.md) for the assignment table and exact blocker boundary. The working CPU result remains experiment 0012 with warm median RTF `0.630`.

## Claim boundaries

- “FP ONNX” describes the source graph tensors; it does not establish HTP arithmetic precision.
- Partial QNN assignment is not called full HTP.
- CPU fallback remained disabled during compatibility gates.
- No mixed route, quantization, calibration, or operator rewrite was performed.
- Experiment 0012 was not modified.
