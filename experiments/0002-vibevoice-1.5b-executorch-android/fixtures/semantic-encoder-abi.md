# Semantic audio encoder streaming ABI

This ABI isolates the pinned VibeVoice semantic tokenizer encoder. It consumes one causal 3,200-sample chunk (one acoustic token at 24 kHz) and produces one 128-wide semantic feature. All tensors are contiguous CPU FP32. Batch and chunk sizes are fixed.

## Entry points

- **`first` / reset:** input 0 `audio [1,1,3200]`; outputs are `semantic_features [1,1,128]` then the 34 caches below. No cache inputs are permitted.
- **`cached`:** inputs are `audio` then all 34 caches below; outputs are `semantic_features` then all 34 replacement caches in the identical order.
- **Reset rule:** discard every prior cache and call `first`. Passing zero tensors to `cached` is not the reset ABI. A repeated `first` call is bit-exact on host runtime.
- **Bounds:** exactly one sample and 3,200 audio values. Cache shapes are fixed causal-context bounds, never grow, and are replaced rather than appended. Missing, reordered, wrong-shape/dtype, non-contiguous, or non-finite tensors are rejected before export.

## Cache tensor order

| Position after audio/features | Tensor name | Shape | Dtype |
|---:|---|---|---|
| 1 | `cache.downsample_layers.0.0` | `[1, 1, 6]` | `float32` |
| 2 | `cache.downsample_layers.1.0` | `[1, 32, 2]` | `float32` |
| 3 | `cache.downsample_layers.2.0` | `[1, 64, 2]` | `float32` |
| 4 | `cache.downsample_layers.3.0` | `[1, 128, 4]` | `float32` |
| 5 | `cache.downsample_layers.4.0` | `[1, 256, 5]` | `float32` |
| 6 | `cache.downsample_layers.5.0` | `[1, 512, 5]` | `float32` |
| 7 | `cache.downsample_layers.6.0` | `[1, 1024, 8]` | `float32` |
| 8 | `cache.head` | `[1, 2048, 6]` | `float32` |
| 9 | `cache.stages.0.0.mixer.conv` | `[1, 32, 6]` | `float32` |
| 10 | `cache.stages.0.1.mixer.conv` | `[1, 32, 6]` | `float32` |
| 11 | `cache.stages.0.2.mixer.conv` | `[1, 32, 6]` | `float32` |
| 12 | `cache.stages.1.0.mixer.conv` | `[1, 64, 6]` | `float32` |
| 13 | `cache.stages.1.1.mixer.conv` | `[1, 64, 6]` | `float32` |
| 14 | `cache.stages.1.2.mixer.conv` | `[1, 64, 6]` | `float32` |
| 15 | `cache.stages.2.0.mixer.conv` | `[1, 128, 6]` | `float32` |
| 16 | `cache.stages.2.1.mixer.conv` | `[1, 128, 6]` | `float32` |
| 17 | `cache.stages.2.2.mixer.conv` | `[1, 128, 6]` | `float32` |
| 18 | `cache.stages.3.0.mixer.conv` | `[1, 256, 6]` | `float32` |
| 19 | `cache.stages.3.1.mixer.conv` | `[1, 256, 6]` | `float32` |
| 20 | `cache.stages.3.2.mixer.conv` | `[1, 256, 6]` | `float32` |
| 21 | `cache.stages.4.0.mixer.conv` | `[1, 512, 6]` | `float32` |
| 22 | `cache.stages.4.1.mixer.conv` | `[1, 512, 6]` | `float32` |
| 23 | `cache.stages.4.2.mixer.conv` | `[1, 512, 6]` | `float32` |
| 24 | `cache.stages.5.0.mixer.conv` | `[1, 1024, 6]` | `float32` |
| 25 | `cache.stages.5.1.mixer.conv` | `[1, 1024, 6]` | `float32` |
| 26 | `cache.stages.5.2.mixer.conv` | `[1, 1024, 6]` | `float32` |
| 27 | `cache.stages.6.0.mixer.conv` | `[1, 2048, 6]` | `float32` |
| 28 | `cache.stages.6.1.mixer.conv` | `[1, 2048, 6]` | `float32` |
| 29 | `cache.stages.6.2.mixer.conv` | `[1, 2048, 6]` | `float32` |
| 30 | `cache.stages.6.3.mixer.conv` | `[1, 2048, 6]` | `float32` |
| 31 | `cache.stages.6.4.mixer.conv` | `[1, 2048, 6]` | `float32` |
| 32 | `cache.stages.6.5.mixer.conv` | `[1, 2048, 6]` | `float32` |
| 33 | `cache.stages.6.6.mixer.conv` | `[1, 2048, 6]` | `float32` |
| 34 | `cache.stages.6.7.mixer.conv` | `[1, 2048, 6]` | `float32` |

The order is lexical by stable encoder module path, not Python object ID. The leading dimension is explicit batch; upstream eager cache snapshots omit it per sample.

## Streaming and validation semantics

Call two consumes **actual ExecuTorch call-one outputs 1–34**, not eager cache tensors. Semantic features pass `atol=1e-5, rtol=1e-4` for both calls. Strict cache metrics remain reported; XNNPACK convolution reduction ordering produces a maximum cache delta of `0.000907599925994873`. The component-specific cache bound is `atol=1e-3, rtol=1e-4`, with zero bounded mismatches, and the chained call-two semantic result still passes the strict feature criterion.

Canonical tensor hashes, PTE hashes/sizes, timings, RSS, commands, revisions, and conclusion are in [`semantic-encoder-manifest.json`](semantic-encoder-manifest.json) and [`../results/semantic-encoder-host.json`](../results/semantic-encoder-host.json). Large fixtures, PTEs, references, and logs remain ignored.
