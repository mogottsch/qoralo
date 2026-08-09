# Mobile podcast preview bake-off

This experiment locks the common input, audio derivation, evidence schemas, and machine-enforced resource controls for the VibeVoice Realtime 0.5B, Pocket TTS, and Kokoro host previews. It does **not** download or run a model.

## Frozen protocol v1

The exact 226 UTF-8 bytes in `protocol/transcript.txt` (no trailing newline) are the only accepted input:

> Welcome to our small studio, where curious minds unpack one surprising idea at a time. Today, we explore why familiar voices build trust, how thoughtful pauses shape meaning, and what makes a conversation feel genuinely alive.

It has 36 whitespace-delimited words and SHA-256 `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`. `protocol/preview-protocol-v1.json` is normative. A transcript byte change—including punctuation—requires protocol v2 and invalidates all v1 preview acceptances. Results must embed the four fields returned by `tools/protocol.py:protocol_reference`; validation compares all four and fails closed.

The derived comparison is mono PCM S16LE, 24,000 Hz, and exactly 360,000 samples (15.000 seconds). The pipeline averages channels in float64, applies the frozen rational polyphase resampler, chooses a nearby zero-crossing end for an exact-length window, applies 10 ms sine-squared fades, targets -20 LUFS subject to a -1 dBFS ceiling, then uses deterministic TPDF dither. It never stretches, loops, or invents audio. Inputs shorter than 15 seconds are rejected. Use a documented model speed control to regenerate; changing transcript punctuation requires a protocol revision and regeneration of **all** candidates.

Native output is copied once with exclusive creation to `artifacts/raw/<model>/`; derivation writes separately to `artifacts/normalized/<model>/`. Both are ignored. Never pass a raw destination as a normalized output path.

Create a small derivation environment from `requirements-protocol.txt`; the pinned NumPy/SciPy versions are part of protocol v1 and prevent resampler or dither drift.

```bash
python -m venv artifacts/protocol-venv
artifacts/protocol-venv/bin/pip install -r experiments/0007-mobile-podcast-preview-bakeoff/requirements-protocol.txt
artifacts/protocol-venv/bin/python experiments/0007-mobile-podcast-preview-bakeoff/tools/audio_protocol.py derive \
  artifacts/raw/MODEL/native.wav artifacts/normalized/MODEL/preview.wav \
  --metadata artifacts/normalized/MODEL/derivation.json
artifacts/protocol-venv/bin/python experiments/0007-mobile-podcast-preview-bakeoff/tools/audio_protocol.py validate \
  artifacts/normalized/MODEL/preview.wav
```

Timing, process-tree RSS, first-output, audible-output, RTF, hashes, and audio statistic definitions are frozen in the manifest. `schemas/preview-result.schema.json` is the candidate result contract. Artifact paths in committed JSON are references only; media remains ignored.

## Resource controls

Locks are atomic directories under `${PREVIEW_LOCK_ROOT:-/tmp/mobile-podcast-preview-locks}`. Each contains `owner.json` with owner, PID, task, host, UTC creation time, and an unguessable ownership token. Locks are never silently stolen. A dead local PID is reported as `stale`, but the command refuses acquisition and tells the operator to verify liveness and remove the directory manually. Remote, unreadable, and partially-created locks also fail closed.

Run a heavy-RAM job:

```bash
tools/with-resources.sh --task task-7 --heavy-ram -- python model_job.py
```

Run the exclusive phone job:

```bash
tools/with-resources.sh --task task-16 --phone -- adb devices
```

Task 6 must produce a policy conforming to `schemas/generation-policy.schema.json`. It can permit only one or two generation slots:

```bash
tools/with-resources.sh --task task-8 \
  --generation-policy results/generation-capacity.json -- python generate.py
```

Options compose, so Realtime generation uses both `--heavy-ram` and `--generation-policy`. Acquisition is ordered heavy-RAM, phone, generation to avoid inconsistent lock ordering. The wrapper forwards termination signals and releases every acquired lock in a `finally` block after success, command failure, or interruption.

## Tests

```bash
python -m pytest experiments/0007-mobile-podcast-preview-bakeoff/tests -q
```

Tests cover transcript/hash drift, schema validity, protocol invalidation, malformed and multichannel WAVs, resampling, exact trimming, fades, LUFS/peak gain, deterministic dither, raw preservation, statistics/RTF, lock contention and ownership, failure cleanup, safe stale reporting, and one-/two-slot capacity.
