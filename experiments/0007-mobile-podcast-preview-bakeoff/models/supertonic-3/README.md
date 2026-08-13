# Candidate D — official Supertonic 3 CPU track

This isolated host-listening track is **only** for official [`Supertone/supertonic-3`](https://huggingface.co/Supertone/supertonic-3) and the official [`supertone-inc/supertonic-py`](https://github.com/supertone-inc/supertonic-py) SDK. It does not establish Android feasibility.

## Frozen identity and licensing

`pins.json` fixes model commit `724fb5abbf5502583fb520898d45929e62f02c0b`, the complete inference artifact allowlist and hashes, SDK source commit `908a56486e821e833a80530ff0cae3ad0b046fce` (signed tag `v1.3.1`), PyPI wheel hash, dependency lock, and license hashes. This model revision is the exact revision embedded by SDK 1.3.1. The SDK is MIT licensed. The model's bundled `LICENSE` is OpenRAIL-M and includes its third-party notices. Neither repository is gated and no click-through or proprietary/manual acceptance is needed.

The only voice is bundled stock style `M1` at the pinned `voice_styles/M1.json`. Custom styles, Voice Builder exports, voice cloning, reference audio, personal input, alternate repositories, moving branches/tags, and environment overrides of repository/revision are outside this track and must be rejected. Never supply `HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN`; the scripts fail closed if credentials are present.

Native SDK output is a mono NumPy float32 waveform at 44,100 Hz. The scaffold preserves its flattened little-endian float32 bytes. It does not resample, normalize, stretch, pad, loop, or replace them. Only the unchanged protocol-v2 normalization tool may later derive the 24 kHz listening sample.

## Local CPU setup and verification

Prerequisites are `uv`, an already-installed CPython 3.11, network access for initial public artifact download, and sufficient disk/RAM for the 398 MB snapshot. No script invokes `sudo`, `apt`, system `pip`, downloads Python, requests credentials, or modifies the system environment.

```bash
cd experiments/0007-mobile-podcast-preview-bakeoff/models/supertonic-3
./setup.sh
./verify_pins.py --online       # optional official API comparison
./smoke-load.sh                # gated download, hash verification, CPU-only load; no inference
```

`setup.sh` reproduces `uv.lock` in the ignored experiment artifact environment. `smoke-load.sh` is the only supported load entry point and uses the shared global resource gate. It allows only ONNX Runtime `CPUExecutionProvider`, explicitly disables SDK auto-download during load, verifies every local byte first, loads only `M1`, and records a report.

## Precommitted length attempts

[`speed-attempts.json`](speed-attempts.json) is immutable generation input. SDK documentation defines speed range 0.70–2.00 and default 1.05. The exact sequence is default with the argument omitted, then `1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70`: a descending grid with step 0.05 and inclusive lower endpoint. Run in order and stop at the first raw waveform at least 15.0 seconds long. A failure or short waveform remains at its separate write-once attempt path. Do not skip ahead or run attempts after the first pass.

Task 6 invokes one full job at a time so each has its own exclusive grant:

```bash
./generate_preview.sh 0
# inspect immutable attempt-00 metadata; only if <15.0 seconds:
./generate_preview.sh 1
```

`generate_preview.py` is intentionally generation scaffolding, not permission to run now. A deterministic fresh-process repeat and shared monotonic/RSS/first-audible metrics are Task 6 responsibilities. The non-streaming SDK exposes its first API waveform only when the complete synthesis call returns, so API-first-output equals completion time and is recorded with that explanation.
