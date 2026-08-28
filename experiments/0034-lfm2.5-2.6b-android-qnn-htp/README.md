# Experiment 0034: LFM2.5-2.6B Android QNN/HTP

## Status

**Physical direct-QNN HTP canonical-short bounded generation passed. The Galaxy S23 Ultra loaded one ordinary non-shared context once, consumed all 171 exact canonical-short tokens, and produced a coherent 16-token greedy continuation through 186 stateful graph executions with no reload or streaming. This is one bounded output-sanity run—not a completed answer, statistical performance campaign, or registry entry.**

This is a separate accelerator arm. It preserves `0029` CPU viability and `0033` CPU/OpenCL campaign evidence without modifying either experiment.

## Exact route

- Model: `LiquidAI/LFM2.5-2.6B`
- Source revision: `ab00687315bc1298e9d54e9c4b611dde9867ccc2`
- Source shards: 5,329,406,264 bytes / SHA-256 `05be188e…854cc`; 65,021,192 bytes / SHA-256 `532f803a…bca8`
- Architecture: 22 recurrent short-convolution layers plus 8 full-attention layers
- Exporter: `Liquid4All/onnx-export` commit `9a23ddd23035165f7414a5de3220a51e85780f64`
- Quantization: symmetric INT4 weight-only block quantization, block size 32, represented with `MatMulNBits` and `GatherBlockQuantized`; no activation calibration
- Provider: Qualcomm-maintained ONNX Runtime QNN EP 2.5.0 with its 2.49.40 host preparation runtime, targeting SoC model 43 / SM8550 / HTP v73

Moritz personally reviewed and authorized the Qualcomm AI Stack License for the named public QNN packages. Those packages, source weights, large ONNX data, and future license-controlled compiled artifacts remain outside Git. Git retains only permitted tools, hashes, provenance, analysis, and evidence.

## Export milestone

The exporter produced a 315,101-byte ONNX graph and 1,855,348,736-byte external tensor file. The raw graph exposed all expected stateful architecture components: 22 convolution nodes, 8 `GroupQueryAttention` nodes, and 167 `MatMulNBits` nodes.

LiquidONNX commit `9a23ddd…` emitted 76 `SimplifiedLayerNormalization` nodes into the standard ONNX domain even though that op is a Microsoft contrib op. ONNX Runtime 1.26 correctly rejected it before provider selection. [`tools/rewrite_rms_norm.py`](tools/rewrite_rms_norm.py) applies the mathematically equivalent standard-ONNX formula to those 76 nodes and the final skip-RMSNorm:

```text
x * scale / sqrt(reduce_mean(pow(x, 2), axis=-1) + 1e-5)
```

The rewritten graph is 410,142 bytes, SHA-256 `c2020ab7371d52df51683e663abff5d07eefcda604ddee159d02b7d73432d157`, passes the ONNX checker, and still references the exact external tensor file SHA-256 `d3cf09855c69d5226d9ce481a83bce31981496e2a686a7879750a3f82e90f457`.

Exact source, exporter, graph, operator, and quantization provenance is in [`results/export-provenance/result.json`](results/export-provenance/result.json).

## Bounded host viability

The rewritten export loaded with ONNX Runtime 1.26 CPU and processed the exact canonical short workload using the pinned tokenizer/template:

- workload SHA-256: `81d23ec04cb821625d3717ab50db7df3d9821a8d2987f1eb107fc90df9d1f2ae`;
- 171 input tokens, rendered prompt SHA-256 `9e6c713e…e622`;
- bounded 16-token continuation: 88 UTF-8 bytes, SHA-256 `f048f9244ab0728a86719fa502f954da2acc987eabb68220995b98ff18718518`;
- superficial sensible-text check: passed.

See [`results/host-export-smoke/`](results/host-export-smoke/). This is only an economical export viability check. Its timing, output length, and CPU provider are not Android/QNN/HTP evidence and are not registry eligible.

## Fallback-disabled QNN AOT milestone

A one-token static route now submits prompt and generated tokens sequentially through one explicit-state pipeline with a 4,096-token attention capacity. Request reset is unambiguous: zero 22 convolution caches and all 8 attention K/V pairs. The architecture-aware lowering:

- expands RoPE and grouped-query attention into standard QNN-owned operations while returning only each new K/V slice for a left-aligned cache;
- explicitly keeps the selected-row asymmetric Q4 embedding lookup on CPU because QNN EP 2.5 does not claim `GatherBlockQuantized` on HTP—this is a declared frontend, not provider fallback;
- splits every 10,752-wide MLP as 6,144 + 4,608, padding only the second down-projection dot product with mathematically zero activation/weight blocks to the v73-supported 6,144 width;
- splits the model into memory-bounded contexts: 22 convolution cores, 8 attention cores, all MLP projection/activation/residual work, final norm, and 22 LM-head chunks;
- performs only one global greedy argmax across the HTP LM-head chunks on CPU.

All **263** parts compiled through ONNX Runtime QNN EP 2.5.0 with `session.disable_cpu_ep_fallback=1`, block-quant optimization enabled, and target SoC 43 / HTP V73. Their traces bind all 1,583 source ONNX nodes to 2,747 QNN operations, with zero unsupported nodes. Context binaries total 1,779,492,144 bytes and remain outside Git. See [`results/qnn-aot/result.json`](results/qnn-aot/result.json).

A bounded host reconstruction submitted the exact 171-token canonical short prompt through the final 263-part ordering with zeroed state. Its first five greedy tokens matched both the unsplit transformed graph and the original exported reference. Exact comparisons and limitations are in [`results/htp-pipeline-host-equivalence/`](results/htp-pipeline-host-equivalence/). This protects route wiring; CPU timings and host logits are not Android or HTP results.

## Phone preparation

The native API-31 AArch64 runner and ignored phone stage are ready. The runner loads all 263 context sessions once, requests HTP resource sharing and basic per-context profiling, keeps fallback disabled, submits the exact 171-token short prompt, and caps the viability continuation at 16 tokens. Public Maven artifacts, the runner, every context pair, Q4 embedding tables, and the prompt are covered by a local 540-file stage manifest. The license-controlled stage is 2,015,057,362 bytes before its metadata/manifests and remains outside Git.

The first physical attempt used the full `phone.lock` lifecycle, verified the exact authorized device and every local/remote staged hash, then failed while creating the first EPContext session. ORT reported that nodes would remain on the default CPU EP; `session.disable_cpu_ep_fallback=1` correctly stopped the route. No context session, model token, HTP graph, output, or profile was produced. The 2.0 GB scoped remote root was removed and verified absent. Raw evidence is retained in [`results/phone-attempt-1-provider-selection-failure/`](results/phone-attempt-1-provider-selection-failure/).

The revised runner logged both advertised devices: the ARM CPU and `QNNExecutionProvider type=2 vendor=Qualcomm` (NPU). It selected only the NPU, began loading `layer-00-core-norm`, and received the same default-CPU assignment error. The unchanged `session.disable_cpu_ep_fallback=1` gate stopped it. Again all 540 staged hashes matched locally and remotely; no session/model/HTP execution occurred; the scoped root was verified absent and `phone.lock` released. Raw evidence is in [`results/phone-attempt-2-npu-context-claim-failure/`](results/phone-attempt-2-npu-context-claim-failure/).

The blocker is now precise: the public Android QNN EP 2.5.0 plugin advertises the physical NPU but does not claim the first SM8550/V73 EPContext emitted by the matched 2.5.0 host package. Progress requires a matched Android plugin/runtime that claims these contexts, authorization for a separately bounded direct-QNN context loader that bypasses ORT's failing claim layer, or authorization to escalate the minimal compatibility artifact to Qualcomm's maintainers. No further phone attempt or campaign is authorized.

## Direct-QNN continuation

Moritz selected the direct loader option. The new native runner bypasses ONNX Runtime entirely and uses the public QNN APIs to deserialize, retrieve, and execute the same exact 263 context binaries. The declared CPU boundary is unchanged: selected-row Q4 embedding, orchestration, and global greedy argmax only. All model body, explicit state, final norm, and LM-head chunks remain QNN graphs.

A bounded host probe loaded `layer-00-core-norm` directly with QNN backend build `v2.49.40.260810104044`, retrieved its SM8550/V73 graph, and executed it successfully. Its residual, FFN-normalized, and convolution-state outputs are finite and closely match the CPU graph reference. The x86 backend internally emulates on v79, so this protects direct-loader wiring but is not physical HTP or performance evidence.

The API-31 AArch64 direct runner is 307,416 bytes, SHA-256 `484c4a196f2951f20ef3dbba25c08467451b6a5bac8e7320e12b64b3fab03148`. The corrected 273-payload-file, 1,983,513,152-byte ignored stage contains the exact 263 contexts, embedding tables, prompt, QNN runtime, and NDK `libc++_shared.so`; its local manifest and ELF dependency preflight pass. See [`results/direct-qnn-host-preparation/`](results/direct-qnn-host-preparation/).

The first direct phone gate verified identity and every stage hash, then the Android linker rejected the runner before `main` because the original stage omitted `libc++_shared.so`. Raw evidence is under [`results/direct-qnn-phone-attempt-1-linker-failure/`](results/direct-qnn-phone-attempt-1-linker-failure/).

The corrected retry passed all 273 hashes and ELF preflight, entered the direct runtime, and loaded 57 contexts (all parts through layer 6 plus layer 7 core). Context 58, `layer-07-up-0`, failed in `QnnContext_createFromBinary`. No graph executed because setup never reached readiness. Cleanup was verified absent and `phone.lock` released. See [`results/direct-qnn-phone-attempt-2-context-limit/`](results/direct-qnn-phone-attempt-2-context-limit/).

That result established the need to reduce simultaneously resident contexts. No campaign followed.

## Consolidated loaded route

The host-prepared replacement reduces 263 contexts to **37 ordinary single-graph contexts**:

- 30 layer contexts, each fusing the exact eight prior core/MLP/residual parts in their original dependency order;
- one final-normalization context;
- six LM-head contexts containing at most four independent vocabulary chunks each;
- all contexts loaded once at runner setup, with no per-request or per-token context reload;
- the same 22 explicit convolution states, 8 explicit attention K/V pairs, CPU embedding/orchestration/global-argmax boundary, and 4,096-token capacity.

The initial shared-EP-context approach did compile 263 ordered graphs into 33 multi-graph binaries, but host retrieval rejected its shared-weights buffer as unsupported on that platform. The retained route therefore uses graph fusion rather than weight-sharing serialization.

Every fused model passed ONNX checking. All 37 contexts compiled with fallback disabled for SoC 43 / HTP V73; their traces again bind all 1,583 source nodes to 2,747 QNN operations with zero unsupported nodes. The binaries total 1,733,937,336 bytes. Five bounded CPU steps produced the same greedy decision as the proven split route while exposing all logit and state deltas caused by changed graph-optimization boundaries. A fused layer-0 context also loaded and executed successfully in x86 HTP emulation, returning finite hidden/state outputs close to CPU reference. Neither check is physical-phone evidence.

The rebuilt API-31 direct runner is SHA-256 `92689331d11ecf48fb226e82c0f77133e2b72c505b976f2e801c6fffda506f83`. Its ignored Android stage has 48 payload files totaling 1,937,978,519 bytes; stage metadata SHA-256 is `c17f77a1493c6465a4ba91b410a3f4f586da283cdb19702ca040ac75825a3dd8`, manifest SHA-256 is `675e441c6adac5c46671f325f46477b182d1233ae56806f3c1dfaf74855a1e79`, and the ELF dependency/hash preflight passes. See [`results/qnn-consolidated-host-preparation/`](results/qnn-consolidated-host-preparation/).

The one authorized physical gate verified the exact 48-file stage and entered direct QNN backend `v2.49.0.260730134355`. It loaded `layer-00` through `layer-18`, then `QnnContext_createFromBinary` failed on the twentieth context, `layer-19`. No graph executed because the complete route was not resident. Sampled Android-process VmHWM peaked at 109,940 KiB, but that excludes DSP/backend allocations and does not measure total HTP residency. The scoped root was verified absent and `phone.lock` released. Raw evidence is under [`results/consolidated-qnn-phone-attempt-1-residency-limit/`](results/consolidated-qnn-phone-attempt-1-residency-limit/).

The result shows that the blocker is total resident backend resources rather than a fixed number of context handles: the smaller route loaded 57 contexts, while larger fused contexts stopped after 19. Per-layer or per-token context reload is not treated as equivalent loaded-route behavior.

A materially stronger host-only continuation now packages all 37 fused graphs into **one** shared-resource QNN context. Its binary is 1,601,482,752 bytes, SHA-256 `7942ad31b0bae6d4368ec4a3c86c84ce022c2e6c62bafebeb513c7f38228d8a3`. QNN system metadata reports exactly 37 graphs in the required layer/final-norm/head order, and each retained EPContext descriptor binds the corresponding graph name to that single binary. The runner loads this context once and retrieves all 37 graphs; no reload workaround is introduced.

The x86 HTP emulator rejects context creation with `Shared weights buffer isn't supported on this platform`. That is a host-platform limitation and leaves physical Android support explicitly unproven; it is not execution evidence. The ignored 12-payload Android stage totals 1,805,523,151 bytes, passes all local hashes and ELF preflight, and is bound by stage SHA-256 `9fafbe10f2d69ed4f6690d4e3b010c565f0c222778144d1415d4fa76e79715d7` and manifest SHA-256 `b3ee38ecc999bb74d989058f2342aeee3ab535eee364f14776b94cba9e36400f`. See [`results/qnn-whole-route-shared-host-preparation/`](results/qnn-whole-route-shared-host-preparation/).

The authorized physical compatibility gate passed all 12 local/remote hashes and ELF preflight, entered direct QNN backend `v2.49.0.260730134355`, and attempted the single 1,601,482,752-byte context. `QnnContext_createFromBinary` returned failure before any graph could be retrieved. Android emitted only the generic `Could not create context from binary`, not the host emulator's explicit shared-weight message. Process VmHWM reached 1,613,220 KiB while materializing the blob; this is not evidence that DSP allocation succeeded. The scoped root was verified absent and `phone.lock` released. See [`results/whole-route-shared-qnn-phone-attempt-1-load-failure/`](results/whole-route-shared-qnn-phone-attempt-1-load-failure/).

That result was terminal for the mismatched v2.49.0 Android runtime used by the attempt. Context streaming remains a protocol change and is not authorized.

## Exact QAIRT 2.49.40 Android runtime continuation

Moritz authorized one ordered correction: retry the unchanged one-context/37-graph route with the exact licensed QAIRT 2.49.40 Android libraries matching the host compiler. The prepared runtime identifies itself as `v2.49.40.260810104044`, exactly equal to the context metadata build ID. The prior physical backend identified as `v2.49.0.260730134355`.

The replacement stage binds:

- `libQnnHtp.so`: SHA-256 `4f5b4d11b128d78433730a4f5e88841e51aec472c6bd28ffd858dba8ea1012fb`;
- `libQnnSystem.so`: SHA-256 `536201ed918f4066f9ef35671198c072faf9ef04af24545f5fae0fc79aa05baa`;
- `libQnnHtpV73Stub.so`: SHA-256 `7837f29bd84dbcf542faf1047d3904dc14f578e3d1a472c41eee792e7a1a8db0`;
- `libQnnHtpV73Skel.so`: SHA-256 `e618168c82a0ec763b8543268b2783f5d28c9525fb6d0741afd667869ee493c8`.

All Android libraries retain the expected AArch64/DSP6 ABIs, SONAMEs, and declared system dependencies. The ignored stage has 12 payload files totaling 1,799,472,275 bytes; stage metadata SHA-256 is `ec531bd03cfbb0a271f9b7c1c5d6471ccff202223cab25e36a6da63eee649edb`, manifest SHA-256 is `ae0e147f1d352984ded9f42bb10545478ce7e979f92451b20dec532d01e79602`, and local hash plus ELF dependency checks pass. See [`results/qairt-24940-matched-android-preparation/`](results/qairt-24940-matched-android-preparation/).

The one authorized matched-runtime physical gate passed all 12 local/remote hashes and ELF preflight. The direct backend reported exact build `v2.49.40.260810104044`, equal to the context build, but rejected the 1.60 GB shared context in `QnnContext_createFromBinary`. No graph was retrieved or executed. Peak sampled process VmHWM was 1,613,264 KiB while materializing the blob and is not evidence of successful DSP allocation. Cleanup and lock release passed. See [`results/qairt-24940-matched-phone-attempt-1-context-create-failure/`](results/qairt-24940-matched-phone-attempt-1-context-create-failure/).

Option 1 is rejected and will not be retried.

## Ordinary monolithic one-token route

Authorized option 2 merges the 37 previously verified fused regions into one ordinary ONNX graph in exact order: layers 0–29, final normalization, and all 22 logit chunks. Its external state boundary remains 38 inputs and 38 outputs (22 recurrent-convolution states plus K/V state for 8 attention layers). CPU still performs only selected-row asymmetric Q4 embedding dequantization, orchestration, and global greedy argmax.

The ordinary ONNX model is SHA-256 `40e0e0bf4e0ba0076402b6bcd78496485c7b93117aeb2867968dd421cb2c3eb4`; its 1,779,169,280-byte external data is SHA-256 `f0d25ed9203c132259e9563a43736dc4bae35d7b46c064bebf3fa5464afe16ea`. ORT QNN compiled it fallback-disabled for SM8550/V73 as one subgraph: 1,541/1,541 optimized source nodes supported, 2,698 QNN operations, and zero unsupported nodes.

The resulting **ordinary**, non-shared context is 1,600,097,976 bytes, SHA-256 `76ba15e7fd95e5e13e92be0e88e8e6bbd3123f2b993b6986c9dac8800a9bf212`. QNN metadata reports build `v2.49.40.260810104044`, one graph, 41 inputs, and 60 outputs. Its sole EPContext descriptor has `main_context=1`, `embed_mode=0`, and no shared-resource generation option.

A direct-QNN host probe loaded the single context once and executed the complete graph through x86 HTP emulation. For token 124894 at position zero, global greedy argmax was 124894, matching both the split and consolidated CPU references. The 467.814-second host timing is emulator diagnostics, not physical performance evidence.

The ignored QAIRT 2.49.40 Android stage contains 12 payload files totaling 1,798,094,075 bytes. Stage metadata SHA-256 is `3260c006faf29fc8081f29f4c87069cafeee7919a9af54ac3ceb184e03bcc952`; manifest SHA-256 is `5dc9815787046507b3b09a4aebbe0eb6fd97e6effda3247cfeddda6fb474169c`; the API-31 runner SHA-256 is `4515d7f58889121542b9ff3535d5e083a89095f008fb7bb23ae421f67c8cacfd`. Local hashes and ELF preflight pass. See [`results/qnn-ordinary-monolithic-host-preparation/`](results/qnn-ordinary-monolithic-host-preparation/).

After independent review, one bounded physical gate used that exact stage. All 12 local and remote hashes plus ELF preflight passed. Physical backend `v2.49.40.260810104044` loaded the single ordinary context and retrieved its one graph. Exactly one position-zero token/state graph execution completed through direct QNN HTP, with neural CPU fallback unavailable. Input token 124894 produced global greedy argmax 124894, matching the split CPU, consolidated CPU, and x86 HTP references.

Setup took 4.02188 seconds and the single position-zero request took 0.980297 seconds. These values are diagnostic only: one execution is not a canonical benchmark or throughput campaign. Peak sampled process VmHWM was 1,611,888 KiB and is not total system/DSP residency. Raw identity, provider, stage hashes, input/output, timing, memory, thermal/power snapshots, and cleanup evidence are retained in [`results/qnn-ordinary-monolithic-phone-viability-position0/`](results/qnn-ordinary-monolithic-phone-viability-position0/). The scoped remote root was verified absent and `phone.lock` released.

This establishes physical full-graph viability only. No further ADB, expanded prompt, output-quality claim, campaign, performance publication, or registry row is authorized pending independent review and a separately agreed next gate. Context streaming remains prohibited.

As the smallest feasible host-side preparation for a proposed loaded multi-token gate, the direct runner then executed the first two canonical-short tokens through the same one context in x86 HTP emulation. It executed the graph twice without reloading, carried all 38 state tensors from position 0 to position 1, advanced `position_ids`, and updated the attention mask. The position-1 global argmax was 25, matching both existing CPU references. The 778.395-second host duration is emulator diagnostics only. See [`results/qnn-ordinary-monolithic-host-two-step-state-check/`](results/qnn-ordinary-monolithic-host-two-step-state-check/).

After independent review, the same exact two-token prefix was authorized on the phone. All 12 stage hashes and ELF preflight passed; direct QNN HTP backend `v2.49.40.260810104044` loaded one ordinary context and one graph once, then completed two sequential graph executions without reload. Position-1 output/global argmax was 25, equal across physical, CPU, and host x86 HTP.

Physical setup took 4.19607 seconds and the combined two-step request took 2.06277 seconds. These remain bounded diagnostic timings, not throughput or campaign measurements. Peak sampled process VmHWM was 1,611,028 KiB and is not total DSP/system residency. Raw provider, stage hashes, exact prefix, output, memory, thermal/power, device identity, and cleanup are retained in [`results/qnn-ordinary-monolithic-phone-two-step-state-check/`](results/qnn-ordinary-monolithic-phone-two-step-state-check/). Cleanup verified the scoped root absent and released `phone.lock`.

That two-token prefix is not canonical prompt completion or text generation. No further ADB is authorized until independent review and a separately agreed next gate.

A host-reviewed **plan only** now binds the proposed next gate without using the phone: consume all 171 exact canonical-short prompt tokens with the same loaded context and generate at most 16 greedy tokens, stopping early at EOS 124900. The unchanged 12-file stage, context, runner, QAIRT build, workload/rendered/token hashes, tokenizer/template hashes, state/position/mask semantics, evidence order, fail-closed checks, and cleanup lifecycle are fixed in [`results/qnn-ordinary-monolithic-canonical-short-gate-plan/`](results/qnn-ordinary-monolithic-canonical-short-gate-plan/). Raw token output must be pulled and preserved before post-run range checks or decoding.

After independent review and explicit priority, exactly that planned gate ran once. All local/remote hashes and ELF checks passed; backend `v2.49.40.260810104044` loaded one ordinary context/graph once. The runner consumed 171 prompt tokens and generated 16 tokens, for 186 sequential graph executions with all 38 states carried and positions/masks advanced. It stopped at the authorized ceiling, not EOS.

The raw 64-byte output was pulled and preserved before validation, SHA-256 `214a8f58d0fa410b99c6b4ba417d24289079c0a0579467c0e91859b1297d8ef2`. Post-cleanup decoding with the bound tokenizer produced:

> The user wants me to read a fictional engineering brief about three local inference engines (

All token IDs are in vocabulary. This is a coherent partial continuation but not a complete sentence or answer. Setup took 3.47177 seconds, request-to-first-token took 185.986 seconds, and total request time was 202.433 seconds. These are single-run diagnostics, not statistical benchmark results. Peak sampled process VmHWM was 1,611,816 KiB, not total DSP/system residency.

Raw provider, stage/workload hashes, output, memory, thermal/power, identity, and cleanup evidence plus post-cleanup decode are retained in [`results/qnn-ordinary-monolithic-phone-canonical-short-max16/`](results/qnn-ordinary-monolithic-phone-canonical-short-max16/). The scoped root was absent and `phone.lock` released. No retry or campaign is authorized pending independent review and a separately agreed next gate; no registry row or broad output-quality claim exists.

## Performance baseline and bottleneck inventory

Moritz authorized performance engineering, including explicitly declared hybrid routes, but not a campaign of the current AR1 graph. The host-side inventory in [`results/qnn-ordinary-monolithic-ar1-profile/`](results/qnn-ordinary-monolithic-ar1-profile/) binds QNN metadata, compiler traffic estimates, runner copy behavior, and the accepted single physical baseline without using the phone again.

Each AR1 execution exposes 41 raw-buffer inputs totaling **134,750,216 bytes (128.508 MiB)**. FP32 attention K/V state accounts for 134,184,960 bytes; recurrent convolution state adds 540,672 bytes. The runner memcpy-copies every input from CPU memory into QNN raw buffers. Sixty FP32 outputs total 1,085,440 bytes, including 573,440 bytes of updated state and 512,000 bytes across 22 logit chunks.

The context metadata reports a 1,596,407,808-byte constant footprint, 135,979,008 bytes of IO tensors, a 103,874,560-byte spill/fill buffer, 15,385,088 bytes of DDR tensors, 6,409,984 bytes of op data, and zero shared weights. Compiler sequencing estimates 6,029,426,688 spill bytes, 6,068,150,272 fill bytes, 6,105,014,528 total write bytes, and 7,816,581,632 total read bytes per graph execution. Those are compiler estimates, not measured bus counters, and the constant footprint does not prove every constant byte is reread.

The 2,698 QNN operations include 698 reshapes, 557 casts, 281 elementwise multiplies, 278 Conv2d operations, 192 adds, 16 MatMuls, 22 depthwise convolutions, and 8 Softmax operations. From the one accepted physical canonical-short run, prompt processing averaged 1.088 seconds per AR1 graph (including final prompt argmax) and the 15 post-first decode calls averaged 1.096 seconds each; these remain single-run diagnostics.

The highest-leverage next candidate is chunked prompt prefill, starting with bounded AR32 and AR128 compilation/semantic probes. FP16/uFxp16 state plus registered/device-resident memory, reduced logit return, and coarse explicitly declared hybrid partitions follow. Every candidate must preserve recurrent ordering and attention KV semantics and compare output/state against trusted CPU references before a phone request.
