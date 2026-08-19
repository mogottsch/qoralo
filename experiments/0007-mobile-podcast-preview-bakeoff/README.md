# Mobile podcast preview bake-off

This experiment contains host listening evidence for VibeVoice Realtime 0.5B, Pocket TTS, Kokoro 82M, Supertonic 3, Inflect Nano v1, and Kitten TTS Mini 80M v0.8. It does not establish Android feasibility. Moritz's recorded review ranked only the historical Kokoro, Pocket, and VibeVoice Realtime samples; a relative ranking is not an acceptance of any sample's usability or product quality.

The completed campaign plan is retained at [`planning/campaign-plan.md`](planning/campaign-plan.md).

## Active listening policy

The active six-candidate bake-off uses each model's natural-duration output. There is no 15-second gate and no normalization. The page reports actual duration and native sample rate, starts with neutral Candidate A–F labels, and fetches model identities only after a per-card or reveal-all action. Historical normalized artifacts remain evidence but are noncanonical and are not loaded by the active page.

## Historical frozen protocol v1/v2

The exact 226 UTF-8 bytes in `protocol/transcript.txt` (no trailing newline) are the only accepted input:

> Welcome to our small studio, where curious minds unpack one surprising idea at a time. Today, we explore why familiar voices build trust, how thoughtful pauses shape meaning, and what makes a conversation feel genuinely alive.

Protocol v2 is normative after the parent-owned punctuation revision requested by Pocket TTS. It retains 36 words and has transcript SHA-256 `350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f`. `protocol/preview-protocol-v2.json` is normative; all v1 preview acceptances are invalidated and Tasks 6–8 must regenerate. Results must embed the four fields returned by `tools/protocol.py:protocol_reference`; validation compares all four and fails closed.

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

Timing, process-tree RSS, first-output, audible-output, RTF, hashes, and audio statistic definitions are frozen in the manifest. `tools/generation_metrics.py` implements the shared monotonic 20 ms recursive process-tree measurement method, including pre-load baseline/peak semantics, raw-duration RTF, 10 ms/-50 dBFS audible detection, process-race reporting, and null-plus-reason unavailable timings. `schemas/preview-result.schema.json` is the candidate result contract. Artifact paths in committed JSON are references only; media remains ignored.

## Resource controls

`protocol/model-resource-policy-v1.json` starts fail-safe: every smoke load, RSS preflight, preview generation, VibeVoice capture, export, and protocol revision is mutually exclusive. There are no independently acquired locks or slots. `ResourceGrant` takes one administrative `flock`, examines every active grant, and creates one logical grant as a single transaction under `${PREVIEW_LOCK_ROOT:-/tmp/mobile-podcast-preview-gate}`. Its `owner.json` records owner/task/kind, hostname plus boot ID, PID plus Linux process-start ticks, UTC creation time, and an unguessable token. The wrapper forwards termination signals and releases its grant in `finally`.

```bash
# New tracks use model-load for any load/smoke operation and full-generation
# for every default, failed attempt, speed retry, and fresh-process repeat.
# Historical kinds remain accepted but are exclusive in the same global gate.
tools/with-resources.sh --task task-6-attempt-0 --kind full-generation -- python generate.py
```

A schema-valid replacement policy may be installed in one administrative transaction only when no grant is active. The loader accepts exclusive policies only; the historical Pocket-plus-Kokoro sharing exception is retired, so all attempts, retries, and repeats are mutually exclusive.

The repeatable capacity-measurement entry point is:

```bash
experiments/0007-mobile-podcast-preview-bakeoff/tools/run-preflights.sh
```

It acquires one `preflight` grant around all three workers, runs them strictly in Realtime/Pocket/Kokoro order, and records process-tree cold-load, cold-inference, and warm-inference RSS plus host baselines, lazy artifact growth, and post-exit cleanup under ignored `artifacts/task-5/`; the reviewed measurement summary is committed at `results/generation-capacity.json`. Each worker performs two deliberately short inference calls; their samples are discarded in memory and can never become preview evidence. After releasing the preflight grant, the script obtains the administrative policy-update transaction (which requires no active grant) and atomically replaces `protocol/model-resource-policy-v1.json` with the exclusive policy. Final generation wrappers consume that installed default policy without an extra slot or lock.

A grant is never reclaimed because it is old. Inspection must match host name, boot ID, PID liveness, and process start ticks. Dead or reused PIDs with a complete matching host identity are reported `stale_proven` but still block acquisition. Remote, incomplete, unreadable, and partially created grants are `remote_or_unknown` or `stale_unverifiable` and fail closed. Only the parent, after setting `PREVIEW_PARENT_ORCHESTRATOR=1`, may explicitly run `resource_lock.py recover-stale`; even then the tool removes only `stale_proven` grants and requires manual investigation otherwise.

## Historical short-output and protocol-revision procedure

Silence padding, looping, and time stretching are prohibited. A worker whose raw output is short must first exhaust documented model speed controls. It then writes a request conforming to `schemas/protocol-revision-request.schema.json`; it does **not** edit the transcript or manifest and does not mark the candidate blocked yet.

Only the parent orchestrator may make the single shared punctuation revision. It sets `PREVIEW_PARENT_ORCHESTRATOR=1`, acquires `--kind protocol-revision`, stops or waits for active preview workers, writes the incremented manifest/transcript atomically, and cascade-resets preview tasks 6–8 plus publication/report tasks 16–18. All three preview results fail `validate_result_protocol` until regenerated. The unrelated VibeVoice 1.5B capture is not invalidated. A candidate is blocked only if documented speed controls and that shared revision both fail to produce at least 15 seconds.

## Private listening publication

`publication/bakeoff-manifest.json` is the checked-in reproducibility index for all six results. It records the common transcript, stock-voice provenance, source/model revisions, commands, native formats, actual durations, hashes, browser carriers, and historical protocol status. The active page publishes one natural-duration player per candidate and no normalized players.

Build and validate the private blind listening page with interactive identity reveal:

```bash
python experiments/0007-mobile-podcast-preview-bakeoff/publication/build_publication.py
python -m unittest discover -s experiments/0007-mobile-podcast-preview-bakeoff/publication/tests -v
```

The build copies ignored browser-playable WAV carriers directly to ignored `artifacts/publication-build/`, checks hashes, validates cross-file invariants, and fails if media or artifact paths are staged. Model identities are absent from initial HTML and embedded page JSON; `bakeoff-manifest.json` is fetched only after an explicit reveal action. The recorded historical order is Kokoro, Pocket, then Realtime. This order states preference among those three exact host previews only; no explicit quality-acceptance verdict was recorded. Supertonic, Inflect, and Kitten were not reviewed, so their listening quality is unknown. No conversion or Android follow-up has started from this campaign.

## Tests

```bash
python -m pytest experiments/0007-mobile-podcast-preview-bakeoff/tests -q
python -m unittest discover -s experiments/0007-mobile-podcast-preview-bakeoff/publication/tests -v
```

Tests cover transcript/hash drift, schema validity, protocol invalidation, malformed and multichannel WAVs, resampling, exact trimming, fades, LUFS/peak gain, deterministic dither, raw preservation, statistics/RTF, lock contention and ownership, failure cleanup, safe stale reporting, one-/two-slot capacity, publication consistency, privacy, blind labels, interactive per-card/reveal-all identity disclosure, responsive controls, and task dependency edges.
