# Experiment 0034: LFM2.5-2.6B Android QNN/HTP

## Status

**Active with a host-prepared single-context shared-resource route after the 37-context physical residency failure. One 1,601,482,752-byte SM8550/V73 QNN context now contains all 37 fused graphs in exact order and preserves loaded-once semantics. Android support for its shared-weights buffer is unproven; no new physical execution, output, performance result, or campaign exists.**

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

This is a host AOT/metadata milestone only. A single bounded physical compatibility gate requires a new explicit Pi priority grant; no retry or campaign is currently authorized.
