# Profile-OFF whole request returned a WAV — 29.80s, speech review pending

**Run:** `tts-long-profile-off-20260910t205719z`. Service `tts_complete/finished`; one complete227-word narration was submitted and a valid WAV returned. **The roughly90s target was not met.** The whole-input submission and returned WAV do not establish that every word was spoken intelligibly or that this is an accepted long chapter.

## Exact usable artifact

[`device/long-library-01.wav`](device/long-library-01.wav)

- SHA256: **`bb61a552d5a631d05aee7aaa79695946f8a53aa01ebd4d82a9060bab95714d98`**.
- 2,628,128 bytes;1,314,042 frames;44,100Hz mono PCM16.
- **29.79687074829932 seconds**, measured from WAV frames/rate, not the prose target.
- Listening: **not_reviewed**. Moritz alone can accept/reject this exact hash. No audible autoplay overnight.
- PCM sanity: non-silent, normalized RMS0.052454, max absolute sample16,264, zero full-scale samples. These are structural/amplitude observations, not speech coverage or quality.

Kate received the stable local file/hash immediately, before commit or audit. Only this real WAV merits a listening page; failed/preflight attempts remain status-board lines.

## Bindings and actual installation

Observed app/test identities match candidate **`efdb831a8f987d4a32ef21d121f065ea26f40c9dfdd8f7f6f946b6ec3b484c7b`**:

- App `59e33847e9ff94f1ea8fdbd07d7881543bb90a80031a585cb6178be2c5e1842e`.
- Test `6d97d38d7c3acb3d65234f289fe53114e4aaa98fc32afd6356bb96eddc8aa49b`.
- Frozen APKs `.local/tts-profile-off-ready/cc7e772/{app,test}.apk`; source `cc7e772ca825f6f5e939071b4737ba8a7976504a`, effective app/src `8e83f6bb158b6b2f45323b7898a6591c7a619c42`.
- Contract `8d6b93557a2ac9d191b731735015bad6ce9d95c9b605861dc3c930cf9c82cd35`; caller `2a43becadc897a47c6c50424479e68fa996a05c0f70787be802ff6b2bf8b742d`; guard `5ca6be91be151acd2937b5e65871a40361f9bae99ae444880eae0e29b6f2c425`; unchanged privacy a62…bec3c.
- Same already staged pack `supertonic-3-t2048-l2048-parity/current`, manifest `116fda95a907f6dc35bfe7c2144fe2818ed438cc109c1faa3f95cafc2fc84066`; authenticated and reused, no push/overwrite/removal.

These diagnostic APKs were actually installed for this run. They are **not** the coherent normal production UI candidate and do not establish product E2E.

Actual raw/normalized text is retained, matching the same1327-byte raw SHA `f25655b54ad4e8d5e782dedf069867d6c201f1ea48327724527356d0f35aea37` and1324-codepoint normalized SHA `7add3140f7c8d871d0291e30ac1ca79546ad5fec9792ef78428e7eda9484c8b9`. Chapter ID/seed, M1/SID5,5steps,speed1, native9 and T2048/L2048/144 are unchanged. Token/mask/seed evidence is reconstructed from pinned source/indexer, **not captured native buffers**. No chunks, stretching, forced duration, fallback, Gemma or retry.

## Measurements and deliberately absent proof

- Four-context adapter load: **3832.259686ms**.
- First complete render: **23697.614053ms**, including normalization/native calls/WAV validation-publication; excluding verify/load/close.
- Recomputed first-request RTF: **0.7953054618781592**, using actual29.7968707483s audio. Not a warm median or a result using90s as denominator.
- Generation-process lifetime `VmHWM`: **418,016 kernel-kB/KiB**, sampled after render and close. Not PSS, model-only allocation, whole-device memory or DSP memory.

`profiling-policy.json` records `collectProfiles:false`. No profile directory was produced. ORT Node/Session records and QNN load/execute RPC/cycle/HVX/op profiles are **UNAVAILABLE_BY_DESIGN**. `observedPerComponentRuns` is null. Planned1/1/5/1 is not measured execution and must not be borrowed from another run. Runtime declarations, APK/library bindings and a WAV are not replacements for direct per-graph accelerator counters.

This successful return with profiling disabled supports a diagnostic difference from the failed profiled run, not a proven internal root cause, universal profiling fix, numerical fidelity or speech-completeness claim. The previous6006/cDSP user-PD crash/native teardown failure remains unchanged.

## Cleanup and retention

All three startup checkpoints used the known-terminal-history guard; active/unknown work still rejected. Separate setup receipt `../pre-run-20260910t205716z/` found all actual app/generation/test PIDs absent, so no force-stop was needed. No data clear, job deletion or model-pack removal occurred.

Host cleanup: errors[]/settingsErrors[], all three actual PIDs absent, packages retained, no transfer scratch created, settings readback matched and lock released. Close-stage completion and after-close process snapshot were captured; no6006/context-free/TLBMISS error was observed in the retained target-PID QNN/FastRPC subset. This is not an independent global DSP-health certification. No further phone/model action followed.

`retained-manifest.json` binds315 public files/7,725,774 bytes;10 complete condition/DB/global-logcat originals (3,505,578 bytes) remain private and hash-bound. The archive contains app-owned run evidence only. The identical convenience WAV stays local; the exact archive member is retained directly here. Separate setup:54 originals/3,543 bytes. Initial derived review-pending observations remain unchanged. [Nik's FINAL audit](nik-review.md) independently accepts bounded whole-input→valid-WAV operability, explicitly records the target miss/unknown speech coverage, and verifies exact identities, timings, mode and host handback. His unchanged report/audit are bound by `nik-review-retention.json`; no diagnostic replay or stronger quality/per-graph claim follows.

Normal-app integration/production lifecycle/playback/export remain separate work. The canonical short accepted sample is untouched. No pushes/external publication.
