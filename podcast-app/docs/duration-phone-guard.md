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

## Deliberately narrow eligibility

Actual QUEUED/RUNNING rows are reported as **pending/reconcilable work found**. For this diagnostic, the fast guard additionally supports only:

- no database directory, or the pinned known Room v1 schema/identity;
- no generation-job/revision/chapter/agent-message/audio/playback history;
- only SOURCES/INSTRUCTIONS episodes with no active/locked/output/failure metadata; Instructions must have a source.

Completed/failed history is **not automatically pending work**. It causes the distinct result **“guard cannot establish safe state: conservative no-generation-history eligibility rule.”** Draft/frozen/failed or otherwise unsupported episode states are also ineligible, not proof that startup would retry them. Any real-device limitation is reported for Pi's decision; nothing is cleared, reset or changed to satisfy the guard.

## Snapshot and privacy boundary

Only fixed database filenames are accepted; other members, links, duplicates, unknown schema/indices/triggers/views, Room/version mismatches, corruption and foreign-key inconsistencies fail closed. Two matching bounded copies and PID checks detect observable change, rather than treating an arbitrary base DB copy as current.

Nonempty WAL is not ignored: header/version/page size, every frame salt/checksum and a committed final frame are validated. Valid committed pages form a **local temporary inspection copy** opened with SQLite read-only/immutable/query-only settings; this avoids SQLite silently falling back to old base pages on a torn WAL. Uncommitted/truncated/checksum-invalid tails stop the gate instead of being recovered. SHM is copied/hash-compared but not needed to read the explicitly materialized committed WAL view. This does not modify/checkpoint any device file, private raw archive or application row.

Original and even failed/partial DB pulls are retained only in owner-only `.private-db/`, never published. Public evidence contains hashes, byte counts and minimal state summaries, not private rows. The temporary local inspection copy is deleted after validation.

## Residual race and review scope

The host lock excludes coordinated agents, **not Android/user activity**. These checks are not atomic with later process creation: Moritz or an uncoordinated/system actor could launch/write after the final check. The same-frozen-APK guard narrows and records this interval; it does not claim to eliminate it. No other phone interaction is permitted during the released slot. Eliminating that race in-process would require a separately reviewed APK change, which is outside this patch.

Focused tests: `tools/tests/test_duration_phone_guard.py`. They exercise real host SQLite WAL fixtures, corrupt/recovery/unknown states, conservative terminal-history classification, snapshot changes, private failed pulls, identity/PID failures, guarded action/cleanup order, one lock and real host-child FD non-inheritance. Controller tests mock all device calls and use temporary lock paths. Existing Python scope tests remain applicable; no JVM rebuild, UI matrix or physical probe is needed for this host review.

The required host closure digest is emitted by the plan-only command and binds the controller, guard, existing imported helpers and pinned schema. Pi must explicitly approve this digest as well as the unchanged candidate hash and release a new physical slot before execution.
