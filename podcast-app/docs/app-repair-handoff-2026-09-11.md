# Earlier capacity-repair handoff — 2026-09-11

**Superseded installation nomination:** the current app is now `04d9293b…`, retaining structured chat edits and adding provider HTP synthesis. See [the current provider handoff](provider-app-handoff-2026-09-12.md). The50a367… capacity milestone and its original results below remain preserved.

## Installed build

**VibeVoice is updated.** Use the exact frozen build, not arbitrary Gradle output:

`podcast-app/.local/user-diagnostic-ready/capacity-01/app.apk`

- App SHA256: **`50a367b602d607a9a35d1836258c327b3c78fa9d9f6a835d7575139335937a47`**.
- Test APK: `podcast-app/.local/user-diagnostic-ready/capacity-01/test.apk`.
- Test SHA256: `8ed6c5e7958d87a677c9e98a0f86c764272a590837ec4b6f30a2c7d4d1f39e04`.
- App/test source: `59953d5`; frozen candidate SHA `ed9e02e7627b1bf35b229f3daded5f9c8c2504b5fec2d0c21881c9664efa839b`.
- Same short variant/model pins/native9 as before: Gemma4 E2B/LiteRT0.16.1 GPU and Supertonic3 QNN/HTP T239. No model/native rebuild or fallback.

## What was established and fixed

**Two real-input SCRIPT runs succeeded.** Each used a fresh normal-UI copy of a preserved failed user's source bytes/title/instructions, with review ON. They produced complete five- and four-chapter drafts, not the tiny E2E fixture. Both original failed episodes and all earlier data were preserved. The instructions did not constrain chapter count, word count or duration.

**The historical SCRIPT failures were not reproduced.** Fresh source IDs plus newly generated notes/outline changed the effective requests;5vs6 chapters is not attributed to GPU nondeterminism. The old underlying exception/raw response was never retained, so its cause remains unknown. These two passing cases are not general reliability, factual-quality or historical-root-fix proof.

The installed changes address concrete defects:

1. **Useful, private failure provenance.** Future errors retain bounded safe phase/type/cause details instead of only a wrapper. Opt-in exact-owned diagnostics can preserve request/system/config/raw-return/exception details in app-private storage. No raw prompt/response is added to UI/logcat or shared export.
2. **Source-notes contract guidance.** The prompt now states the existing nonempty≤2000 decoded-character requirement, with≤1600 guidance for margin and no minimum/padding. The hard validator and1200-token ceiling are unchanged; no output repair/truncation/retry. Host tests cover this alignment. The two successful phone drafts used the earlier prompt, so no new model-adherence claim is made.
3. **Early audio-capacity handling.** Both manual locking and review-OFF auto-lock check exact normalized text capacity. Over-capacity generation preserves a complete editable draft and does not enqueue AUDIO. Review explains the limit and disables locking; deliberate agent editing remains available. No full chapter or requested episode scope is shortened automatically.

## Actual capacity and remaining limitation

The selected T239 pack admits **230 normalized codepoints plus9 language-tag codepoints**. Shared Kotlin measurements:

- Five-chapter draft: **2199 /2786 /3070 /2902 /3158** normalized codepoints.
- Four-chapter draft: **3409 /2567 /2961 /2343**.

All exceed the selected voice input limit and even the experimental long pack's2039 normalized-codepoint limit. Passing a text limit would not prove waveform/duration capacity or speech coverage. The earlier227word long diagnostic's29.8s duration/coverage issue also remains unresolved. **Full-length chapter narration is still not ready; this build prevents an irreversible unsupported lock rather than pretending to fix the voice model.**

## Validation and preserved state

- **44/44 host JVM tests +7 Python checks:** exact manifest/text bounds and shared normalization, boundary/Unicode cases, both lock paths, full review-OFF draft retention, stale-revision recheck, notes-contract validation and privacy/cleanup controls.
- **Actual `capacity-ui-20260911t111704z`, independently accepted by Nik:** reused the genuine five-chapter draft; repository rejection checked under an always-rollback outer transaction, real warning/disabled Lock/available agent-editor verified. **Zero model calls, jobs, edits, playback or export.**
- All **8 episodes,7 sources,6 revisions,17 chapter rows,10 jobs**, remaining rows/catalog and **17 episode files** unchanged during the capacity check. Cleanup had no errors, exact app/generation/test PIDs were absent, controls absent and phone lock released.
- Review-OFF preservation and positive boundary locking are host-tested, not additional physical model runs. [Capacity design and evidence boundaries](audio-text-capacity.md).

The earlier Ready short episode/master/export remain unchanged. Moritz accepted that exact21.067s master (`3b631…a0a44`) in the additive `e7218cd` listening record; that does not accept the long sample or other hashes. [Earlier short-flow/audio handoff](final-short-app-handoff.md).

Raw user text, model outputs, DB/WAL, inventories and logs remain private/hash-bound. Original failures, all frozen APKs/packs and exports remain intact. The optional plaintext-v2 chapter prototype is parked and **not deployed**. No further app phone/model run is needed for these validated changes; all pushes/history rewrites remain held.
