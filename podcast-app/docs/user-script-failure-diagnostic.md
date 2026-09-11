# Real-user script failure: diagnosis and bounded reproduction

## Observed, not inferred

The read-only phone diagnostic `readonly-20260911t095222z` took4.662s under the canonical phone lock. Installed app95103/test07a matched the final short build. Three DB/WAL/SHM snapshots were byte-identical, schema/integrity/FK checks passed, no job was active, and the existing main process was left running. No install, generation, force-stop or device-data write was requested.

The latest user job failed during **SCRIPT chapter5 of6**, after preparation/outline and four earlier chapter-call boundaries. The stored error is `Gemma LiteRT GPU chapter request failed`; no script revision or AUDIO job was produced. This is not the earlier tiny E2E fixture, an agent-edit failure, or a T239 audio failure. It does not prove that prompts, JSON, context size, or GPU execution caused the stop.

The installed code wraps conversation creation/send/close and JSON extraction/parsing with the same message, and the service stored only that message. Normal user requests retained neither the raw response nor underlying exception. Captured bounded app-UID logs contain later UI records, not the failing interval. **The historical deepest cause cannot be reconstructed from these records.** Full user data/logs remain private; the safe derived observation only binds them by hashes.

## Diagnostic change, not a claimed generation fix

- Exact phases for conversation creation, send, close, JSON-object extraction and parsing. Existing single-send/use/first-brace-to-last-brace parsing is unchanged: no repair, retries, truncation, output relabelling or prompt/sampler/token-limit change.
- Existing job/episode failure fields carry bounded content-free type/cause/suppressed graphs, with explicit cycle/truncation handling and allowlisted typed SDK status prefixes. Arbitrary exception messages, including direct schema errors and deep outer wrappers, do not enter broad UI/notifications.
- Debug-only optional receipts require an exact episode/input/model/APK binding and review-ON queued SCRIPT job. A new private directory atomically consumes one capture; no wildcard, existing-directory reuse, DB schema change or alternative model engine.
- Exact request/system UTF-8, config, verified model/runtime/APK bindings, raw response when the synchronous SDK actually returned it, and full underlying private exception details are retained. SDK-no-return and unavailable writes have explicit null/reasons. Raw output is saved before conversation close; observation failures cannot replace the original error. Job-level receipts also cover post-return schema/ID failures.
- Content lives only under app-internal `files/user-failure-diagnostics/`. No new raw logcat, shared export, public input fixture or UI dump. Limits:64 requests,1MiB per artifact,8MiB reserved total (including failed writes). Over-limit content is omitted with a reason, never silently truncated or substituted as model output. Release builds have no capture control/hook implementation.

## Normal-input reproduction

`UserScriptReproductionTest` opens the real Main UI, creates one separate owned episode, and copies the actual failed source bytes/title and instructions through normal Paste/Instructions controls. Hash/length equality is checked. It clicks Create once with review ON and uses the normal dispatcher/service/coordinator. It stops at the SCRIPT terminal state: zero edits, lock, TTS, playback or export. Original failed episode/job/sources and all other existing rows/files are retained; only the fresh owned script artifacts and exact verified Gemma catalog upsert may be added.

The480s SCRIPT wait is a **polling bound**, not native termination. The540s test timer kills only its main process. The600s host instrumentation deadline is followed by independently attempted bounded ownership checks/closure even when log/archive/preservation observations fail. Closure rejects foreign/unknown active jobs; an unreadable safety state is a genuine blocker, never permission to kill. An owned orphan RUNNING row can be failed by the existing normal watchdog after generation has stopped; a QUEUED restart is refused. Minimal ownership is authenticated independently of whole-tar extraction and cannot designate a pre-existing episode. All phone operations remain under `artifacts/locks/phone.lock`.

Capture observations are additive; after-file inventory precedes independent DB validation. Driver exceptions are preserved privately, then replaced with a content-free runner failure without the original cause chain. Cleanup errors are private and cannot expose the original UI tree.

This reproduction is diagnostic until an observed cause is fixed and tested. Moritz's standing assignment permits reasoned bounded repair iterations without phase-by-phase approval waits. Nik reviews Janek's concrete source/candidate/results. No blind full-flow reruns, hidden speech workaround, new agents or push/history rewrite. The separate long-duration/coverage limitation remains unresolved.
