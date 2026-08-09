# Pocket TTS 100M — pinned setup

This directory prepares Kyutai's official Pocket TTS implementation for the shared preview. It does **not** generate a preview or introduce another transcript. Task 7 must read the one frozen file at `../../protocol/transcript.txt`.

## Reproducible setup and smoke load

```bash
./setup.sh
./smoke_load.sh
```

`setup.sh` checks out source revision `d108410d23eef7e01db282f9442891162dbc3db6` and runs its committed `uv.lock` with `uv sync --frozen --no-dev` in the ignored model-local artifact root. It then applies the shared protocol's exact NumPy 2.5.1 pin: the upstream source explicitly warns that 2.4 produces wrong audio, while its current lock still selects 2.4.3 on Python 3.14 (and 2.2.6 on 3.10). Setup asserts 2.5.1 and fails closed. It never changes system Python. Source origin, clean tracked state, commit, protocol revision, dependency correction, and native sample rate fail closed.

`smoke_load.sh` is the only supported load entry point. It wraps the Python process with task 1's atomic `smoke-load` model-resource grant. Direct execution of `smoke_load.py` is refused. The passing evidence is ignored at `artifacts/setup/pocket-tts/smoke-load.json`; a failure is not a completion artifact.

## Official weights and access

The pinned English config references the gated `kyutai/pocket-tts` file at revision `39592ff23c9ef80098bb74895d104c26275fe2c9`. If the current Hugging Face identity has not accepted the additional conditions, official source falls back to the public, official `kyutai/pocket-tts-without-voice-cloning` model file at revision `d29db7978e464fb90cb3359ee0c69a273b9142cc`. This public fallback is sufficient for the required stock voice and is the smoke path recorded in `pins.json`; it does not require or enable cloning. The stock-state repository itself is pinned at `e041936c75475d350b405bc870bcf7c22da4e9e6`.

Both model repositories declare CC-BY-4.0. Source is MIT. The gated repository additionally presents prohibited-use conditions and form fields. This task does not accept those terms: if a later task requires arbitrary voice cloning, it must block for explicit user action rather than silently accepting them.

## Voice and native behavior

- **Selected voice:** `alba`, an official, precomputed English stock state. Kyutai documents its original reference as `kyutai/tts-voices/alba-mackenna/casual.wav`. We load only the published state; no personal audio is supplied and no voice cloning is performed.
- **Native output:** 24,000 Hz mono, returned by the Python API as a 1-D float32 PCM tensor. The model's acoustic frame rate is 12.5 Hz. Task 7 must preserve yielded native chunks before assembly and derivation.
- **Streaming and latency:** `generate_audio_stream` yields each decoded Mimi frame as soon as it is available. First-chunk latency is monotonic time from API invocation to the first yielded tensor, including silence, per the shared protocol. The README's upstream “~200 ms” is a project claim, not our measurement.
- **Determinism:** generation is stochastic (default English temperature `0.3`). Task 7 must call `torch.manual_seed(0)` immediately before generation and record the exact environment. Reproducibility is claimed only for the pinned dependency graph and same supported platform; a seed is not a cross-platform bit-exact guarantee.
- **Persistent voice state:** supported. `get_state_for_audio_prompt("alba")` produces a reusable KV/state dictionary. Generation's default `copy_state=True` preserves it, and multiple named states can be kept resident for later alternating-turn composition. The model instance itself is not thread-safe.

All normative pins are machine-readable in `pins.json`. Neither setup nor smoke copies the shared transcript, and no second transcript lives in this directory.

## Frozen-preview generation

```bash
./generate_preview.sh
```

This is the only supported preview entry point. It obtains one atomic `generation-pocket` grant for model load and generation, so the measured policy can overlap it only with one Kokoro generation and excludes Realtime, preflights, capture, and export. It refuses protocol/source drift and write-once output replacement. Native yielded tensors are preserved as float32 chunks and an exact concatenated float32 stream under ignored `artifacts/previews/pocket/raw/`; accepted runs derive the exact protocol WAV with the shared utility.

The protocol-v1 seed-0 `alba` run deterministically produced 324,480 samples (13.520 seconds), too short for the required 360,000-sample preview. Pocket's pinned Python API has no documented speed setting, and upstream lists adding silence in text as unsupported. The worker therefore did not pad, loop, time-stretch, or edit the parent-owned transcript. `results/pocket-preview.json` records the blocked measurement and `results/pocket-protocol-revision-request.json` requests the parent-owned punctuation transaction. No normalized WAV is claimed until the parent increments the protocol and resets all three preview tasks.
