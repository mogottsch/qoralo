# All48 persistent-state ranges — offline source/saved-tensor audit

**Saved data only: no model/weight load, model execution, compilation, QNN runtime call or phone access.** This audits the retained HistogramObserver QDQ metadata and five saved p0/p1 output bundles. It does not change the model, any encoding, the frozen tiny PTE, the diagnostic PTE or the physical baseline. Candidate changes remain hypotheses.

## Scope and provenance

The source is the already-retained32,499,235-byte graph JSON, SHA `2d879235c4d4a47643378e3ec3739bd587d4b0a68b23097b8ba64092ce20ad86`, recovered from its758,313-byte zstd file. **No model archive/weight member was opened.** Its original model route is Histogram QDQ archive `30799090…c492364` / diagnostic PTE `7f30be3d…ff3fea`, as bound by saved receipts, not newly read/model-loaded artifacts. These are not the physical MinMax baseline's encodings.

`metadata/metadata.json` maps all48 state inputs (logical indices3–50) to outputs1–48. Every direct input boundary has a unique explicit per-tensor Q/DQ domain; every output is a matching Q/DQ pair. Quantizer/dequantizer nodes, numerical consumers, immediate output-producer branches and unknown/absent reasons are retained. The18 additional `expand_as.other` references supply **shape only**, not state values or extra quantization branches. Tests cover multiple, unequal, dynamic, missing and unquantized cases even though the actual48 boundary domains are resolved. This is not a complete native/finalized-graph encoding map.

Graph logical tensor metadata uses serialized FLOAT32 dtype7; Q/DQ integer carrier4 is INT32 with codes0..65535. Neither is the native QNN dtype identifier or the model's W4 weight precision. Exact FP32 scale bits/zero points and decoded endpoints are recorded.

### Transport matters

| State kind | Count | Input → output shape | Actual saved runner transport |
|---|---:|---|---|
| Recurrent |18| `[1,16,128,128]` → same | Clone-replace |
| Convolution history |18| `[1,6144,1,4]` → same | Clone-replace |
| Key update |6| `[1,2,256,4095]` → `[1,2,256,1]` | Insert new token at source position, axis3 |
| Value update |6| `[1,2,4095,256]` → `[1,2,1,256]` | Insert new token at source position, axis2 |

K/V outputs are **not complete cache replacements or rolling-cache shifts**. The original state-transport source SHA `f2a38866…9ee58f` matches the retained trajectory binding. Exact source excerpts and full shape/dtype metadata are retained. Clipped-example coordinates include both returned-tensor indices and mapped next-input coordinates. Only newly returned values were inspected: old/zero-filled4095-position cache contents were **not loaded or counted**. p0 outputs project to p1 inputs; p1 outputs project to a hypothetical next call, not a replay of p1.

## Theoretical compatibility

[`STATE_RANGES.md`](STATE_RANGES.md) gives every exact input/output domain. Fifteen pairs have identical encodings;19 output decoded intervals lie wholly inside their next-input intervals. Therefore29 have an endpoint overhang, but only27 would clip any of the65536 decoded output-grid codes under the next-input scalar quantizer.

| Kind | States | Identical domains | Output interval contained | Output code grid can clip |
|---|---:|---:|---:|---:|
| Recurrent |18|6|9|8|
| Convolution |18|9|10|7|
| K updates |6|0|0|6|
| V updates |6|0|0|6|

State5 (recurrent layer5) and state45 (convolution layer21) have a decoded endpoint overhang but **no code clipping in the enumerated output grid**. This is the same distinction between decoded endpoints and actual rounded-code clipping that matters in the tiny sweep. The grid is a theoretical set of representable outputs, **not an observed distribution or clipping probability**. No grid is treated as a model forward.

## Observed saved values, then hypothetical next-input QDQ

Exactly five bounded≈21.9MB **saved output** bundles were deserialized with `torch.load(..., weights_only=True, map_location='cpu')`. No checkpoint/model/cache archive was substituted. All returned state values are finite. NumPy FP32 multiplication, round-to-nearest-even, zero-point addition, clamp and dequantization were checked against the existing scalar-stage implementation; comparisons use FP64 differences. These calculations do **not observe how QNN quantizes a next call**.

| Saved output source | States with would-clip values | Would-clip values | State indices |
|---|---:|---:|---|
| QDQp0 |8|11|3,7,11,24,26,27,31,34|
| QNNp0 |8|11|3,7,11,24,26,27,31,34|
| Controlled QDQp1, QDQp0-origin inputs |1|1|26|
| Controlled QNNp1, same QDQp0-origin inputs |3|3|24,26,34|
| Own-state QNNp1, QNNp0-origin inputs |3|3|24,26,34|

The p0 cases comprise **three convolution, three key and two value interfaces**. No recurrent p0/p1 return value predicts code clipping, despite eight recurrent interfaces having theoretical grid exposure. This does not rule out recurrent rounding effects or later clipping.

Examples from saved QDQp0, before hypothetical next-input quantization:

- K layer3/state3:10.028990745544434 exceeds input maximum6.853979110717773.
- K layer7/state7:−15.016722679138184 is below input minimum−8.453450202941895.
- V layer7/state31:15.535654067993164 exceeds input maximum9.832738876342773.
- Conv layer0/state24: the known23.721895217895508 value exceeds input maximum22.131834030151367.
- Controlled QDQp1's sole would-clip value is conv layer2/state26, channel5588/slot2:14.044342041015625 vs input maximum14.043567657470703 (unbounded code65536).

These are boundary-compatibility observations, **not measured clipping inside the SDK and not attribution of logit drift**. The controlled p1 pair and own-state p1 result have different state origins and are kept separate. No historical p1 full-replay state-byte identity is newly asserted. QNN saved returns include3/2/3 values outside their own serialized output decoded intervals at p0/controlled-p1/own-p1; these endpoint differences are retained separately, not mislabelled as next-input code clipping.

[`OBSERVED_VALUES.md`](OBSERVED_VALUES.md) gives all48 states across the five samples. Per-state JSON retains shape, complete FP32 tensor hash, finite/min/max/signed-zero counts, own-output-domain coverage, per-input-quantizer counts and every clipped example here. `observations/theory-grid.json` retains exhaustive code-grid results.

## Retention, validation and next gate

`tools/audit_persistent_state_ranges.py` has metadata and saved-output observation modes only. Eleven source/NumPy tests passed; metadata took0.403s and five-bundle observation2.203s under separate guards. There were **zero model loads/forwards, zero native loads/forwards and zero compiles**. Tensor deserialization count5 is recorded separately. No ExecuTorch modules were imported.

**44 default saved-data contract tests also passed** in2.478s (2.603s guarded), covering all48 mappings/statuses, insertion shapes/axes, theoretical/observed totals, conv anchors and complete QDQp0 byte recovery. They perform no additional tensor-bundle deserialization. All four supervised workers were reaped, their groups absent and owned scratch empty. Original118/48/61 firstcase/readiness/sweep hashes and exact file sets are unchanged; no evidence bytecode cache appeared. The earlier209-test full suite was not rerun because this lane deliberately remained source/NumPy/saved-data only.

The already-durable four QNN/p1 bundles remain at their original paths. This result additionally retains the complete QDQp0 bundle losslessly as `observations/qdq-p0.outputs.pt.zst`:4,244,370 bytes, recovering21,879,364 bytes/SHA `a471368c8b319013c6b0827afb172fd69aabbc11f12bf7de90556af79a7c8bf2`. Its original LOCAL-ONLY copy and all protected model/PTE/context/state data remain untouched; do not clean them during migration. Model identities are historical receipt pins, not hashes recomputed by opening large model artifacts.

Review [`ALIGNMENT_HYPOTHESES.md`](ALIGNMENT_HYPOTHESES.md) before any future change. No alignment, calibration, recompilation, native test or physical work is released by this audit. The app retains the first physical slot.
