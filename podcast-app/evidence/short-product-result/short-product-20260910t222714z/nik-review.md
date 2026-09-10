# Nik — short production flow, first chapter response rejected

**Valid first-model-phase evidence; production E2E FAILED before draft commit.** This attempt is consumed and must not be replayed by a queued EXECUTE message. No second chapter, agent edit, lock, TTS or WAV occurred.

Exact candidate9c54da04…23b9 installed app4e438b62…af8c8/test56be356f…f8739. Private run archive839,680 bytes, SHA256 `c3d50ca680ac20ae484849cc3b979c601b8a33841e6f3cee9655962996383d36`. Driver PID20282; normal production generation PID20433; owned episode `e4279db8-d281-4657-867e-545491f6afc5` and SCRIPT job934e0e22-d792-4bce-ae51-0ff0f9d538db.

## What worked and what failed

The corrected real Library action worked. The UI created one owned episode, pasted/persisted the fixed source and instructions with reviewON, and normal repository/dispatcher/GenerationService execution began. Saved Home/reopen evidence identifies the same generation process without force-stop/task clear. The model observer records three synchronous returns at normal limits1200/1200/4096, context8192/topK1/thinkingfalse: source_notes, outline, first chapter. Their raw hashes match returned receipts; service finally records3 logical sends/25.429s.

Request3 explicitly contains `requestedChapterId:"chapter-1"` and a correct two-item outline with chapter-1/chapter-2. The chapter system prompt uses the generic schema placeholder `"id":"requested id"` while the preserved episode instructions request two chapters and an episode title.

Actual raw response SHA256 `4491ff363c66fed4765e060654112ccbfe9a33f7ebf4cbc957062dda0a3b7206` returns:

- id: `short plumbing e4279db8` — not chapter-1;
- episode-title-like title;
- one text containing both `Chapter 1` and `Chapter 2` mini narrations.

The fenced JSON was parseable by the existing production extractor. The failure is not a JSON-fence/parser, word-count, model-runtime, capacity or TTS error. GenerationCoordinator correctly rejected `generated.id != planned.id` before building/committing the complete draft. Do not relabel this response or extract its fragments to fabricate a successful requested chapter.

## Preservation and cleanup

The two pre-existing episodes, source, FAILED job and existing file remain unchanged. Exactly one new owned episode/source/FAILED job and one source artifact are retained; no revisions/chapters/messages/audio/playback rows were added. Host cleanup reports no errors/settings errors, all three app/test/generation PIDs absent and the control absent. No listening page/sample is applicable.

No new ADB, model call, UI replay or data mutation by Nik. This establishes part of the normal UI→disk-state→generation path, not a complete source-to-audio product pass or direct model throughput/profiling proof.

## Smallest source-backed follow-up

Clarify the normal single-chapter task boundary: generate only the requested chapter; copy its exact quoted requestedChapterId into the output id and use its planned title; episode-wide count/title instructions apply to planning, while other outline entries are context, not requested output. A concrete escaped expected-ID/schema example is preferable to the ambiguous placeholder. Preserve source/outline and strict ID checks, limits, route/sampler and parser behavior. No automatic ID repair, pruning, truncation or extra model retry.

A new source/build/candidate review and separately released fresh short flow are required. The previous failed episode/artifacts remain; next preflight must bind the now-observed4e438/56be installed tuple and preserve the increased existing-state baseline. This recommendation does not authorize execution itself.
