# Authorized app closure, then terminal-history eligibility stop

Moritz/Pi authorized ordinary closure of the exact podcast app/test packages for this test setup, without data clear or further routine-close confirmation. Under the canonical lock, Janek verified the exact S23 identity, MAIN PID4813/name/UID10755 and installed test-package UID10756. Generation/test processes were absent. Only the main package needed `am force-stop`; the following actual-name check proved all three processes absent. The unchanged separate receipt is in `authorized-closure-20260910t201545z/`.

The exact approved candidate/controller was then invoked once with fresh run ID **`tts-long-20260910t201548z`**. Its first `before-app-install` checkpoint stopped on the conservative no-generation-history eligibility rule:

- One `generation_jobs` row in terminal `FAILED` state.
- **Zero QUEUED/RUNNING jobs**; not pending or reconcilable generation.
- No rows in script revisions, chapters, agent messages, chapter audio or playback state.
- Two episodes. No episode/source content, IDs or timestamps are published.

Schema/integrity/FK and two identical bounded snapshot checks passed before the explicit no-history rejection. This does **not** prove that all other episode-state conditions would pass: the guard stopped before them. The failure means this guard cannot establish its conservative eligibility, not that the database is corrupt or TTS failed.

**No installs, new-pack staging, constructors, Runs or WAV occurred.** No data, jobs or model packs were cleared, removed or repaired. Cleanup reports no errors/settings errors, no scratch creation, retained packages and all three actual PIDs absent; settings readback matched, old pack manifest identity was preserved and the lock released. No retry or rebuild was performed. Any subsequent eligibility correction/continuation is separate work, never deletion to pass.

`tts-long-20260910t201548z/retained-manifest.json` binds157 public original files/25,578 bytes, plus five local-only private bindings/818,528 bytes: two original DB archives, two original full condition outputs and a labelled derived local read-only database materialization. The aggregate counts are explicitly derived, not raw DB evidence. Neither original DB/condition contents nor the materialized database are copied here. Global logcat was never started because execution stopped before installation.

The separate setup receipt binds62 originals/3,900 bytes. Exact candidate/source/pack approval remains valid. Failures belong in one status-board line; **no no-audio listening page**. Only a real hash-bound WAV will receive a listening handoff. No pushes/external publication.
