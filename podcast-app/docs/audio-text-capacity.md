# Early audio input-capacity handling

## Concrete mismatch

The two real-input SCRIPT reproductions completed, but neither reproduced the historical failure. Their full narration is far beyond the installed voice's text input capacity. This is a separate, confirmed product mismatch—not evidence that TTS caused either earlier SCRIPT error.

The exact app-pinned short manifest `dc4ac737…5952d` declares **T239**. Native `PrepareText` counts `<en>` + normalized text + `</en>`: **nine additional codepoints**, so the pre-tag normalized limit is **230**. The experimental long manifest `116fda95…84066` declares T2048, giving2039 normalized codepoints. These bindings are tested against byte-exact copies of the previously verified manifests; unrecognized pins do not imply unlimited capacity. Full pack-file/runtime verification still runs at normal audio startup.

Shared Kotlin frontend measurements on the actual private drafts:

| Draft | Normalized codepoints per chapter | Short limit |
|---|---|---|
| Five-chapter real-input case |2199 /2786 /3070 /2902 /3158|230|
| Four-chapter real-input case |3409 /2567 /2961 /2343|230|

Add9 to each count for native input occupancy. All nine chapters also exceed the experimental T2048 text limit. Counts include the existing frontend replacements, Unicode whitespace handling, punctuation insertion, per-codepoint NFKD and native trailing-whitespace behavior. They are not raw characters, words, bytes or duration estimates. User text remains private and unchanged.

## What changes

- Manual lock rechecks **the current active revision's complete text inside the same transaction**, before setting any lock fields or adding an AUDIO job. A cached UI result cannot authorize a changed revision.
- Review-OFF generation still commits the full script and marks SCRIPT complete. If the configured voice cannot accept it, the episode remains an editable SCRIPT_DRAFT, with no lock/AUDIO enqueue. It does not delete successful model work or force a shorter output.
- Review shows the limit and per-chapter counts, disables audio locking, and keeps agent editing available as a deliberate user choice. Async capacity state resets with changed chapters. Instructions expose the supported bound without modifying the user's instructions or chapter/episode scope.
- A text-fit result is **not** proof of latent/waveform capacity, duration, runtime success, pronunciation mapping, quality or long-speech coverage. The227word/29.8s long-duration issue remains unresolved.

The physical negative check reuses the genuine five-chapter draft (`7dbc3e96…`, revision `8e303378…`, content `e7d9d969…972db`). A repository call is wrapped in an **unconditionally rolled-back outer transaction**: even if the guard regressed, no AUDIO row could commit/be dispatched. UI proof requires the actionable warning, disabled lock and available agent editor. The slot requests zero models/jobs/edits/playback/export; every existing row/catalog/episode file must remain unchanged.

## Source-notes contract alignment

The existing source-notes validator remains nonempty and at most2000 decoded UTF-16 code units, with the normal1200-token output ceiling unchanged. The production prompt now states that requirement and asks for at most1600 characters as margin, with no minimum/padding.1601–2000 remain valid. No output is truncated, repaired, retried or silently shortened into compliance, and final chapter/episode instructions are unchanged.

This is contract hardening, not recovery/proof of either historical cause. Both successful phone drafts used the earlier prompt; new guidance is covered by focused source/validator tests, not a claim of measured model adherence. The optional plaintext-v2 chapter proposal is parked locally and is **not** in this build; chapter JSON behavior remains unchanged.

## Validation boundaries

Focused tests cover exact manifest bindings, native tag overhead, inclusive230/231 boundaries, NFKD/punctuation/emoji behavior, empty normalization, manual transactional rejection, review-OFF full-draft preservation, changed-revision recheck, and allowed short locking. Exact real-draft counts come from the shared Kotlin normalizer without printing user text. Physical guard/UI results are retained separately when observed. Earlier raw failures and successful model outputs are immutable; all publication/history-rewrite holds remain.
