# Exact-WAV local listening handoff

**No WAV means no listening page or tab.** Preflight stops and failures belong in one status-board line, optionally linking safe evidence. Do not create/open placeholder or failure listening pages.

When Janek has a stable retained WAV, hand off the run ID, exact source path/SHA-256, format/frames/duration, and evidence/cleanup status. A commit may follow; a campaign is not a prerequisite. Do not infer success from a partial artifact.

For an actual sample:

```sh
python3 scripts/prepare_listening_page.py \
  --run-id '<actual-distinct-run-id>' \
  --wav '/absolute/path/to/actual.wav' \
  --sha256 '<expected-full-sha256>' \
  --title 'Long narration listening sample' \
  --note '<short safe run/evidence status, including any limitations>' \
  --open
```

The helper verifies the copied bytes against the expected SHA and checks nonempty PCM format, frame count and payload completeness. It creates a **new** private-cache directory at `~/.cache/vibevoice-listening/<run-id>/` containing `sample.wav`, `index.html` and `listening-page.json`. It never overwrites an existing sample/page or changes the source WAV. No synthesis, ADB, server, forced duration, autoplay or auto-refresh occurs. `--open` uses `xdg-open` only after successful preparation.

Verify the actual page and audio metadata load, report the file URL promptly, and keep the original accepted short player untouched. The planned ~90 seconds is a natural-duration target, not a padding/truncation or acceptance gate. Structural WAV validation is not run success, speech quality, capacity, fidelity or campaign proof.

New samples start **not_reviewed**. Only Moritz can accept/reject the exact WAV hash. A later hash-bound verdict is a separate review update; do not rewrite original experiment records or invent playback timestamps. No external push while the privacy hold applies. Keep private logs/battery histories out of notes/receipts.

Tests use only small synthetic PCM fixtures, never offered as listening samples:

```sh
python3 -m unittest discover -s scripts/tests -p 'test_prepare_listening_page.py'
```
