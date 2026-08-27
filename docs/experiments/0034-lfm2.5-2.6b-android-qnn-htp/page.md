---
experiment: 0034-lfm2.5-2.6b-android-qnn-htp
status: blocked
summary: The fused direct-QNN route physically loaded 19 of 37 exact contexts, then context 20 failed before readiness or graph execution; stronger within-context sharing or whole-route fusion is required.
benchmark: android-llm
---

# Experiment 0034 — LFM2.5-2.6B Android QNN/HTP

## Experiment description

LFM2.5-2.6B has complete Android CPU and OpenCL benchmark routes, but its original QNN assessment found no high-level tool path for the model's `lfm2` architecture. This experiment now tests an architecture-aware route: export the exact model to Q4 ONNX, split its stateful computation into memory-bounded parts, compile every claimed neural part for the Galaxy S23 Ultra's SM8550/HTP v73 target with CPU provider fallback disabled, and then prove that the complete route can execute physically on the phone.

LFM2 is not a renamed Llama-like transformer. Its 30 layers combine 22 recurrent short-convolution layers with 8 full-attention layers, so the route must preserve both convolution state and attention KV state, bind their reset behavior, and prove that claimed model computation runs through QNN HTP. The intentionally CPU-side tokenizer, selected-row Q4 embedding lookup, request orchestration, and one global greedy argmax remain explicit; they are not hidden provider fallback.

The route binds `LiquidAI/LFM2.5-2.6B` revision `ab006873…`, the architecture-aware `Liquid4All/onnx-export` exporter at `9a23ddd…`, symmetric block-32 INT4 weights, and 263 contexts prepared for SoC model 43 / SM8550 / HTP v73. The failed phone route used ONNX Runtime QNN EP 2.5.0; the active continuation now bypasses its EPContext claim layer and calls the public QNN context/graph APIs directly. Moritz reviewed and authorized the named Qualcomm package license and this bounded direct-loader continuation. Packages, source weights, large ONNX data, compiled contexts, and phone stages stay outside Git. The owning [experiment README](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/protocol/experiment-contract.json), [QNN AOT result](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-aot/result.json), [host pipeline comparison](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/htp-pipeline-host-equivalence/result.json), [NPU-selection retry](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/phone-attempt-2-npu-context-claim-failure/result.json), [direct-QNN host preparation](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/direct-qnn-host-preparation/result.json), [first direct phone attempt](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/direct-qnn-phone-attempt-1-linker-failure/result.json), [corrected direct phone attempt](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/direct-qnn-phone-attempt-2-context-limit/result.json), [37-context host preparation](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-consolidated-host-preparation/result.json), and [fused-route physical attempt](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/consolidated-qnn-phone-attempt-1-residency-limit/result.json) are the evidence authority.

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

The complete API-31 AArch64 direct runner is 307,416 bytes with SHA-256 `484c4a19…3148`. It is designed to load all 263 contexts once, preserve explicit 22-convolution plus 8-attention state, and execute the same direct QNN API sequence.

The first bounded direct phone attempt held `phone.lock`, verified the authorized device plus all 272 local and remote payload hashes, and then stopped before entering `main`. Android's dynamic linker reported a missing `std::__ndk1::basic_ifstream` symbol because the stage omitted the NDK `libc++_shared.so` required by the runner. No QNN API was called, no context loaded, no graph or HTP work executed, and no output or performance observation exists. The one memory sample is pre-main only. The process and scoped root were verified absent, and `phone.lock` was released.

The corrected ignored stage contains 273 payload files totaling 1,983,513,152 bytes before its additional metadata and manifest. It includes exact NDK r28b `libc++_shared.so` at SHA-256 `77a34d3f…c754`. An architecture-aware host `readelf` preflight confirms that every AArch64 `DT_NEEDED` dependency is either staged or Android-system-provided and records the DSP6 libc++ dependency as firmware-provided.

The authorized corrected attempt passed the ELF preflight and verified all 273 hashes locally and remotely under the full `phone.lock` lifecycle. The direct QNN runtime then physically deserialized the first 57 exact contexts on SM8550. Context 58 of 263, `layer-07-up-0`, failed in `QnnContext_createFromBinary` before the complete route became ready.

No graph executed and no output or performance result exists. Peak sampled process VmHWM was 74,164 KiB and PSS 43,419 KiB, but process memory excludes DSP/backend allocations and does not explain the backend context limit; these startup observations are not benchmark memory. The process and scoped root were verified absent, and `phone.lock` was released.

The 57-context limit established the need to reduce simultaneously resident contexts. A first shared-EP-context diagnostic compiled 263 ordered graphs into 33 multi-graph binaries, but host retrieval rejected its shared-weights buffer. That 33-context route is retained as rejected rather than assumed to work on Android.

The prepared replacement instead fuses each layer's eight sequential graphs in dependency order and groups independent LM-head chunks. It contains 37 ordinary single-graph contexts:

- 30 fused layer contexts;
- one final-normalization context;
- six LM-head group contexts, each containing at most four vocabulary chunks.

All 37 contexts are loaded once during setup. No request-level or token-level context reload is allowed. The route retains the same 22 convolution states, 8 attention K/V pairs, 4,096-token capacity, and declared CPU selected-row embedding, orchestration, and global-argmax boundaries.

Every fused ONNX model passes checking. All 37 contexts compile fallback-disabled for SoC 43 / HTP v73; framework traces still cover all 1,583 source nodes, 2,747 QNN operations, and zero unsupported nodes. The context binaries total 1,733,937,336 bytes.

Five bounded host CPU steps preserve the split route's greedy decisions while retaining the exact logit/state deltas introduced by changed graph-optimization boundaries. A fused layer-0 context also loads and executes through x86 HTP emulation with finite hidden/state outputs close to CPU reference. These checks protect consolidation wiring only, not exact numerical equivalence, physical HTP, or performance.

The rebuilt API-31 direct runner has SHA-256 `92689331…6f83`. Its ignored stage contains 48 payload files totaling 1,937,978,519 bytes; metadata SHA-256 `c17f77a1…3dd8`, manifest SHA-256 `675e441c…1e79`, and the ELF/hash preflights pass.

The bounded physical gate verified all 48 stage hashes locally and remotely and passed the ELF preflight under the full `phone.lock` lifecycle. Direct QNN successfully deserialized 19 exact fused contexts, `layer-00` through `layer-18`. Context 20 of 37, `layer-19`, then failed in `QnnContext_createFromBinary` before setup completed.

No graph executed and no output or performance result exists. Peak sampled Android process VmHWM was 109,940 KiB, but process RSS excludes DSP/backend allocations and cannot quantify total HTP residency. Because the larger fused contexts fail at a lower count than the former 263-context route, the evidence indicates a resident backend/DSP resource limit rather than a simple context-handle threshold. The process and scoped root were verified absent, and `phone.lock` was released.

The route is blocked. An all-loaded implementation requires materially stronger within-context sharing or whole-route fusion that still passes host compilation and exact graph-order/state validation. Per-layer or per-token context reload is not accepted as equivalent without a separate protocol decision. No further phone run or campaign is authorized.

## Results

**The experiment is blocked on physical all-loaded QNN/DSP residency.** Consolidation reduced the route from 263 to 37 contexts, but the phone loaded only 19 before context 20 failed. The route did not reach readiness or graph execution.

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
| First direct phone attempt | 272 hashes passed; Android linker failed before `main` because `libc++_shared.so` was omitted |
| Corrected direct stage | 273 payload files / 1,983,513,152 bytes, exact NDK r28b libc++ included, ELF dependency preflight passed |
| Corrected physical context loading | 57/263 exact contexts deserialized on SM8550 |
| Historical physical blocker | 263-context route failed at context 58, `layer-07-up-0`, before readiness or graph execution |
| Rejected consolidation diagnostic | 33 shared-weight multi-graph contexts compiled, but host retrieval rejected the shared buffer |
| Prepared consolidated route | 37 ordinary loaded-once contexts: 30 fused layers + final norm + 6 head groups; no per-token reload |
| Consolidated host ownership | 1,583 source nodes / 2,747 QNN ops / 0 unsupported; fallback-disabled SM8550/v73 compile |
| Consolidated host checks | Five greedy decisions preserved with deltas retained; fused layer 0 executes in x86 HTP emulation |
| Consolidated Android stage | Runner SHA `92689331…6f83`; 48 payload files / 1,937,978,519 bytes; local/remote hash and ELF preflight passed |
| Physical fused-context loading | 19/37 contexts (`layer-00`…`layer-18`) deserialized on SM8550 |
| Current blocker | Context 20, `layer-19`, failed in `QnnContext_createFromBinary` before readiness |
| Graph/model/HTP execution and output | 0 graphs; no output or performance result |
| Memory boundary | Process VmHWM 109,940 KiB excludes DSP/backend allocations; not total residency or benchmark memory |
| Cleanup | Scoped root/process absent; `phone.lock` released |
| Declared CPU boundary | Selected-row Q4 embedding, orchestration, and global argmax only |
| Canonical campaign and Android performance | Not run; no setup, TTFT, prefill, decode, memory, thermal, or power result |
| Android LLM registry row | None; host AOT and wiring evidence are not registry-eligible |

The fused attempt proves physical direct-QNN deserialization for 19 exact contexts, not HTP graph execution. It also shows that reducing handle count alone does not resolve the all-loaded residency requirement. Fallback-disabled host compilation, matching five greedy choices, x86 emulation, and partial phone loading cannot substitute for complete readiness plus provider/RPC/accelerator/cycle/HVX execution proof. Retained host deltas and process-only memory are descriptive observations, not an Android performance metric.

No 0034 row belongs in the Android LLM registry. A new host design must materially increase within-context sharing or fuse the whole route while preserving exact loaded-route semantics; only then could a separately authorized physical viability gate be considered. No per-layer/token reload, retry, campaign, or registry publication is currently authorized.
