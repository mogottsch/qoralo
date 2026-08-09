# Kokoro 82M pinned setup

This directory prepares the Kokoro candidate only. It does not produce the task 8 preview. Environments, weights, caches, logs, and smoke evidence stay under ignored `artifacts/kokoro/`.

## Immutable inputs

`pins.json` locks the public, ungated Apache-2.0 `hexgrad/Kokoro-82M` repository at `f3ff3571791e39611d31c381e3a41a3af07b4987`, each file used by the smoke load by byte count and SHA-256, and the recommended Hexgrad `kokoro` package at 0.9.4. The PyPI wheel and its SHA-256 are pinned; `uv.lock` closes the dependency graph. The corresponding official source revision is `dfb907a02bba8152ca444717ca5d78747ccb4bec`.

The library's default constructors download from a moving repository revision. `smoke_load.py` deliberately avoids those defaults: it downloads the named snapshot revision and passes local config, weights, and voice paths to `KModel`/`KPipeline`.

Run local or live provenance checks:

```bash
python models/kokoro/verify_pins.py
python models/kokoro/verify_pins.py --online
```

## Isolated installation and exact blocker

Kokoro 0.9.4 supports Python 3.10–3.12. The setup uses an already-installed Python 3.11 via `uv`, the CPU PyTorch index, and an ignored venv. It never calls `sudo`, `apt`, or system `pip`.

American English G2P is provided by `misaki[en]`. It uses its English lexicon first and the `espeak-ng` executable for out-of-dictionary fallback. `espeak-ng` is therefore treated as required, even though a particular transcript might happen not to exercise fallback. If it is absent, setup exits 69 with the exact blocker. Supply a permitted user/project-local binary on `PATH`; do not install it with privileges from this experiment. Japanese and Mandarin need `misaki[ja]` and `misaki[zh]`, respectively, but are outside this English preview. Other supported languages use eSpeak directly.

Misaki otherwise lazily downloads spaCy's English model on first use, so `en-core-web-sm` 3.8.0 is an explicit locked environment dependency rather than an unrecorded smoke-time install. Misaki also unconditionally selects `espeakng-loader`'s bundled library; its 0.2.4 Linux wheel has a nonportable compiled data prefix on this host. The smoke loader selects the already-installed system library and `/usr/share/espeak-ng-data` after validating both. A project-local replacement can be selected with `KOKORO_ESPEAK_LIBRARY` and `KOKORO_ESPEAK_DATA`.

From the experiment directory:

```bash
models/kokoro/setup.sh
models/kokoro/smoke-load.sh
```

The second command is the only supported smoke entry point. It wraps download, hash verification, model construction, voice loading, and frozen-transcript phonemization in task 1's conservative `smoke-load` grant. A direct Python invocation fails closed. The smoke report is ignored at `artifacts/kokoro/smoke-load.json`.

## Voice provenance

The selected voice is `af_heart`, the model repository's documented American-English female stock voice. The pinned `VOICES.md` gives it overall grade A and SHA-256 prefix `0ab5709b`; `pins.json` contains the full digest of `voices/af_heart.pt`. No personal recording, cloning input, or external conditioning audio is used.

At the pinned revision, stock packs comprise:

- American English: `af_alloy`, `af_aoede`, `af_bella`, `af_heart`, `af_jessica`, `af_kore`, `af_nicole`, `af_nova`, `af_river`, `af_sarah`, `af_sky`, `am_adam`, `am_echo`, `am_eric`, `am_fenrir`, `am_liam`, `am_michael`, `am_onyx`, `am_puck`, `am_santa`;
- British English: `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`, `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis`;
- Spanish/French: `ef_dora`, `em_alex`, `em_santa`, `ff_siwis`;
- Hindi/Italian: `hf_alpha`, `hf_beta`, `hm_omega`, `hm_psi`, `if_sara`, `im_nicola`;
- Japanese: `jf_alpha`, `jf_gongitsune`, `jf_nezumi`, `jf_tebukuro`, `jm_kumo`;
- Brazilian Portuguese: `pf_dora`, `pm_alex`, `pm_santa`;
- Mandarin: `zf_xiaobei`, `zf_xiaoni`, `zf_xiaoxiao`, `zf_xiaoyi`, `zm_yunjian`, `zm_yunxi`, `zm_yunxia`, `zm_yunyang`.

The authoritative quality/training-data and any CC-BY notes remain the pinned `VOICES.md`, linked in `pins.json`; this list does not invent provenance beyond it.

## Native output and determinism

The library yields mono `torch.float32` waveform tensors at 24,000 Hz. Its official CLI writes mono 24 kHz PCM signed 16-bit WAV. Task 8 must preserve the native raw output before applying the shared exact-15-second derivation.

Kokoro inference samples excitation noise (`torch.rand`, `torch.randn_like`) and exposes no generator/seed argument. Reproducibility therefore requires setting `torch.manual_seed(0)` immediately before every generation and enabling deterministic PyTorch algorithms. CPU execution, the locked environment, exact local artifacts, text, voice, language `a`, speed, and chunking must remain fixed. Task 8 must render twice in fresh processes and compare raw hashes; a mismatch is a reproducibility blocker, not permission to publish one run. The setup smoke records the controls but intentionally defers this full generation repeat check.

The documented `speed` control defaults to 1.0. It changes predicted durations without time-stretching. Task 8 may use it only according to the shared short-output procedure and must record the value. No transcript other than `protocol/transcript.txt` is accepted.

## Accepted preview (task 8)

Run from the experiment directory:

```bash
models/kokoro/generate_preview.sh
```

The wrapper obtains one atomic `generation-kokoro` grant and holds it across two fresh-process CPU renders. It refuses direct loading, transcript or pinned-file drift, an absent isolated environment, missing eSpeak resources, and an existing write-once output directory. Generation is network-offline and uses the documented `speed=0.85` duration control; it does not time-stretch audio.

The protocol-v2 accepted capture produced 17.475 seconds of native 24 kHz mono float32 audio. Both fresh processes produced SHA-256 `b6d8d126dae93f3d1f52bebf96d695c48d07c8ddf79a97d429c4687007e57494`; the exact 15-second normalized WAV has SHA-256 `24cdb3b81fff87a1ecc46ff4e6aa740512f3eab2e33f5ae4cbec541b12fed196`. The ignored native files and normalized WAV are under `artifacts/previews/kokoro/`; the committed measurements and hashes are in `results/kokoro-preview.json`. The invalidated protocol-v1 capture was moved aside without modification. Re-running intentionally requires moving the existing ignored output aside rather than overwriting raw evidence.
