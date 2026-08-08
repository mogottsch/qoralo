# Experiment 0001 — VibeVoice 1.5B local reference

## Result

**Succeeded on CPU.** The fixed two-speaker input produced 13.07 seconds of 24 kHz mono PCM audio.

The first CUDA attempt failed while loading checkpoint shard 3: the RTX 3060 Laptop GPU has 6 GiB VRAM, of which the desktop already occupied roughly 0.8 GiB. The unmodified BF16 model did not fit. CPU execution used FP32 and SDPA.

| Metric | Result |
|---|---:|
| Model generation time | 113.43 s |
| Whole process wall time | 139.16 s |
| Audio duration | 13.066667 s |
| Real-time factor | 8.68 |
| Peak process RSS | 13,023,192 KiB (~12.42 GiB) |
| Input / generated tokens | 503 / 102 |
| Output | PCM S16LE, 24 kHz, mono |
| Output size | 627,244 bytes |
| Output SHA-256 | `fb0152dc686836fe23d9c39c3b24c1de82398f51b9747f5e36ad1db819ce0358` |

Human listening review is still pending. The WAV is intentionally ignored at `artifacts/0001/output-cpu/reference_generated.wav`.

## Locked inputs

- Model: `microsoft/VibeVoice-1.5B`
- Model revision: `c00898d257e6b46004e3e2866a47534085fb685a`
- Official source revision: `6dd49cb7200c0367205a5f1e650244259e9e423d`
- Transcript: [`transcript.txt`](transcript.txt)
- Voices: `en-Carter_man.wav`, `en-Maya_woman.wav`
- Voice SHA-256:
  - Carter: `9dd7b12f25bf279d878a9f7a3125f64bff2b312a189959090acff9138a55e8dd`
  - Maya: `eb1288bc02546c7f1117698fb78e994f060e623af148be8ccbf93dd0bea79e32`
- Seed: `42`
- CFG scale: `1.3`
- Diffusion steps: `10`
- Sampling: disabled

The official historical source was changed only to add an explicit seed argument and select SDPA instead of FlashAttention for this machine. [`prepare_official_source.py`](prepare_official_source.py) applies those changes reproducibly.

## Environment

| Component | Version |
|---|---|
| Python | 3.11.13 |
| PyTorch | 2.7.1+cu128 |
| Transformers | 4.51.3 |
| Diffusers | 0.39.0 |
| Accelerate | 1.6.0 |
| NumPy | 2.4.6 |
| SciPy | 1.17.1 |
| librosa | 0.11.0 |
| NVIDIA driver | 610.57.04 |

## Reproduction outline

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python torch==2.7.1 \
  --index-url https://download.pytorch.org/whl/cu128

# Fetch the historical official TTS source and check out the locked commit.
git clone https://github.com/microsoft/VibeVoice.git artifacts/source/microsoft-vibevoice
git -C artifacts/source/microsoft-vibevoice fetch origin \
  6dd49cb7200c0367205a5f1e650244259e9e423d
git -C artifacts/source/microsoft-vibevoice checkout --detach \
  6dd49cb7200c0367205a5f1e650244259e9e423d
python experiments/0001-vibevoice-1.5b-local-reference/prepare_official_source.py
uv pip install --python .venv/bin/python -e artifacts/source/microsoft-vibevoice

.venv/bin/hf download microsoft/VibeVoice-1.5B \
  --revision c00898d257e6b46004e3e2866a47534085fb685a \
  --local-dir artifacts/models/microsoft-VibeVoice-1.5B

.venv/bin/python artifacts/source/microsoft-vibevoice/demo/inference_from_file.py \
  --model_path artifacts/models/microsoft-VibeVoice-1.5B \
  --txt_path experiments/0001-vibevoice-1.5b-local-reference/transcript.txt \
  --speaker_names Carter Maya \
  --output_dir artifacts/0001/output-cpu \
  --device cpu --cfg_scale 1.3 --seed 42
```

Structured measurements are in [`result.json`](result.json).
