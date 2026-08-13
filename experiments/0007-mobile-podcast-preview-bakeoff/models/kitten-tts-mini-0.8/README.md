# Candidate F: Kitten TTS Mini 80M v0.8

This isolated track prepares **only** `KittenML/kitten-tts-mini-0.8` at immutable Hugging Face revision `c02725660cea441db4c383af69f1f26f5cd00947`, with the official GitHub `0.8` release asset `kittentts-0.8.0-py3-none-any.whl`. It does not permit Kitten nano, micro, a later mini release, a moving revision, PyPI's unrelated/unofficial resolution, or a package inferred from an unversioned URL.

Environments, downloads, weights, smoke reports, and generated audio stay in ignored `artifacts/kitten-tts-mini-0.8/`.

## Frozen provenance and licenses

`pins.json` records the exact 80M mini identity, model revision, model/config/voice-pack hashes and sizes, official source tag commit `0c61f684b54fe962e4b7c2fa0285ed75f64ad402`, release-wheel name/size/SHA-256, source requirements hash, Apache-2.0 license hash, native format, and CPU execution contract. `uv.lock` pins the complete dependency graph and distribution hashes; its own digest is frozen in `pins.json`.

The model card declares Apache-2.0. The official source and wheel contain Apache-2.0 text with SHA-256 `787aa312b93eee80b636f35652469df29efdb7582239d6a9c088467555a3c7fd`. The bundled voices are distributed in that model repository; the selected voice inherits the model repository's declared Apache-2.0 license. Installed dependencies retain their own licenses and notices in their locked distributions and environment; this track does not relicense them.

The official 0.8 wheel is upstream-mispackaged: its filename/release is 0.8.0, but its embedded distribution metadata and `kittentts.__version__` still say `0.1.0` and describe the earlier nano model. Verification therefore establishes package identity from the official release tag, exact asset URL/name/size/hash, source commit, and model config. It records rather than conceals the stale internal metadata. Setup narrowly sets `UV_SKIP_WHEEL_FILENAME_CHECK=1` only after independently checking the official asset hash, because uv otherwise rejects that upstream filename/METADATA mismatch. Replacing it with PyPI `kittentts`, 0.8.1, or any rebuilt wheel is forbidden.

Check committed evidence offline or compare it to the public, ungated upstream APIs:

```bash
python models/kitten-tts-mini-0.8/verify_pins.py
python models/kitten-tts-mini-0.8/verify_pins.py --online
```

## Fixed stock voice

The chosen voice is the documented bundled alias **`Jasper`**, mapped by pinned `config.json` to `expr-voice-2-m` in pinned `voices.npz`. The exact float32 `[400, 256]` array has 409,600 C-order bytes and SHA-256 `4fc6fdcbaac820aad0d2f3040709bc0e23e3674d9c7f2eaa67ddc9573f128de4`. The smoke load recomputes it. There is no reference-audio argument, speaker upload, custom conditioning, or cloning path in this track.

## Default-only duration plan

`attempt-plan.json` was committed before full generation. The pinned README and wheel document `speed`, and say only that `1.0` is normal. They do not document supported numeric bounds or which direction lengthens this model's output. Therefore the only eligible attempt is the official default `speed=1.0`. This is deliberately not an invented grid.

The first native output at least 15 seconds would be accepted. If the default is shorter, Candidate F has a terminal protocol blocker: do not add an ad hoc speed, pad, loop, time-stretch, alter the transcript, or replace raw evidence.

## Isolated CPU setup and gated load

From the experiment directory:

```bash
models/kitten-tts-mini-0.8/setup.sh
models/kitten-tts-mini-0.8/smoke-load.sh
```

Setup uses an already installed Python 3.11 and `uv`; it never calls `sudo`, an OS package manager, or system pip. It downloads the exact official wheel to the ignored artifact directory and checks its hash before `uv sync --locked`. The lock selects `onnxruntime` and pins the indirect PyTorch dependency to `torch==2.6.0+cpu` from PyTorch's CPU-only index; no CUDA/NVIDIA distributions are present in the graph. Setup and smoke reject CUDA/TensorRT providers. English phonemization requires an already-provided `espeak-ng`, library, and data directory. The locked loader wheel embeds a nonportable build-host data prefix, so the scripts validate and select `/usr/lib/libespeak-ng.so` plus `/usr/share/espeak-ng-data`, or permitted project-local replacements via `KITTEN_ESPEAK_LIBRARY` and `KITTEN_ESPEAK_DATA`; they never install these with privileges.

`smoke-load.sh` is the only supported load entry point. It obtains task 1's global exclusive `model-load` grant, downloads only the pinned model revision, checks every byte count/hash and the selected voice digest, constructs the official ONNX class from local files, and writes an ignored report without synthesizing the protocol transcript. Direct `smoke_load.py` execution fails closed.

## Generation scaffold (task 8 only)

```bash
models/kitten-tts-mini-0.8/generate-preview.sh primary
models/kitten-tts-mini-0.8/generate-preview.sh repeat-1
```

Each invocation independently acquires the same global `full-generation` gate. The scaffold accepts only the committed `default` attempt, exact protocol-v2 transcript hash, local hash-verified assets, Jasper, CPU providers, and a unique output below the ignored generation directory. Native mono float waveform bytes are written with exclusive creation and measured at 24 kHz. The official API is non-streaming, so first API output is explicitly completion-equivalent. Shared monotonic/RSS/audibility/RTF metrics are recorded. A short default is preserved with metadata and exits as the declared terminal blocker.

Do not run full generation as part of this preparation task. No credentials, gated assets, privileged installation, Android work, reference recordings, or voice cloning are used.
