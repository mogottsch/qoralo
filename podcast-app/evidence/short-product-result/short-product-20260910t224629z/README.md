# Five normal Gemma returns; requested rename failed before audio

Consumed candidate79945…171c7, installed app eb22ac17…49a62/test56be356f…f8739. Frozen paths: `.local/short-product-ready/attempt-04/{app,test}.apk`.

The actual normal UI/dispatcher/isolated service completed four SCRIPT requests and one separately loaded agent-edit request. The single-chapter prompt correction produced correct separate chapter-1/chapter-2 drafts. Owned episode `54f07f5a-76d7-4303-8ce0-b6b3a1b3bf8e` and its two immutable revisions were persisted.

The agent request explicitly asked for `Short plumbing 54f07f5a checked`. The returned and persisted root title remained `Short plumbing 54f07f5a`, though both chapter texts were rewritten. Its summary claimed a rename to that same old title. This is genuine instruction noncompliance, **not a lost suffix or field-mapping bug**. The exact rename assertion correctly stopped before lock/TTS. No WAV, playback, export or listening result. No host-applied title, assertion relaxation or automatic retry.

Exact agent raw return: `device/jobs/c0da6aa0-8d49-4add-aa43-68e09ed26e8a/request-1-raw.txt`, SHA `c28ebe4a5f218a74c7356256273353602a7d303a971a3ca0cbee66ef0f7c0fe7`. All five raw returns, requests and system instructions remain unchanged.

## Preservation: original gap and separate later checks

Original host cleanup has a **preservation error**: its all-physical-frames WAL reader rejected frame82 with `WAL page bound`. PID absence, settings and control absence passed; no device repair occurred. The original controller aborted DB validation before collecting its post-file inventory, so **there is no original after-file inventory**. This error/absence is not rewritten or called a clean original handback.

Saved metadata established81 valid/current-salt WAL frames ending in a35-page commit, corroborated by duplicated checksummed SHM headers/mxFrame81/final-frame checksum; the24 remaining allocated frames all carry noncurrent salts. A narrowly fenced host reader now validates the live prefix and rejects current-epoch tails or inconsistent metadata. It never edits/checkpoints/truncates original DB/WAL files.

`additive/offline-row-preservation.json` records a separate read-only comparison with that reader: the three pre-existing episodes, two sources and two FAILED jobs are unchanged; additions are only the owned draft/edit data, with zero active jobs. Full private rows are not included. The original archives remain byte-identical.

A separately authorized **CURRENT** read-only file observation at23:03:34–37UTC is retained in [`../current-files-20260910t230334z/`](../current-files-20260910t230334z/). Both pre-existing file hashes still match; the three additional files belong to this owned episode. It is current evidence, **not reconstructed original-time post-file proof**. No app launch/install/force-stop/data write/repair/model call occurred in that maintenance scope.

Manifest:388 public original/additive files635,281B;22 private originals10,066,936B. Full DB/WAL, inventories, conditions, global logcat, mixed private archive and UI remain local/hash-bound. Old failures/data stay intact. Next edit prompt only clarifies editable NEW fields versus immutable STORED base; model compliance remains unproven until separately tested. No push or long-chapter readiness claim.
