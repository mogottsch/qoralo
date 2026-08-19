# Pocket FP ONNX → QNN HTP results

## Clear outcome

**The working Pocket ONNX CPU model did not pass the mandatory full-HTP compatibility gate.**

This experiment therefore did not run on the phone, did not measure an HTP RTF, and did not generate an HTP audio sample. Publishing the latency of a partially delegated or CPU-fallback route as “HTP performance” would be misleading.

The successful CPU result remains unchanged in [`../0012-pocket-onnx-vs-executorch-android/RESULTS.md`](../0012-pocket-onnx-vs-executorch-android/RESULTS.md): warm median RTF `0.630`.

## What was tested

The test reused and hash-verified the exact five unquantized floating-point ONNX graphs from experiment 0012. It did not download or substitute another Pocket model.

The frozen text, Bria reference audio, seed, temperature, and one-flow-step setting were retained. Actual runtime call shapes were captured, then eight concrete graph variants were produced for:

- 26-token text conditioning
- one flow step
- 240,000-sample (10-second) voice encoding
- FlowLM voice prefill, text prefill, and one-frame autoregressive calls
- 12-frame Mimi decode chunks and the 6-frame tail

Each variant was constant-folded with ONNX Runtime 1.27.1 and tested through QAIRT/QNN 2.49 with:

```text
session.disable_cpu_ep_fallback = 1
```

This makes the gate fail closed: any node left on the CPU rejects the session.

## Assignment results after static specialization

| Required variant | QNN nodes | Total nodes | Partitions | Full QNN assignment |
|---|---:|---:|---:|---|
| Text conditioner, 26 tokens | 1 | 1 | 1 | **Yes** |
| Flow step | 167 | 167 | 1 | **Yes** |
| FlowLM voice prefill | 400 | 685 | 15 | **No** |
| FlowLM text prefill | 400 | 685 | 15 | **No** |
| FlowLM autoregressive step | 396 | 680 | 15 | **No** |
| Mimi encoder, 10-second reference | 179 | 184 | 5 | **No** |
| Mimi decoder, 12 frames | 294 | 335 | 3 | **No** |
| Mimi decoder, 6-frame tail | 294 | 335 | 3 | **No** |

Only two of the required boundaries fully assigned. Pocket synthesis cannot complete without FlowLM main, Mimi encoder, and Mimi decoder.

## Exact blockers

### FlowLM main

This is not a single unsupported activation. More than 280 optimized nodes remain outside QNN in each required variant. The graph contains runtime shape construction around zero-length recurrent-state tensors, `IsNaN` sentinel logic, `SkipLayerNormalization`, unresolved tensor shapes, and multiple QNN partitions.

The current export deliberately represents recurrent caches and empty sequences as explicit tensors, including zero-length tensors. Making this graph QNN-compatible requires a QNN-oriented state and attention re-export rather than a small I/O-shape edit.

### Mimi encoder

The static encoder is close but not complete: 179 of 184 optimized nodes assign. Remaining preparation failures include `IsNaN`, `Erf`/GELU, and an invalid zero-only padding value. A rewrite would need CPU equivalence proof before it could be used.

### Mimi decoder

The decoder assigns 294 of 335 nodes across three partitions. Remaining nodes include `IsNaN` checks and state-output `Identity` nodes. Both the regular and tail decode variants fail with CPU fallback disabled.

## Why no phone run or sample exists

The experiment protocol required every neural component and every shape variant to pass the host QNN gate before touching the phone. Since essential components failed:

- no phone lock was needed
- no files were staged on the S23
- no mixed CPU/HTP benchmark was run
- no HTP latency or RTF exists
- no HTP-generated WAV exists

This avoids turning partial assignment into an unsupported “HTP backend works” claim.

## What would be needed next

Making Pocket run fully on HTP would require a larger conversion project:

1. Re-export FlowLM attention and recurrent state without zero-length shape operations or NaN sentinel control flow.
2. Replace unsupported fused/activation operations with audited QNN-safe equivalents.
3. Normalize Mimi state outputs so they do not require CPU `Identity` nodes.
4. Prove component and recurrent-step equivalence against the working FP ONNX model.
5. Repeat the fallback-disabled host gate before any phone benchmark.

That is substantially broader than reusing the existing ONNX files with the QNN provider. Quantization could be evaluated separately, but it was not silently introduced here.

Machine-readable evidence: [`results/host-gate.json`](results/host-gate.json).
