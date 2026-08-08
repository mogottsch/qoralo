# Component fixtures

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

CFG scale 1.3 is frozen in this correctness graph. Scheduler state, the scheduler update, and the ten-step loop remain native-controller responsibilities. Generate the ignored `fixture.pt`, manifest, and log only in the lane-specific artifact directory:

```bash
ROOT=/home/moritz/dev/vibevoice-android-spike
$ROOT/.venv/bin/python \
  experiments/0002-vibevoice-1.5b-executorch-android/export/capture_diffusion_fixture.py \
  --source $ROOT/artifacts/source/microsoft-vibevoice \
  --model $ROOT/artifacts/models/microsoft-VibeVoice-1.5B \
  --output $ROOT/artifacts/0002/lane-b/diffusion-head
```
