# Short real workflow: three Gemma returns, wrong chapter scope rejected

Run `short-product-20260910t222714z` consumed candidate9c54…23b9. Installed app4e438b62…af8c8/test56be356f…f8739 are bound in `device/identity.json`; frozen files remain `.local/short-product-ready/attempt-03/{app,test}.apk`.

The real named Library action worked. Main UI created owned episode `e4279db8-d281-4657-867e-545491f6afc5`, persisted its fixed source and review-ON instructions, and queued the normal production SCRIPT job `934e0e22-d792-4bce-ae51-0ff0f9d538db`. Generation PID20433 survived the recorded Home/reopen without force-stop or redispatch. Its three normal synchronous Gemma returns were source_notes, outline and the first requested chapter; service finally was reached after25,429ms. This is logical request timing/count evidence, not token throughput or a warm benchmark.

## Exact rejected return

The outline contains chapter-1/chapter-2 correctly. Request3 selects **chapter-1 / Checking Before Borrowing**. The model instead returned:

- id `short plumbing e4279db8` and the episode title;
- one text field containing **both** Chapter1 and Chapter2 mini narrations and headings.

The JSON parser accepted its syntax/fence handling, but the unchanged coordinator correctly rejected `generated.id != planned.id`. No second chapter request, draft commit, edit, lock, TTS, master, playback, export or WAV followed. **This is a single-chapter task-scope/schema-adherence failure, not a harmless ID typo or TTS failure.** Do not relabel the ID, split/extract narration or silently drop content to fake success.

Exact files are under `device/jobs/934e0e22-d792-4bce-ae51-0ff0f9d538db/`: request3 SHA `d14bb902a981d5c246ce3f54683170497380f7e4fa5c5c16862057a948d46791`, system `4435baaf939e0fd243cb4e4e075707eadd38b3021a37871d48e0e7457a8404c5`, raw return **`4491ff363c66fed4765e060654112ccbfe9a33f7ebf4cbc957062dda0a3b7206`**. These remain unchanged. The focused source remedy is a concrete single-chapter instruction/escaped ID+title schema while preserving all context, model settings, parser and strict ID gate. Its effect on future model adherence remains unproven until separately tested.

## Preserved state and cleanup

The two pre-existing episodes, source, FAILED job and existing episode file remain unchanged. The new owned failed episode/source/job and source file remain intact. There is no data deletion, repair, model retry or automatic replay.

Cleanup errors[]/settingsErrors[], actual app/generation/test PIDs absent, control disarmed/absent, no scratch, model packs/packages retained and lock released. The run authorizes no further phone work. No listening page because no WAV exists.

`retained-manifest.json` binds372 public original/labelled files341,741B and21 private originals7,217,941B. Full DB/WAL, inventories, conditions, global logcat, mixed private archive and UI stay local/hash-bound. Only the newly owned episode-artifact archive is retained publicly here. No push or long-chapter readiness claim.
