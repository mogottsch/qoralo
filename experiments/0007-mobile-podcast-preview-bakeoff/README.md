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

`protocol/model-resource-policy-v1.json` starts fail-safe: every smoke load, RSS preflight, preview generation, VibeVoice capture, export, and protocol revision is mutually exclusive. There are no independently acquired locks or slots. `ResourceGrant` takes one administrative `flock`, examines every active grant, and creates one logical grant as a single transaction under `${PREVIEW_LOCK_ROOT:-/tmp/mobile-podcast-preview-gate}`. Its `owner.json` records owner/task/kind, hostname plus boot ID, PID plus Linux process-start ticks, UTC creation time, and an unguessable token. The wrapper forwards termination signals and releases its grant in `finally`.

```bash
# kind is smoke-load, preflight, generation-realtime, generation-pocket,
# generation-kokoro, capture, export, or protocol-revision
tools/with-resources.sh --task task-7 --kind generation-pocket -- python generate.py
```

Task 5 may install a schema-valid measured policy in one administrative transaction, and only with no active grants:

```bash
python tools/resource_lock.py install-policy \
  artifacts/task-5/measured-policy.json artifacts/shared/model-resource-policy.json
```

The only less-conservative policy accepted by the code permits one Pocket generation and one Kokoro generation to coexist. Realtime, capture, export, preflight, smoke loads, and protocol revisions remain exclusive and block both. Capacity can never exceed two. The loader independently recomputes Pocket-plus-Kokoro peak RSS plus a positive safety margin and rejects a policy unless it leaves explicit headroom below both physical RAM and 32 GiB.

Task 5's repeatable measurement entry point is:

```bash
experiments/0007-mobile-podcast-preview-bakeoff/tools/run-preflights.sh
```

It acquires one `preflight` grant around all three workers, runs them strictly in Realtime/Pocket/Kokoro order, and records process-tree cold-load, cold-inference, and warm-inference RSS plus host baselines, lazy artifact growth, and post-exit cleanup under ignored `artifacts/task-5/`; the reviewed measurement summary is committed at `results/generation-capacity.json`. Each worker performs two deliberately short inference calls; their samples are discarded in memory and can never become preview evidence. After releasing the preflight grant, the script obtains the administrative policy-update transaction (which requires no active grant) and atomically replaces `protocol/model-resource-policy-v1.json`. Final generation wrappers consume that installed default policy without an extra slot or lock.

A grant is never reclaimed because it is old. Inspection must match host name, boot ID, PID liveness, and process start ticks. Dead or reused PIDs with a complete matching host identity are reported `stale_proven` but still block acquisition. Remote, incomplete, unreadable, and partially created grants are `remote_or_unknown` or `stale_unverifiable` and fail closed. Only the parent, after setting `PREVIEW_PARENT_ORCHESTRATOR=1`, may explicitly run `resource_lock.py recover-stale`; even then the tool removes only `stale_proven` grants and requires manual investigation otherwise.

## Short-output and protocol-revision procedure

Silence padding, looping, and time stretching are prohibited. A worker whose raw output is short must first exhaust documented model speed controls. It then writes a request conforming to `schemas/protocol-revision-request.schema.json`; it does **not** edit the transcript or manifest and does not mark the candidate blocked yet.

Only the parent orchestrator may make the single shared punctuation revision. It sets `PREVIEW_PARENT_ORCHESTRATOR=1`, acquires `--kind protocol-revision`, stops or waits for active preview workers, writes the incremented manifest/transcript atomically, and cascade-resets preview tasks 6–8 plus publication/report tasks 16–18. All three preview results fail `validate_result_protocol` until regenerated. The unrelated VibeVoice 1.5B capture is not invalidated. A candidate is blocked only if documented speed controls and that shared revision both fail to produce at least 15 seconds.

## Tests

```bash
python -m pytest experiments/0007-mobile-podcast-preview-bakeoff/tests -q
```

Tests cover transcript/hash drift, schema validity, protocol invalidation, malformed and multichannel WAVs, resampling, exact trimming, fades, LUFS/peak gain, deterministic dither, raw preservation, statistics/RTF, lock contention and ownership, failure cleanup, safe stale reporting, and one-/two-slot capacity.
