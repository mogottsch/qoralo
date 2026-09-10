# Nik — five-return short workflow, rename assertion and WAL-reader findings

The79945c8d…171c7 attempt is consumed. It reached real normal SCRIPT completion with two distinct chapter IDs and four returns, then one agent return and a persisted new revision. It failed the exact requested-rename assertion BEFORE lock/TTS; no WAV or product E2E pass exists. No replay was performed by Nik.

Owned episode:54f07f5a-76d7-4303-8ce0-b6b3a1b3bf8e. SCRIPT jobc4735e83-8f38-4e9d-9319-d45e5e1881c3 records4 sends; AGENT_EDIT jobc0da6aa0-8d49-4add-aa43-68e09ed26e8a records1. Main app installed eb22ac…49a62 with test56be…f8739. Run archive SHA01ef2c4ec014327c20f7232623da7af420c73ca9f41e4be6ce7d9cefab187879; owned-artifact archive SHAea6b36b0cccbeead528b38b2b10fb18f5308b7cbad14a0fa1a18121c39488e2e.

## Agent noncompliance, not mapping failure

The exact user instruction asks to rename the episode to `Short plumbing 54f07f5a checked`. The raw agent response c28ebe4a…c0fe7 retains root.title `Short plumbing 54f07f5a`; its summary falsely claims renaming to that same old title. Both chapter texts were rewritten and IDs retained, so there was a real model revision, but not fulfillment of the requested rename.

Owned persisted script5023bf40-dafb-4571-9c4f-2d2d178858a3.json matches the raw new chapter contents and old root.title. Original script70e6bab6-af8c-466b-a3ee-41a299c42011.json remains unchanged. Production parsing/persistence therefore did not lose a suffix; the driver assertion is correct and must not be weakened or satisfied by host title application.

Smallest source-backed correction is the edit-system boundary: stored base revision is immutable, but fields in the returned NEW revision are editable; input root.title is the current EPISODE title, distinct from chapter titles; the latest instruction governs requested new values and summary must reflect actual differences. Preserve payload/parser/ID schema/persistence, model/sampler/limits and raw output. No NL rename extractor or additional inference is implied by this report.

## WAL format diagnosis and saved row comparison

Original host cleanup reported a preservation error `WAL page bound`; it must remain recorded, not overwritten as if collection had succeeded. Both captured post DB/WAL/SHM sets are byte-identical. Header/checksum-only inspection found105 physical WAL frames, duplicated valid WAL-index headers with mxFrame81/nPage35,4096-byte pages and matching current salts. All81 live frames validate their page bounds/salt/checksum chain; frame81 is a35-page commit and its checksum matches the WAL index. All24 physical tail frames have noncurrent-generation salts. Frame82's cleared page/salt fields trigger the old all-physical-frames reader.

This is consistent with a retained/recycled WAL tail, not established corruption. Official SQLite walformat documentation defines mxFrame as last valid commit and notes SHM is volatile cache data. Consequently the reader correction requires both valid duplicate index metadata AND the fully checked committed prefix/final checksum, with exclusively noncurrent tail salts; it does not trust SHM alone, ignore arbitrary corruption or repair/truncate originals.

The narrowly corrected guard file854a67ae…5896/closure3e807ad5…b3116 passed26 independent guard/WAL regressions. Programmatic comparison in local read-only reconstructed views now confirms SAVED ROW preservation: previous3 episodes,2 sources and2 FAILED jobs unchanged; only the owned episode/source,2 revisions,4 chapters,2 messages and2 COMPLETE jobs added, no active jobs or audio/playback rows. Existing-row content was not exposed in the report. Raw snapshot hashes remained unchanged.

## Remaining file-evidence boundary

The original controller called DB validation BEFORE post-file inventory; the WAL exception prevented `.private-user-files/after.stdout` from being collected. Therefore SAVED FILE preservation cannot be retroactively claimed from that run. The new offline row-pass is additive and does not replace missing file evidence.

Pi subsequently authorized a separate bounded READ-ONLY CURRENT inventory by Janek. Its result, if obtained, must retain its current timestamp/input identities and compare the old before-file hashes without pretending it was captured at original cleanup. Future host collection should retain post-file evidence independently of row-parser success.

Original host PID/settings/control cleanup succeeded. That is separate from the original preservation-error record, the later saved-row verification and the pending/current file observation. No device, model, original DB/WAL mutation or data repair by Nik; the historical attempt remains intact. Final new candidate/host fix and any later fresh flow still require their exact scoped review/release.
