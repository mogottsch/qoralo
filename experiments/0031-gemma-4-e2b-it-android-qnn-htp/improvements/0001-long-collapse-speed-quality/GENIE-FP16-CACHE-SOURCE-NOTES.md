# Genie FP16 global-value caches: source rationale and remaining risks

The context in `results/global-value-fp16-context-attempt-01/` compiled successfully and passed official metadata checks. This note does **not** establish runtime compatibility, fidelity, quality or physical neural placement.

## What is bound

The new context is 1,186,430,976 bytes, SHA-256 `1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8`. It is 61,440 bytes larger than the accepted baseline.

The exact accepted compiler script (`bda9216`, source SHA `cf997a64…72a67b`) was executed without source edits. Only the reviewed DLC selection/hashes and fresh cache/scratch paths were substituted. A read-only observer captured the options: HTP, SM8550/soc43, v73, unsigned PD, weight sharing, both original graph aliases, O3 and `fp16_relaxed_precision=0`. The original default recipe was executed, not replaced with inferred compiler settings.

Official `qnn-context-binary-utility` metadata confirms:

- backend 6 / SM8550, build `v2.49.40.260810104044`;
- AR1 and AR128 each retain 38 inputs / 31 outputs;
- only the three global value-cache inputs/outputs become FP16;
- all other public names, shapes, positional/SWA bindings and active quantization remain unchanged;
- all 30 four-way cache contracts match;
- **all 120 cache tensor boundaries are flat buffers**, not NativeKV/HMX cache layout.

Raw metadata, baseline metadata, source-file hashes/line ranges, compiler options and logs are retained with the result. The weight-sharing/HMX weight-kernel markers must not be confused with NativeKV cache layout.

## Source-backed rationale

The inspected QAIRT 2.49.40 Genie sources are hash-bound in `raw/genie-fp16-source-check.json`.

| Source | Observation |
|---|---|
| `qnn-api/qnn-utils.cpp:119–158` | Nonquantized tensors receive a `(scale, offset)=(0,0)` placeholder. Float cache matching uses this rather than inactive QNN quantization-union contents. |
| `qnn-htp/nsp-model.cpp:1017–1068` | Validation compares matching cache aliases' quantization parameters across inputs/outputs/variants. The separate metadata gate also checks actual datatypes and shapes. |
| `KVCache/kvmanager.cpp:39–98` | Cache-group storage width and quantized/clear mode are derived from the **key** tensor. Flat buffers select SmartMask. |
| `KVCache/smart-mask.cpp:19–152` | Ordinary clear/update operations use storage-width-aware filling and raw byte copies. The inspected normal update/move path does not scale values with `value_quant`. |

Here keys remain quantized uint16. The group clear pattern is therefore `0x8000`, also used for FP16 values. It represents **negative zero** in IEEE FP16. That is a bit-interpretation observation, not proof of equivalent end-to-end semantics or long-output fidelity.

## Paths that must not be assumed supported

- **NativeKV:** `native-kv.cpp:18–25` explicitly accepts only quantized uint8. It is not selected or claimed; compiled cache metadata must remain flat-buffer.
- **Cache dump/spec/export:** `kvmanager.cpp` uses key-derived UINT8/UINT16 file/spec labels and exports value scales/offsets. Those representations must not be generalized to mixed quantized-key/FP16-value state.
- **Quant-dependent value fill:** `smart-mask.cpp:407–427` uses `-value_quant.offset` for an out-of-range-head dump fill. The FP16 placeholder offset of zero produces positive-zero bits, unlike the key-derived negative-zero clear pattern. Both are numerical zero but are not bit-identical. This API was not exercised.
- **Shipped-runtime correspondence:** SDK example source and successful compilation are not proof that every relevant shipped Genie runtime path has equivalent semantics. No runtime reset, graph execution or output test occurred for this context.

## Unsupported status and performance limits

The requested HTP compiler accepted both graphs. An exhaustive unsupported-operator count remains **null**: the accepted compiler API can suppress native stdout around context generation, and this run was not repeated just to obtain optional logs. The bootstrap architecture-default warning remains in raw logs; it is not a CPU-provider observation.

The increased AR128 Convert/operator counts and floating-precision warnings from the DLC milestone remain relevant. No speed gain is established. Physical CPU-free neural placement, runtime loading, fidelity and long-output quality remain unmeasured and require separately reviewed steps. No phone work is authorized by this note.
