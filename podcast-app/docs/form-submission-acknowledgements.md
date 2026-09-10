# Preserve Agent and Paste input until submission is acknowledged

This is a separate input-preservation change after the frozen gallery/layout candidates. It adds no automatic retries, inference fallback, job recovery or direct transcript editing.

## Completion contract

- Paste awaits the VM's actual source-save completion before automatically closing. File work runs on IO; the captured episode ID is used throughout. The repository rechecks source-editable phase transactionally before inserting the row, so a write that finishes after generation is queued is rejected and its new file removed.
- Agent awaits queue acceptance, including insertion of its user message, before clearing the field. **This acknowledges queueing, not successful model editing.** Later model/job failure remains the existing distinct unchanged-draft/error state.
- Queue, validation and storage exceptions reach the originating form rather than being swallowed behind an obscured global snackbar. Entered text is retained and a local error is shown. A current-input rejection clears focus/hides the keyboard so the error is visible; a rejection for older input does not disturb newer typing.
- Each form has a lifetime ID, monotonically increasing submission sequence and input revision. Duplicate pending submissions are suppressed. Editing while a submission is pending creates a newer draft: an older success cannot clear/dismiss it and explicitly reports that the newer text was not sent. An old failure is labelled as a previous submission failure.
- Closing/replacing a form invalidates its outstanding acknowledgement before a new form can be affected. Cancellation is not misreported as rejection. A VM-owned operation already submitted may finish for its original episode after the UI closes; closing is not a promise to undo a persisted write. The pending Paste close action is therefore labelled Close, not Cancel.
- Sources/Review composition lifetimes and callbacks are bound to the episode. Late callbacks do not read mutable current selection. Source/message/chapter/job rows are filtered to the displayed owner/revision, and selecting another episode resets open modal state.

An unchanged form closes/clears only after success. A newer form or newer input never does so because of an earlier response. Manual resubmission is a new explicit user action; no task is scheduled automatically after an error.

## Evidence and remaining gate

Host tests cover nine form-state cases (awaiting completion, duplicate suppression, rejection/no retry, newer edits including edit-undo, stale/out-of-order responses, replacement forms and cancellation) and five real repository/VM cases: queue rejection without user-message insertion, storage failure, source validation failure, delayed A callbacks after selecting B, and a source stream finishing after the queue freezes its inputs.

`FormSubmissionInteractionTest` adds seven Android UI methods with synthetic callbacks and production forms: Paste and Agent rejection retention/local errors, success-only Paste dismissal and Agent clearing, newer Paste/Agent input preservation, and a disposed form's late non-cancellable completion. These must be executed by Nik at the default and actual320dp/font2 settings before claiming UI success. Gallery/layout candidates remain separately frozen; their previous passing results do not validate these changed forms.

No model packs, native preparation, model inference or physical-device activity is needed or authorized for this work.
