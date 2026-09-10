# Focused host guard for the frozen duration-load diagnostic

**Host-only patch; physical execution remains paused until review and a fresh Pi slot.** No APK, service contract, model/context or runtime option is changed. The diagnostic remains frozen `3fd75c0` (candidate SHA `806c9b6db0766eb3a7455cc2bd23a68c61153d257f4b0f0b7bb98ced6972238d`). This revised host controller is **not** relabelled as the unchanged3fd75c0 controller.

## The readiness gap

The frozen `PodcastApplication.onCreate` starts the queued-command dispatcher and running-job watchdog in the main process. That happens during instrumentation startup, before the test body launches MainActivity and before the duration service's own idle check. Empty current PIDs alone do not establish that launching instrumentation cannot dispatch persisted work. We missed this boundary in the earlier host readiness.

Frozen startup inspection found QUEUED dispatch and RUNNING-job reconciliation, not an additional automatic episode-phase recovery callback. The fix is host preflight before both installs and `am instrument`, not a new recovery framework or APK change.

## Exact action order

1. CLI closes inherited descriptors above stdio; validates exact frozen candidate/APK/contract and separately approved **host-guard closure SHA**. Without `--execute`, it only prints the plan and closure identity—no ADB.
2. Create a fresh owner-only output directory. Acquire the **existing canonical phone.lock once**, mark its descriptor non-inheritable. Existing Device/logcat children use `close_fds=True`, including any ADB daemon they might start.
3. Verify serial/model/SoC/ABI/Android release/API/fingerprint against Pi's explicit S23 identity. Read current settings/conditions and the existing pack manifest only; no staging or SQLite command runs on the phone.
4. **Before app install, before test install and immediately before instrumentation:** recheck candidate/APK/host identities, exact phone identity and empty app/generation/test PIDs; pull two bounded read-only DB/WAL/SHM snapshots; require identical member bytes and no change since the first checkpoint; validate the logical database; check PID absence again. A mismatch stops downstream actions without retry.
5. Only then allow the unchanged one-constructor diagnostic. Existing45s load/close,120s service,135s driver,150s instrumentation,180s installs and120s evidence pull bounds remain. Zero Run/Gemma/other-context/TTS/capacity calls.
6. Preserve raw diagnostic outcome and cleanup failures. After a launched attempt, the existing controller stops its app/test, pulls evidence and proves PID absence. Read back settings without repairing unrelated changes, reap logcat, write cleanup **before the one lock release**. Failed pulls do not delete remote evidence. A prelaunch failure does not force-stop someone else's newly observed app process.

## Current startup eligibility — host-only correction,2026-09-10

The original blanket no-history policy was over-restrictive. It stopped long run `tts-long-20260910t201548z` before installation on one FAILED job despite zero QUEUED/RUNNING jobs. That stopped record remains unchanged in `evidence/tts-long-startup-stop/`.

The corrected guard retains the pinned schema/identity, integrity/FK, WAL, snapshot coherence, PID, lock and hash checks. **QUEUED/RUNNING still means pending/reconcilable work and always stops.** Other job statuses must be the known terminal values COMPLETE/FAILED; unknown statuses stop. Episodes must use one of the eight known phases; unknown phases stop.

Known terminal jobs, populated revisions/chapters/messages/audio/playback tables, and known episode phases/metadata do not independently dispatch work in the frozen source. `PodcastApplication` starts only the dispatcher/watchdog; DAO predicates select QUEUED/RUNNING respectively, repository methods forward those queries, and the ViewModel starts with no selected episode/Library. New work is queued only by explicit user actions. Consequently the no-history, nonnull-metadata and Instructions-source eligibility vetoes are removed. This is **no automatic startup work**, not a claim that arbitrary product content/state is correct. Nothing is deleted or repaired to pass.

The exact long candidate `b86008708cc459c855149eee49c58a7468e079d24c9de4842eab56a5bcef325d` remains frozen with its historical guard reference. `config/diagnostics/tts-long-terminal-history-override.json` explicitly replaces only that host guard reference, via the existing CLI flag:

- Old guard: `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`.
- New guard: `5ca6be91be151acd2937b5e65871a40361f9bae99ae444880eae0e29b6f2c425`.
- Override SHA: `60dd58885efdc8406049365d92c26838fdedf4db99f568638479a1f71e1b046d`.
- Unchanged long caller: `a87b3f358f9efff213beeed3261f651620e5763c0f3b022718190860740815a4`; unchanged privacy dependency `a62d204c380a5b2d0c8f7c5bd94729b6f823e18200feed2ebe24fa73962bec3c`.

The override binds the same APKs/contract/pack and seven exact frozen startup sources. No APK/controller/native/pack rebuild. The long staging/render bounds stay those of its existing contract, not the duration-only bounds described in the historical action sequence above. Routine exact app/test closure is authorized within the separately released test setup; no data clear/job deletion/model-pack removal. The override alone grants no phone access.

## Snapshot and privacy boundary

Only fixed database filenames are accepted; other members, links, duplicates, unknown schema/indices/triggers/views, Room/version mismatches, corruption and foreign-key inconsistencies fail closed. Two matching bounded copies and PID checks detect observable change, rather than treating an arbitrary base DB copy as current.

Nonempty WAL is not ignored: header/version/page size, every frame salt/checksum and a committed final frame are validated. Valid committed pages form a **local temporary inspection copy** opened with SQLite read-only/immutable/query-only settings; this avoids SQLite silently falling back to old base pages on a torn WAL. Uncommitted/truncated/checksum-invalid tails stop the gate instead of being recovered. SHM is copied/hash-compared but not needed to read the explicitly materialized committed WAL view. This does not modify/checkpoint any device file, private raw archive or application row.

Original and even failed/partial DB pulls are retained only in owner-only `.private-db/`, never published. Public evidence contains hashes, byte counts and minimal state summaries, not private rows. The temporary local inspection copy is deleted after validation.

## Residual race and review scope

The host lock excludes coordinated agents, **not Android/user activity**. These checks are not atomic with later process creation: Moritz or an uncoordinated/system actor could launch/write after the final check. The same-frozen-APK guard narrows and records this interval; it does not claim to eliminate it. No other phone interaction is permitted during the released slot. Eliminating that race in-process would require a separately reviewed APK change, which is outside this patch.

Focused tests: `tools/tests/test_duration_phone_guard.py`. They exercise real host SQLite WAL fixtures, corrupt/recovery/unknown states, accepted terminal history with mixed-active and unknown-status negatives, snapshot changes, private failed pulls, identity/PID failures, guarded action/cleanup order, one lock and real host-child FD non-inheritance. Controller tests mock all device calls and use temporary lock paths. Existing Python scope tests remain applicable; no JVM rebuild, UI matrix or physical probe is needed for this host review.

The required host closure digest is emitted by the plan-only command and binds the controller, guard, existing imported helpers and pinned schema. Pi must explicitly approve this digest as well as the unchanged candidate hash and release a new physical slot before execution.
