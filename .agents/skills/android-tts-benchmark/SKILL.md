---
name: android-tts-benchmark
description: Run, complete, review, or publish Android text-to-speech benchmarks in this repository. Use this skill whenever an agent creates a TTS experiment, measures CPU/QNN/HTP latency or RTF, generates a listening WAV, compares routes, refreshes a historical result, or hands evidence to the Android benchmark dashboard—even if the request only says to benchmark a model, run it on the phone, collect audio, or update experiment results.
---

# Android TTS benchmark

Produce comparable, reproducible full end-to-end Android TTS evidence. Keep technical execution, audio structure, numerical comparison, and Moritz's listening verdict separate.

## Start from the repository contract

Read these before designing or running a benchmark:

- `protocols/android-tts-benchmark/README.md`
- `protocols/android-tts-benchmark/contract.json`
- `protocols/android-tts-benchmark/transcript.txt`

Treat `transcript.txt` as exact bytes: 230 bytes, no trailing newline, SHA-256 `350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f`.

Use that exact transcript for every new comparable route. Do not change punctuation, turn `...` into `…`, add a newline, or substitute a model-specific demo sentence. Record both input bytes/hash and effective frontend/tokenizer output. If a model contract cannot use it, report the route as noncanonical with the exact blocker and keep it out of matched comparisons until a bounded specialization is available.

Historical records are immutable evidence. Add provenance-tracked refreshes rather than rewriting old metrics or pretending an old noncanonical route was matched.

## Freeze the route before measurement

Record:

- model repository, revision, files, hashes, license/provenance, precision and transformations;
- Android device identity, SoC/ABI, OS, runtime/build and provider versions;
- graph/session inventory and which work remains application CPU orchestration;
- tokenizer IDs or other frontend output;
- voice/reference/state, seed, temperature and decoding parameters;
- threads, affinity, graph optimization, cache/state shape and reset policy;
- exact output and stop/EOS contract.

A transformed fixed-shape graph is a derivative route. Name it separately from the original dynamic route.

## Measure setup, first and warm correctly

Reuse the same created sessions within a benchmark process:

1. Measure session/model setup separately.
2. Run and time one unprofiled first complete generation after setup.
3. Fully reset recurrent caches, decoder state, RNG/noise and orchestration state.
4. Run at least five additional timed warm generations in those same sessions.
5. Validate the intended complete utterance after every iteration.

For every timed iteration preserve:

- generation seconds;
- actual emitted audio duration;
- `RTF = generation seconds / actual emitted audio seconds`;
- EOS/stop position or frame count;
- structural output status and, when retained, WAV hash.

Report the warm median from per-run warm RTF values. Never call a single run, a first post-setup run, or an instrumented proof run a warm median. Keep profiled physical-proof latency separate from unprofiled performance latency.

If output duration changes across routes or runs, disclose it prominently. Faster incomplete speech is not a speedup.

## Record resource semantics

Report memory with the measurement type and lifecycle, such as process VmHWM, peak RSS or PSS. Do not compare unlike memory measures without labeling them.

For physical Android runs capture thermal status and relevant temperatures before/after, power/USB/battery context, and any CPU orchestration or thread settings that affect interpretation.

## Prove accelerated execution fail-closed

For a QNN/HTP claim:

- disable CPU fallback;
- require complete intended neural graph assignment;
- invoke every required session;
- collect provider events and show zero CPU neural events;
- collect matching physical DSP RPC, accelerator, cycle and HVX evidence;
- distinguish host QNN eligibility/simulation from physical phone execution.

Label partial assignment as mixed. Tokenization, cache copying, EOS scan and WAV encoding may remain disclosed application CPU work; do not call them neural CPU fallback.

## Produce listening evidence

Retain a valid PCM WAV with sample rate/channels/encoding, duration, finite/peak/clipping checks and SHA-256. Create a simple listening page when review is needed.

Only Moritz can set `accepted` or `rejected`, and only for the exact route/sample hash he heard. Use `not_reviewed` until then. Numerical correlation, SNR, EOS agreement and structural validity are descriptive evidence, not a listening verdict. Do not inherit a verdict across CPU/HTP, text, voice, model or changed-output hashes unless the WAV bytes are identical.

## Complete the evidence package

A new measurable full end-to-end route is not benchmark-complete while an existing dashboard field is avoidably missing. At minimum provide:

- canonical transcript provenance;
- setup, first and at least five warm runs;
- warm-median RTF using actual durations;
- memory semantics;
- runtime/provider/thread/device provenance;
- structural WAV evidence and exact listening status;
- acceleration proof when claimed;
- null plus explicit reason for genuinely unavailable values.

Validate scripts, JSON, WAV headers/hashes, cleanup and scoped commits. For phone work follow the repository's exact device identity, `phone.lock`, unique staging, evidence pullback and cleanup requirements.

Hand only committed evidence to the dashboard owner. The dashboard remains exhaustive internally but should show only appropriate full end-to-end routes in its compact table. Preserve proof-run, first-run and warm values as distinct source fields even when the UI chooses one headline RTF.
