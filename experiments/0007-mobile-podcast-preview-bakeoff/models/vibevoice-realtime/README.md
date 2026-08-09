# VibeVoice Realtime 0.5B — pinned preparation

This directory prepares the official Microsoft source, model, and embedded voice without changing system Python. It is setup evidence only; a successful host load is **not** evidence of Android feasibility or listening quality.

## Immutable inputs

[`pins.json`](pins.json) locks official source commit `94da20d…`, Hugging Face model commit `6bce5f0…` (including the 2,035,332,888-byte safetensors SHA-256), and the otherwise-floating Qwen tokenizer at commit `060db64…`. Both code and model card declare MIT. The public model is not gated and required no click-through or proprietary agreement at inspection time. If that changes, stop and block the Crew task rather than accepting terms.

[`provenance.json`](provenance.json) records the complete official English preset set, conditioning mechanism, selected `en-Grace_woman.pt` and its hash, determinism limits, 24 kHz mono output, streaming distinctions, and lazy-download behavior. “Grace” is an opaque Microsoft-committed cached prompt: Microsoft publishes neither an underlying recording nor identity provenance. It is still preferable to cloning a personal sample, but this limitation must remain visible.

## Isolated setup

Requires `uv`, Git, network access, and a Python 3.11 interpreter discoverable by `uv`.

```bash
./setup.sh
```

The script creates only ignored `artifacts/{venv,source,model}` under this directory. It syncs the fully resolved, hash-locked [`requirements.lock`](requirements.lock), installs the exact source checkout editable with `--no-deps`, downloads the exact model and tokenizer revisions, then validates source/model/tokenizer/voice hashes and direct dependency versions. It never invokes `pip` against system Python. Override the artifact root with `VIBEVOICE_REALTIME_ARTIFACTS` if needed.

The lock is an inference-only subset, not the official web-demo stack: Gradio, WebRTC, FastAPI, and video packages are deliberately absent because model loading/generation does not import them. `transformers==4.51.3` is the official streaming extra's exact pin; Torch is locked to the CUDA 12.8 build used by this host.

## Gated smoke load

After setup:

```bash
./smoke-load.sh
```

Never run `_smoke_load.py` directly. The wrapper acquires task 1's atomic `smoke-load` model-resource grant, forces offline/local-only loading, loads BF16 weights with CUDA SDPA, validates the selected voice cached prompt, and writes ignored `artifacts/smoke-load.json`. It intentionally generates no audio. Failure to acquire the gate is a failure, not permission to bypass it.

## Validation

Metadata and safety checks do not load weights:

```bash
python3 -m unittest discover -s tests -v
python3 verify_pins.py --source artifacts/source/microsoft-vibevoice \
  --model artifacts/model/microsoft-VibeVoice-Realtime-0.5B \
  --tokenizer artifacts/model/Qwen2.5-0.5B-tokenizer
```

Any access, license, dependency, revision, hash, or reproducibility mismatch is fail-closed and must block task 2 and downstream tasks 5/6 rather than being recorded as successful setup.

## Locked preview capture (task 6)

Run only the gated entry point, then derive the normalized copy with the protocol Python environment:

```bash
./generate-preview.sh
python3 finalize_preview.py
```

`generate-preview.sh` obtains one atomic `generation-realtime` grant before importing Torch or loading weights. Under policy v2 that grant is globally exclusive, so Realtime cannot overlap Pocket or Kokoro. It captures every native float32 streaming payload as an immutable `.npy` file and assembles the official-demo-style PCM16 WAV. Both commands refuse to overwrite evidence.

The accepted protocol-v2 measurement is [`../../results/realtime-preview.json`](../../results/realtime-preview.json). The ignored raw output is 20.133333 seconds (483,200 samples); generation took 8.888568 seconds (RTF 0.441485), first output and first audible output arrived at 0.484388 seconds, and peak process-tree RSS was 3,531,898,880 bytes. A second explicitly seeded generation matched the float waveform and WAV byte-for-byte. The derived comparison file is exactly 360,000 mono PCM16 samples at 24 kHz with SHA-256 `a010e2e685446cd5904a0b02ad806f04bb5b5c2bfa2bd7f1c002d1691e9d0d41`. Protocol-v1 raw artifacts remain unchanged in their original directory; v2 evidence is stored under versioned `raw/realtime/v2` and `normalized/realtime/v2` paths.

This is host-preview-only listening and reproducibility evidence. It is not evidence of Android feasibility; subjective anomaly review remains pending the user's listening review.
