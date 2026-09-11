# Nik — real AUDIO/Player continuation, SAF UI stop

**PASS for the normal AUDIO/assembly and silent Player continuation; SAF export is incomplete.** The released continuation is consumed. Do not rerender or repeat LLM calls to fix the export helper. This is a multi-stage SHORT production workflow, not a single fresh pass or full1–2minute/long-speech readiness.

Exact candidatebb8c169c…4e622b installed app95103b2c…29fe969/test35faf3a6…92a3625. Existing real episodeba099f63-74da-43c5-96a1-27eb84251da4 retained revisionf48e7ea3-62cf-4afc-9b17-2cc6659c6e5a/contentc1c9…c2b5. Driver PID8749; production generation PID8839. One new AUDIO job350094cb-e393-439d-b742-660bead68d54 completed in29,887ms; zero new Gemma sends. No model, phone or playback call by Nik.

Run archive SHAe21ff32aa78f386f5ae09aec01df6208906e4025c5a622ff8815c63f8b7509a6; owned-artifact archive SHA6ab2d651897d7008f3f77da3be7461a43776a14ad4fbc5c36673106bc3312327.

## Real production audio and exact artifacts

Normal UI cancel-lock/confirm led to the ordinary repository/dispatcher/GenerationService AUDIO path and FROZEN_READY. Saved state and read-only comparison bind the same locked revision/hash to the one completed audio job. Original source/both script revisions remain intact; no imported WAV, seeded draft or new LLM generation was used.

All WAVs independently parse as44,100Hz monoPCM16:

| Artifact | Frames | Duration | SHA256 |
|---|---:|---:|---|
|chapter-000.wav|433420|9.8281179138s|22fdd462f7287116f5a73c9f4ab6f757e5d6bdf1518babc5ae3f5d0c7e2d1942|
|chapter-001.wav|464772|10.5390476190s|03cf36fbc73fe439e058c9d3c235e9cb374473e19176823b5a2ec4f6beff3dba|
|episode.wav|929062|21.0671655329s|3b631cc55da41f4e87ae3f251204c8d162c377bdf38092b41da0017e8baa0a44|

The1,858,168-byte master PCM is exactly first chapter +30,870 zero frames(700ms) +second chapter. Timeline SHAfa7cce7b60d42f61fc1595bcd9979927e27b8d4b1e70f0e4ca86276024060891 matches, total frames and both frozen chapter IDs/start/end frames agree; chapter2 begins at464290 frames/10528ms integer UI boundary.

Profiling is unavailable by design. The source-defined two-render route and actual produced chapter artifacts are not fabricated per-graph ORT/QNN/RPC counters. No listening/coverage verdict is inferred from WAV validity. All three exact WAVs remain not_reviewed; no audible autoplay.

## Player evidence

The bound test reached and recorded successful assertions for initial paused state, app-only volume0 before playback, actual isPlaying/clock advancement, pause, next-chapter boundary, speed1.25, chapter2 frozen transcript, configuration recreation and a fresh Activity/ViewModel opened from Library. It checked new player object identity, restored paused/volume0/speed/position/transcript. Source/UI/records support this narrow silent-player result; no global audio-focus/noisy-device/TalkBack claim is added.

No previous QNN graph-execute/contextFree failure or cDSP crash pattern was found for this run in the collected relevant log. That is not a universal DSP-health guarantee.

## Exact remaining SAF failure

The test threw NoSuchElementException in saveThroughLocalDocumentsUi before export completion. Saved private UI window9470 shows the Google DocumentsUI root drawer open, Downloads selected, current Downloads breadcrumb/header and the unchanged suggested episode-title filename. Thus filename replacement/Save was not reached. No export-before-write or export callback receipt exists.

The helper incorrectly filters the Downloads label by self/immediate-parent clickable status, even though its click routine can walk higher ancestors. The matching-predicate failure and still-default filename localize the stop to that root selection stage. This is not an audio/write failure and not proof that a file was exported.

Smallest correction direction: select android:id/title Downloads specifically under roots_list and use its nearest actual CLICK action ancestor bounded by that list; alternatively avoid reopening roots when a verified local Downloads destination is already current. No guessed coordinates/cloud selection, adb-copy masquerading as export or model replay. Reuse the existing immutable Ready master in a separately reviewed EXPORT-only test/controller/contract,0LLM/0TTS/0newjobs, preserving all app data except explicitly scoped playback persistence and the new local SAF document. Existing pre-write local-authority/unique-empty-filename protection remains essential.

Private drawer screenshot/tree contain unrelated provider/account information and stay private; local review copies have restrictive permissions. No such content is copied into this report.

## Preservation and handback

Independent saved-row and captured-file comparison passes: other rows unchanged, only the explicitly allowed owned lock/audio/playback transitions, one new AUDIO job/two audio rows/one playback row, and four new audio/timeline files. All eight prior files are byte-identical. Do not read the coarse per-table episodes count as proof that the intentionally transitioned owned row stayed byte-identical.

Host cleanup has no errors/settings errors; all app/test/generation PIDs absent and control absent. Raw prior5-return/word-target failure, this partial continuation and all actual WAVs remain retained. Export and any final installed-test identity require their next separate evidence; the AUDIO/Player result need not be repeated.
