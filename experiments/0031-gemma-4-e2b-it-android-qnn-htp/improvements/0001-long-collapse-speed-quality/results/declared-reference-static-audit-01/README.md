# Active reference defect: FP16 transport words decoded as integers

This bounded saved/static audit identifies a concrete defect in the **host reference**, not in QNN or the model. No full model or phone was replayed during the audit.

## The BW4 interpretation was supported

All 522 signed weight tensors use actual `BW_AXIS_SCALE_OFFSET`, bitwidth 4, offset 0. QAIRT's `QnnTypes.h` (lines 593–631) explicitly defines low-bit storage and effective-bit signed interpretation, even in an int8 container.

Independent comparisons used the hash-verified original float export, not QNN logits:

| Static weight check | Values checked | Documented BW4 result |
|---|---:|---|
| Language-model head, 1,024 output-channel samples | 1,572,864 | Exact float match; all requantized codes match |
| Layer-0 Q projection head 0, complete tensor | 393,216 | All codes match; max float error 1.49e−8 |
| PLE projection `val_42`, 1,024 channel samples | 1,572,864 | 1,572,863 codes match; clipping/rounding retained |

The head's float region matches the independently established `eb7ac2b1…146fc` hash. Correct OIHW→HWIO and FullyConnected transpose/channel-axis mappings were checked. Ignoring BW4 signed interpretation produces over 535,000 head sign errors in this sample. We did not switch encodings to fit the QNN result.

## The actual defect is FP16 static storage

All **30 static tensors declared `Float_16`** were returned by the IR reader and saved as NumPy **uint16 transport words**. Fifteen generated RMS gamma tensors contain **`0x3c00`**, the binary16 representation of **1.0**. The old reference's generic float decode numerically cast the uint16 array to F32, producing **15360.0** instead.

- **4,608 gamma values** were wrong; 4,608 zero bias words happened to remain zero.
- **15 RmsNorm consumers** are affected, first known consumer **operator 52, `rms_norm_node___413645`**.
- The saved operation trace confirms all 15 consumers ran in all 16 chunks: **240 affected operator invocations**.
- The saved host stderr contains FP16 overflow, invalid matmul/cast and divide-by-zero warnings. Finite final UINT16/F32 files did **not** establish finite or valid intermediates.

Independent Python IEEE-binary16 decoding and the SDK's `fp16_ieee_to_fp32_value` word-conversion path support reinterpretation, not numeric casting. An audit-only storage-normalized prototype was exercised through the actual reference loader, a preserved Reshape, RmsNorm and identity Cast in a **three-op synthetic graph**. The original result `[5608,11216,16832,22432]` became the expected half-precision normalized values `[0.365234375,0.73046875,1.095703125,1.4609375]`. True quantized UINT16 data and already-typed FP16 arrays remained unchanged.

This proves an active wrong-math path. It does not prove that this is the sole cause of every difference, that a corrected full run will match QNN, or anything about long-generation quality.

## Other checked contracts and remaining limits

Eleven bounded synthetic/static checks cover unsigned mask endpoints **0/65535 → −50/0**, the output grid, Convert quantization, FP16 ties/signed zero/subnormal behavior, RmsNorm axis/gamma/beta, Softmax axis 3, innermost MatMul/broadcasting, 1×1 NHWC/HWIO convolution, FullyConnected orientation, and own-cache global/SWA wrapping through 16 chunks with final 9 rows and untouched FP16 negative-zero slots.

All 6,893 operation shapes/topology were checked. There are no duplicate output writers. A separate **dormant** generality gap exists: the old helper treats non-preserved Cast like Convert, whereas QNN Cast ignores quantization parameters. All three actual Cast nodes here are FP16→FP16 identities, so that gap is not an active explanation for this result.

No matching QNN/reference intermediate activation values were saved. The first dynamic nonfinite tensor is not recoverable from the old timing/name trace. A corrected run must record the first unexpected nonfinite and stop rather than turn NaNs into valid-looking integer codes.

## Evidence and execution scope

The BW4 audit completed under **1 GiB / 1 CPU / no swap / 300 seconds** in 89.26 seconds. The initial ONNX `dims` property/call error is retained. Operator/cache checks and FP16 transport validation used separate bounded host-only units; the latter completed in 2.694 seconds / 527.3 MiB. All actual tensors/vectors and SDK material remain private; this packet contains hashes, metadata, authored tools and synthetic checks.

The failed reference is preserved with an additive [INVALID-REFERENCE notice](../paired-declared-policy-prefill-01/INVALID-REFERENCE.json). Pi separately authorized a tested storage correction and one corrected host-only reference, not an automatic replay. See [corrected-reference-storage-readiness-01](../corrected-reference-storage-readiness-01/README.md).
