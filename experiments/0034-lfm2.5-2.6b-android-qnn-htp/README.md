# Experiment 0034: LFM2.5-2.6B Android QNN/HTP

## Status

**Active. The exact model has an architecture-aware Q4 ONNX export and a bounded host viability pass. Static shared-cache QNN profiles and fallback-disabled SM8550/v73 AOT compilation are next; no Android or HTP result exists yet.**

This is a separate accelerator arm. It preserves `0029` CPU viability and `0033` CPU/OpenCL campaign evidence without modifying either experiment.

## Exact route

- Model: `LiquidAI/LFM2.5-2.6B`
- Source revision: `ab00687315bc1298e9d54e9c4b611dde9867ccc2`
- Source shards: 5,329,406,264 bytes / SHA-256 `05be188e…854cc`; 65,021,192 bytes / SHA-256 `532f803a…bca8`
- Architecture: 22 recurrent short-convolution layers plus 8 full-attention layers
- Exporter: `Liquid4All/onnx-export` commit `9a23ddd23035165f7414a5de3220a51e85780f64`
- Quantization: symmetric INT4 weight-only block quantization, block size 32, represented with `MatMulNBits` and `GatherBlockQuantized`; no activation calibration
- Candidate provider: Qualcomm-maintained ONNX Runtime QNN EP 2.5.0 with QNN runtime 2.49.0, targeting SM8550 / HTP v73

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

## HTP validity gates still open

Before any HTP claim, this experiment must:

1. create static prefill and one-token decode profiles with a fixed 4,096-token shared KV capacity and explicit convolutional-state handling;
2. replace or lower every operator that QNN HTP cannot own, including the block-quantized embedding if necessary;
3. compile with CPU fallback disabled for SM8550 / HTP v73;
4. retain a framework-op trace binding every claimed model/state graph to QNN HTP;
5. prove host equivalence and full convolution/KV reset semantics;
6. run a bounded physical-phone viability request under `artifacts/locks/phone.lock`;
7. only then run the canonical loaded-route `1+5+5+5` campaign.

A generic SM8550 target, successful context creation, or sensible text alone is not physical HTP proof.
