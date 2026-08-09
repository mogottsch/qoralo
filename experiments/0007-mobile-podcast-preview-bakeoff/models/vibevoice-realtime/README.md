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
