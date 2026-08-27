---
experiment: 0031-gemma-4-e2b-it-android-qnn-htp
status: active
summary: The two static Gemma 4 AR variants now compile into one hash-bound weight-shared SM8550/HTP-v73 context; runtime bundle preparation and physical-phone proof remain open.
benchmark: android-llm
---

# Experiment 0031 — Gemma 4 E2B IT Android QNN/HTP

## Experiment description

Gemma 4 E2B IT already has measured Android CPU and GPU routes, but its QNN arm stopped when QAIRT 2.49.0 could not transform the exact public W4A16 graph. The newly authorized QAIRT 2.49.40 package retained the implicated defect, so this experiment introduced a narrow schema-and-shape compatibility layer. That layer cleared transformation without changing the public checkpoint, both static variants passed host QNN conversion, and one weight-shared SM8550/HTP-v73 context has now compiled. Physical-phone loading and execution are still unproven.

The intended end-to-end result has not changed: an exact, provenance-bound Gemma 4 E2B context compiled for SM8550/HTP v73, physical `QnnHtp` provider proof on the authorized Galaxy S23 Ultra, a bounded viability request, proven loaded-route state isolation, and only then the canonical one-first-plus-five-short/five-medium/five-long Android campaign. Toolchain acquisition or file presence alone cannot satisfy any of those gates.

The public `gemma_4_e2b_it_w4a16.zip` checkpoint remains the pinned model input. It is hash-bound at 2,013,959,998 bytes and includes the exact ONNX/external data, W4A16 encodings, tokenizer, template, and configuration assessed by the earlier transform probe. The owning [experiment README](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/README.md), [experiment contract](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/protocol/experiment-contract.json), [original transform blocker](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/transform-blocker/result.json), [QAIRT 2.49.40 capability comparison](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-capability/result.json), [positive transform result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-transform-compat/result.json), [QNN conversion result](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-qnn-conversion/result.json), and [compiled-context inspection](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-sm8550-context/result.json) are the evidence authority.

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

The active next gate is generating and binding matching token and per-layer-embedding LUTs plus the exact Genie `QnnHtp` runtime configuration. Phone staging remains gated on explicit Pi priority and the full `phone.lock` lifecycle. Any paid Workbench compile/link use remains a separate unapproved cost-and-terms checkpoint.

## Results

**The experiment is active after positive host SM8550/HTP-v73 context compilation and before phone staging.** The static AR1 and AR128 CL4096 variants now exist together in one hash-bound, weight-shared context whose official metadata identifies QNN HTP backend ID 6 and both graph interfaces. The earlier `KeyError('value')` remains historical evidence for the unpatched transform path.

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
| Android load / physical HTP no-fallback execution | Not attempted; no claim |
| Output, setup, TTFT, prefill, decode, memory, or campaign | Unavailable; no inference ran |
| Android LLM registry row | None; toolchain capability evidence is not registry-eligible |

A successful host context compile is not physical provider or no-fallback execution proof. Backend ID 6 and embedded SM8550/v73 markers bind the target and artifact metadata; they do not show that Android can load the context, that every transformer graph executes on HTP, or that the mixed-precision boundaries behave correctly at runtime.

No phone or ADB operation occurred, no paid Workbench job ran, and no QNN/HTP inference, output, or performance evidence exists. A future page may advance beyond this milestone only from committed runtime-bundle, phone-load, or provider evidence. The Android LLM registry remains limited to complete valid physical Android campaigns, so 0031 has no benchmark row.
