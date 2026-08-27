# Experiment 0034: LFM2.5-2.6B Android QNN/HTP

## Status

**Active after one fail-closed physical pre-inference failure. Exact identity and all 540 staged hashes passed, but the Android QNN plugin did not claim the first EPContext; CPU fallback remained disabled, no session/model token/HTP graph executed, and cleanup was verified absent. Pi authorized exactly one bounded NPU-selection diagnostic retry; no campaign is authorized.**

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

The revised runner logs every advertised EP device type and selects only `QNNExecutionProvider` with Android NPU hardware type. Its SHA-256 is `fe3351b84f6588a063642d036bbd4d2a2856a179dbab83d6f21b7978886043ea`; the replacement local stage is again fully hash-bound. See [`results/phone-preparation/result.json`](results/phone-preparation/result.json). Pi authorized exactly one bounded retry with the no-fallback gate unchanged.

## HTP validity gates still open

Before a physical HTP or benchmark claim, this experiment must:

1. package the 263 target contexts and a runtime that keeps the complete route loaded;
2. prove the declared CPU embedding/argmax boundary and all transformer/state/final-norm/head contexts on the authorized phone;
3. demonstrate clean state reset and a bounded sensible-text request under `artifacts/locks/phone.lock`;
4. retain physical QNN/HTP profile/log evidence, device state, memory, and scoped cleanup proof;
5. only then run the canonical loaded-route `1+5+5+5` campaign.

A generic SM8550 target, successful host context creation, or sensible host text alone is not physical HTP proof.
