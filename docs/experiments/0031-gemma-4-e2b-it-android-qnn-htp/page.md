---
experiment: 0031-gemma-4-e2b-it-android-qnn-htp
status: active
summary: The corrected bundle deserialized its weight-shared context on physical SM8550 HTP, then stopped before dialog/query on 30 cross-variant value-cache quantization mismatches; a host rebuild is required.
benchmark: android-llm
---

# Experiment 0031 — Gemma 4 E2B IT Android QNN/HTP

## Experiment description

Gemma 4 E2B IT already has measured Android CPU and GPU routes, but its QNN arm stopped when QAIRT 2.49.0 could not transform the exact public W4A16 graph. The authorized QAIRT 2.49.40 route has since cleared transformation, QNN conversion, weight-shared SM8550/v73 compilation, runtime-bundle preparation, and physical context deserialization. The current blocker is model validation before dialog/query: AR1 and AR128 disagree on 15 value-cache quantization boundaries. No graph has executed.

The intended end-to-end result has not changed: an exact, provenance-bound Gemma 4 E2B context compiled for SM8550/HTP v73, physical `QnnHtp` provider proof on the authorized Galaxy S23 Ultra, a bounded viability request, proven loaded-route state isolation, and only then the canonical one-first-plus-five-short/five-medium/five-long Android campaign. Toolchain acquisition or file presence alone cannot satisfy any of those gates.

The public `gemma_4_e2b_it_w4a16.zip` checkpoint remains the pinned model input. It is hash-bound at 2,013,959,998 bytes and includes the exact ONNX/external data, W4A16 encodings, tokenizer, template, and configuration assessed by the earlier transform probe. The owning [experiment README](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/README.md), [experiment contract](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/protocol/experiment-contract.json), [positive transform result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-transform-compat/result.json), [QNN conversion result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-qnn-conversion/result.json), [compiled-context inspection](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-sm8550-context/result.json), [runtime-bundle/LUT result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/gemma4-sm8550-runtime-bundle/result.json), [first phone attempt](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-01/result.json), and [corrected retry](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-viability-attempt-02/result.json) are the evidence authority.

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

The next gate is host-only: make each of the 15 AR1 value-cache outputs datatype/scale/offset-identical to its AR128 counterpart, then re-convert, recompile, and inspect the context. No validation weakening, CPU conversion boundary, further phone retry, or campaign is authorized. Any paid Workbench use remains a separate unapproved cost-and-terms checkpoint.

## Results

**The experiment is active with a host rebuild required after two physical pre-execution failures.** Attempt 01 established partial physical provider/backend/device and graph initialization before revealing a missing runtime extension. Attempt 02 loaded the corrected runtime and fully deserialized the weight-shared context before the exact 30-entry value-cache validation blocker. Neither attempt executed a graph.

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
| Graph execution, tokens, output, usable profile | None / 0 / none / none |
| Cleanup | Stage hashes passed; scoped root absent and `phone.lock` released after both attempts |
| Next work | Host-only quantization-identical context rebuild; no phone retry or campaign authorized |
| Android LLM registry row | None; toolchain capability evidence is not registry-eligible |

The phone evidence proves progressively deeper physical initialization and, in attempt 02, full context deserialization. It does not prove physical model inference or no-fallback graph execution: Genie stopped validation before dialog/query and no execution profile component exists. The 30 mismatch messages are not performance evidence, and the empty profile is not a zero-time measurement.

No paid Workbench job ran, and no QNN/HTP graph execution, generated output, output sanity, or performance evidence exists. A future page may advance beyond this milestone only from a committed quantization-identical rebuild and separately authorized physical result. The Android LLM registry remains limited to complete valid physical Android campaigns, so 0031 has no benchmark row.
