# Newest chat-edit failure: diagnosis and bounded follow-up

## Saved user failure

The read-only capture `readonly-20260911t131338z` took5.06s under full phone.lock. Installed app50a367…/test8ed6c5… matched before and after. All three DB/WAL/SHM snapshots were byte-identical, no job was active, and main PID27814 remained unchanged. No install, stop, retry, input, model call or device-data write occurred. The app was not the foreground window, so no screenshot was captured.

The newest episode `7467f7ff-681d-4650-ab37-a9b5271232ef` has failed AGENT_EDIT job `45a7d4d0-29ea-40cf-bc3f-88693f7d7b2c`, terminal11:54:10Z. The recorded safe failure is **Gemma edit / JSON_PARSE / JSONException**. It reached a returned SDK response and failed parsing the existing first-`{`…last-`}` slice. It did not fail the20,000-character request gate or enter TTS. There is no recorded GPU/HTP OOM/runtime exception in this failure chain; that is not a blanket exclusion of backend or concurrent-work effects.

The requested base is still the active revision `b6fb54b5-9137-4bb3-8d4d-f8bfc9a056da`, content hash `0878f4af0160cfa8499edb89e16ad86f00c9ee88ac36d4cee6aefbd80d1d87c9`. All five original chapters remain saved (333/196/307/414/290 whitespace-counted words). The27-unit instruction and full text remain private. A Python reconstruction is approximately10,477 UTF-16 units; it is not a captured original request nor a token measurement.

The raw failing reply was not retained in normal mode. The surviving app-only log tail no longer includes that interval. **Truncation, quotation escaping, commentary/extraction issues and runtime interference are not distinguished by the old record.** No further log-hunting slot or generic prompt guess is justified.

## Confirmed independent state bug

`failJob` moved a running AGENT_EDIT's entire episode to FAILED even though a valid unlocked draft remained intact. Navigation then hid the draft behind the failure page. Queued edit failures already preserved SCRIPT_DRAFT.

The source correction makes running edit failures retain SCRIPT_DRAFT too, with the failed job, request and error intact. Stale or locked ownership cannot downgrade/reopen another revision. For already affected episodes, **Return to saved draft** is an explicit normal UI action, not a SQL patch or startup migration. Its transaction verifies exact current episode/job/revision/message ownership, no active work, no lock/final-audio metadata or chapter-audio rows, and the saved artifact hash. It changes only phase/timestamp, preserves failure history/content, and does not retry generation. No original user episode is automatically recovered by installation.

## Baseline one-response diagnostic (4a8722a6, completed)

Before changing response formatting, reconstruct the existing v1 EDIT request using the same shared builder and original saved revision/message/chapter rows. No clone IDs, new source preparation or regeneration is used. This is deterministic reconstruction, not proof of original captured request bytes: the old raw request was not captured.

An explicitly opted-in instrumentation probe creates a private, bounded observer and calls the production Gemma edit engine **once**. Model pack, LiteRT0.16.1 GPU,8,192 context,4,096 output ceiling, greedy sampler, thinking off, system instruction, full-revision JSON protocol and one fresh Conversation stay unchanged. No constrained decoding, repair, parser relaxation, truncation, repeated inference or CPU fallback is introduced. Optional SDK KV/decode counters are attempted **after raw output capture**, and absence never discards the run or becomes a fake stop reason.

The observer is null in normal production construction. Raw request/system/returned reply/underlying parse exception remain in immutable app-private receipts (existing64-request/1MiB-file/8MiB-total bounds). Private failures must not be rethrown into instrumentation/logcat. The host bounds instrumentation to300s and uses independent fresh-state cleanup; there is no unsafe unconditional in-app process killer.

The probe is **not a normal chat E2E success claim**: it does not queue jobs, apply the response, create revisions, alter originals or evaluate humor automatically. It additionally checks the real existing episode's recovery transition under an **unconditionally rolled-back outer transaction**, then checks the actual recovery button without clicking it. All rows/catalog/episode files must remain unchanged. If UI checking fails after a model response, retain that response and do not repeat the model merely to repair UI evidence.

## Actual captured baseline and targeted format change

`edit-probe-20260911t140437z` installed app677be111…/teste3e752… and reproduced JSON_PARSE in exactly one reconstructed EDIT request. Request SHA `0d165d3d4a2472670f2e81e65a8ad6d73b37a339178fecdc28d293693f70c4aa`; returned raw6,959B SHA `dc6d04767024a2382d0a2c6779ca7fbea831ddcd90fa8c551936d574bb183786`. The Android parser and independent strict parse both locate an unexpected extra object-closing token between chapter entries at character2550. The reply has its final document-closing brace and Markdown fence, while the required summary is absent. This is an observed malformed interior structure, not a measured output-ceiling stop. SDK KV count was3848; optional decode counters and stop reason were unavailable.

The real recovery transaction and UI check passed. The transaction was rolled back and the button was not clicked. Every row/catalog and all19episode files across9episodes remained unchanged; no jobs/revisions/TTS/Play/export were added. Cleanup was clean, exact app/test/generation PIDs and controls absent, lock released. Nik was disconnected: this is source/host/physical self-validation, not an independent review verdict.

The next candidate changes **only EDIT response generation** to the SDK's existing JSON-schema constraint (`ConversationConfig.enableResponseFormat` plus `ResponseFormat.json`). It requires the existing complete revision object, all chapter fields and summary. Source-notes/outline/chapter modes retain their prior behavior. The actual0.16.1 AAR exposes the API, and its existing JNI contains the LLGuidance implementation; no extra native library or model change is introduced. Runtime support and the actual changed response remain to be observed.

The input/system instruction, sampling scalars,8,192 context and4,096 output ceiling are unchanged; the **decoder constraint is explicitly changed**, not labelled identical neural settings. Debug/release send paths forward it, and private receipts bind exact schema bytes/hash. The strict parser and semantic script validation remain authoritative and are shared with the diagnostic; no malformed output is repaired or accepted. Grammar does not establish factual correctness, humor or general reliability, and it cannot promise completion if a real token limit is reached.

The changed run must match the prior actual request hash before any inference. It again requests one response without committing it. In addition to syntactic JSON, it checks the normal strict response parser and complete-script validator, reports retained chapter IDs/changed texts, and preserves all originals. No model rerun is allowed solely to repair later UI evidence.

## Evidence and next boundary

The original read-only evidence and hash-bound private files are retained in `evidence/user-edit-diagnostic/readonly-20260911t131338z/`. Source/build and one-response results are separate; a source correction or successful build is not a demonstrated model-formatting fix. Full TTS remains a separate unresolved route, now being compared by other owners. This task does not change that reference or those models. Push/history-rewrite holds remain.
