# Final usable SHORT app handoff

**Historical short-flow/audio handoff.** The current installed build is now `04d9293b…`, retaining structured chat edits and adding the provider HTP sentence pipeline: see [the current provider handoff](provider-app-handoff-2026-09-12.md). The `95103…` artifact and all results below remain preserved unchanged as the earlier technical-chain nomination.

**Phone/model work is stopped. The real multi-stage short workflow reaches local SAF export, with Nik's final saved audit accepted. Moritz has accepted the exact21.067s short master.** Long1–2minute chapter support remains unresolved; this feedback does not approve the long sample or other hashes.

## What to open

The phone already has **VibeVoice** installed. In Library, the Ready episode is **“Short plumbing ba099f63 checked”**. It opens paused; the persisted position is10.528s at1.25×. Test-only app muting was not a system-volume change and is not a permanent user setting.

Use this exact frozen APK if a later, separately authorized installation is needed—not an arbitrary Gradle output:

`podcast-app/.local/short-product-ready/export-only-03/app.apk`

- App SHA256: **`95103b2cc00676e96fe4a2335d489863fcc609f48d5096d20bee2c69529fe969`**.
- Package: `dev.vibevoice.podcast.internal`; version `0.1.0-short-plumbing`.
- Current test APK: `podcast-app/.local/short-product-ready/export-only-03/test.apk`.
- Test SHA256: `07a3177a25a720936a42a3d8de6f54391ac2ec5e1b8d18db99bbb7e0e58b56e3`.
- Final export candidate SHA256: `e06da0329075ee8206c1f90733b09397cbdf543939988647ce851dc9f1ac94b7`.

The app was built from `ca248e61df4cc21ec1f23d370b39aa609bff3888` and reused byte-for-byte for export. Final test/controller source: `335dde8c097bc77d629a17a33211febca90c355b`. Main production tree `39c3b2a99d0c148d48ca8678aff98407a780e4e6` is unchanged across the audio/export continuations. Native9 bytes are unchanged; no model/native rebuild or app reinstall was performed for export.

## What was actually completed

1. **`short-product-20260910t231153z`:** real Main UI→fixed source/instructions/review ON→normal dispatcher/isolated service→four Gemma SCRIPT requests plus one agent edit. Exact requested rename and immutable revision changes passed. The old debug test then stopped at a word-target assertion.
2. **`short-product-cont-20260910t234257z`:** the actual persisted revision was opened through Library/Draft, lock cancelled once and confirmed, then one normal AUDIO job rendered two complete brief chapters and assembled the master/timeline. Zero new Gemma calls. Actual silent app-player playback, chapter boundary, transcript/speed and fresh Activity/ViewModel persistence passed. Export stopped at a test helper issue.
3. **`short-product-export-20260911t002719z`:** the existing Ready episode/master was exported through real Player→ACTION_CREATE_DOCUMENT→Downloads, with pre-write local/empty/unique checks and exact readback hash. Zero LLM/TTS/job/Play/Seek calls. The test-only synchronization fix reused the app and all audio.

This is a **multi-stage real product flow**, not seeded/imported content or a single clean invocation. Original failures remain intact. The final chapters are26/29words and146/159normalized codepoints: the20–25word instruction target was missed, but the hard190codepoint short-test limit was satisfied without text editing.

## Audio and export

[Retained master WAV](../evidence/short-product-result/short-product-cont-20260910t234257z/episode/final/350094cb-e393-439d-b742-660bead68d54/episode.wav): **21.0671655329s**,44.1kHz monoPCM16,929,062frames,1,858,168B.

SHA256 **`3b631cc55da41f4e87ae3f251204c8d162c377bdf38092b41da0017e8baa0a44`**. Chapter durations are9.8281s and10.5390s, separated by exactly700ms of zero PCM. Timeline and master/part PCM hashes were checked independently.

The real new Downloads export is **`podcast-short-product-export-20260911t002719z.wav`**, URI `content://com.android.providers.downloads.documents/document/1364`, with the same bytes/hash. [Exact export receipts](../evidence/short-product-result/short-product-export-20260911t002719z/).

After the short-master listening-page link, Moritz said: **“the samples sound good, but please open the handoff”** (2026-09-11, relayed by Pi). The [additive listening record](../evidence/short-product-result/short-product-cont-20260910t234257z/listening-review-2026-09-11.json) marks only master hash3b631…a0a44 **accepted**. No separate chapter-file verdict or long29.8s/full-coverage approval is inferred. Kate's page remains without autoplay; the earlier accepted canonical sample is a different WAV. Original collection-time `not_reviewed` records remain unchanged.

## Route, retained data and limits

This frozen APK explicitly selects **Gemma4 E2B/LiteRT GPU** and the proven **Supertonic3 external-context QNN/HTP T239/L238** pack (`-Ppodcast.shortProductE2e=true`). Gemma manifest `9fb627ef9a4eb0ed49056c32bc16f2846e6edf68dc8d854b02af90e24e4e96cd`; short Supertonic manifest `dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d`. Both data packs remain installed outside the APK. No CPU fallback/chunks/stretching/automatic inference retry.

The separate long experimental properties/pack remain preserved, but are **not this installed route**. The227word long input produced29.8s with uncertain/poor ASR coverage; the official FP32 duration predictor also produced about29.81s without extra padding. No valid long-duration remedy was established under the unchanged model/speed/full-chapter contract.

Five episodes remain: the original user data and all owned partial/test episodes were not cleared. The final continuation changed only the named owned lock/audio/playback state; the final export changed no durable values or episode files at all. PID/settings/control/lock handback passed. Full DB/WAL, inventories, conditions, global logs and private provider UI remain local/hash-bound; historical missing post-file evidence is separately documented, never retrofilled.

ORT/QNN profiles were off for the short product flow, so direct per-graph counters are unavailable by design. This is not a warm benchmark, universal Android/TalkBack certification, numerical-fidelity proof or long-chapter/other-hash listening acceptance. All pushes remain held.
