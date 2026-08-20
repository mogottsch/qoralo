# 0016 — Pocket ONNX mixed QNN HTP + CPU on Android

This experiment measures Moritz's explicitly authorized CPU-fallback route for the exact technically executing Pocket FP ONNX graphs from experiment 0012. Experiment 0012's retained CPU sample was later rejected by Moritz in blind listening; “working” here must not be used as a quality label.

## Result

**The route completed text-to-WAV and physically used HTP, but it was slower per generated audio second, changed the output, and was rejected in listening for the exact retained sample.** Moritz described SHA `6cd3a98fb821ad76b0c0ad55a20f910da7be9d3058e511ff807b4a4f694aa45f` as “takataktaka.” This is a route/sample-only verdict, not a rejection of Pocket TTS as a family.

- Hybrid warm median RTF: **`1.003`**
- CPU-only warm median RTF: **`0.630`**
- Hybrid regression: **59.1%**
- Hybrid output: 3.84 s / 48 latent frames
- CPU output: 6.24 s / 78 latent frames
- Hybrid provider events: 45,117 CPU and 1,515 QNN

See [`RESULTS.md`](RESULTS.md) for the full provider table, physical HTP evidence, audio path/hash, and fidelity comparison.

## Boundaries

- This is always labeled mixed/hybrid, never full HTP.
- The exact 0012 ONNX graphs and voice were reused unchanged by verified hash.
- CPU fallback was intentionally enabled.
- No quantization, calibration, or operator rewrite was performed.
- Instrumented physical-proof timing is kept separate from the unprofiled benchmark.
- FP source tensors do not prove internal FP HTP arithmetic.
- Moritz rejected the exact hybrid sample as “takataktaka.” The verdict remains bound to this route and SHA; the separate 0012 CPU rejection is also sample-specific, and neither is generalized to Pocket TTS as a family.
