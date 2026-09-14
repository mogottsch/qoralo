# Minimal same-grid ReduceMean and epsilon-Add controls

**Host-only preparation; no phone execution grant is implied.** The preceding chain results have sound name/ID/shape/file bindings, but native buffer independence was not captured and the reviewed docs do not settle the low-code discrepancy. This bundle contains at most two requested controls, each a **single operator with a single output**:

| Control | Actual shape/grids | Authored row patterns | Literal reference codes |
|---|---|---|---|
| `mean_edge` | `[1,128,1536]` squared-grid UF16 → `[1,128,1]` mean-grid UF16; ReduceMean axis 2, keep-dims | all zero; one code 1 and 1,535 zeros; uniform code 1; uniform code 20 | 0, 0, 22, 434 |
| `epsilon_add` | `[1,128,1]` mean-grid UF16 + exact epsilon scalar code 655 → same output grid | codes 0, 1, 22, 434 | 0, 1, 22, 434 |

Each pattern repeats 32 times. The expected values are comparison descriptors, **not an adopted HTP rounding rule**. No Power, complete normalization chain, learned gamma/weight, actual model input, full reference or LLM is included. No epsilon/mean floor, arbitrary clamp or NaN repair is added.

## Frozen artifacts

- Context: **74,776 bytes**, SHA-256 **`7671cb643fc86d9a54e933de4f11889cc5204cb9616cb683eccb8782ae1badfc`**.
- Stage: **8 files / 26,212,392 bytes**, manifest **`f860ed18df22270801551be16499ecb9c2a3f10351f4b84d2da3c5bba7bc60b2`**.
- Exactly one requested operation per DLC, with actual attrs/scalar codes/grids verified; compiled context backend 6 / SoC 43 and both single-input/single-output UF16 flat-buffer interfaces verified.
- Only 512 raw output bytes expected.

One finite authored calibration sample per tiny graph prevents QAIRT's forced float-fallback-without-data mode. All encodings are supplied and verified. Host conversion/context preparation completed in **5.953 seconds / 1 GiB / no swap** under 4 GiB / 1 GiB swap / 2 CPU / 600-second limits. No full-model or phone execution occurred.

## Future execution envelope

A source-bound adapter reuses the tested two-case controller. Each graph is explicitly selected in its own `--num_inferences 1` invocation; the other input-list position is `__`. One parent holds the full phone lease through staging, both cases, final raw pull/postflight and independent cleanup. PID/starttime/executable/NUL-argv identities are separate per case; a first failure or newly active job blocks the second without retry.

The envelope remains **90 seconds per process / AS12 GiB / actual FSIZE8 MiB readback / shared-buffer HTP route / 16 MiB polled evidence budget**. Fresh scheduled authorization, APK/job/playback/resource checks and the full lease are required. No Power/chain replay or CPU fallback is requested.

The goal is to distinguish standalone operator behavior from chain optimization/exposure effects—not to force agreement with full QNN logits or establish the long-generation repetition cause.
