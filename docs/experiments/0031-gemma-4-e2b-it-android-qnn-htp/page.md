---
experiment: 0031-gemma-4-e2b-it-android-qnn-htp
status: active
summary: Authorized QAIRT 2.49.40 is acquired and hash-bound, but its implicated Gemma4 converter sources match 2.49.0 byte-for-byte; the experiment remains pre-transform with no context or HTP execution.
benchmark: android-llm
---

# Experiment 0031 — Gemma 4 E2B IT Android QNN/HTP

## Experiment description

Gemma 4 E2B IT already has measured Android CPU and GPU routes, but its QNN arm stopped when QAIRT 2.49.0 could not transform the exact public W4A16 graph. This milestone asks whether the newly authorized QAIRT 2.49.40 package changes that conversion boundary or at least provides a newer physical-phone runtime for a separately justified converter compatibility fix.

The intended end-to-end result has not changed: an exact, provenance-bound Gemma 4 E2B context compiled for SM8550/HTP v73, physical `QnnHtp` provider proof on the authorized Galaxy S23 Ultra, a bounded viability request, proven loaded-route state isolation, and only then the canonical one-first-plus-five-short/five-medium/five-long Android campaign. Toolchain acquisition or file presence alone cannot satisfy any of those gates.

The public `gemma_4_e2b_it_w4a16.zip` checkpoint remains the pinned model input. It is hash-bound at 2,013,959,998 bytes and includes the exact ONNX/external data, W4A16 encodings, tokenizer, template, and configuration assessed by the earlier transform probe. The owning [experiment README](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/README.md), [experiment contract](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/protocol/experiment-contract.json), [original transform blocker](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/transform-blocker/result.json), and [QAIRT 2.49.40 capability comparison](../../../experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/qairt-2.49.40-capability/result.json) are the evidence authority.

## Progress

The original assessment established credible first-party Gemma 4 route ingredients but no working conversion. QAIRT 2.49.0 resolved SM8550 to HTP v73 and shipped a Gemma 4 HTP example, yet its high-level factory had no `Gemma4ForConditionalGeneration` dispatch. The smallest faithful transform of the unchanged public graph failed during shape inference and constant propagation with `KeyError('value')`, before QNN conversion, context creation, or compilation.

An authorized Qualcomm QPM acquisition has now bound `Qualcomm_AI_Runtime_SDK.2.49.40.260810.Linux-AnyCPU.qik` at 2,410,405,384 bytes and SHA-256 `ef4a63b8…fdb0c`. The package and installed SDK remain outside Git; the committed evidence records no account identity, identifiers, credential contents, or restricted binary. The compared SDK reports QAIRT 2.49.40 premium with the same QNN backend API version as 2.49.0 and retains the Gemma 4 example plus SM8550/v73 runtime components.

The capability inventory compared the exact files implicated by the prior blocker. The Gemma4 builder factory, ONNX utility containing constant handling, shape-inference pass, release notes, and Gemma 4 HTP configuration are byte-identical between QAIRT 2.49.0 and 2.49.40. The new factory still has no Gemma4 dispatch, so the old transform defect should not be expected to disappear merely by changing package versions.

Selected deployment/runtime libraries did change: `libGenie.so`, `libQnnHtp.so`, the Android v73 stub, and the Hexagon v73 skeleton have new hashes, while the compared Genie executables and `libQnnSystem.so` remain identical. Those differences make 2.49.40 a separately bound runtime candidate if a valid context can eventually be produced; they do not prove that the model transforms, compiles, loads, or executes.

No transform probe was run with 2.49.40 in this milestone because the relevant converter sources are unchanged. The active next gate is a `heavy-ram.lock`-protected, transform-only AR1+AR128 CL4096 probe using an isolated, schema-faithful ONNX Constant-attribute compatibility fix. It must preserve the public checkpoint bytes and bind every generated artifact. QNN conversion and SM8550 compilation remain prohibited until that transform succeeds; any paid Workbench compile/link use remains a separate unapproved cost-and-terms checkpoint.

## Results

**The experiment is active at a pre-transform engineering gate.** The result establishes authorized, hash-bound QAIRT 2.49.40 package provenance and a host-side capability comparison. It also establishes a negative finding: the new package does not contain a changed Gemma4 factory or implicated shape/constant-propagation implementation that would resolve the recorded 2.49.0 transform failure.

| Evidence boundary | Current result |
|---|---|
| QAIRT 2.49.40 package provenance | Acquired outside Git and hash-bound |
| Gemma4 factory dispatch | Still absent in the compared source |
| Implicated converter / shape-inference sources | Byte-identical to QAIRT 2.49.0 |
| Android/HTP runtime candidate | SM8550/v73 components present; selected runtime-library hashes changed |
| Gemma transform with 2.49.40 | Not attempted in this milestone |
| QNN conversion or compiled context | None |
| Android / physical HTP execution | Not attempted; no claim |
| Output, setup, TTFT, prefill, decode, memory, or campaign | Unavailable; no inference ran |
| Android LLM registry row | None; toolchain capability evidence is not registry-eligible |

Changed Android runtime binaries are not converter support and are not physical provider proof. Likewise, an active license status, a Gemma 4 example, and a generic SM8550/v73 runtime do not establish that this exact graph compiled or ran. The prior `KeyError('value')` blocker remains the expected behavior of the unchanged converter code until a reviewed compatibility fix or provenance-bound context route proves otherwise.

No transformed graph or context binary was created, no phone or ADB operation occurred, no paid Workbench job ran, and no QNN/HTP inference or performance evidence exists. A future page may advance beyond this milestone only from committed transform, conversion, compilation, or provider evidence. The Android LLM registry remains limited to complete valid physical Android campaigns, so 0031 has no benchmark row.
