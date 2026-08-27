---
experiment: 0034-lfm2.5-2.6b-android-qnn-htp
status: active
summary: The first physical attempt verified device and stage identity but failed closed before its first EPContext session because QNN did not claim the graph; one NPU-filtered diagnostic retry is authorized.
benchmark: android-llm
---

# Experiment 0034 — LFM2.5-2.6B Android QNN/HTP

## Experiment description

LFM2.5-2.6B has complete Android CPU and OpenCL benchmark routes, but its original QNN assessment found no high-level tool path for the model's `lfm2` architecture. This experiment now tests an architecture-aware route: export the exact model to Q4 ONNX, split its stateful computation into memory-bounded parts, compile every claimed neural part for the Galaxy S23 Ultra's SM8550/HTP v73 target with CPU provider fallback disabled, and then prove that the complete route can execute physically on the phone.

LFM2 is not a renamed Llama-like transformer. Its 30 layers combine 22 recurrent short-convolution layers with 8 full-attention layers, so the route must preserve both convolution state and attention KV state, bind their reset behavior, and prove that claimed model computation runs through QNN HTP. The intentionally CPU-side tokenizer, selected-row Q4 embedding lookup, request orchestration, and one global greedy argmax remain explicit; they are not hidden provider fallback.

The route binds `LiquidAI/LFM2.5-2.6B` revision `ab006873…`, the architecture-aware `Liquid4All/onnx-export` exporter at `9a23ddd…`, symmetric block-32 INT4 weights, ONNX Runtime QNN EP 2.5.0, and host QNN runtime 2.49.40 targeting SoC model 43 / SM8550 / HTP v73. Moritz reviewed and authorized the named public Qualcomm package license. Packages, source weights, large ONNX data, compiled contexts, and the assembled phone stage stay outside Git. The owning [experiment README](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/protocol/experiment-contract.json), [QNN AOT result](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-aot/result.json), [host pipeline comparison](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/htp-pipeline-host-equivalence/result.json), [phone-preparation result](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/phone-preparation/result.json), and [first phone-attempt result](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/phone-attempt-1-provider-selection-failure/result.json) are the evidence authority.

## Progress

The historical high-level blocker remains a rejected route: installed QAIRT's direct-GGUF and factory paths do not support `lfm2`. The experiment instead bound the exact source shards and produced an architecture-aware Q4 ONNX export containing the expected 22 convolution nodes, 8 `GroupQueryAttention` nodes, and 167 `MatMulNBits` nodes. A standard-ONNX RMSNorm rewrite corrected an invalid contrib-operator domain emission, after which the graph passed the ONNX checker and completed a bounded canonical-short host CPU smoke. That smoke established export viability only, not QNN or Android execution.

The model was then lowered into a one-token pipeline with a fixed 4,096-token attention capacity. Reset is explicit: all 22 convolution caches and all 8 attention K/V pairs start at zero for each logical request. RoPE and grouped-query attention are expanded into QNN-owned standard operations while returning only the new K/V slices for a left-aligned cache.

The selected-row asymmetric Q4 embedding remains an intentional CPU frontend because QNN EP 2.5 does not claim `GatherBlockQuantized` on HTP. Wide 10,752-element MLP projections were split into 6,144 + 4,608 paths; only the second down-projection dot product receives mathematically zero activation and quantized-weight padding to meet the v73-supported width. The 128,000-wide LM head was split into 22 HTP chunks, followed by one declared CPU global argmax. Tokenizer work and orchestration are also CPU-side. No QNN CPU provider fallback is accepted for the submitted neural parts.

The final memory-bounded route contains 263 compiled parts covering convolution and attention cores, MLP projection/activation/residual work, final normalization, and the 22 LM-head chunks. Every part compiled through ONNX Runtime QNN EP 2.5.0 with `session.disable_cpu_ep_fallback=1`, block-quant optimization, framework-operation tracing, and target SoC 43 / HTP v73. Across the retained QNN source parts:

- all 1,583 source ONNX nodes are marked supported;
- zero source nodes are unsupported;
- the traces map them to 2,747 QNN operations;
- 263 context binaries total 1,779,492,144 bytes and remain outside Git.

A bounded host reconstruction then submitted the exact 171-token canonical short prompt through the final 263-part ordering with zeroed state. The first five greedy token IDs matched the original export, the transformed monolith, and the final split pipeline. This protects the selected route wiring and greedy decisions for those five steps; the recorded logits are not numerically identical, and the host timings/logits are not Android or physical-HTP evidence.

The native Android API-31 AArch64 runner and ignored local stage were prepared for one bounded 16-token canonical-short request. The initial 539-payload-file stage covered public Android runtime artifacts, the runner, every context pair, Q4 embedding tables, and the prompt; metadata and hash manifests were additional. The complete license-controlled stage remained outside Git.

After RSA authorization and Pi's phone handoff, the first physical attempt held `phone.lock` for its full lifecycle. It verified the exact SM-S918B/SM8550 identity, all 540 local stage hashes, all 540 remote hashes, and pushed 2,015,209,698 bytes into an experiment-scoped root. The process started, but the first EPContext model was not claimed by the QNN provider device set. ONNX Runtime reported that graph nodes would remain on the default CPU EP; because `session.disable_cpu_ep_fallback=1` remained enabled, the route stopped at creation of the first session.

The failure occurred before any context session loaded or model token executed. It produced zero HTP graphs, outputs, or profile files. The single retained memory observation covers only process startup and cannot be treated as model memory or performance. The experiment process was absent afterward, the 2.0 GB scoped remote root was removed and verified absent, and `phone.lock` was released.

The replacement runner now logs every advertised execution-provider device type and selects only `QNNExecutionProvider` with Android NPU hardware type. Its SHA-256 is `fe3351b8…43ea`, and the replacement 539-payload-file stage is fully hash-bound. Pi authorized exactly one bounded NPU-selection diagnostic retry with CPU fallback still disabled; no campaign is authorized regardless of that retry's outcome.

## Results

**The experiment remains active after one fail-closed physical pre-inference diagnostic.** Host AOT preparation remains valid, and the phone attempt established device/stage identity plus the exact provider-selection failure boundary. It did not establish model execution or physical HTP use.

| Evidence boundary | Current result |
|---|---|
| Exact-model architecture-aware Q4 export | Completed and hash-bound |
| Target-specific QNN AOT | 263 contexts compiled for SoC 43 / SM8550 / HTP v73 |
| Retained source-part ownership | 1,583/1,583 source nodes supported; 0 unsupported; 2,747 QNN operations |
| CPU provider fallback inside QNN parts | Disabled |
| Declared CPU work outside QNN parts | Tokenizer, selected-row Q4 embedding, orchestration, and global argmax across 22 HTP LM-head chunks |
| Host route-wiring comparison | First five greedy tokens matched reference, transformed monolith, and final pipeline; not exact-logit equivalence |
| First phone attempt identity/staging | Exact device plus 540 local/remote stage hashes verified under full `phone.lock` lifecycle |
| Failure boundary | First EPContext session creation; graph remained unclaimed and fail-closed prevented default CPU execution |
| Sessions, model tokens, HTP graphs, outputs, profiles | 0 / 0 / 0 / none / none |
| Cleanup | Experiment process absent; scoped remote root verified absent; lock released |
| Authorized retry | One NPU-filtered provider-selection diagnostic with runner SHA `fe3351b8…43ea`; no campaign |
| Android / physical HTP execution | Not established; no claim |
| Canonical campaign and Android performance | Not run; no setup, TTFT, prefill, decode, memory, thermal, or power result |
| Android LLM registry row | None; host AOT and wiring evidence are not registry-eligible |

The first attempt is physical phone transport and pre-inference diagnostic evidence, not physical HTP execution. Exact stage hashes and a started Android process do not show that the phone loaded any context or ran QNN. The fail-closed error correctly prevented default CPU execution, but it also means there is no provider, model-output, state-reset, or performance result. The low startup-only memory sample is not benchmark memory. Host context creation, phone staging, and matching five host greedy decisions cannot substitute for phone provider/RPC/accelerator/cycle/HVX proof.

No 0034 row belongs in the Android LLM registry until a complete valid physical Android canonical campaign exists. If physical context loading fails, CPU work expands beyond the declared boundary, any neural context falls back, or full request reset cannot be proven, the route must stop rather than weaken the HTP claim.
