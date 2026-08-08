# Experiment 0002 — VibeVoice 1.5B with ExecuTorch on Android

## Objective

Export VibeVoice components to ExecuTorch, validate them against experiment 0001 fixtures, and progress toward the same approximately 15-second output on the Galaxy S23 Ultra.

## Status

In progress. Experiment 0001 produced the locked PyTorch reference. Calls 0 and 1 have been captured from a deterministic rerun, and the first decoder-only export probe is implemented. `.pte` export, host comparison, and Android execution remain to be run and recorded.

## Current tooling

- [`export/capture_fixtures.py`](export/capture_fixtures.py) wraps the real streaming decode call and captures calls 0 and 1 with stable cache names.
- [`export/acoustic_decoder.py`](export/acoustic_decoder.py) constructs only `TokenizerDecoder` and reads only its tensors from the sharded checkpoint.
- [`export/export_decoder.py`](export/export_decoder.py) exports a fixed `[1,64,1]` FP32 non-streaming operator-coverage probe to portable ExecuTorch or XNNPACK.
- [`fixtures/README.md`](fixtures/README.md) documents the ignored fixture layout and capture command.
- [`fixtures/acoustic-decoder-manifest.json`](fixtures/acoustic-decoder-manifest.json) records the captured shapes, dtypes, stable cache ordering, ranges, and hashes without committing tensors.

The initial `.pte` is deliberately non-streaming. It isolates decoder operator coverage before the upstream Python dictionary cache is replaced by the final explicit tensor-cache ABI. It must not be treated as an audio-equivalent implementation of the captured streaming calls.

Run the first probe after fixture capture in a Python environment containing the ExecuTorch version paired with the Android AAR:

```bash
python experiments/0002-vibevoice-1.5b-executorch-android/export/export_decoder.py \
  --backend xnnpack
```

## Deployment design

Do not export the complete Python `generate()` method as one graph. VibeVoice combines tensor computation with token selection, diffusion iteration, streaming caches, and Python control flow. Keep orchestration in Kotlin or C++ and export tensor-heavy components as one or more ExecuTorch `.pte` modules.

```text
Kotlin test harness
        |
        v
Native generation controller
        |
        +-- text tokenizer
        +-- speaker-prompt preparation
        +-- Qwen2 prefill/decode + explicit KV cache  --+
        +-- diffusion-head step                         +-- ExecuTorch modules
        +-- acoustic/semantic connectors                |
        +-- streaming acoustic decoder                --+
        |
        v
24 kHz PCM -> WAV initially, then Android AudioTrack
```

The development harness may write WAV files first. Real-time playback is not required for the first success.

## Component order

1. Acoustic decoder with a fixed latent and explicit cache tensors
2. One diffusion-head denoising step
3. Language-backbone prefill
4. Single-step language decode with explicit KV-cache input/output
5. Acoustic and semantic connectors
6. Speaker conditioning
7. Native generation controller
8. Three-to-five-second end-to-end generation
9. Fixed experiment 0001 transcript

For every component:

1. capture real inputs and expected outputs from the locked PyTorch model;
2. record tensor names, shapes, dtypes, and SHA-256 hashes;
3. export a minimal wrapper with a tensor-only interface;
4. run the exported module through the ExecuTorch host runtime;
5. compare it numerically against PyTorch;
6. run the same fixture on Android;
7. record errors, unsupported operators, latency, memory, and backend partitioning.

Large fixture tensors and `.pte` files stay under ignored `artifacts/`. Only scripts, tensor metadata, hashes, measurements, and conclusions are committed.

## First milestone: acoustic decoder on the phone

Capture one acoustic latent and decoder-cache state from experiment 0001. Export a wrapper with a stable interface similar to:

```text
(latent, cache tensors...) -> (PCM chunk, updated cache tensors...)
```

Start with fixed shapes and FP32 or FP16 as required for correctness. Dynamic shapes and quantization come later.

The milestone passes when:

- PyTorch and the ExecuTorch host runtime produce outputs within a documented tolerance;
- the Galaxy S23 Ultra loads the `.pte` without termination;
- XNNPACK produces a valid PCM chunk from the same latent;
- Android output is compared numerically with the host fixture;
- load time, inference time, peak RSS, package size, and delegated operators are recorded.

A WAV assembled from this single chunk is useful for diagnosis but is not an end-to-end VibeVoice result.

## Backbone and cache design

Treat the Qwen2 backbone as two entry points:

- **prefill** consumes the transcript and speaker-conditioning sequence and creates the initial KV cache;
- **decode** consumes one token or embedding plus explicit KV-cache tensors and returns the next hidden state and updated cache.

Do not depend on mutable Hugging Face cache objects across the runtime boundary. Use fixed tensor layouts first. Add bounded dynamic sequence dimensions only after fixed-shape export is correct.

## Diffusion design

Export one denoising step rather than the complete diffusion loop:

```text
(noisy latent, timestep, positive condition, negative condition)
    -> predicted latent update
```

Run the locked ten DDPM inference steps in native orchestration code. Preserve FP16 initially; quantize only after numerical and audio comparisons pass.

## Backend progression

Use the same fixtures in this order:

1. ExecuTorch portable/host runtime for export debugging;
2. XNNPACK on Android for the broadest practical CPU baseline;
3. ExecuTorch Qualcomm backend/QNN for Snapdragon acceleration;
4. Vulkan only for a component with a clear coverage or performance advantage.

XNNPACK establishes correctness before Qualcomm SDK, operator, shape, and quantization constraints are introduced. Direct QNN integration remains experiment 0005; using the ExecuTorch Qualcomm backend here does not replace that later comparison.

## Precision progression

1. Use the highest supported precision for component correctness.
2. Move the Qwen2 backbone to weight-only INT8, then INT4.
3. Keep the diffusion head and audio components FP16 initially.
4. Try INT8 for individual diffusion/audio components only with fixture and listening comparisons.

A full FP16 deployment is a diagnostic target, not the expected final configuration. Experiment 0001 used about 12.42 GiB peak RSS in FP32, so the Android build will probably require an INT4 backbone and careful cache bounds.

## Android packaging and runner

During the spike:

- do not package models inside the APK;
- push `.pte` files and fixtures over ADB into app-private or test storage;
- memory-map model files where the runtime permits;
- use a minimal Kotlin/JNI or C++ runner rather than a product UI;
- write PCM/WAV output before adding `AudioTrack` streaming;
- keep model weights, APKs, traces, generated audio, and tensors uncommitted.

Suggested experiment layout:

```text
0002-vibevoice-1.5b-executorch-android/
├── fixtures/
│   └── README.md
├── export/
│   ├── capture_fixtures.py
│   ├── acoustic_decoder.py
│   └── export_decoder.py
├── android/
│   └── minimal runner
└── README.md
```

Directories and scripts should be added only when needed; this tree is not a requirement to create empty scaffolding.

## End-to-end controller

After the components pass independently, the native controller will:

1. tokenize the transcript;
2. prepare speaker prompts or precomputed speaker features;
3. run backbone prefill;
4. run one-step decode and token selection;
5. invoke the diffusion loop for speech diffusion tokens;
6. decode the resulting acoustic latent into PCM;
7. update KV, semantic, and acoustic caches;
8. repeat until the speech-end token;
9. save or stream the resulting 24 kHz mono audio.

The first end-to-end target is three to five seconds. The second is the locked experiment 0001 transcript with both speaker identities.

## Stop and pivot conditions

Record the failure and move to the next component or runtime when:

- required operators cannot be decomposed or implemented without a substantial custom-kernel effort;
- the minimally viable precision cannot fit within Android memory limits;
- numerical drift corrupts diffusion or decoded audio;
- backend partitioning transfers tensors so often that acceleration is ineffective.

A failed full export does not invalidate useful results from individual components.
