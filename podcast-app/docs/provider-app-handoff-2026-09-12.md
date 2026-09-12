# Installed provider HTP app — 2026-09-12

## Current app

The provider pipeline is installed. The library contains **Provider HTP 0912t112924z**, a Ready210.184-second episode made from a labelled copy of the authentic487-word chapter. Original user podcasts, sources, revisions, chat history, playback and exports were not overwritten.

Normal drafts now use provider sentence-segment admission rather than the old230-character whole-chapter limit. Long individual sentences that exceed the320-position processed-segment capability are still rejected before lock, without forced splitting or truncation. Native duration must fit L512 during rendering; input admission is not a universal success guarantee.

- App: `podcast-app/.local/provider-integration/candidate-04/app.apk`
- **App SHA256:** `04d9293b9a128730bac7a4a12a469b74ba367a4936b251cfa6ca4e253c3aef7f`
- Test: `podcast-app/.local/provider-integration/candidate-04/test.apk`
- Test SHA256: `2dd4e0d89a38ec763dfd50ef101496c4f56e4f7db2cfaf1fa935fed6616d3184`
- Source fix: `fda7e706`; candidate SHA `0a97e6a70c9a2e19eb6c41b79768a9cd257438e36da1a365e9fee3e5ecc7838a`.
- Provider pack: `supertonic-3-provider`, manifest `423429c6642da131ac62511e3b233f1a121b97975aa5b6e9aa755bb13a927670`,13 data files/212,921,074B.

The structured chat-edit and saved-draft recovery fixes remain. Gemma settings are unchanged. Existing short/experimental model packs and the accepted short-flow sample/export remain preserved.

## What is integrated

The full pinned supertonic-py1.3.1 recipe: raw paragraph/sentence grouping toward300 Unicode codepoints, followed by global Unicode14 NFKD/provider normalization and language tags; English/M1,8steps,speed1.05; each segment's own HTP duration/nativeL and continuous NumPy-compatible Gaussian stream; full nativeL×3072 waveform and0.3s gaps only between segments. No CPU neural fallback, forced duration, extra word splitting or text rewriting.

Four resident generic contexts replace the experiment's15 case-specific duration/text pairs. The new native-T boundary inputs include DP's learned sentence-token prefix. All other DP/text nodes/initializers are unchanged; accepted shared vector/vocoder context bytes are reused. The old vector strict numerical gate remains failed/non-bit-exact; accepted0037 listening quality is not relabelled as numerical parity or transferred to a new WAV.

The app reports completed segment progress and publishes complete chapters/episodes. No streaming playback is implemented or claimed. A nonce-bearing, hash-addressed AUDIO plan binds the exact revision, pack, frontend and segment inputs; legacy UUID jobs are never silently interpreted under new settings.

## Actual composed app proof

###1. Real synthesis, followed by a publication failure

`provider-app-20260912t112924z` used the normal lock UI, durable AUDIO dispatcher and foreground service. It completed **15 segments /165 reported native neural calls** and assembled the complete WAV. Native Android Gaussian generation matched the full2,160,000-sample frozen NumPy stream. The whole PCM payload was independently verified as the exact retained native segment payloads plus fourteen13,230-frame zero gaps.

Publication then failed because the existing atomic-commit helper requires the temporary file to share the destination directory. The provider engine had staged it in a scratch subdirectory. This was **after successful synthesis**, not an HTP/OOM or speech-generation failure. The FAILED synthesis job and all completed sources were preserved:

`27a86e7407164a1b1f0768c21ab6dc8de4e9574cf99a17f31d8628654b88a9b6`

###2. Same-directory fix and exact-byte recovery, with zero model calls

The fix copies a verified completed artifact to a unique sibling staging file, syncs/verifies it and uses the unchanged production atomic-commit helper. Regression tests exercise this actual path with synthetic bytes and preserve the original source.

`provider-app-recovery-20260912t115732z` installed the corrected APK, verified all retained segment hashes/PCM/gaps and the original plan/revision/pack, then queued a **distinct nonce/hash publication attempt**:

`77e469782cf737b600845519069c713cef62af4b549f2ae10134c5a753aaedcf`

It reached **FROZEN_READY** without constructing or invoking a model. The old FAILED job and42existing episode files remained unchanged; only the owned publication state, new recovery job/chapter-audio row and four publication files were added. All nine pre-existing user episodes and their newer edit history remain unchanged.

This is **composed synthesis + recovery evidence**, not a clean full neural replay on the corrected build. The recovery gets zero of the165 neural calls. Player availability follows the Ready state and validated artifact; no Play/export action or new streaming-playback proof is claimed.

## Exact published audio

- SHA256: **`2194bce66f8abd05bdf10fefc5cf4aaef49cac647992f637db319b7d14be532a`**
-18,538,292B;9,269,124frames; mono44.1kHz PCM16; **210.184217687s**.
- Published bytes are identical to the completed synthesis WAV—no regeneration, repair, stretching or resampling.
- App path: `e22a61c9-ec57-46f1-a700-83d55ef88e08/final/77e469782cf737b600845519069c713cef62af4b549f2ae10134c5a753aaedcf/episode.wav`.
- Private host copy: `podcast-app/.local/provider-integration/phone/provider-app-recovery-20260912t115732z/private-extracted-02/files/episodes/` followed by the app path above.
- **Listening status: not_reviewed** until Moritz accepts this exact new hash. No agent-initiated playback.

## Safety, tests and qualifications

-199 JVM tests pass; one unrelated optional long-TTS fixture is recorded skipped. Seven controller/source checks pass. Debug/test APKs and release Kotlin compile; no new full release-APK assembly claim.
- Full phone.lock, fresh identities and coherent user-job/data checks covered all device actions. The neural run passed the unchanged3.5GiB/<42°C gate; the recovery used an explicitly non-neural copy/UI budget. No third-party app had to be closed. No data clear, reboot, global swap change or unrelated process termination.
- Recovery cleanup errors[], exact app/generation/test PIDs absent, controls absent and phone lock released. Prior hash-bound files are intact.
- Reported neural-process lifetime RSS337,124KiB is not total DSP/device memory. No warm-median/performance-speedup claim or independent hardware cycle count is made.
- Nik was unavailable; no independent-review verdict or substitute reviewer is claimed. All raw user text, model/audio outputs, DB/WAL, inventories and logs remain private/hash-bound. All first failures are retained, including regex preflight, configured-memory stop, symbol-stripping freeze mismatch, publication failure and disconnected-device recovery preflight.
- No push/history rewrite. [Integration design](provider-htp-integration.md) · [Memory assessment](provider-memory-assessment.md) · [Prior chat-edit handoff](chat-edit-repair-handoff-2026-09-11.md).
