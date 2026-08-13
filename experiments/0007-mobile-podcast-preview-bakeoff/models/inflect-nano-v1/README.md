# Candidate E: pinned Inflect-Nano-v1 CPU track

This isolated track prepares **only** `owensong/Inflect-Nano-v1` at immutable Hugging Face revision `ab0302781cb0cb9969a9a28ce8e1b259539275dd`. It does not permit v2, an alias, a similarly named repository, or replacement weights. Setup and smoke loading do not generate the full protocol transcript.

## Frozen provenance

`pins.json` records SHA-256 and byte size for every file in the inference path. In particular:

- acoustic checkpoint: `weights/inflect_nano_v1_acoustic.pt`, SHA-256 `0129f730a25a1e44d1799a1d47166c9a3a5644e58fb84a3b554d5c036827ec89`;
- vocoder checkpoint: `weights/inflect_nano_v1_vocoder.pt`, SHA-256 `57482bee18ef72c2df0153f44dafd14f1666ce11cd1558e3437272b13fa18d08`;
- model, source, and repository license: Apache-2.0, with the pinned `LICENSE` hash;
- vendored `tiny_tts_frontend`: every source/dictionary asset is pinned to the same repository revision and hashed; its separately included license is Apache-2.0 and is hashed in `pins.json`;
- frontend runtime assets: the frontend's `bert-base-uncased` tokenizer is forced to local `google-bert/bert-base-uncased` revision `86b5e0934494bd15c9632b12f734a8a67f723594` (Apache-2.0) with every required file hashed; the three `g2p-en`/NLTK data archives are frozen at `nltk/nltk_data` revision `550b6625bcef1f2abff2ff770a5a0d272c9c6b2a` with hashes and their upstream package license/README provenance retained;
- dependency graph: exact direct versions in `pyproject.toml`, transitive artifacts/hashes in `uv.lock`, whose hash is also frozen in `pins.json`.

The upstream model card documents one built-in English male voice. Its checkpoint speaker identifier is `mark`. This is the fixed stock model voice, not a user voice: no voice selector, reference recording, speaker embedding input, builder, or cloning path is exposed by this track.

The official native CLI returns 24 kHz mono PCM S16LE WAV. The pinned CPU command is equivalent to:

```bash
python inference.py --device cpu \
  --text "$(cat ../../protocol/transcript.txt)" \
  --length-scale PREDECLARED_VALUE --pitch-scale 1.00 --energy-scale 1.00 \
  --out UNIQUE_WRITE_ONCE_PATH
```

The wrappers hide CUDA. The raw waveform is preserved before the unchanged protocol-v2 normalizer is used by the later generation task.

## Default-first duration plan

`attempt-plan.json` is the pre-inference authority. The documented `length_scale` default is `1.00`; larger values increase predicted duration. This experiment freezes a finite ascending grid from **1.00 through 1.50 inclusive**, step **0.05**:

`1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50`.

Run in that exact order and stop at the first native output lasting at least 15.0 seconds. If no value passes, Candidate E is blocked. The bounds are the experiment's conservative precommitted search bounds, not an invented upstream claim. Pitch and energy stay at their documented defaults (`1.00`) and may not adjust duration. Padding, looping, time stretching, altered text, or an ad hoc length scale are forbidden.

Every primary attempt and fresh-process repeat has its own exclusive directory. Directory creation and WAV/report writes refuse existing paths; failed paths are retained for investigation rather than overwritten. Each invocation acquires the same global `full-generation` gate.

## Commands

From `experiments/0007-mobile-podcast-preview-bakeoff`:

```bash
python models/inflect-nano-v1/verify_pins.py
python models/inflect-nano-v1/verify_pins.py --online  # optional upstream comparison
models/inflect-nano-v1/setup.sh
models/inflect-nano-v1/smoke-load.sh
```

Setup uses only `uv`, an already installed Python 3.11, and ignored paths below `artifacts/inflect-nano-v1/`. It never uses `sudo`, system `pip`, credentials, or license click-through. A gated repository, changed revision/hash/license, missing public dependency, or proprietary/manual acceptance is a terminal blocker.

After preparation, task 7 runs attempts individually:

```bash
models/inflect-nano-v1/generate-attempt.sh 0
# only if attempt 0 is under 15 seconds:
models/inflect-nano-v1/generate-attempt.sh 1
# after the first passing primary, repeat that same index in a fresh process:
models/inflect-nano-v1/generate-attempt.sh PASSING_INDEX --repeat
```

The generator reads only the frozen protocol-v2 transcript (SHA-256 `350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f`), uses CPU and the fixed voice, records shared monotonic/RSS metrics, and writes native evidence below ignored `artifacts/raw/inflect-nano-v1/v2/`.
