# Spike plan

## Research question

Can VibeVoice generate useful podcast-style audio locally on a modern Android flagship, and which inference runtime offers the best combination of correctness, portability, memory use, speed, and implementation effort?

## Model order

1. **VibeVoice TTS 1.5B** — primary target; joint multi-speaker podcast generation.
2. **VibeVoice Realtime 0.5B** — second model; smaller single-speaker deployment comparison.

VibeVoice Large/7B is excluded from the phone spike.

## Phase 1 — Local 15-second reference

Run the official VibeVoice 1.5B implementation on the local laptop and generate one fixed two-speaker clip of approximately 15 seconds.

Freeze and record:

- Hugging Face repository and exact revision;
- VibeVoice source revision;
- Python, PyTorch, Transformers, and dependency versions;
- transcript and speaker labels;
- speaker prompts or embedded voices;
- random seed;
- CFG scale, diffusion steps, sampling settings, and precision;
- model-load time, peak process RSS, generation wall time, and output duration;
- output sample rate, format, file size, and SHA-256;
- warnings, fallbacks, and deviations from the official example.

If the laptop cannot run the BF16 model acceptably, document that result and produce the reference on a temporary GPU environment with the same locked inputs.

### Phase 1 output

`experiments/0001-vibevoice-1.5b-local-reference/` must contain the reproducible configuration, commands, environment lock information, metrics, and a short listening assessment. The large WAV stays under ignored `artifacts/`.

## Phase 2 — ExecuTorch on Android

ExecuTorch is the first Android candidate because VibeVoice originates in PyTorch and ExecuTorch supports Android CPU, Vulkan, and Qualcomm backends.

Do not export the complete model first. Attempt components in this order:

1. acoustic decoder with a fixed latent;
2. one diffusion-head step;
3. language backbone forward pass;
4. KV-cache update;
5. speaker conditioning;
6. 3–5 seconds end-to-end;
7. the fixed 15-second reference transcript.

For each component, compare output tensors against the local PyTorch reference before proceeding.

## Phases 3–5 — Other Android runtimes

Repeat the smallest meaningful component and end-to-end tests with:

3. LiteRT / LiteRT-LM;
4. ONNX Runtime Mobile;
5. Qualcomm QNN / AI Engine Direct.

Use the same fixtures and metrics so the results remain comparable. Direct QNN work begins only after a general runtime produces a correct output.

## Phase 6 — Realtime 0.5B

After recording the 1.5B results, test Realtime 0.5B using the most promising runtime paths. Measure its smaller deployment footprint and streaming performance, while treating its single-speaker behavior as functionally different from the 1.5B podcast model.

## Precision ladder

Quantize one component at a time:

| Backbone | Diffusion | Audio components | Purpose |
|---|---|---|---|
| BF16/FP16 | FP16 | FP16 | correctness reference where supported |
| INT8 | FP16 | FP16 | conservative mobile candidate |
| INT4 | FP16 | FP16 | likely practical target |
| INT4 | INT8 | FP16 | aggressive experiment |

Do not assume that the diffusion or audio paths tolerate INT4.

## Common metrics

Every measured run records:

- source and model revisions;
- runtime/backend and versions;
- precision and quantization method;
- model and package size;
- model-load time;
- peak RSS;
- time to first audio;
- generated duration and wall time;
- real-time factor;
- output hash;
- tensor error where a fixture exists;
- omissions, repetitions, corruption, speaker consistency, and listening notes.

## First Android success threshold

On the Galaxy S23 Ultra:

- load the complete candidate without a low-memory kill;
- generate at least 15 seconds from the fixed two-speaker transcript;
- preserve both speaker identities;
- produce no major omissions, repetitions, or corrupted audio;
- collect complete memory and runtime measurements.

Real-time generation is not required for the first success.
