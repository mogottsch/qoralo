# First short plumbing attempt: initial action-semantics stop, zero model calls

Run `short-product-20260910t22141789078483z` consumed the exact1f7a450…61700 slot. App8ffae458…3d851/test911897a3…69400 were installed and independently hashed by the driver. The15s initial Library lookup for text “New episode” timed out at testline113. This is **not a TTS/model failure or product E2E pass**.

The private screenshot shows the normal Library and visible New episode FAB; the same-window9435 accessibility tree lacks its name. Saved/local bytecode inspection identified Material3 1.3.1's animated FAB text `clearAndSetSemantics {}`; our Icon had a null description. No lockscreen/permission overlay or model wait was evident. The proposed small correction names the actual action and queries that semantic name; no coordinates, unmerged-text bypass, seeded state or timeout increase.

No episode, source, revision, message, job or audio was added; no control was armed. **Zero Gemma/TTS requests, no WAV or listening page.** Both existing episodes, the existing source and FAILED job, all prior user rows and the one existing episode file remain unchanged. Full DB/WAL, file inventory, conditions, global logcat and UI originals stay private.

Cleanup: errors[]/settingsErrors[], all actual app/generation/test PIDs absent, control absent without host removal, no scratch, packs/packages retained, lock released. Frozen installed paths are `.local/short-product-ready/attempt-02/{app,test}.apk`; full hashes are in `device/identity.json` and `host/candidate.json`. This replaces the previously installed59e diagnostic, not a new generation success.

`retained-manifest.json` binds340 public original/labelled files49,280B and19 local-only originals4,824,368B. Archive/UI/private files are deliberately not copied here. The run and frozen candidate remain unchanged; a corrected fresh flow needs its new exact app/test/controller binding and release. No push or automatic replay.
