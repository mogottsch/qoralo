---
experiment: 0034-lfm2.5-2.6b-android-qnn-htp
status: active
summary: Moritz authorized a direct-QNN continuation that bypasses ORT EPContext; the first exact context executes on the host emulator and the full Android runner/stage is hash-bound, with physical-phone proof pending.
benchmark: android-llm
---

# Experiment 0034 — LFM2.5-2.6B Android QNN/HTP

## Experiment description

LFM2.5-2.6B has complete Android CPU and OpenCL benchmark routes, but its original QNN assessment found no high-level tool path for the model's `lfm2` architecture. This experiment now tests an architecture-aware route: export the exact model to Q4 ONNX, split its stateful computation into memory-bounded parts, compile every claimed neural part for the Galaxy S23 Ultra's SM8550/HTP v73 target with CPU provider fallback disabled, and then prove that the complete route can execute physically on the phone.

LFM2 is not a renamed Llama-like transformer. Its 30 layers combine 22 recurrent short-convolution layers with 8 full-attention layers, so the route must preserve both convolution state and attention KV state, bind their reset behavior, and prove that claimed model computation runs through QNN HTP. The intentionally CPU-side tokenizer, selected-row Q4 embedding lookup, request orchestration, and one global greedy argmax remain explicit; they are not hidden provider fallback.

The route binds `LiquidAI/LFM2.5-2.6B` revision `ab006873…`, the architecture-aware `Liquid4All/onnx-export` exporter at `9a23ddd…`, symmetric block-32 INT4 weights, and 263 contexts prepared for SoC model 43 / SM8550 / HTP v73. The failed phone route used ONNX Runtime QNN EP 2.5.0; the active continuation now bypasses its EPContext claim layer and calls the public QNN context/graph APIs directly. Moritz reviewed and authorized the named Qualcomm package license and this bounded direct-loader continuation. Packages, source weights, large ONNX data, compiled contexts, and phone stages stay outside Git. The owning [experiment README](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/protocol/experiment-contract.json), [QNN AOT result](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-aot/result.json), [host pipeline comparison](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/htp-pipeline-host-equivalence/result.json), [NPU-selection retry](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/phone-attempt-2-npu-context-claim-failure/result.json), and [direct-QNN host preparation](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/direct-qnn-host-preparation/result.json) are the evidence authority.

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

The replacement runner logged both advertised device types: ARM `CPUExecutionProvider` hardware type 0 and `QNNExecutionProvider` hardware type 2, vendor Qualcomm, identified as NPU. Runner SHA-256 `fe3351b8…43ea` selected only that QNN NPU device and kept CPU fallback disabled.

The one authorized retry again verified all 540 hashes locally and remotely under the full `phone.lock` lifecycle. It selected the Qualcomm NPU successfully and began loading `layer-00-core-norm`, but the official Android QNN EP 2.5.0 plugin still did not claim the first EPContext produced by the matched host package for SM8550/v73. ONNX Runtime therefore left the wrapper assigned to default CPU, and the unchanged fail-closed gate stopped before session creation. The retry again produced zero loaded sessions, model tokens, HTP graphs, profiles, or output. Cleanup removed and verified the scoped root absent, and `phone.lock` was released.

Those two attempts remain terminal evidence for the ORT EPContext route. Moritz selected the separately bounded direct-QNN option rather than weakening the claim or retrying the same plugin. The new native loader bypasses ONNX Runtime entirely and uses `QnnContext_createFromBinary`, `QnnGraph_retrieve`, and `QnnGraph_execute` on the same exact 263 contexts. The declared CPU boundary remains selected-row asymmetric Q4 embedding, token/request orchestration, and one global greedy argmax across 22 QNN LM-head chunks; model body, state, final norm, and head chunks remain QNN graphs.

A host probe loaded exact first context `layer-00-core-norm` at SHA-256 `63e6f58a…21f1`, retrieved its SM8550/v73 graph, and executed it with QNN status 0. Residual, FFN-normalized, and convolution-state outputs were finite. Their maximum absolute differences from the CPU reference were approximately `0.000202`, `0.002389`, and `0.01229` respectively. This protects first-context loader wiring only: the x86 HTP backend reports internal v79 emulation for the requested v73 context, so it is not physical SM8550 execution or performance evidence.

The complete API-31 AArch64 direct runner is 307,416 bytes with SHA-256 `484c4a19…3148`. It is designed to load all 263 contexts once, preserve explicit 22-convolution plus 8-attention state, and execute the same direct QNN API sequence. A locally verified ignored stage contains 272 payload files totaling 1,974,276,800 bytes before its additional metadata/manifest; it includes the exact contexts, embedding tables, prompt, runner, and QNN runtime.

No phone access occurred for the direct-QNN continuation. Jere retains higher device priority, and 0034 must wait for explicit Pi priority before taking `phone.lock` or staging the direct runner. The first phone gate remains bounded physical viability only and does not authorize a campaign.

## Results

**The experiment is active on the authorized direct-QNN continuation, with physical phone execution pending.** The ORT attempts remain valid negative evidence: the plugin advertised and exclusively selected the Qualcomm NPU but refused the first EPContext. The new result establishes direct-QNN first-context load/retrieve/execute wiring on the host emulator and a complete hash-bound Android runner/stage, not physical HTP use.

| Evidence boundary | Current result |
|---|---|
| Exact-model architecture-aware Q4 export | Completed and hash-bound |
| Target-specific QNN AOT | 263 contexts compiled for SoC 43 / SM8550 / HTP v73 |
| Retained source-part ownership | 1,583/1,583 source nodes supported; 0 unsupported; 2,747 QNN operations |
| CPU provider fallback inside QNN parts | Disabled |
| Declared CPU work outside QNN parts | Tokenizer, selected-row Q4 embedding, orchestration, and global argmax across 22 HTP LM-head chunks |
| Host route-wiring comparison | First five greedy tokens matched reference, transformed monolith, and final pipeline; not exact-logit equivalence |
| Phone attempt identity/staging | Both attempts verified exact device and all 540 local/remote stage hashes under full `phone.lock` lifecycles |
| Retry provider selection | ORT 1.26 advertised QNN EP 2.5.0 as Qualcomm NPU type 2; runner selected only it |
| Failure boundary | NPU plugin did not claim first matched EPContext; fail-closed prevented default CPU execution before session creation |
| Sessions, model tokens, HTP graphs, outputs, profiles | 0 / 0 / 0 / none / none in both attempts |
| Cleanup | Experiment process absent; scoped remote root verified absent; lock released after both attempts |
| ORT EPContext route | Stopped after two pre-inference phone attempts; plugin did not claim first context |
| Direct-QNN host probe | Exact first context loaded, graph retrieved, and graph executed status 0 on x86 HTP emulation; outputs finite |
| Direct Android runner | API-31 AArch64, 307,416 bytes / SHA `484c4a19…3148`; direct public QNN APIs, no ORT |
| Direct phone stage | 272 payload files / 1,974,276,800 bytes, locally hash-verified outside Git |
| Declared CPU boundary | Selected-row Q4 embedding, orchestration, and global argmax only |
| Android / physical HTP execution for direct route | Not attempted; pending Pi priority |
| Canonical campaign and Android performance | Not run; no setup, TTFT, prefill, decode, memory, thermal, or power result |
| Android LLM registry row | None; host AOT and wiring evidence are not registry-eligible |

The previous phone attempts are physical transport/provider-selection diagnostics, not HTP execution. The new direct-QNN result is host emulator execution, not physical execution: host emulation, finite outputs, a cross-compiled runner, and a verified local stage cannot substitute for phone context loading plus provider/RPC/accelerator/cycle/HVX proof. The CPU-bounded host differences are descriptive wiring checks, not a numerical acceptance policy or Android metric.

No 0034 row belongs in the Android LLM registry. A new bounded direct-QNN phone viability gate must first succeed with exact context identity, declared CPU boundaries, physical QNN proof, output evidence, state reset, and scoped cleanup. Even success would be a milestone; a separate complete loaded-route campaign is required for registry publication.
