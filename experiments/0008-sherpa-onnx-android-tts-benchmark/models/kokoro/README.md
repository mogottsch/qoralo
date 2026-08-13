# Exact Kokoro v1.0 deployment track

This directory describes only `kokoro-multi-lang-v1_0` from the pinned archive SHA-256 `c133d26353d776da730870dac7da07dbfc9a5e3bc80cc5e8e83ab6e823be7046`. It is not interchangeable with Kokoro v1.1, the original PyTorch checkpoint used in experiment 0007, or another sherpa conversion.

## Voice proof

[`voice-proof.json`](voice-proof.json) binds the archive and `model.onnx` hashes to the v1.0 conversion source at sherpa-onnx commit `3dc7c569f31ca2cd4a20ed6f7db780327e6714c5`. The exact upstream [`generate_voices_bin.py`](conversion/generate_voices_bin.py) is retained with its SHA-256. Its literal `id2speaker` ordering maps index `3` to `af_heart`. The exact ONNX file also carries `id2speaker` metadata containing `3->af_heart`; `validate_track.py --model-root ...` checks that metadata in the hash-verified model. A guessed or shifted speaker ID fails validation.

## Deployment

[`deployed-inventory.json`](deployed-inventory.json) pins all 377 regular files (400,786,089 bytes), including:

- `model.onnx`, `voices.bin`, and `tokens.txt`;
- US/GB English and Chinese lexicons and the Chinese FSTs;
- the complete packaged `espeak-ng-data` tree;
- packaged dictionaries, notices, README, and Apache-2.0 `LICENSE`.

[`sherpa-config.json`](sherpa-config.json) selects the US-English lexicon and packaged eSpeak data through filesystem-relative paths. [`benchmark-descriptor.json`](benchmark-descriptor.json) pins every deployed file plus the config and frozen transcript, selects `provider="cpu"`, one thread, English, SID `3`, and app-specific external-file storage. Asset URIs, absolute/traversing paths, QNN, and all non-CPU providers are rejected.

Acquire and verify the model through the common pinning utility:

```sh
BASE=experiments/0008-sherpa-onnx-android-tts-benchmark
python "$BASE/tools/pinning.py" --manifest "$BASE/pins/assets.json" download kokoro artifacts/0008/downloads
python "$BASE/tools/pinning.py" --manifest "$BASE/pins/assets.json" extract kokoro \
  artifacts/0008/downloads/kokoro-multi-lang-v1_0.tar.bz2 artifacts/0008/models/kokoro
python "$BASE/models/kokoro/validate_track.py" \
  --model-root artifacts/0008/models/kokoro/kokoro-multi-lang-v1_0
```

Model archives, extracted files, wheels, and WAVs remain ignored artifacts.

## Host configuration smoke

[`host-smoke-report.json`](host-smoke-report.json) was produced with the two manifest-pinned sherpa-onnx 1.13.5 wheels on Ubuntu 22.04 x86-64 and CPython 3.11.9. `run_host_smoke.py` refuses another platform, Python patch version, wheel set, wheel hash, model tree, transcript, provider, or voice. It writes PCM16 only after synthesis, independently decodes the complete WAV with Python's standard `wave` decoder, and verifies frame integrity and non-silence.

The report intentionally contains **no elapsed time or RTF**. Its 24 kHz, non-empty, non-silent output proves configuration compatibility only. It is not Galaxy S23 Ultra timing, memory, thermal, callback, or Android performance evidence.

```sh
python "$BASE/models/kokoro/run_host_smoke.py" \
  --model-root artifacts/0008/models/kokoro/kokoro-multi-lang-v1_0 \
  --wheel-dir artifacts/0008/host-wheels \
  --transcript "$BASE/protocol/transcript.txt" \
  --output-wav artifacts/0008/kokoro-host-smoke.wav \
  --report "$BASE/models/kokoro/host-smoke-report.json"
```

Run the fail-closed contract tests with:

```sh
python -m unittest "$BASE/models/kokoro/test_track.py"
```
