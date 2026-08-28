---
experiment: 0031-gemma-4-e2b-it-android-qnn-htp
status: active
summary: A numerically identical dual-AR symbol rename now matches Genie's positional tensor names; the rebuilt SM8550/v73 context and 17-file private stage pass host checks and await physical validation.
benchmark: android-llm
---

# Experiment 0031 — Gemma 4 E2B IT Android QNN/HTP

## Experiment description

Gemma 4 E2B IT already has measured Android CPU and GPU routes, but its QNN arm stopped when QAIRT 2.49.0 could not transform the exact public W4A16 graph. The authorized QAIRT 2.49.40 route has since cleared transformation, QNN conversion, weight-shared SM8550/v73 compilation, runtime-bundle preparation, and physical context deserialization. An initial context stopped before dialog/query because AR1 and AR128 disagreed on 15 value-cache quantization boundaries. A host correction made all four AR1-input/output and AR128-input/output signatures identical, and that context physically deserialized without the prior 30 validation errors. Genie then stopped before dialog or graph execution because its positional binding requested tensor names that differed from the context. A numerically identical input-symbol correction now aligns both AR variants with the exact Genie names; the rebuilt context and stage await physical validation.

The intended end-to-end result has not changed: an exact, provenance-bound Gemma 4 E2B context compiled for SM8550/HTP v73, physical `QnnHtp` provider proof on the authorized Galaxy S23 Ultra, a bounded viability request, proven loaded-route state isolation, and only then the canonical one-first-plus-five-short/five-medium/five-long Android campaign. Toolchain acquisition or file presence alone cannot satisfy any of those gates.

The public `gemma_4_e2b_it_w4a16.zip` checkpoint remains the pinned model input. It is hash-bound at 2,013,959,998 bytes and includes the exact ONNX/external data, W4A16 encodings, tokenizer, template, and configuration assessed by the earlier transform probe. The owning [experiment README](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/README.md), [experiment contract](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/protocol/experiment-contract.json), [positive transform result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-transform-compat/result.json), [QNN conversion result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-qnn-conversion/result.json), [compiled-context inspection](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-sm8550-context/result.json), [runtime-bundle/LUT result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/gemma4-sm8550-runtime-bundle/result.json), [first phone attempt](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-01/result.json), [corrected retry](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-02/result.json), [cache-quantization correction](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-cache-quantization-correction/result.json), [cache-corrected phone-stage preparation](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/cache-corrected-phone-stage/result.json), and [third physical attempt](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-03/result.json), [position-ID binding correction](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-position-id-binding-correction/result.json), and [position-ID-corrected phone stage](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/position-id-corrected-phone-stage/result.json) are the evidence authority.

## Progress

The original assessment established credible first-party Gemma 4 route ingredients but no working conversion. QAIRT 2.49.0 resolved SM8550 to HTP v73 and shipped a Gemma 4 HTP example, yet its high-level factory had no `Gemma4ForConditionalGeneration` dispatch. The smallest faithful transform of the unchanged public graph failed during shape inference and constant propagation with `KeyError('value')`, before QNN conversion, context creation, or compilation.

An authorized Qualcomm QPM acquisition has now bound `Qualcomm_AI_Runtime_SDK.2.49.40.260810.Linux-AnyCPU.qik` at 2,410,405,384 bytes and SHA-256 `ef4a63b8…fdb0c`. The package and installed SDK remain outside Git; the committed evidence records no account identity, identifiers, credential contents, or restricted binary. The compared SDK reports QAIRT 2.49.40 premium with the same QNN backend API version as 2.49.0 and retains the Gemma 4 example plus SM8550/v73 runtime components.

The capability inventory compared the exact files implicated by the prior blocker. The Gemma4 builder factory, ONNX utility containing constant handling, shape-inference pass, release notes, and Gemma 4 HTP configuration are byte-identical between QAIRT 2.49.0 and 2.49.40. The new factory still has no Gemma4 dispatch, so the old transform defect should not be expected to disappear merely by changing package versions.

Selected deployment/runtime libraries did change: `libGenie.so`, `libQnnHtp.so`, the Android v73 stub, and the Hexagon v73 skeleton have new hashes, while the compared Genie executables and `libQnnSystem.so` remain identical. Those differences make 2.49.40 a separately bound runtime candidate if a valid context can eventually be produced; they do not prove that the model transforms, compiles, loads, or executes.

The compatibility layer addresses only the observed schema and shape gaps: it reads the checkpoint's four standards-valid `Constant(value_ints=...)` nodes, seeds Gemma4-specific axes, materializes the exact sliding-window cache and attention-mask widths, and propagates the shape-preserving `Reciprocal` operation. It is isolated from the checkpoint and does not rewrite the public source graph, external data, or encodings.

Under `heavy-ram.lock`, QAIRT 2.49.40 completed a transform-only AR1+AR128, CL4096, one-split run. It produced:

- AR1 ONNX SHA-256 `9f3077b4…e472` and encodings SHA-256 `0dbb1aad…e2a8`;
- AR128 ONNX SHA-256 `d1171990…e9a` and encodings SHA-256 `7e264005…a251`;
- shared 9,119,006,720-byte transformed external data at SHA-256 `b9b73b98…a65d`.

Both output graphs pass the ONNX checker, and every graph input and output is static. Post-transform hashes prove that the original ONNX, external data, and encodings remain unchanged. This milestone requested no QNN conversion, HTP compilation, inference, phone access, or paid Workbench job.

Both static variants now pass QAIRT 2.49.40 QNN conversion with `backend=HTP` and the published quantization overrides:

- AR1 DLC: 2,356,831,668 bytes, SHA-256 `02a79060…ff68`;
- AR128 DLC: 2,356,851,284 bytes, SHA-256 `5f17ece8…56ee`.

`qairt-dlc-info` binds each converted graph at 2,280,676,608 parameters and retains its operator and I/O encoding inventory. The conversion is not uniformly integer: the converter reports 15 RmsNorm float fallbacks in each variant. AR1 also exposes 15 value-cache outputs as Float16, while all 31 AR128 outputs are uFxp16. These mixed-precision facts remain visible for compilation and runtime validation; they are not silently described as uniform W4A16 or as CPU-provider fallback.

Both DLCs now compile together in QAIRT weight-sharing mode. The resulting 1,186,349,056-byte serialized context has SHA-256 `b8c169ce…af95a`. Official `qnn-context-binary-utility` inspection reports:

- QAIRT build `v2.49.40.260810104044` and QNN HTP backend ID 6;
- exactly two graphs, `ar1_cl4096_1_of_1` and `ar128_cl4096_1_of_1`;
- 38 inputs and 31 outputs for each graph;
- embedded `soc_type=SM8550`, `arch=73`, and `native_hmx_a16w4=true` markers.

The mixed-precision boundary remains present in compiled metadata: all 31 AR128 outputs are unsigned fixed-point 16, while AR1 retains 15 Float16 value-cache outputs and 16 unsigned fixed-point outputs. This is not a uniform-integer claim.

The private runtime bundle is now prepared from the pinned, ungated Apache-2.0 QAT checkpoint. A pinned Google/Hugging Face formula decodes its low-bits-first signed INT2 token embeddings and INT4 per-layer embeddings, applies per-row/per-block plus architectural embedding scales, and requantizes them into the uint8 LUT format expected by the QAIRT Gemma 4 runtime:

- token LUT: 402,653,184 bytes, SHA-256 `3b55bb6b…4239`;
- per-layer embedding LUT: 2,348,810,240 bytes, SHA-256 `bc5f25db…9fa4`.

Deterministic sampled reconstruction covers selected vocabulary rows and remains within half of one uint8 quantization step for both LUTs. This is a bounded LUT-fidelity check, not full-tensor numerical equivalence or model-output validation.

The bundle manifest binds both LUTs, context SHA-256 `b8c169ce…af95a`, exact tokenizer, QAIRT 2.49.40 Genie plus QNN HTP host/stub/v73 skeleton libraries, and a `QnnHtp` configuration with CL4096, greedy sampling, and the 2,048-token ceiling. All large or restricted artifacts stay outside Git.

The bounded phone tooling required `phone.lock`, exact device and artifact hashes, raw-first evidence capture, a 16-token ceiling, and verified scoped cleanup. The first authorized attempt passed identity and hash checks, parsed the `QnnHtp` configuration, discovered both AR graphs and their sliding-window mappings, detected physical SM8550, and initialized the HTP provider/backend/device, v73 stub, and first QNN stub connection. It then exited 139 during dialog creation because `libQnnHtpNetRunExtensions.so` was absent. No query, graph execution, output, or profile occurred.

The missing QAIRT 2.49.40 Android extension was added at 1,091,656 bytes, SHA-256 `e25a816d…04ae`, and both stage and run tooling now fail closed on an incomplete runtime. The one authorized corrected retry loaded that extension, initialized the physical HTP stack, and fully deserialized the two-graph weight-shared context.

Genie then rejected model validation before dialog/query with exactly 30 non-identical quantization-parameter errors. The 15 AR1 value-cache outputs are Float16, while the corresponding 15 AR128 cache inputs and 15 AR128 cache outputs are unsigned fixed-point 16 with defined scale/offset encodings. This is the mixed-precision boundary already visible in host context metadata, now confirmed as a physical runtime blocker.

Attempt 02 exited 1 with zero graph executions, tokens, or output. Its profile exists but contains no components. Both attempts verified their stage hashes, removed and verified the scoped remote root absent, and released `phone.lock`.

The cache blocker is now corrected without changing the checkpoint or weakening Genie validation. A schema-standard ONNX float fork and `QuantizeLinear` boundary maps each of the 15 public AR1 value-cache outputs to the already-bound source-QAT uint16 zero point 32768, QNN offset -32768, and exact per-cache scale. Internal transformer consumers keep the existing path; this adds no host CPU cache-conversion boundary.

The corrected AR1 DLC is 2,356,847,444 bytes with SHA-256 `7e88facd…c9e1`, retains 2,280,676,608 parameters, and exposes 31/31 outputs as uFxp16. Recompiling it with the unchanged AR128 DLC produced a 1,186,369,536-byte weight-shared SM8550/v73 context at SHA-256 `a1d52d00…cc44`. Official metadata identifies QNN HTP backend ID 6, the exact QAIRT 2.49.40 build, and two 38-input/31-output graphs.

For every one of the 15 value caches, official context inspection verifies that AR1 input, AR1 output, AR128 input, and AR128 output now share identical uFxp16 datatype, scale, and offset signatures. This clears the exact attempt-02 validation mismatch on the host.

The correction is not a uniform-integer execution claim: QAIRT still reports 75 float-precision component fallback operations around affected normalization paths. Host conversion, recompilation, and metadata inspection also do not prove that the phone will accept or execute the revised context.

The private runtime bundle and phone stage are now rebuilt around corrected context SHA-256 `a1d52d00…cc44`. The stage contains 17 manifest entries totaling 4,003,765,361 logical bytes and binds the exact tokenizer, source-derived token/PLE LUTs, Genie/QNN HTP/v73 dependencies, canonical short prompt, and 16-token viability ceiling. The full manifest, `SHA256SUMS`, required-runtime completeness, restrictive file permissions, and dependency checks all pass; the run script fails closed on any corrected-context hash mismatch.

Stage preparation itself was host-only, but Pi subsequently authorized exactly one bounded physical gate. The full `phone.lock` lifecycle covered ADB; the SM-S918B/SM8550 identity, local and remote hashes, and runtime completeness all passed. On the physical phone, the backend extension loaded, QNN HTP provider/backend/device and the v73 stub initialized, and the corrected two-graph weight-shared context deserialized. The prior 30 cache-quantization validation errors were absent, physically clearing that blocker.

Genie then reported `position_ids_global_cos` and `position_ids_global_sin` as unconnected context inputs while searching for `position_ids_cos` and `position_ids_sin`. I/O discovery failed with `Could not find I/O tensors in loaded graphs`; dialog creation failed, and the later scripted query addressed a nonexistent dialog. Attempt 03 exited 1 before graph execution, generated zero tokens, created no output, and retained a profile with null components.

Cleanup verified the experiment-scoped remote root absent and no residual process, then released `phone.lock`.

The positional binding is now corrected on the host with a symbol-only graph-input and activation-encoding rename in both AR variants: `position_ids_global_cos/sin` becomes Genie's exact `position_ids_cos/sin`. Checkpoint weights and graph numerics are unchanged, and the AR1 value-cache quantize/dequantize boundary is preserved. Both rebuilt DLCs retain 2,280,676,608 parameters and 31/31 uFxp16 outputs.

The rebuilt 1,186,369,536-byte weight-shared context has SHA-256 `7739ce52…d394`. Official metadata reports QNN HTP backend ID 6, QAIRT build `v2.49.40.260810104044`, SM8550/v73, and both 38-input/31-output graphs. Both expose unprefixed `position_ids_cos/sin` for global RoPE plus `swa_position_ids_cos/sin` for SWA; the old global names occur zero times. All 15 four-way AR1-input/output and AR128-input/output cache signatures remain identical.

The private 16-token stage is rebuilt around this context. Its 17 files total 4,003,765,361 logical bytes; manifest, `SHA256SUMS`, runtime completeness, dependencies, and restrictive modes all pass. Preparation used no ADB and did not acquire `phone.lock`. This is host conversion, AOT inspection, name-set verification, and stage readiness only—not revised dialog creation, graph execution, no-fallback proof, output, performance, or campaign evidence.

## Results

**The experiment is active with the positional binding corrected and a rebuilt private stage ready.** The numerically identical dual-AR rename now matches Genie's global and SWA tensor names while preserving all cache contracts. Physical dialog creation and graph execution of this new context remain unproven.

| Evidence boundary | Current result |
|---|---|
| QAIRT 2.49.40 package provenance | Acquired outside Git and hash-bound |
| Gemma4 factory dispatch | Still absent in the compared source |
| Implicated converter / shape-inference sources | Byte-identical to QAIRT 2.49.0 |
| Android/HTP runtime candidate | SM8550/v73 components present; selected runtime-library hashes changed |
| Gemma transform with 2.49.40 compatibility layer | AR1 and AR128 CL4096 one-split variants completed; static I/O and ONNX checker passed |
| Public checkpoint identity | Original ONNX, external data, and encodings unchanged after transform |
| Host QNN conversion | AR1 and AR128 HTP-targeted DLCs completed and hash-bound |
| Converted graph inventory | 2,280,676,608 parameters per DLC |
| Mixed-precision boundary | 15 RmsNorm float fallbacks per variant; 15 AR1 Float16 value-cache outputs; AR128 outputs uFxp16 |
| Host weight-shared context | 1,186,349,056 bytes / SHA `b8c169ce…af95a`; QNN HTP backend ID 6 |
| Context graph inventory | AR1 + AR128, each 38 inputs / 31 outputs; SM8550, arch 73, native HMX A16W4 markers |
| Token LUT | 402,653,184 bytes / SHA `3b55bb6b…4239`; source INT2 to runtime uint8 |
| Per-layer embedding LUT | 2,348,810,240 bytes / SHA `bc5f25db…9fa4`; source INT4 to runtime uint8 |
| Sampled LUT fidelity | Both within half of one uint8 quantization step on the deterministic sample |
| Runtime bundle | Context + tokenizer + Genie/QNN HTP/v73 libraries + CL4096 greedy configuration hash-bound outside Git |
| Attempt 01 physical boundary | Both AR graphs/SWA mappings and SM8550 HTP stack initialized; missing NetRun extension caused exit 139 pre-query |
| Attempt 02 physical boundary | Corrected extension loaded and context deserialized; 30 value-cache quantization mismatches caused exit 1 pre-dialog/query |
| Root cause | 15 AR1 Float16 value outputs versus matched AR128 uFxp16 inputs and outputs with differing quantization parameters |
| Corrected AR1 DLC | 2,356,847,444 bytes / SHA `7e88facd…c9e1`; 2,280,676,608 params; 31/31 uFxp16 outputs |
| Corrected context | 1,186,369,536 bytes / SHA `a1d52d00…cc44`; QNN HTP backend ID 6; two 38-in/31-out graphs |
| Cache correction proof | All 15 AR1-in/out + AR128-in/out datatype/scale/offset signatures identical |
| Remaining precision boundary | 75 float-precision component fallback ops retained; not uniform-integer/no-fallback proof |
| Cache-corrected phone stage | 17 files / 4,003,765,361 logical bytes; manifests, hashes, dependencies, and permissions verified |
| Attempt 03 physical boundary | Verified SM-S918B/SM8550; local/remote hashes passed; extension + QNN HTP/backend/device/v73 initialized; corrected context deserialized |
| Cache blocker on physical load | Prior 30 cache-quantization validation errors absent; blocker cleared |
| New pre-execution blocker | Context exposes `position_ids_global_cos/sin`; Genie requests `position_ids_cos/sin`; I/O discovery/dialog creation fails |
| Attempt 03 execution/output | Exit 1; 0 graph executions; 0 tokens; no output; profile components null |
| Position-ID correction | Identity rename `position_ids_global_cos/sin` → `position_ids_cos/sin` in AR1 and AR128; weights/numerics unchanged |
| Rebuilt DLC boundary | 2,280,676,608 params and 31/31 uFxp16 outputs each; AR1 cache QDQ preserved |
| Rebuilt context | 1,186,369,536 bytes / SHA `7739ce52…d394`; HTP backend 6; two SM8550/v73 graphs |
| Positional-name proof | Exact global + SWA names present in both graphs; old global names absent |
| Cache-contract preservation | All 15 four-way AR1/AR128 datatype/scale/offset signatures remain identical |
| Corrected private stage | 17 files / 4,003,765,361 logical bytes; hashes, deps, runtime completeness, and modes pass |
| Current physical boundary | No ADB or `phone.lock`; revised dialog/execution/output/performance unproven |
| Cleanup | Scoped root absent, no residual process, and `phone.lock` released after attempt 03 |
| Android LLM registry row | None; toolchain capability evidence is not registry-eligible |

The phone evidence proves that the earlier context reached physical SM8550 QNN HTP deserialization and that the cache-contract mismatch was gone. It does not prove model inference or no-fallback graph execution: Genie stopped during I/O discovery before dialog creation. The new host correction removes the exact positional name-set mismatch without changing numerics, but cannot retroactively establish physical behavior.

No paid Workbench job ran, and no QNN/HTP graph execution, generated output, output sanity, or performance evidence exists. A future page may advance beyond this milestone only from a separately authorized physical result using the exact rebuilt context. The Android LLM registry remains limited to complete valid physical Android campaigns, so 0031 has no benchmark row.
