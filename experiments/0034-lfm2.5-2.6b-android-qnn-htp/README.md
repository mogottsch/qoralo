# Experiment 0034: LFM2.5-2.6B Android QNN/HTP

## Status

**A single-process direct-QNN AR171→AR1 runner is host-built and Android-staged for review with correct native INT64 position buffers. A source audit found that the earlier qnn-net-run AR171 and phase-switch diagnostics instead read their INT32 position files as default FLOAT32 input and cast every value to INT64 zero. Those runs remain physical HTP execution evidence for their actual inputs, but no longer prove exact position/state semantics. No corrected integrated phone run has occurred.**

## Evidence correction: qnn-net-run position ingestion

[`results/qnn-net-run-position-ingestion-audit/`](results/qnn-net-run-position-ingestion-audit/) binds the exact QAIRT 2.49.40 source, documentation, commands, graph descriptors, and raw position files used by the prior qnn-net-run diagnostics.

Both recorded commands omitted qnn-net-run's documented `--use_native_input_files` and targeted `--native_input_tensor_names` options. The vendor qnn-net-run documentation says unspecified input files are parsed in floating point. The installed SampleApp source provides supporting implementation detail: it defaults to FLOAT input, reads one FLOAT32 value per element for non-FLOAT32 graph inputs, and dispatches `castFromFloat<int64_t>`, whose implementation applies `static_cast<int64_t>` element by element. The SampleApp's separate `--input_data_type` spelling is not claimed as an accepted flag for the shipped qnn-net-run binary.

The AR171 graph declares `position_ids` as INT64 `[1,171]`, but its 684-byte file contained INT32 bit patterns `0..170`. Read as FLOAT32, those bytes represent zero and tiny subnormal values up to `2.382e-43`; all cast to INT64 zero. The phase-switch AR1 graph declares INT64 `[1,1]`, but its 4-byte INT32 value 171 becomes FLOAT32 `2.396e-43` and then INT64 zero. This is high-confidence source-plus-runtime evidence rather than an output inference: the exact packaged binary rejected the earlier 1,368-byte native INT64 file and demanded 684 bytes, matching the packaged source's FLOAT32 file path. The stripped binary is not reproducibly linked bit-for-bit to the sample source, so that provenance limitation remains explicit.

Consequences:

- the prior physical qnn-net-run AR171 call did **not** prove rotary positions `0..170`;
- the qnn-net-run AR1 phase-switch call did **not** prove position 171;
- their matching endpoint argmax values cannot establish exact state/position semantics;
- their graph load/execution, provider, actual-output, timing, process-memory, thermal, and cleanup evidence remains factual when scoped to the all-zero position inputs;
- the physical custom direct-QNN max16 continuation used correct INT64 positions, but its starting state came from the affected AR171 call.

The integrated direct-QNN runner bypasses qnn-net-run file conversion and copies descriptor-matched INT64 buffers—1,368 bytes for AR171 and 8 bytes for AR1—but remains physically unexecuted. A future qnn-net-run diagnostic would need numeric FLOAT32 position files under the default mode or native INT64 files using the binary's documented `--use_native_input_files` / targeted `--native_input_tensor_names` option; exact flag syntax and values must be checked in a bounded run. Neither correction is retroactively claimed.

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

The highest-leverage next candidate is chunked prompt prefill. AR32 and AR128 host probes are now retained in [`results/qnn-prefill-ar32-ar128-host-probes/`](results/qnn-prefill-ar32-ar128-host-probes/). Each graph keeps prior K/V left-aligned, applies causal attention inside the chunk, returns only the new K/V slices, carries all 22 convolution states, computes LM-head logits only for the final chunk position, and keeps CPU embedding/argmax boundaries explicit.

Both candidates compile fallback-disabled to one SM8550/V73 subgraph with 1,542/1,542 optimized nodes supported, 2,699 QNN operations, and zero unsupported nodes. AR32 produces a 1,602,820,688-byte context; AR128 produces a 1,605,986,896-byte context. Compiler-estimated traffic rises moderately per call, but each call represents 32 or 128 tokens rather than one.

CPU comparison against the accepted sequential AR1 transformation preserves the final greedy decision: AR32 token 32 is 20 in both routes, and AR128 token 128 is 116311 in both. A second AR32 chunk also preserves argmax 342 at token 64. Numeric differences remain material and are not hidden: only 20/38 AR32 and 19/38 AR128 state tensors meet `rtol=0.02, atol=0.02`; state max-absolute deltas are 0.307 and 0.552, while logit max-absolute deltas are 0.512 and 0.383. These are viability probes, not exact numerical equivalence or output-quality evidence.

Neither width exactly tiles the 171-token canonical short prompt without a tail graph or padding. Exact-tiling AR57 and AR171 results are now retained in [`results/qnn-prefill-ar57-ar171-host-probes/`](results/qnn-prefill-ar57-ar171-host-probes/).

AR57 carries all 38 states across three chunks and preserves sequential-AR1 greedy decisions at every boundary: `[8771, 437, 597]` at tokens `[57, 114, 171]`. AR171 preserves final argmax 597 in one chunk. Numeric differences remain material: AR57's maximum state/logit deltas reach 0.665/0.724; AR171 reaches 0.514/0.771. No exact numerical or broad-equivalence claim is made.

Both compile fallback-disabled as one ordinary QNN graph with 1,542/1,542 optimized nodes, 2,699 QNN operations, and zero unsupported nodes. AR57's 1,600,858,704-byte context has a 156,434,432-byte spill/fill buffer. AR171's 1,602,378,320-byte context has a 463,667,200-byte spill/fill buffer. One AR171 call has lower aggregate compiler-estimated prompt read/write traffic than three AR57 calls, so AR171 is the strongest current physical diagnostic candidate.

A bounded AR171 x86 HTP-emulator probe loaded its context and retrieved its graph, then exceeded 1,800 seconds during graph execution and produced no graph output. The process was absent afterward. This establishes only that the emulator is impractical for the candidate; it is not a target-SM8550 failure or physical timing result. No phone access occurred. A bounded physical AR171 diagnostic requires independent review and explicit Pi priority.

After review, one bounded physical AR171 runtime diagnostic used context SHA-256 `d5ca624cc71a173c7de969fac777e2ce136db3b502e04c2991651b510dabba5a` and 41 precomputed raw inputs totaling 133,358,252 bytes. All 48 staged payload hashes passed locally and remotely. Physical QAIRT `v2.49.40.260810104044` created the context, retrieved one graph, and completed one execution. The later ingestion audit proves its position tensor became all zeros; this was not exact AR171 position semantics.

All 60 raw outputs were pulled before validation: 38 state tensors and 22 logit chunks were finite. Physical last-sequence-row argmax was 597, matching sequential AR1 and chunk CPU references despite the position error. That coincidence does not establish position/state or numerical equivalence.

The detailed QNN profile reports:

- NetRun initialization: 1.724910 seconds;
- backend accelerator binary load: 0.656467 seconds;
- NetRun execution including IO/misc: 6.308347 seconds;
- QNN execution: 6.308240 seconds;
- RPC execution: 6.294107 seconds;
- accelerator execution: 5.234013 seconds (5.231422 seconds excluding wait);
- 3,260,126,464 accelerator cycles using four HVX threads.

Inputs, including CPU-dequantized embeddings, were precomputed before qnn-net-run; CPU embedding/input preparation was not timed. Therefore these numbers are neither end-to-end TTFT nor directly comparable campaign measurements against the 185.986-second AR1 custom-runner TTFT. Peak sampled process VmHWM was 1,576,200 KiB and is not total DSP/system residency.

Raw provider/profile, stage hashes, all outputs, output validation, memory, thermal/power, identity, and cleanup are retained in [`results/qnn-prefill-ar171-phone-runtime-diagnostic/`](results/qnn-prefill-ar171-phone-runtime-diagnostic/). Scoped process/root cleanup passed and `phone.lock` was released.

## AR171-to-AR1 state bridge

The bounded host bridge in [`results/qnn-prefill-ar171-to-ar1-host-bridge/`](results/qnn-prefill-ar171-to-ar1-host-bridge/) consumes the retained physical outputs, not regenerated substitutes. Each 171-position physical K/V slice is copied into positions `0:171` of the accepted 4,095-position AR1 cache, the remaining positions are zeroed, all 22 convolution states are carried directly, token 597 is CPU-embedded, `position_ids=171`, and the AR1 mask exposes prior positions `0:171` plus the current final slot.

Physical-AR171→AR1, CPU-AR171→AR1, and sequential-AR1→AR1 all produce next global argmax **4695**, which also matches the second token of the accepted physical AR1 continuation. Numeric fidelity is not close: physical prefill state versus CPU AR171 is only 3/38 tensors allclose at `rtol=0.02, atol=0.02`, with maximum absolute delta 10,586.69; after one AR1 continuation, physical-versus-CPU-AR171 state/logit maximum deltas are 3.61/7.07. The outlier-bearing physical outputs are finite, declared FP32, and every file size matches qnn-net-run's tensor metadata. The drift is retained as a serious fidelity warning.

Concurrent AR171+AR1 residency was not attempted. Metadata totals 3,202,476,296 bytes of context binaries, roughly 3.19 GB of duplicated constants, 276 MB of IO tensors, and 568 MB of spill/fill buffers. Metadata alone cannot prove failure, but prior residency evidence makes simultaneous loading high risk. The selected candidate therefore has one explicit phase transition: load AR171 once, preserve state, free it, convert the cache contract on CPU, then load AR1 once for decode. This is not per-token context streaming and must be declared in all future results.

Additional bridge analysis compares physical AR171 endpoint logits before continuation: maximum/mean absolute deltas are 7.218/1.055 versus CPU AR171 and 7.312/1.053 versus sequential AR1, while all endpoint argmax values remain 597. The largest `present.2.key` outliers localize to layer 2, head 5, token position 76: 58/87,552 values have physical magnitude above 100, the physical range is −5024 to 10592, and the CPU range is −9.69 to 10.25. The extreme values are sparse enough to sit beyond the 99.9th percentile, but they are a serious retained risk. Existing physical sequential-AR1 evidence did not persist raw states, so physical-versus-physical state comparison is unavailable.

The exact phase-switch diagnostic is prepared but unexecuted in [`results/qnn-prefill-ar171-ar1-phase-switch-readiness/`](results/qnn-prefill-ar171-ar1-phase-switch-readiness/). A host-validated Android CPU bridge copies all physical convolution states byte-for-byte, expands each physical K/V prefix row into the AR1 4,095-position layout with zero padding, embeds token 597, writes position 171, and constructs the exact mask. Its ignored 51-file stage totals 3,362,360,562 bytes and binds both contexts, qnn-net-run, QAIRT runtime, prefill inputs, bridge utility, and embedding.

The planned diagnostic was independently reviewed and executed exactly once. All 51 payload hashes passed locally and remotely. Phase 1 loaded AR171 once, executed one 171-token graph call, and pulled all 60 raw outputs before the AR171 qnn-net-run process exited. Physical endpoint argmax was 597. The Android CPU bridge completed in 0.341 seconds and produced 41 tensor inputs plus an input-list, all hashed. Phase 2 loaded AR1 once and executed token 597 with a position file nominally encoding 171; the ingestion audit proves qnn-net-run converted that value to zero. All 60 outputs were finite and metadata-size-valid, and argmax 4695 matched the references despite the position error.

Detailed phase profiles report:

- AR171: 2.029-second NetRun initialization, 0.546-second accelerator binary load, 5.915-second QNN execution, and 4.967-second accelerator execution;
- AR1: 0.489-second NetRun initialization, 0.142-second accelerator binary load, 1.817-second QNN execution, and 1.048-second accelerator execution;
- host-observed walls: 13.562 seconds for phase 1, 0.341 seconds for the CPU bridge, and 6.093 seconds for phase 2;
- 21.309 seconds from phase-1 start through phase-2 stop, including the raw-output evidence pull and AR1-input hashing but excluding initial preparation of the 171 CPU embeddings and stage push/hash verification.

Peak sampled process VmHWM was 1,577,640 KiB for prefill and 1,575,268 KiB for AR1. Both are process-only measurements. Raw phase outputs, QNN profiles, separate lifecycle timings, bridge-input hashes, memory, thermal/power, provider, and cleanup evidence are retained in [`results/qnn-prefill-ar171-ar1-phone-phase-switch-diagnostic/`](results/qnn-prefill-ar171-ar1-phone-phase-switch-diagnostic/). The scoped process/root were absent and the lock released.

This is not a loaded dual-context route: contexts are mutually exclusive across one explicit phase transition. It proves one continuation token and greedy agreement only; severe localized state drift remains. No numerical-equivalence, text-generation, canonical-TTFT, statistical-performance, campaign, or registry claim is made.

## In-process AR1 max16 continuation readiness

CPU generation from the retained physical AR171 state is now extended for 16 AR1 steps in [`results/qnn-prefill-ar171-ar1-max16-readiness/`](results/qnn-prefill-ar171-ar1-max16-readiness/). Its continuation token sequence starts `[4695, 10966, 622, 310]`, matching CPU-AR171 and sequential-AR1 references for four tokens, then diverges at decode index 4 / position 175: physical state chooses 5272 while both references choose 1561. Index 5 briefly realigns at token 267, after which the sequences mostly diverge. Per-step state/logit deltas are retained; physical-versus-CPU logit maximum deltas reach 36.50.

With endpoint token 597 included, the physical-state CPU continuation decodes to:

> The user wants me to write a self-contained technical recommendation for the team comparing three local

The CPU reference decodes to:

> The user wants me to read a fictional engineering brief about three local inference engines (C

Both are coherent partial continuations, but they are not equal. The divergence prevents any fidelity-equivalence claim.

The custom direct-QNN runner can now load all 38 bridged states from raw files, validate position 171 and the exact mask, load one AR1 context once, and greedily update state in process for up to 16 tokens. A bounded x86 HTP max1 probe loaded the context/graph and produced 4695; its 751-second runtime makes max16 emulation impractical. The ignored Android stage contains 53 payloads totaling 1,932,854,438 bytes, with context SHA-256 `76ba15e7fd95e5e13e92be0e88e8e6bbd3123f2b993b6986c9dac8800a9bf212`, runner SHA-256 `659fa97a84d789d0630051d5ff0031d494820de6517e34cccfcb6d116edf9758`, and passing hashes/ELF preflight.

One reviewed physical max16 resume diagnostic used that exact stage. All 53 hashes passed locally and remotely. The custom direct-QNN runner loaded the accepted AR1 context and the bridged states originating from the affected all-zero-position AR171 call, validated native INT64 position 171 and the mask, then completed 16 HTP graph executions while keeping one context and all 38 states in process. It produced exactly the CPU continuation from that same affected physical state:

`[4695, 10966, 622, 310, 5272, 267, 2014, 116311, 9516, 28817, 374, 278, 2909, 19260, 1703, 2165]`

With prefill endpoint 597, the bound decode is:

> The user wants me to write a self-contained technical recommendation for the team comparing three local

The runner reported 3.80356 seconds setup, 1.11786 seconds to the first resumed token, and 17.4183 seconds for max16; the post-first 15 calls average 1.086696 seconds in this one diagnostic. Request timing includes CPU row embedding and global argmax plus HTP calls, but excludes AR171 prefill and the CPU phase bridge. Peak sampled process VmHWM was 1,611,744 KiB.

Evidence limitations are explicit: the custom runner retained states/logits only in process, did not serialize a detailed QNN profile, and did not explicitly finite-scan each output tensor. It did validate initial state/mask and each QNN input type/size, complete all 16 stateful calls, and emit the exact expected token sequence. Raw token/provider/timing/memory/thermal/cleanup evidence is retained in [`results/qnn-prefill-ar171-ar1-phone-max16-resume/`](results/qnn-prefill-ar171-ar1-phone-max16-resume/). Cleanup passed.

This is not per-call state/logit finiteness evidence, numerical equivalence, a complete answer, canonical end-to-end TTFT, or a statistical campaign.

## Integrated single-logical-request readiness

The host readiness artifact in [`results/qnn-prefill-ar171-ar1-integrated-readiness/`](results/qnn-prefill-ar171-ar1-integrated-readiness/) closes the evidence gaps in the proposed runner rather than claiming a new result. One process creates the QAIRT backend/device, then:

1. loads AR171 once;
2. dequantizes the exact 171 prompt embedding rows on CPU inside the request boundary;
3. constructs exact positions/mask/zero state, executes AR171, finite-scans and copies all 38 state plus 22 logit outputs, and reduces endpoint argmax;
4. emits phase-labelled recursive detailed QNN events, frees AR171, and resets the detailed profile;
5. bridges all 38 states in memory;
6. loads AR1 once, then performs max16 with each call requesting and finite-scanning all 60 outputs while carrying state in process;
7. emits a separate AR1 detailed profile and frees the context.

For this integrated route, `MAX_NEW=16` is explicitly the **total output cap**, including the AR171 endpoint token; therefore it performs at most 15 AR1 graph calls and stops early on EOS. The output file is created with exclusive semantics before backend setup. The endpoint and each later token are appended and `fsync`ed immediately, so a later graph, finite-scan, or optional-profile failure leaves already emitted raw tokens intact. Profile extraction failures are logged as missing optional telemetry rather than invalidating completed inference.

Timing fields separate backend/device setup, each context load/free, CPU prompt input construction, AR171 graph execution, endpoint argmax, state bridge, profile dumps/reset, AR1 first resumed token, AR1 decode, emitted-token delivery, and diagnostic overhead. Actual request-start-to-first-emitted-token time includes that token's `fsync` and excludes later profile work. Request-start-to-final-emitted-token time necessarily includes the intervening prefill profile dump, context free, profile reset, and AR1 context load, while excluding the trailing AR1 profile dump/free; compute-only phase sums and diagnostic total with all profile/free overhead are separate. The canonical short token IDs are precomputed, so tokenization remains outside every reported timing boundary. Backend setup is also reported separately.

Both host and API-31 Android binaries compile. The Android runner SHA-256 is `94e76c339107cc3bfae2fb9b296cbcdb76f1970f7aeb8a734bb564029fd6fdb1`; the host binary SHA-256 is `ed122a00e0982317805137c2ea08cdbe5aeb297c6cf1527c3c68872129cde261`. The ignored integrated stage has 12 payload files totaling 3,400,505,468 bytes; stage metadata SHA-256 is `dbb9d687b34d4476086f59e746907dfb8bef32c5fcf36a0b83331d9b0b02a60f` and manifest SHA-256 is `8fa2c53c79c1ad994ea269266da14fb70c9cf03913d36753220d1379b6e79616`. All hashes and ELF preflight pass.

The direct-QNN ABI is bound separately from earlier qnn-net-run file ingestion. Both context descriptors expose `position_ids` as `QNN_DATATYPE_INT_64`: `[1,171]` / 1,368 bytes for AR171 and `[1,1]` / 8 bytes for AR1. The integrated runner copies those exact INT64 byte counts. Earlier accepted qnn-net-run stages used INT32 raw position files through qnn-net-run's own file-population/conversion boundary; that observation is not generalized to direct QNN.

A combined/shared-constant two-graph context is not claimed. The ordinary contexts each report `sharedWeightsSize=0` and together expose roughly 3.19 GB of constants. ORT's multi-graph sharing route uses the already rejected shared-weight resource format, while a single static graph cannot select AR171 versus AR1 shapes without duplicated execution or unsupported control flow. A genuinely shared Qualcomm multi-graph context would require new supported tooling or maintainer guidance and fresh evidence.

No integrated inference was run because AR171 x86 HTP already exceeds 1,800 seconds. A no-QNN host regression verifies exclusive output creation, incremental flushed partial-token preservation under injected late failure, rejection of overwrite attempts, and fail-open optional profile capture. No ADB or phone access occurred. This is build/static/stage readiness only—not integrated operability, TTFT, numerical fidelity, a performance distribution, campaign, or registry result. FP16/uFxp16 state, registered/device-resident memory, reduced logit return, and coarse declared hybrid partitions remain later candidates.
