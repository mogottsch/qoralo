# Tiny convolution-history harness readiness

**Source + tiny CPU-reference preparation only. No QNN import, compile or runtime, no full-model load, and no phone access.**

The three weight-free variants are implemented in `tools/conv_history_probe.py`. Capture hooks are in `tools/conv_history_probe_hooks.py`; their compiled/runtime interfaces were tested using explicitly labelled mocks. There is no real QNN adapter or compile/runtime CLI in this release.

## Exact variants and inputs

There are **three encoding domains**, not three Q/DQ pairs. The full chain uses **four pairs**: history, projection, concat, output. The projection uses the output domain, matching Q/DQ66/218 in the audited source graph.

| Variant | History | Projection | Concat | Output | Q/DQ pairs |
|---|---|---|---|---|---:|
| `fullchain` | input domain | output domain | concat domain | output domain | **4** |
| `outputonly` | none | none | none | output domain | **1** |
| `aligned` | output domain | output domain | output domain | output domain | **4** |

The exact domains are:

| Domain | Scale | Zero point | Code range / carrier |
|---|---:|---:|---|
| Input | 0.0007933978922665119 | 37640 | 0–65535 / INT32 |
| Concat | 0.0009200899512507021 | 32457 | 0–65535 / INT32 |
| Output | 0.0008176580304279923 | 36523 | 0–65535 / INT32 |

All variants concatenate history `[1,6144,1,4]` and projection `[1,6144,1,1]` on the last axis, then retain `[:, :, :, -4:]`. The modules have **zero parameters and zero buffers**. They do not use a quantizer, observers, calibration or model weights.

Inputs are synthetic, not a saved full-model state pack. History slots are `[-0.25, 0.5, -0.75, 1.0]` per channel, with history `[0,6053,0,3]` changed to `23.721895217895508`. Projection is 0.125 except channels 0, 1 and 6143, which are -0.125, 0 and 0.25. The selected retained output is `[0,6053,0,2]`.

## Retained CPU references

Exactly three forwards were made in the separately retained reference preparation, one per variant. The synthetic unit tests also exercise tiny CPU operations; they are separate from these retained references.

| Variant | Selected CPU output | All 24,576 output values vs independent scalar oracle |
|---|---:|---|
| `fullchain` | **22.131549835205078** | bit-identical |
| `outputonly` | **23.721895217895508** | bit-identical |
| `aligned` | **23.721895217895508** | bit-identical |

Complete little-endian float32 inputs, all three CPU output tensors, and all three independent scalar-oracle tensors are retained, with shape/byte/hash manifests. Each output is 98,304 bytes. `outputonly` and `aligned` happen to have identical complete outputs for these synthetic inputs; they remain separate graph variants and artifacts.

The oracle reconstruction uses the standard-library FP32 rounding helper from the accepted audit, including the projection branch. Oracle files were materialized from saved input bytes without importing Torch or QNN. CPU references use the public `quantized_decomposed` operators from Torch 2.11.0+cpu. Source hashes and four-thread configuration are recorded.

The 60-second external guard completed after 1.603 seconds, reaped its child, and left disk scratch empty. This is preparation telemetry, **not an inference-performance result**.

## Capture contract

`Hooks.install` only attaches/restores process-local hooks; it does not call any pass, builder, compiler or runtime itself. A future reviewed adapter supplies the real classes. Current tests supply mocks.

1. **Before/after each supplied capture and preprocess pass:** node targets, arguments, shapes/dtypes, all non-value metadata, including quantization and per-consumer requantization attributes. Tensor payloads are never read. Failed passes retain their last graph and error.
2. **`NodeVisitor.get_quant_encoding_conf`:** source/consumer names and the selected encoding/configuration, explicitly before `get_data_type` may change the carrier dtype.
3. **`QnnBackend._build_op_wrappers`:** graph before and after preprocessing, then getters on every operator's actual input/output tensor wrappers. The pinned source returns these wrappers immediately before `QnnManager.Compile`.
4. **Wrapper getters:** `GetName`, `GetDims`, `GetDataType`, and, for fixed-point tensors, `GetEncodings`. Preserve scale, FP32 scale bytes, **QNN offset** (not a mislabeled PyTorch zero point), and axis. The Python binding does not expose full encoding-kind/bitwidth through these getters; those remain null with an explicit limitation.
5. **Optional manager IO:** getter-only `GetGraphNames/GetGraphInputs/GetGraphOutputs` after a separately authorized compile. No implicit allocation or context load. This describes manager-reported graph IO, not internal finalized/fused operators.

Attach the pass hooks to the active `get_capture_program_passes()` classes plus preprocess classes (`FoldQDQ`, `InsertRequantize`, `InsertIOQDQ`, `LayoutTransform`, `FuseConsecutiveCast`, `FuseConsecutiveTranspose`, and `ConvertMhaToSha` only if enabled). Repeated classes are deduplicated; repeated actual invocations still receive distinct numbered taps. The tiny route should keep TagQuantIO disabled, as in the accepted model compile.

`source-interface-manifest.json` binds the inspected Python and C++ accessor source. `mock-tap-example/` is an **API-shaped mock demonstration**, not a lowered variant. Native binding compatibility and real QNN delegation are untested. Missing metadata remains null with reasons and blocks attribution, not preservation of a raw output.

## Tests and retained failure

21 new tests cover exact variants/geometry/all scalar bytes, exclusive outputs, raw-before-validation retention, no real-interface acceptance, one-call mock orchestration, fallback rejection before runtime, compile/runtime failure retention, input mutation, capture ordering, pass failure, patch restoration, missing encoding metadata and getter-only IO inspection. The complete **152-test** regression passed; its commands/logs/supervision are retained in `regression/`.

`test-attempts/attempt-01` failed at launch: resolving the venv Python symlink selected its base interpreter and `import torch` failed. No tests or CPU reference forwards ran. The corrected `attempt-02` preserves the venv executable path and passed all 21 tests. Both attempts are retained; this was not a numerical failure or a hidden model retry.

## Proposed execution budget — not released

- Cases: `fullchain`, `outputonly`, `aligned`, each in a fresh owned process/evidence directory; at most one compile and one forward per case.
- Compile deadline **120 s**, runtime deadline **60 s**, total active deadline **240 s per case**; at most **720 s active** across three cases. External TERM/grace20 s/KILL/reap may add bounded cleanup time.
- Four math threads, nice15/ionice2:7, owned disk scratch, actual PSI/memory monitoring and STOP support. App work retains priority.
- Stop at the first error, interruption or missing zero-fallback proof; retain every artifact and do not retry/resume. No later case is implicitly authorized.
- Require zero nondelegated tensor compute before any runtime call. The output-only graph leaves concat/slice floating before output quantization, so its HTP delegation is **not assumed**. Do not silently insert quantization, switch precision or execute fallback to make that control pass.
- Store raw outputs before comparisons. Missing/failing encoding taps prevent frontend/SDK attribution but do not erase an execution result.

Pi must review this committed harness before any QNN import/compile/runtime release. The exact model, physical baseline and protected evidence remain unchanged. No model-wide fidelity, backend-defect, FP32-accuracy, Android-performance or campaign-readiness claim follows from these controls.
