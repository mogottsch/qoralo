---
experiment: 0034-lfm2.5-2.6b-android-qnn-htp
status: active
summary: Retained physical AR171 state bridges into CPU AR1 with next argmax 4695 matching both CPU references, but severe state/logit drift makes fidelity a prominent unresolved risk.
benchmark: android-llm
---

# Experiment 0034 — LFM2.5-2.6B Android QNN/HTP

## Experiment description

LFM2.5-2.6B has complete Android CPU and OpenCL benchmark routes, but its original QNN assessment found no high-level tool path for the model's `lfm2` architecture. This experiment now tests an architecture-aware route: export the exact model to Q4 ONNX, split its stateful computation into memory-bounded parts, compile every claimed neural part for the Galaxy S23 Ultra's SM8550/HTP v73 target with CPU provider fallback disabled, and then prove that the complete route can execute physically on the phone.

LFM2 is not a renamed Llama-like transformer. Its 30 layers combine 22 recurrent short-convolution layers with 8 full-attention layers, so the route must preserve both convolution state and attention KV state, bind their reset behavior, and prove that claimed model computation runs through QNN HTP. The intentionally CPU-side tokenizer, selected-row Q4 embedding lookup, request orchestration, and one global greedy argmax remain explicit; they are not hidden provider fallback.

The route binds `LiquidAI/LFM2.5-2.6B` revision `ab006873…`, the architecture-aware `Liquid4All/onnx-export` exporter at `9a23ddd…`, symmetric block-32 INT4 weights, and 263 contexts prepared for SoC model 43 / SM8550 / HTP v73. The failed phone route used ONNX Runtime QNN EP 2.5.0; the active continuation now bypasses its EPContext claim layer and calls the public QNN context/graph APIs directly. Moritz reviewed and authorized the named Qualcomm package license and this bounded direct-loader continuation. Packages, source weights, large ONNX data, compiled contexts, and phone stages stay outside Git. The owning [experiment README](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/README.md), [experiment contract](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/protocol/experiment-contract.json), [QNN AOT result](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-aot/result.json), [host pipeline comparison](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/htp-pipeline-host-equivalence/result.json), [NPU-selection retry](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/phone-attempt-2-npu-context-claim-failure/result.json), [direct-QNN host preparation](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/direct-qnn-host-preparation/result.json), [first direct phone attempt](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/direct-qnn-phone-attempt-1-linker-failure/result.json), [corrected direct phone attempt](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/direct-qnn-phone-attempt-2-context-limit/result.json), [37-context host preparation](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-consolidated-host-preparation/result.json), and [fused-route physical attempt](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/consolidated-qnn-phone-attempt-1-residency-limit/result.json), [single-context host preparation](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-whole-route-shared-host-preparation/result.json), [single-context physical attempt](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/whole-route-shared-qnn-phone-attempt-1-load-failure/result.json), [matched QAIRT 2.49.40 Android preparation](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qairt-24940-matched-android-preparation/result.json), [matched-runtime physical attempt](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qairt-24940-matched-phone-attempt-1-context-create-failure/result.json), [ordinary monolithic host preparation](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-ordinary-monolithic-host-preparation/result.json), [ordinary monolithic physical viability](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-ordinary-monolithic-phone-viability-position0/result.json), [host two-step state check](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-ordinary-monolithic-host-two-step-state-check/result.json), [physical two-step state check](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-ordinary-monolithic-phone-two-step-state-check/result.json), [canonical-short gate plan](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-ordinary-monolithic-canonical-short-gate-plan/result.json), and [canonical-short bounded output](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-ordinary-monolithic-phone-canonical-short-max16/result.json), and [AR1 bottleneck inventory](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-ordinary-monolithic-ar1-profile/result.json), and [AR32/AR128 chunked-prefill probes](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-prefill-ar32-ar128-host-probes/result.json), [AR57/AR171 exact-tiling probes](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-prefill-ar57-ar171-host-probes/result.json), and [physical AR171 diagnostic](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-prefill-ar171-phone-runtime-diagnostic/result.json), and [AR171-to-AR1 bridge validation](../../../experiments/0034-lfm2.5-2.6b-android-qnn-htp/results/qnn-prefill-ar171-to-ar1-host-bridge/result.json) are the evidence authority.

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

The physical 37-context failure remains the motivation for stronger sharing. All 37 fused graphs are now compiled into one 1,601,482,752-byte shared-resource QNN context at SHA-256 `7942ad31…8a3`. QNN system metadata reports exactly 37 graph names in required layer/final-normalization/head order, and every EPContext descriptor binds its corresponding graph name to that single binary. The runner loads the context once and retrieves all 37 graphs; it introduces no request-level or token-level reload.

The x86 HTP emulator rejects context retrieval with `Shared weights buffer isn't supported on this platform`. This is an explicit host-platform limitation, not evidence that Android supports or rejects the context. As a result there is no host graph execution for the one-context route and no physical execution claim.

The ignored Android stage contains 12 payload files totaling 1,805,523,151 bytes. It binds runner SHA-256 `92689331…6f83`, stage metadata SHA-256 `9fafbe10…15d7`, manifest SHA-256 `b3ee38ec…00f`, the single exact context, embedding tables, prompt, and QNN runtime; hash and ELF preflights pass.

The authorized physical compatibility gate passed the 12 local/remote hash checks and ELF preflight under the full `phone.lock` lifecycle. It then passed the one 1,601,482,752-byte context to direct QNN. `QnnContext_createFromBinary` returned `Could not create context from binary` before any of the 37 graphs could be retrieved.

Zero contexts loaded, zero graphs were retrieved or executed, and no output or performance result exists. Sampled process VmHWM reached 1,613,220 KiB and PSS 1,599,271 KiB while materializing approximately the blob size; this does not prove successful DSP allocation or explain the generic backend failure. The scoped root/process were verified absent, and `phone.lock` was released.

The single-context failure is terminal for the mismatched Android runtime used in that attempt, not for an exact 2.49.40 pairing. The context metadata identifies compiler build `v2.49.40.260810104044`, while the physical attempt entered Android backend `v2.49.0.260730134355`. Moritz therefore authorized one ordered correction using the exact licensed QAIRT 2.49.40 Android runtime.

A replacement ignored stage now binds the unchanged 1,601,482,752-byte, 37-graph context to Android HTP/System/v73 stub and skeleton libraries whose build ID exactly matches `v2.49.40.260810104044`. The 12 payload files total 1,799,472,275 bytes. Stage metadata SHA-256 is `ec531bd0…9edb`, manifest SHA-256 is `ae0e147f…602`, and the runner remains `92689331…6f83`. All local hashes, AArch64/DSP6 ABIs, SONAMEs, declared system dependencies, and ELF dependency preflight pass.

Pi then authorized one bounded matched-runtime compatibility gate. Under the full `phone.lock` lifecycle, the verified SM-S918B/SM8550 passed all 12 local and remote hashes plus ELF preflight. The direct backend reported build `v2.49.40.260810104044`, exactly matching the context compiler build. The unchanged 1,601,482,752-byte, 37-graph shared-resource context nevertheless failed in `QnnContext_createFromBinary` before graph retrieval or readiness. This rules out runtime-version mismatch as the explanation for the shared-context rejection.

Zero contexts loaded successfully, and zero graphs were retrieved or executed. No output or performance result exists. Sampled process VmHWM peaked at 1,613,264 KiB while materializing approximately the context-blob size; this does not prove DSP allocation or identify the rejected backend resource. Cleanup verified the scoped remote root and process absent, then released `phone.lock`.

The shared-resource option is rejected and will not be retried.

Authorized option 2 now merges the 37 previously verified fused regions into one ordinary non-shared ONNX graph in exact execution order: layers 0–29, final normalization, then the six grouped LM-head regions. Its external boundary preserves 38 explicit state inputs and outputs for the 22 recurrent-convolution states and eight attention K/V pairs, plus 22 logit-chunk outputs. The route is loaded once with no sharing or streaming; CPU work remains selected-row asymmetric Q4 embedding dequantization, orchestration, and one global greedy argmax.

The one-token graph compiles fallback-disabled for SM8550/v73 with all 1,541 optimized source nodes supported, zero unsupported nodes, 2,698 QNN operations, and one QNN subgraph. The resulting ordinary context is 1,600,097,976 bytes with SHA-256 `76ba15e7…f212`. QNN metadata binds build `v2.49.40.260810104044`, one graph with 41 inputs and 60 outputs, `main_context=1`, `embed_mode=0`, and no shared-resource generation option.

A direct-QNN host probe loaded the single context once and executed the complete graph through x86 HTP emulation. For token 124894 at position zero, global greedy argmax was 124894, matching both the split and consolidated CPU references. The 467.814-second host duration is emulator diagnostics only, not Android or physical performance.

The exact-runtime Android stage contains 12 payload files totaling 1,798,094,075 bytes. Stage metadata SHA-256 is `3260c006…c952`, manifest SHA-256 is `5dc98157…169c`, and runner SHA-256 is `4515d7f5…cfd`; local hashes and ELF dependency preflight pass.

After independent review, one bounded phone gate used that exact stage under the full `phone.lock` lifecycle. The verified SM-S918B/SM8550 passed all 12 local and remote hashes plus ELF preflight. Physical direct QNN backend `v2.49.40.260810104044` loaded the ordinary non-shared context once, retrieved its one full graph, and completed exactly one position-zero token/state execution through HTP v73. Neural CPU fallback was unavailable.

Input token 124894 produced global argmax 124894, matching the split CPU, consolidated CPU, and x86 HTP references. This establishes physical full-graph viability and the expected greedy decision for one position-zero input only. It is not a canonical prompt, multi-token generation, decoded-text result, or output-quality claim.

Setup took 4.02188 seconds and the single request took 0.980297 seconds. These are viability diagnostics, not setup/TTFT/throughput campaign measurements. Peak sampled process VmHWM was 1,611,888 KiB and total PSS 1,597,572 KiB; both are Android process observations, not total system or DSP residency.

Raw provider, identity, stage-hash, input/output, timing, memory, thermal/power, and cleanup evidence are retained. Cleanup verified the scoped remote root and process absent, then released `phone.lock`.

The smallest host-side preparation for a proposed multi-position gate then ran canonical-short prefix tokens `[124894, 124899]` through the same ordinary context in x86 HTP emulation. The context loaded once and executed twice without reload. After position zero, all 22 recurrent-convolution states were replaced; each of eight attention K/V pairs wrote its 512-element token slice; all 38 state tensors were supplied to position one. `position_ids` advanced from 0 to 1 and the attention mask opened the prior position while retaining the current slot.

At position one, global greedy argmax was 25, matching both split and consolidated CPU references. This protects two-step state, position, mask, and greedy-decision flow on the host. The 778.395-second duration is x86 emulator diagnostics only.

A separately authorized phone gate then ran the same exact prefix `[124894, 124899]` on the verified SM-S918B/SM8550. All 12 local/remote stage hashes and ELF preflight passed. One ordinary context and graph loaded once through direct QNN HTP `v2.49.40.260810104044`; two sequential graph executions completed with zero context reloads and neural CPU fallback unavailable. All 38 states were carried to position one, including replacement of 22 convolution states and insertion of eight 512-element K/V slices, while position and attention mask advanced identically to the host check.

Physical position-one global argmax was 25, matching both CPU references and x86 HTP. Setup was 4.196 seconds and the two-step request was 2.063 seconds; these are bounded diagnostics, not token throughput or campaign performance. Peak sampled process VmHWM was 1,611,028 KiB and PSS 1,598,512 KiB, which are process-only observations rather than total system or DSP residency.

Exact provider, stage, prefix, output, timing, memory, thermal/power, identity, and cleanup evidence are retained. The scoped root and process were absent afterward and `phone.lock` was released. Two prefix tokens still do not complete the canonical prompt or produce generated text, so no output-quality, performance, campaign, or registry claim exists.

A host-reviewed plan now binds the next proposed boundary without running it. The unchanged 12-file stage, ordinary context, runner, QAIRT build, canonical workload, rendered prompt, token IDs, tokenizer, and template remain hash-fixed. The proposed gate would consume all 171 exact canonical-short input tokens on one loaded context and greedily generate at most 16 tokens, stopping early at EOS 124900. That implies 171–186 full-graph executions.

The plan retains all 38 explicit state tensors, advances position IDs across prompt and generated-token positions, opens prior populated attention-mask positions, and prohibits context reload or streaming. Its evidence order requires device identity, local hashes/ELF, remote hashes, provider and process sampling, then pulling raw `output.int32le` before token range checks or decoding. Any context-load or graph-execution failure stops without retry; output must contain 1–16 IDs in `[0, 127999]`.

The plan itself was host review only. After independent review and explicit priority, exactly one planned gate ran under the full `phone.lock` lifecycle. The verified SM-S918B/SM8550 passed all stage and ELF checks; direct QNN HTP `v2.49.40.260810104044` loaded the ordinary context and graph once. It consumed all 171 exact prompt tokens and generated 16 greedy tokens across 186 sequential full-graph executions with all 38 states carried, positions 0–185 advanced, and no context reload or streaming.

The 64-byte raw token output was pulled before validation or decoding and is bound at SHA-256 `214a8f58…8ef2`. All 16 IDs are in vocabulary. After cleanup, the pinned tokenizer decoded the exact partial continuation:

> The user wants me to read a fictional engineering brief about three local inference engines (

This is coherent bounded output, but it stops at the authorized 16-token ceiling without EOS 124900 and is neither a complete sentence nor a complete answer. It supports narrow generated-token sanity only, not broad output quality.

Setup took 3.472 seconds, request-to-first-token took 185.986 seconds, and total request time was 202.433 seconds. These are single-run diagnostics, not a statistical benchmark or campaign performance distribution. Peak sampled process VmHWM was 1,611,816 KiB and PSS 1,599,584 KiB; both are process-only observations, not total system or DSP residency.

Exact provider, stage/workload hashes, raw output, decode, timing, memory, thermal/power, identity, and cleanup evidence are retained. The scoped root and process were absent afterward and `phone.lock` was released.

Performance engineering now begins from a host-only static inventory of that accepted AR1 baseline. Each graph call exposes 41 raw FP32 inputs totaling 134,750,216 bytes (128.508 MiB); attention K/V state alone is 134,184,960 bytes. The runner copies every input from CPU memory into QNN raw buffers. Its 60 raw outputs total 1,085,440 bytes: 573,440 bytes of updated state and 512,000 bytes across 22 logit chunks.

Context metadata reports 1,596,407,808 bytes of constants, 135,979,008 bytes of I/O tensors, a 103,874,560-byte spill/fill buffer, 15,385,088 bytes of DDR tensors, 6,409,984 bytes of operation data, and zero shared weights. Compiler sequencing estimates 6.029 GB spill, 6.068 GB fill, 6.105 GB total writes, and 7.817 GB total reads per execution. These are compiler estimates, not measured bus counters, and do not prove every constant byte is reread.

The exact 2,698-operation mix includes 698 reshapes, 557 casts, 281 elementwise multiplies, 278 Conv2d operations, 192 adds, 22 depthwise convolutions, 16 MatMuls, and eight Softmax operations. Arithmetic over the single accepted phone run gives about 1.088 seconds per prompt AR1 call and 1.096 seconds per post-first decode call; these remain one-run diagnostics, not a candidate benchmark or statistical distribution.

The first chunked-prefill probes now cover AR32 and AR128. Both keep prior K/V left-aligned, apply causal attention within the current chunk, return only the new K/V slices, carry all 22 convolution states, and compute the 22 logit chunks only at the final chunk position. CPU work remains selected-row Q4 embedding and one global argmax.

CPU comparison against sequential AR1 preserves each final greedy decision: AR32 selects token 20 at position 32, and a carried second AR32 chunk selects 342 at position 64; AR128 selects 116311 at position 128. Numeric equivalence is not established. Only 20/38 AR32 and 19/38 AR128 state tensors meet `rtol=0.02, atol=0.02`; maximum state deltas are 0.307 and 0.552, and maximum logit deltas are 0.512 and 0.383.

Both candidates compile fallback-disabled for SM8550/v73 as one QNN subgraph with 1,542/1,542 optimized nodes supported, 2,699 QNN operations, and zero unsupported nodes. AR32 produces a 1,602,820,688-byte context; AR128 produces a 1,605,986,896-byte context. These are host AOT artifacts only—neither graph has executed through HTP or on the phone.

Neither width exactly tiles the 171-token canonical short prompt, so exact-tiling host probes tested AR57 and AR171. AR57 carries all 38 states across three chunks and preserves sequential-AR1 endpoint decisions `[8771, 437, 597]` at positions `[57, 114, 171]`; AR171 preserves final argmax 597 in one chunk. Material drift remains: AR57 state/logit maximum deltas reach 0.665/0.724, while AR171 reaches 0.514/0.771. This is not exact equivalence.

Both exact-tiling variants compile fallback-disabled as one ordinary QNN graph with 1,542/1,542 supported nodes, 2,699 QNN operations, and zero unsupported nodes. AR57's context is 1,600,858,704 bytes; AR171's is 1,602,378,320 bytes at SHA-256 `d5ca624c…ba5a`. Compiler estimates favor one AR171 call over three AR57 calls for aggregate read/write traffic, but those estimates are not physical counters.

A bounded AR171 x86 HTP probe loaded the context and retrieved its graph, then exceeded 1,800 seconds during execution with no output; the process was absent afterward. That establishes an impractical host emulator path, not a target-SM8550 failure.

The subsequent physical diagnostic staged 48 exact payloads and 41 precomputed raw inputs totaling 133,358,252 bytes. On verified SM-S918B/SM8550, QAIRT `v2.49.40.260810104044` created the ordinary context, retrieved one graph, and completed one direct-QNN HTP execution across all 171 prompt tokens. All 60 raw outputs—38 state tensors and 22 logit chunks—were finite. Physical endpoint argmax 597 matches sequential AR1 and chunk CPU references; numeric state/logit equivalence is not claimed.

Detailed profile observations are NetRun initialization 1.724910 seconds, NetRun execution 6.308347 seconds, QNN execution 6.308240 seconds, RPC execution 6.294107 seconds, and accelerator execution 5.234013 seconds (5.231422 excluding wait), with 3,260,126,464 cycles and four HVX threads. CPU embedding dequantization and raw-input preparation were precomputed and excluded. These numbers are not end-to-end TTFT, apples-to-apples AR1 comparison, statistical performance, or a campaign.

Peak sampled process PSS was 1,572,936 KiB and VmHWM 1,576,200 KiB; HTP-private and total system residency remain unavailable. AP temperature rose 37.8→47.3°C and skin 35.4→36.4°C. Raw provider/profile, hashes, inputs, all outputs, validation, memory, thermal, identity, and cleanup evidence are retained; scoped process/root cleanup passed and `phone.lock` was released.

A host bridge then consumed those retained physical outputs rather than regenerated substitutes. Each physical 171-position K/V slice is copied into positions `0:171` of the AR1 cache, remaining positions are zeroed, all 22 convolution states are carried, token 597 is CPU-embedded at position 171, and the mask exposes prior positions plus the current slot. The resulting next argmax is 4695 for physical-AR171→AR1, CPU-AR171→AR1, and sequential-AR1→AR1; it also matches the second token from the earlier physical AR1 continuation.

That greedy agreement is not numerical fidelity. Before the continuation, physical AR171 versus CPU AR171 has only 3/38 state tensors allclose at `rtol=0.02, atol=0.02`, with maximum absolute delta 10,586.69. After one AR1 step, physical-versus-CPU state and logit maximum deltas remain 3.61 and 7.07. Every retained physical file is finite FP32, metadata-size-valid, and layout-validated, so the drift is real evidence rather than hidden corruption or a parsing shortcut.

Concurrent AR171+AR1 residency was not attempted. Metadata totals 3,202,476,296 bytes of context binaries, roughly 3.19 GB duplicated constants, 276 MB I/O tensors, and 568 MB spill/fill buffers. Metadata alone does not prove failure, but earlier residency failures make simultaneous loading high risk.

The selected candidate therefore uses one explicit phase transition: load AR171 once for prefill, preserve its 38 outputs, free AR171, convert/place the cache contract on CPU, then load AR1 once for decode. This is a declared CPU bridge and one-time prefill-to-decode switch, not an HTP-only route and not per-token context streaming. No phone bridge, end-to-end performance, generated-text, campaign, or registry result exists.

## Results

**The experiment is active on an explicit AR171-prefill to AR1-decode phase-switch candidate.** Retained physical state produces the expected next greedy token through CPU AR1, but severe pre-state and post-step numerical drift remains. The bridge is host-only and the two-context route has not run physically.

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
| Single shared-resource context | 1,601,482,752 bytes / SHA `7942ad31…8a3`; all 37 fused graphs bound once in exact order |
| Host retrieval | Rejected because shared weights are unsupported on the x86 HTP platform; no one-context graph executed |
| One-context Android stage | 12 payload files / 1,805,523,151 bytes; hash and ELF preflight passed outside Git |
| Physical single-context gate | All 12 hashes/ELF passed; mismatched v2.49.0 backend rejected the v2.49.40 1.60 GB context before graph retrieval |
| Shared-route context/graph/output | 0 loaded / 0 retrieved or executed / none |
| Shared-route memory boundary | VmHWM 1,613,220 KiB reflects blob materialization only, not proven DSP allocation or benchmark memory |
| Cleanup | Scoped root/process absent; `phone.lock` released |
| Exact runtime correction | Context and Android backend build IDs both `v2.49.40.260810104044` |
| Matched Android stage | 12 payload files / 1,799,472,275 bytes; licensed HTP/System/v73 stub/skel hashes and ABIs bound |
| Matched-stage checks | Local/remote hashes and ELF preflight pass on verified SM-S918B/SM8550 |
| Exact physical build match | Backend and context both `v2.49.40.260810104044`; runtime mismatch ruled out |
| Matched physical outcome | `QnnContext_createFromBinary` rejected unchanged 1.60 GB / 37-graph shared context before retrieval |
| Matched-route context/graphs/output | 0 loaded / 0 retrieved or executed / none |
| Matched-route memory boundary | VmHWM 1,613,264 KiB is blob materialization only, not successful DSP allocation or benchmark memory |
| Active option 2 | Ordinary non-shared one-token graph; 38 explicit state inputs/outputs + 22 logit chunks; loaded once, no streaming |
| Monolithic QNN ownership | 1,541/1,541 optimized source nodes supported; 2,698 QNN ops; 0 unsupported; one subgraph |
| Ordinary context | 1,600,097,976 bytes / SHA `76ba15e7…f212`; QAIRT 2.49.40; one graph / 41 inputs / 60 outputs |
| Host x86 HTP check | Context loaded once, full graph executed; argmax 124894 matches split and consolidated CPU references |
| Host timing boundary | 467.814 s is x86 emulator diagnostics, not physical or benchmark performance |
| Monolithic Android stage | 12 payload files / 1,798,094,075 bytes; exact runtime; local hashes and ELF preflight pass |
| Monolithic physical route | Verified SM-S918B/SM8550; QNN HTP v2.49.40; ordinary context loaded once; one full graph retrieved and executed |
| Position-zero decision | Input 124894 → global argmax 124894, matching split CPU, consolidated CPU, and x86 HTP references |
| Physical workload boundary | One position-zero token/state graph execution; not canonical prompt, multi-token text, or quality evidence |
| Physical timing boundary | Setup 4.02188 s; request 0.980297 s; viability diagnostics only, not campaign performance |
| Physical memory boundary | VmHWM 1,611,888 KiB / PSS 1,597,572 KiB are process-only, not total DSP/system residency |
| Host two-step input | Canonical-short prefix `[124894, 124899]`; two full-graph executions on one loaded context, no reload |
| Host state transport | All 38 states carried position 0→1; recurrent states replaced; eight K/V slices written; position/mask advanced |
| Host position-one decision | Argmax 25 matches split and consolidated CPU references |
| Host two-step timing/scope | 778.395 s x86 emulator diagnostic; not physical or benchmark performance |
| Physical two-step route | Verified SM-S918B/SM8550; one ordinary context/graph loaded once; two direct-QNN HTP executions; zero reloads |
| Physical state flow | All 38 states carried position 0→1; position/mask advanced; neural CPU fallback unavailable |
| Physical position-one decision | Argmax 25 matches CPU and x86 HTP references |
| Physical two-step timing | Setup 4.196 s / request 2.063 s; bounded diagnostic, not throughput or campaign performance |
| Physical two-step memory | VmHWM 1,611,028 KiB / PSS 1,598,512 KiB are process-only, not total DSP/system residency |
| Two-step claim limit | First two canonical-short tokens only; no full prompt, generated text, or output quality |
| Planned workload | Exact 171-token canonical short + greedy max 16 / EOS 124900; 171–186 executions |
| Planned loaded route | Same one context/graph loaded once; all 38 states; position/mask advancement; no reload/streaming |
| Planned evidence order | Preserve raw token output before validation/decoding; retain provider/hash/memory/thermal/identity/cleanup |
| Canonical-short physical route | One ordinary context/graph loaded once; 171 prompt + 16 generated tokens; 186 QNN HTP executions; no reload/streaming |
| Stateful range | All 38 states carried and position/mask advanced across positions 0–185 |
| Raw output provenance | 64 bytes / SHA `214a8f58…8ef2`; preserved before validation and decode; all IDs in vocabulary |
| Bound decoded fragment | `The user wants me to read a fictional engineering brief about three local inference engines (` |
| Output boundary | Coherent partial continuation; max-16 stop, no EOS, sentence, or answer completion; narrow sanity only |
| Single-run timing | Setup 3.472 s; request-to-first-token 185.986 s; total 202.433 s; not statistical performance |
| Canonical-short memory | VmHWM 1,611,816 KiB / PSS 1,599,584 KiB are process-only, not total DSP/system residency |
| Result limit | No broad quality, campaign, statistical-performance, or registry claim |
| AR1 raw input per call | 134,750,216 B / 128.508 MiB; 134,184,960 B attention state; all 41 inputs CPU-memcpy to QNN |
| AR1 raw output per call | 1,085,440 B: 573,440 B state + 512,000 B logits |
| Context static footprint | 1,596,407,808 B constants; 135,979,008 B I/O; 103,874,560 B spill/fill buffer |
| Compiler traffic estimate | 6.029 GB spill / 6.068 GB fill / 6.105 GB write / 7.817 GB read per call; not measured counters |
| Operation inventory | 2,698 QNN ops; led by 698 reshape, 557 cast, 281 multiply, 278 Conv2d |
| Baseline arithmetic | ~1.088 s prompt AR1 / ~1.096 s post-first decode graph; one-run diagnostic only |
| AR32 semantics | Causal chunk + carried K/V/state; argmax 20 at token 32 and 342 after second chunk match AR1 |
| AR128 semantics | Causal chunk + carried K/V/state; token-128 argmax 116311 matches AR1 |
| Numeric drift boundary | AR32 20/38 states close, max state/logit 0.307/0.512; AR128 19/38, 0.552/0.383 |
| AR32 host QNN AOT | 1,542/1,542 supported; 2,699 ops; 0 unsupported; 1 subgraph; 1,602,820,688 B context |
| AR128 host QNN AOT | 1,542/1,542 supported; 2,699 ops; 0 unsupported; 1 subgraph; 1,605,986,896 B context |
| Chunked-prefill physical boundary | CPU semantics + host AOT only; no HTP graph execution or phone performance |
| AR57 exact tiling | 3×57 chunks; endpoint argmax `[8771,437,597]` matches AR1; state/logit max delta 0.665/0.724 |
| AR171 exact tiling | 1×171 chunk; argmax 597 matches AR1; state/logit max delta 0.514/0.771 |
| Exact-tiling AOT | Both 1,542/1,542 supported, 2,699 ops, 0 unsupported, one ordinary QNN graph |
| Host emulator boundary | AR171 load/retrieve passed, execution timed out at 1,800 s with no output; not SM8550 failure |
| Physical AR171 route | 48 hashes passed; one 171-token HTP graph call; 41 inputs/133,358,252 B; 60 outputs finite |
| Physical endpoint | Argmax 597 matches sequential AR1 and chunk CPU; no numeric-equivalence claim |
| Physical profile | NetRun 6.308347 s; QNN 6.308240 s; accelerator 5.234013 s; CPU input prep excluded |
| AR171 memory/thermal | PSS 1,572,936 KiB / VmHWM 1,576,200 KiB process-only; AP 37.8→47.3°C, skin 35.4→36.4°C |
| Diagnostic boundary | No end-to-end TTFT, decode, generated text, statistical campaign, or registry claim |
| Bridge construction | Retained physical K/V → AR1 cache `0:171`; 22 conv states carried; token597/position171/mask bound |
| Bridge greedy result | Next argmax4695 matches physical-state bridge, CPU-AR171 bridge, sequential AR1, and prior physical AR1 token2 |
| Severe pre-state drift | Physical vs CPU AR171 only 3/38 allclose; max absolute delta 10,586.69 |
| Post-step drift | Physical-state vs CPU-state AR1 continuation max state/logit delta 3.61/7.07 |
| Output integrity | Physical tensors are finite FP32 with metadata-valid sizes/layout; drift remains disclosed |
| Concurrent residency | Untested/high-risk; 3.202 GB contexts, ~3.19 GB duplicated constants before I/O/spill |
| Selected phase semantics | AR171 load/prefill/free → CPU cache conversion → AR1 load/decode; one switch, no per-token streaming |
| Bridge physical boundary | Host-only; no concurrent/phase-switch phone execution, end-to-end performance, text, or campaign |
| Hybrid disclosure rule | CPU bridge + HTP phases must remain explicit; never label this candidate HTP-only |
| Declared CPU boundary | Current baseline: selected-row Q4 embedding, orchestration, and global argmax only |
| Canonical campaign and Android performance | Not run; no setup, TTFT, prefill, decode, memory, thermal, or power result |
| Android LLM registry row | None; host AOT and wiring evidence are not registry-eligible |

The ordinary AR1 route remains the end-to-end bounded baseline. AR171 proves physical one-call prefill viability, and the host bridge preserves the next greedy choice, but the severe retained-state drift blocks any broad equivalence claim. The explicit free/convert/load phase switch is a candidate design, not a measured complete route.

No 0034 row belongs in the Android LLM registry. The registry requires the fully disclosed selected prefill+decode route to complete a valid loaded-route campaign. Physical phase-switch execution, generated text, reset isolation, statistical performance, and registry publication remain outside this milestone.
