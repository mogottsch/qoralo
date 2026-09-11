# Real owned audio and Player passed; local export helper stopped

**Multi-stage REAL workflow, not a fresh single-pass run. Zero new Gemma/agent calls.** This continuation used the actual five-return draft/edit from `short-product-20260910t231153z`, owned episode `ba099f63-74da-43c5-96a1-27eb84251da4`, revision `f48e7ea3-62cf-4afc-9b17-2cc6659c6e5a`, content hash `c1c9d30a1d1264e5c212b53d53d5b014b1900c56b87945174fbd24f4aeb2c2b5`. No text was seeded, shortened, relabelled or imported as audio. The26/29word target miss remains reported; both146/159codepoint inputs are short-capacity-safe.

The real Library/Draft UI cancelled lock once, then irreversibly locked this revision. Normal AUDIO job `350094cb-e393-439d-b742-660bead68d54` completed, produced two whole-chapter WAVs and the normal master/timeline, and persisted FROZEN_READY. Whole-job elapsed29,887ms includes orchestration/verification/load/render/close/assembly; it is not a neural-only RTF or warm measurement.

## Actual audio — listening not_reviewed

- [Master](episode/final/350094cb-e393-439d-b742-660bead68d54/episode.wav): **21.0671655329s**,929,062frames,1,858,168B; SHA **`3b631cc55da41f4e87ae3f251204c8d162c377bdf38092b41da0017e8baa0a44`**.
- [Chapter1](episode/chapters/chapter-000.wav):9.8281179138s,433,420frames,866,884B; SHA `22fdd462f7287116f5a73c9f4ab6f757e5d6bdf1518babc5ae3f5d0c7e2d1942`.
- [Chapter2](episode/chapters/chapter-001.wav):10.5390476190s,464,772frames,929,588B; SHA `03cf36fbc73fe439e058c9d3c235e9cb374473e19176823b5a2ec4f6beff3dba`.

All are44.1kHz monoPCM16. The master PCM is exactly chapter1 +30,870 zero frames (**700ms**) +chapter2. Timeline SHA `fa7cce7b60d42f61fc1595bcd9979927e27b8d4b1e70f0e4ca86276024060891` matches frame offsets. ORT/QNN profiles remain unavailable by design; no per-graph counters or broad hardware/fidelity claim. Only Moritz can accept listening quality. Kate received stable original files immediately; no audible autoplay.

## Player and remaining export failure

Actual silent app-volume0 playback, next-chapter boundary10,528ms, speed1.25, chapter2 transcript, Activity recreation/disposal persistence and a fresh Library/ViewModel/Player reopening passed. New Player identities were checked; no system-volume or TalkBack change.

The final SAF helper failed in the open DocumentsUI roots drawer: it looked for the Downloads row's immediate clickable parent, while the real action lies higher in that row hierarchy. The default filename was still visible; filename replacement/Save were not reached, and there is no export-before-write/callback receipt. This is **export-incomplete**, not audio/Player failure. Private drawer screenshots contain unrelated provider/account information and remain private. A new export-only scope must reuse these exact Ready/WAV artifacts with0model calls, never rerender them.

## Preservation and installed identity

Other existing user rows remain unchanged; the owned episode intentionally transitions through lock/audio/progress and receives its new audio/playback rows. All eight prior episode files are byte-identical; four new audio/timeline files belong to this episode. Only the exercised Supertonic catalog row may be added. The original per-table episodes.existingUnchanged count includes the owned exception; use `otherExistingRowsUnchanged` and `ownedEpisodeOnlyAllowedTransitions`, **not** a claim that this episode row stayed identical.

Cleanup errors[]/settingsErrors[], all actual app/generation/test PIDs absent, control absent, lock released, no scratch. Installed frozen pair `.local/short-product-ready/continuation-01/{app,test}.apk`: app95103b2c…fe969/test35faf3a6…a3625, full hashes in `device/identity.json`; candidatebb8c169…4e622b.

Manifest binds364 public original/derived files7,662,515B;23 private originals9,557,023B stay local/hash-bound. Original failures and raw records are immutable. This establishes a short multi-stage product path through AUDIO/Player, not completed export,1–2minute/full-long readiness, numerical fidelity or listening acceptance. No push.
