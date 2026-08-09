# Component fixtures

The Qwen2 backbone's fixed prefill/decode contract, completed heavy-RAM
capture, exact determinism check, and real host export result are documented in
[`qwen2-backbone-abi.md`](qwen2-backbone-abi.md), with the complete ordered
shape contract in [`qwen2-backbone-abi.json`](qwen2-backbone-abi.json). Raw
fixtures and PTEs remain ignored; committed summaries preserve hashes and the
unwidened host numerical failure.

## Recurrent eager trace (calls 0–19)

[`recurrent-calls-0-19-manifest.json`](recurrent-calls-0-19-manifest.json)
records two byte-identical CPU/FP32 captures of the first 20 actual acoustic
calls. Each call includes positive Qwen input, hidden state, logits and all 56
pre/post KV tensors; the selected token; positive/negative diffusion conditions,
initial noise, all ten prediction-head inputs/outputs and the final latent;
acoustic and semantic connector outputs; decoder input, PCM and all 34 pre/post
cache tensors; and semantic input/output with all 34 pre/post cache tensors.
Every tensor has stable shape/dtype/range metadata and an exact-byte SHA-256.

The capture asserts Qwen, decoder, and semantic pre-state equals the preceding
actual eager post-state. It also verifies contiguous indices, 3,200-sample
boundaries, 64,000 samples total, and records per-chunk peak, RMS and dBFS. Raw
`.pt` payloads total about 1.2 GiB per run and remain under ignored `artifacts/`.
No deployment ABI is selected by this evidence capture.

The subsequent reviewed decision is frozen separately in
[`four-call-cache-abi.md`](four-call-cache-abi.md) and its normative
[`four-call-cache-abi.json`](four-call-cache-abi.json). It uses fixed maximum
FP32 audio caches plus explicit phase/valid lengths; it is a pre-export
contract, not evidence that an export already works.

Run twice through the one global model-resource gate:

```bash
experiments/0002-vibevoice-1.5b-executorch-android/run-recurrent-capture.sh \
  artifacts/0002/recurrent-calls-0-19/capture-1
experiments/0002-vibevoice-1.5b-executorch-android/run-recurrent-capture.sh \
  artifacts/0002/recurrent-calls-0-19/capture-2 \
  artifacts/0002/recurrent-calls-0-19/capture-1
```

Copy only capture 2's `manifest.json` to the committed manifest path. The repeat
matched every call's tensor metadata and hash; wall time and peak RSS are run
observations and are intentionally outside the equality comparison.

### Cache stabilization and audible onset

[`../results/cache-stabilization.json`](../results/cache-stabilization.json)
preserves the manifest order and all 20 pre/post lengths for every one of the 34
acoustic and 34 semantic caches. The six acoustic `SConvTranspose1d` caches have
configured `kernel_size - 1` targets `[15, 9, 9, 7, 3, 3]` and per-call input
widths `[1, 8, 40, 200, 800, 1600]`. Their post-caches first reach full context
on calls `[14, 1, 0, 0, 0, 0]`; calls `[15, 2, 1, 1, 1, 1]` are the first to
enter with full pre-context. Thus call 15 is the first call with full pre-context
at all six transpose layers. In particular, calls 0–3 are genuine warm-up calls,
not a repeatable all-full-context ABI: the first transpose holds only 4 of its 15
required input samples after call 3.

The locked S16 waveform has the expected onset rather than immediate speech:
chunks 0 and 1 are near-silence at -93.6608 and -93.4909 dBFS, chunk 2 fades in
at -52.3799 dBFS, and chunk 3 is clearly voiced at -21.7126 dBFS. The
[`../results/locked-reference-prefix-comparison.json`](../results/locked-reference-prefix-comparison.json)
supplement recomputes the 6,400-sample Android comparison directly as signed
16-bit integers: maximum absolute difference 1 unit, mean absolute difference
0.4709375 units. This prefix agreement passes its numerical criterion but does
not reverse the historical quality rejection; the matching prefix is short,
introductory silence and cannot satisfy intelligibility, duration, or speaker
criteria.

Regenerate both derived results without loading model weights:

```bash
python3 experiments/0002-vibevoice-1.5b-executorch-android/export/analyze_cache_stabilization.py
```

## Acoustic decoder

Raw fixture tensors are generated under the ignored directory:

```text
artifacts/0002/acoustic-decoder-fixtures/
├── call_000.pt
├── call_001.pt
└── manifest.json
```

`call_000` is the first streaming decoder call with an empty pre-cache. `call_001` is the next call with populated cache state. Each payload contains:

- `latent_b64t`: the real scaled acoustic latent in fixed `[batch, 64, steps]` layout;
- `sample_indices`;
- `pcm`: expected streaming decoder output;
- `pre_cache` and `post_cache`: cloned tensors keyed by stable decoder module name and sample index.

The committed [`acoustic-decoder-manifest.json`](acoustic-decoder-manifest.json) records tensor shapes, dtypes, exact-byte SHA-256 hashes, ranges, and stable cache ordering. Runtime `layer_id` strings are deliberately excluded because upstream derives them from Python object addresses.

Observed capture:

| Call | Latent | PCM | Pre-cache | Post-cache |
|---|---|---|---:|---:|
| 0 | `[1,64,1]` FP32 | `[1,1,3200]` FP32 | 0 entries | 34 entries |
| 1 | `[1,64,1]` FP32 | `[1,1,3200]` FP32 | 34 entries | 34 entries |

The deterministic capture rerun produced the same final WAV SHA-256 as experiment 0001: `fb0152dc686836fe23d9c39c3b24c1de82398f51b9747f5e36ad1db819ce0358`.

Generate the fixtures from the repository root after preparing the historical source as described by experiment 0001:

```bash
python experiments/0001-vibevoice-1.5b-local-reference/prepare_official_source.py
.venv/bin/python \
  experiments/0002-vibevoice-1.5b-executorch-android/export/capture_fixtures.py
```

The capture reruns the locked CPU/FP32 reference with source revision `6dd49cb7200c0367205a5f1e650244259e9e423d`, model revision `c00898d257e6b46004e3e2866a47534085fb685a`, seed 42, CFG scale 1.3, and Carter/Maya voices. Generated audio remains ignored alongside the tensors.

## Diffusion head

[`diffusion-head-manifest.json`](diffusion-head-manifest.json) describes the first real prediction-head call from the same locked reference. The capture stops immediately after that call, so it retains real positive/negative language-model conditions without running all ten DPM steps or decoding audio. Two consecutive captures produced identical hashes for every tensor.

The fixed FP32 ABI is:

```text
(noisy_latent [1,64], timestep [1],
 positive_condition [1,1536], negative_condition [1,1536])
    -> cfg_guided_v_prediction [1,64]
```

CFG scale 1.3 is frozen in this correctness graph. Scheduler state, the scheduler update, and the ten-step loop remain native-controller responsibilities. The Android harness also generates an ignored `diffusion-loop.reference.pt` by invoking this PTE at `[999, 899, 799, 699, 599, 500, 400, 300, 200, 100]`; it contains the eleven latents, ten guided predictions, and eleven DPM sigmas used to validate Java orchestration. Generate the ignored `fixture.pt`, manifest, and log only in the lane-specific artifact directory:

```bash
ROOT=/home/moritz/dev/vibevoice-android-spike
$ROOT/.venv/bin/python \
  experiments/0002-vibevoice-1.5b-executorch-android/export/capture_diffusion_fixture.py \
  --source $ROOT/artifacts/source/microsoft-vibevoice \
  --model $ROOT/artifacts/models/microsoft-VibeVoice-1.5B \
  --output $ROOT/artifacts/0002/lane-b/diffusion-head
```
