# Experiment 0002 — VibeVoice 1.5B with ExecuTorch on Android

## Objective

Export VibeVoice components to ExecuTorch, validate them against experiment 0001 fixtures, and progress toward the same approximately 15-second output on the Galaxy S23 Ultra.

## Status

In progress. The fixed-shape FP32 decoder passes ExecuTorch 1.2/XNNPACK on both the host and Galaxy S23 Ultra. The explicit 34-tensor streaming-cache ABI now passes calls 0 and 1 on the host as eight sequential XNNPACK segments. Android streaming execution remains.

## Current tooling

- [`export/capture_fixtures.py`](export/capture_fixtures.py) wraps the real streaming decode call and captures calls 0 and 1 with stable cache names.
- [`export/acoustic_decoder.py`](export/acoustic_decoder.py) constructs only `TokenizerDecoder` and reads only its tensors from the sharded checkpoint.
- [`export/export_decoder.py`](export/export_decoder.py) exports a fixed `[1,64,1]` FP32 non-streaming operator-coverage probe to portable ExecuTorch or XNNPACK, with optional graph diagnostics and the verified causal-padding rewrite.
- [`export/validate_pte.py`](export/validate_pte.py) executes a PTE with its saved input and writes a structured numerical comparison even when the runtime fails.
- [`export/android_io.py`](export/android_io.py) serializes the fixed FP32 input and compares raw Android output with the PyTorch reference.
- [`export/diagnose_decoder.py`](export/diagnose_decoder.py) exports fixed-shape stem, upsampler, stage, and composite micro-probes.
- [`export/streaming_decoder.py`](export/streaming_decoder.py) replaces Python dictionary caches with a stable tensor-only ABI.
- [`export/export_streaming_segments.py`](export/export_streaming_segments.py) exports first and cached entry points as eight stage-aligned XNNPACK PTEs.
- [`export/validate_streaming_sequence.py`](export/validate_streaming_sequence.py) chains actual call-0 cache outputs into call 1 and validates PCM plus all updated caches.
- [`android/`](android/) contains the minimal debug-only ExecuTorch 1.2 runner and its repeatable ADB harness.
- [`fixtures/README.md`](fixtures/README.md) documents the ignored fixture layout and capture command.
- [`fixtures/acoustic-decoder-manifest.json`](fixtures/acoustic-decoder-manifest.json) records the captured shapes, dtypes, stable cache ordering, ranges, and hashes without committing tensors.
- [`results/acoustic-decoder-host.json`](results/acoustic-decoder-host.json) records the host failure matrix, micro-probe evidence, rewrite, and passing result.
- [`results/acoustic-decoder-android.json`](results/acoustic-decoder-android.json) records device runs, memory observations, and the numerical comparison.
- [`results/acoustic-decoder-streaming-host.json`](results/acoustic-decoder-streaming-host.json) records the two-call host streaming sequence and selected segmented ABI.

The initial non-streaming `.pte` remains the Android operator-coverage baseline. Streaming uses separate first and cached entry sets with eight stage-aligned segments because the monolithic streaming graph terminates the host runtime.

## FP32 host result

ExecuTorch 1.0, 1.1, and 1.2 exported the unmodified graph but XNNPACK failed during shape propagation with `xnn_status_invalid_parameter`. Portable execution failed earlier because `constant_pad_nd` received input and output tensors with different dim orders. ExecuTorch 1.2's constant-layout fixes did not resolve this rank-3 pad path, and `_skip_dim_order=True` did not change the portable failure.

Micro-probes isolated the problem:

- the unmodified stem failed;
- the same stem convolution with padding materialized before the graph passed;
- all six `ConvTranspose1d` upsamplers passed individually;
- stages 1–6 passed after rewriting their causal padding;
- stage 0 alone exposed a singleton-time output layout ambiguity, but the complete initial stem → stage 0 → upsampler 1 graph passed.

The verified rewrite expresses causal zero padding as symmetric padding inside `Conv1d` and slices away the right-padding-only outputs. All 28 decoder `SConv1d` modules are rewritten only in the non-streaming export wrapper. Eager output remains within `atol=1e-6, rtol=1e-5` of the pinned implementation.

The full ExecuTorch 1.2 XNNPACK host result:

| Metric | Result |
|---|---:|
| PTE size | 1,375,020,420 bytes |
| Load time | 0.00144 s |
| Inference time | 0.06768 s |
| Peak host RSS | 1,881,128 KiB |
| Output | `[1,1,3200]` FP32 |
| Maximum absolute error | `8.08e-10` |
| Mean absolute error | `1.01e-11` |
| Comparison | passed (`atol=1e-5`, `rtol=1e-4`) |

Reproduce the passing export and host comparison with ExecuTorch 1.2, its paired PyTorch 2.11 environment, and FlatBuffers compiler 25.12.19 on `PATH`:

```bash
uv venv --python 3.11 artifacts/venv-executorch-1.2
uv pip install --python artifacts/venv-executorch-1.2/bin/python torch==2.11.0 \
  --index-url https://download.pytorch.org/whl/cpu
uv pip install --python artifacts/venv-executorch-1.2/bin/python \
  --prerelease=allow executorch==1.2.0
uv pip install --python artifacts/venv-executorch-1.2/bin/python \
  --no-deps -e artifacts/source/microsoft-vibevoice
uv pip install --python artifacts/venv-executorch-1.2/bin/python \
  transformers==4.51.3 accelerate==1.6.0 safetensors ml-collections absl-py

artifacts/venv-executorch-1.2/bin/python \
  experiments/0002-vibevoice-1.5b-executorch-android/export/export_decoder.py \
  --backend xnnpack --rewrite-constant-pad \
  --graph-output artifacts/0002/acoustic-decoder-xnnpack.graphs.txt \
  --output artifacts/0002/acoustic-decoder-xnnpack.pte

artifacts/venv-executorch-1.2/bin/python \
  experiments/0002-vibevoice-1.5b-executorch-android/export/validate_pte.py \
  artifacts/0002/acoustic-decoder-xnnpack.pte
```

## FP32 Android result

The matching ExecuTorch 1.2 Android AAR loaded the XNNPACK PTE from app-private storage and produced the expected `[1,1,3200]` FP32 output on the Galaxy S23 Ultra.

| Metric | Result |
|---|---:|
| First cold inference | 8.078 s |
| Subsequent inference | 4.551 s, 4.154 s, 6.628 s |
| Subsequent median | 4.551 s |
| Maximum process VmHWM | 1,602,328 KiB (~1.53 GiB) |
| Maximum observed PSS | 1,401,425 KiB (~1.34 GiB) |
| Maximum absolute error | `8.50e-10` |
| Mean absolute error | `1.09e-11` |
| Comparison | passed (`atol=1e-5`, `rtol=1e-4`) |

All four device runs produced the same raw output SHA-256. The first run followed model transfer and includes cold filesystem/backend effects; later runs benefited from cached pages but still showed meaningful timing variability. Memory is app-reported `VmHWM` plus point-in-time PSS rather than a high-frequency external trace.

Reproduce the Android build, install, app-private transfer, execution, retrieval, and comparison with:

```bash
experiments/0002-vibevoice-1.5b-executorch-android/android/run-decoder-probe.sh
```

The 1.375 GB FP32 module is a correctness artifact. The passing result establishes Android operator coverage but does not make this a practical deployment.

## FP32 streaming host result

The tensor-only streaming ABI orders 34 cache tensors by stable decoder module name. A first entry consumes one `[1,64,1]` latent; a cached entry consumes the next latent plus those 34 tensors. Both return `[1,1,3200]` PCM and 34 updated tensors.

A monolithic XNNPACK streaming PTE exported but terminated the host process during execution. The portable form also retained an invalid rank-3 convolution dim order. The validated design therefore follows natural decoder boundaries: seven upsample/stage PTEs plus one norm/head PTE for each entry type.

| Metric | Call 0 / first | Call 1 / cached |
|---|---:|---:|
| XNNPACK segments | 8 | 8 |
| Total host inference | 0.08936 s | 0.10632 s |
| PCM shape | `[1,1,3200]` | `[1,1,3200]` |
| PCM maximum absolute error | `8.08e-10` | `3.87e-11` |
| Maximum cache absolute error | `4.96e-5` | `4.96e-5` |
| Comparison | passed | passed |

Call 1 consumed the **actual ExecuTorch cache outputs from call 0**, not the fixture pre-cache tensors. Every PCM output and all 34 updated caches were compared with the deterministic PyTorch fixtures using `atol=2e-5, rtol=1e-5`. Peak host RSS for the two-call sequence was 1,648,768 KiB.

The first entry set occupies 1,375,063,172 bytes and the cached entry set 1,379,159,424 bytes, so the current FP32 diagnostic ABI duplicates weights on disk. This is acceptable for correctness but must be addressed through FP16, packaging, or entry unification before practical deployment.

Reproduce both entry exports and the chained host comparison with:

```bash
export PATH="$PWD/artifacts/tools/flatbuffers-25.12.19:$PATH"
PY=artifacts/venv-executorch-1.2/bin/python
EXP=experiments/0002-vibevoice-1.5b-executorch-android/export

$PY "$EXP/export_streaming_segments.py" --entry first
$PY "$EXP/export_streaming_segments.py" --entry cached
$PY "$EXP/validate_streaming_sequence.py" \
  artifacts/0002/acoustic-decoder-streaming-first-segments-1.2 \
  artifacts/0002/acoustic-decoder-streaming-cached-segments-1.2 \
  --output artifacts/0002/acoustic-decoder-streaming-sequence-host.json
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
